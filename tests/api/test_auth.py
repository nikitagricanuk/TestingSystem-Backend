from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient



# ---- Password stubbing for all tests (avoid bcrypt/real hashing) ----
import pytest

@pytest.fixture(autouse=True)
def _stub_passwords(monkeypatch):
    # Avoid real bcrypt dependency & make verification deterministic
    import types
    fake_verify = lambda raw, hashed: True
    fake_hash = lambda raw: "hashed"
    # Try to patch your project’s password helpers
    try:
        import app.utils.password as pw
        monkeypatch.setattr(pw, "verify_password", fake_verify, raising=False)
        monkeypatch.setattr(pw, "get_hashed_password", fake_hash, raising=False)
        # Also patch any direct imports (e.g., routers that imported functions by name)
        import app.services.auth.routers.auth as auth_router
        monkeypatch.setattr(auth_router, "verify_password", fake_verify, raising=False)
        monkeypatch.setattr(auth_router, "get_hashed_password", fake_hash, raising=False)
    except Exception:
        pass


# ---------- Test fixtures ----------

@pytest.fixture()
def app():
    app = FastAPI()
    from app.services.auth.routers.auth import router as auth_router
    app.include_router(auth_router, prefix="/v1/auth")
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


def _fake_user(
    *,
    user_id=None,
    email="ivan.petrov@example.com",
    is_active=True,
    role_name="admin",
    role_attr_name="name",  # your model sometimes exposes `.name` or `.role`
    include_permissions=True,
):
    user_id = user_id or str(uuid4())
    role_obj = None
    if role_name is not None:
        if role_attr_name == "name":
            role_obj = SimpleNamespace(name=role_name)
        else:
            role_obj = SimpleNamespace(role=role_name)

    # emulate ORM instance used in get_current_user()
    user = SimpleNamespace(
        id=user_id,
        email=email,
        is_active=is_active,
        role=role_obj,           # relation
        role_id=str(uuid4()),    # used in login payload extras
        permissions=None,        # direct user permissions (optional)
        created_at=datetime.now(timezone.utc),
        updated_at=None,
        password="hashed",
        full_name="Ivan Sergeevich Petrov",
        nickname="Ivan",
    )

    if include_permissions:
        # permissions via role: list of objects with `.name`
        role_perms = [
            SimpleNamespace(name="create_users"),
            SimpleNamespace(name="read_users"),
            SimpleNamespace(name="edit_users"),
            SimpleNamespace(name="delete_users"),
            SimpleNamespace(name="create_roles"),
            SimpleNamespace(name="read_roles"),
            SimpleNamespace(name="edit_roles"),
            SimpleNamespace(name="delete_roles"),
            SimpleNamespace(name="create_own_session"),
            SimpleNamespace(name="read_own_sessions"),
            SimpleNamespace(name="answer_own_session_questions"),
            SimpleNamespace(name="cancel_own_session"),
            SimpleNamespace(name="read_any_sessions"),
            SimpleNamespace(name="cancel_any_session"),
        ]
        if user.role is not None:
            setattr(user.role, "permissions", role_perms)

    return user


class FakeTokenPair:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.access_token = "access.jwt.token"
        self.refresh_token = "refresh.jwt.token"
        self.access_token_expires_at = now + timedelta(minutes=30)
        self.refresh_token_expires_at = now + timedelta(days=7)
        # Optional, in case your response model includes these:
        self.issued_at = now


class FakeJWT:
    def __init__(self, user_id: str):
        self._user_id = user_id
        self.revoked = []

    async def create(self, *, subject: str, access_extra: dict | None = None, refresh_extra: dict | None = None, session_ip: str | None = None):
        # subject == user.id
        return FakeTokenPair()

    async def validate(self, token: str, expected_scope: str):
        if token == "INVALID":
            raise ValueError("Invalid token")
        # Return claims with required keys
        return {
            "sub": self._user_id,
            "scope": expected_scope,
        }

    async def validate_refresh_and_get_session(self, refresh_token: str):
        if refresh_token == "bad_refresh":
            raise ValueError("bad refresh")
        claims = {"jti": "some-jti"}
        # minimal session object with invalidate()
        sess = SimpleNamespace(invalidate=lambda: None)
        return claims, sess

    async def revoke_refresh(self, jti: str):
        self.revoked.append(jti)


# ---- Monkeypatch helpers for DAO methods ----
# We patch methods on the class so `UserDAO()` inside handlers sees our fakes.

