from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user


def _fake_db_user(user_id: UUID | None = None):
    now = datetime.now(timezone.utc)
    user_id = user_id or uuid4()
    school = SimpleNamespace(
        id=uuid4(),
        full_name="School 12",
        short_name="S12",
        city_id=uuid4(),
    )
    role = SimpleNamespace(name="admin")
    return SimpleNamespace(
        id=user_id,
        email="user@example.com",
        is_active=True,
        role=role,
        created_at=now,
        updated_at=None,
        nickname="nick",
        full_name="Test User",
        age=17,
        phone_number="+79990000000",
        school=school,
    )


def _make_user(user_id: UUID, *, permissions: list[str] | None = None, role: str = "student") -> UserFull:
    now = datetime.now(timezone.utc)
    return UserFull(
        id=user_id,
        nickname="tester",
        email="tester@example.com",
        is_active=True,
        role=role,
        created_at=now,
        created_at_unix=int(now.timestamp()),
        updated_at=None,
        updated_at_unix=None,
        full_name="Test User",
        age=None,
        phone=None,
        school=None,
        permissions=permissions or [],
    )


@pytest.fixture()
def app():
    app = FastAPI()
    from app.services.auth.routers.auth import router as auth_router
    app.include_router(auth_router, prefix="/v1/auth")
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


@pytest.fixture()
def override_user(app: FastAPI):
    user_id = uuid4()

    async def _override():
        return _make_user(user_id)

    app.dependency_overrides[get_current_user] = _override
    return user_id


@pytest.fixture()
def override_admin(app: FastAPI):
    """An authenticated user with full user-management permissions — needed for
    the admin-only /users* endpoints (GET /users is admin/admissions_committee
    only; PATCH/DELETE are admin only, per Permissions.Users)."""
    user_id = uuid4()

    async def _override():
        return _make_user(
            user_id,
            role="admin",
            permissions=["read_users", "edit_users", "delete_users", "create_users"],
        )

    app.dependency_overrides[get_current_user] = _override
    return user_id


@pytest.fixture()
def patch_userdao(monkeypatch):
    from app.repositories.dao.userdao import UserDAO

    state = {}

    async def fake_list_users(self):
        return state.get("list_users", [])

    async def fake_get_user_by_id(self, user_id: UUID | str):
        return state.get("get_user_by_id")

    async def fake_update_user_by_id(self, user_id: UUID | str, user_data):
        state["update_user_by_id_payload"] = user_data
        return state.get("update_user_by_id")

    async def fake_delete_user_by_id(self, user_id: UUID | str):
        state["delete_user_by_id_called"] = True
        return True

    monkeypatch.setattr(UserDAO, "list_users", fake_list_users, raising=False)
    monkeypatch.setattr(UserDAO, "get_user_by_id", fake_get_user_by_id, raising=False)
    monkeypatch.setattr(UserDAO, "update_user_by_id", fake_update_user_by_id, raising=False)
    monkeypatch.setattr(UserDAO, "delete_user_by_id", fake_delete_user_by_id, raising=False)

    return state


def test_list_users_returns_data(client: TestClient, patch_userdao, override_admin):
    patch_userdao["list_users"] = [_fake_db_user(), _fake_db_user()]

    res = client.get("/v1/auth/users")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert body[0]["email"] == "user@example.com"
    assert body[0]["role"] == "admin"


def test_list_users_forbidden_for_non_admin(client: TestClient, patch_userdao, override_user):
    res = client.get("/v1/auth/users")

    assert res.status_code == 403


def test_get_user_not_found(client: TestClient, patch_userdao, override_admin):
    patch_userdao["get_user_by_id"] = None

    res = client.get(f"/v1/auth/users/{uuid4()}")

    assert res.status_code == 404
    assert res.json()["detail"] == "User not found"


def test_get_user_success(client: TestClient, patch_userdao, override_admin):
    user_id = uuid4()
    patch_userdao["get_user_by_id"] = _fake_db_user(user_id)

    res = client.get(f"/v1/auth/users/{user_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(user_id)
    assert body["nickname"] == "nick"


def test_update_user_normalizes_payload(client: TestClient, patch_userdao, override_admin):
    user_id = uuid4()
    patch_userdao["update_user_by_id"] = _fake_db_user(user_id)

    res = client.patch(
        f"/v1/auth/users/{user_id}",
        json={"first_name": "Ivan", "last_name": "Petrov", "phone": "+7111"},
    )

    assert res.status_code == 200
    payload = patch_userdao["update_user_by_id_payload"]
    assert payload["full_name"] == "Ivan Petrov"
    assert payload["phone_number"] == "+7111"


def test_update_user_rejects_empty_payload(client: TestClient, override_admin):
    res = client.patch(f"/v1/auth/users/{uuid4()}", json={})

    assert res.status_code == 400
    assert res.json()["detail"] == "No updatable fields provided"


def test_update_me_success(client: TestClient, patch_userdao, override_user):
    patch_userdao["update_user_by_id"] = _fake_db_user(override_user)

    res = client.patch(
        "/v1/auth/users/me",
        json={"first_name": "Anna", "last_name": "Smirnova"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(override_user)


def test_delete_user_success(client: TestClient, patch_userdao, override_admin):
    user_id = uuid4()
    patch_userdao["get_user_by_id"] = _fake_db_user(user_id)

    res = client.delete(f"/v1/auth/users/{user_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(user_id)
    assert body["username"] == "user@example.com"
    assert patch_userdao["delete_user_by_id_called"] is True