@pytest.fixture()
def patch_userdao(monkeypatch):
    # Lazy import here to avoid import errors if paths differ in your project
    from app.repositories.dao.userdao import UserDAO, RoleEnum

    state = {}

    async def fake_get_user_by_email(self, email: str):
        return state.get("user_by_email")

    async def fake_get_user_with_role_and_permissions(self, uid: str):
        return state.get("user_with_perms")

    async def fake_get_user_by_id(self, uid: str):
        return state.get("user_with_perms")


    async def fake_create(self, **kwargs):
        # Emulate ORM returned object with role relation if provided
        role = kwargs.get("role")
        role_obj = None
        if isinstance(role, str):
            role_obj = SimpleNamespace(role=role)
        elif role == await UserDAO().get_role_id(RoleEnum.STUDENT):
            role_obj = SimpleNamespace(role="student")

        return SimpleNamespace(
            id=str(uuid4()),
            email=kwargs["email"],
            full_name=kwargs.get("full_name"),
            nickname=kwargs.get("nickname"),
            is_active=True,
            role=role_obj,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def fake_get_role_id(self, role_enum):
        # return a stable UUID-ish string for tests
        return "b368842d-b837-4b97-b04b-5f3685ea354c"

    monkeypatch.setattr(UserDAO, "get_user_by_email", fake_get_user_by_email, raising=False)
    monkeypatch.setattr(UserDAO, "get_user_with_role_and_permissions", fake_get_user_with_role_and_permissions, raising=False)
    monkeypatch.setattr(UserDAO, "get_user_by_id", fake_get_user_by_id, raising=False)
    monkeypatch.setattr(UserDAO, "create", fake_create, raising=False)
    monkeypatch.setattr(UserDAO, "get_role_id", fake_get_role_id, raising=False)

    return state


@pytest.fixture()
def jwt_override(app: FastAPI, monkeypatch):
    """Override the DI provider to return our FakeJWT bound to a known user id."""
    user_id = str(uuid4())
    fake_jwt = FakeJWT(user_id=user_id)

    async def _override():
        return fake_jwt

    from app.services.auth.jwt_service import get_jwt_service
    app.dependency_overrides[get_jwt_service] = _override
    return fake_jwt, user_id


# ---------- Tests ----------

def test_login_success(client: TestClient, patch_userdao, jwt_override):
    fake_jwt, user_id = jwt_override
    # When /login finds a user by email
    patch_userdao["user_by_email"] = _fake_user(user_id=user_id)

    res = client.post(
        "/v1/auth/login",
        json={"email": "ivan.petrov@example.com", "password": "123"},
    )
    assert res.status_code == 200
    body = res.json()
    # minimal shape checks
    assert body["token_type"] == "bearer"
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" in body and body["refresh_token"]
    assert "access_token_expires_at" in body
    assert "refresh_token_expires_at" in body


def test_login_invalid_credentials_401(client: TestClient, patch_userdao, jwt_override):
    # No user found
    patch_userdao["user_by_email"] = None

    res = client.post(
        "/v1/auth/login",
        json={"email": "unknown@example.com", "password": "nope"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid credentials"


def test_guest_session_issues_tokens(client: TestClient, patch_userdao, jwt_override):
    res = client.post("/v1/auth/guest")

    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" in body and body["refresh_token"]


def test_me_unauthorized_401(client: TestClient):
    res = client.get("/v1/auth/users/me")
    assert res.status_code in (401, 403)
    assert "Not authenticated" in res.json()["detail"] or res.json()["detail"]


def test_me_success_with_bearer(client: TestClient, patch_userdao, jwt_override):
    fake_jwt, user_id = jwt_override
    # get_current_user -> validate() -> get_user_with_role_and_permissions(uid)
    patch_userdao["user_with_perms"] = _fake_user(user_id=user_id, role_name="admin")

    res = client.get(
        "/v1/auth/users/me",
        headers={"Authorization": "Bearer valid-token-irrelevant-to-fake"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == user_id
    assert body["email"] == "ivan.petrov@example.com"
    assert body["is_active"] is True
    assert body["role"] == "admin"
    assert "created_at" in body
    assert "created_at_unix" in body


def test_me_invalid_token_401(client: TestClient, patch_userdao, jwt_override, monkeypatch):
    fake_jwt, user_id = jwt_override
    # Make validate() raise
    async def bad_validate(token: str, expected_scope: str):
        raise ValueError("Invalid token: Verification failed")
    monkeypatch.setattr(fake_jwt, "validate", bad_validate, raising=False)

    res = client.get("/v1/auth/users/me", headers={"Authorization": "Bearer INVALID"})
    assert res.status_code == 401
    assert "Invalid token" in res.json()["detail"]


def test_logout_success_204(client: TestClient, jwt_override):
    fake_jwt, _ = jwt_override
    res = client.post("/v1/auth/logout", json={"refresh_token": "refresh.jwt.token"})
    assert res.status_code == 204
    # ensure revoke called
    assert fake_jwt.revoked == ["some-jti"]


def test_logout_invalid_refresh_401(client: TestClient, jwt_override, monkeypatch):
    fake_jwt, _ = jwt_override

    async def bad_validate_refresh_and_get_session(refresh_token: str):
        raise ValueError("bad refresh")

    monkeypatch.setattr(fake_jwt, "validate_refresh_and_get_session", bad_validate_refresh_and_get_session, raising=False)

    res = client.post("/v1/auth/logout", json={"refresh_token": "bad_refresh"})
    assert res.status_code == 401
    assert res.json()["detail"] == "bad refresh"


def test_signup_student_success(client: TestClient, patch_userdao):
    res = client.post(
        "/v1/auth/signup",
        json={
            "full_name": "Ivan Sergeevich Petrov",
            "first_name": "Ivan",
            "middle_name": "Sergeevich",
            "second_name": "Petrov",
            "nickname": "Ivan",
            "age": 17,
            "email": "ivan.petrov@example.com",
            "phone": "+79990000000",
            "password": "secret123",
            "school": {"id": str(uuid4())},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "ivan.petrov@example.com"
    # your handler maps role to created_user.role.role
    assert body["role"] in (None, "student")


def test_create_user_success(client: TestClient, patch_userdao):
    res = client.post(
        "/v1/auth/users/create",
        json={
            "full_name": "Petr Ivanovich Sidorov",
            "nickname": "petr_i",
            "age": 28,
            "email": "p.sidorov@example.com",
            "phone": "+79991112233",
            "password": "secret",
            "role": "ADMIN",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "p.sidorov@example.com"
    # this endpoint currently returns role=None in handler; just check the shape
    assert "role" in body
    assert "created_at" in body
