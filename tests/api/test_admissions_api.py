from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user
from app.services.testing_engine.models.redis import SessionStatus


def _make_user(role: str, permissions: list[str]) -> UserFull:
    now = datetime.now(timezone.utc)
    return UserFull(
        id=uuid4(), nickname="tester", email="t@example.com", is_active=True, role=role,
        created_at=now, created_at_unix=int(now.timestamp()), updated_at=None, updated_at_unix=None,
        full_name="Test", age=None, phone=None, school=None, permissions=permissions,
    )


@pytest.fixture()
def app():
    app = FastAPI()
    from app.routers import admissions as admissions_router

    app.include_router(admissions_router.router, prefix="/v1")
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


def _override(app: FastAPI, role: str, permissions: list[str]):
    async def _fn():
        return _make_user(role, permissions)

    app.dependency_overrides[get_current_user] = _fn


def test_list_contacts_forbidden_without_permission(client: TestClient, app: FastAPI):
    _override(app, "student", [])
    res = client.get("/v1/admissions/contacts")
    assert res.status_code == 403


def test_list_contacts_returns_ranked_entries_with_contact_info(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import admissions as admissions_router
    from app.repositories.dao.userdao import UserDAO
    from app.repositories.dao.applicantcontactdao import ApplicantContactDAO
    from app.models.database import ApplicantContactStatus

    uid1, uid2 = uuid4(), uuid4()
    sessions = [
        SimpleNamespace(user_id=uid1, score=90.0, status=SessionStatus.FINISHED, time_finish=None),
        SimpleNamespace(user_id=uid2, score=70.0, status=SessionStatus.FINISHED, time_finish=None),
    ]

    async def fake_load_finished(test_id=None):
        return sessions

    async def fake_get_users_by_ids(self, user_ids):
        return {
            uid1: SimpleNamespace(full_name="Ivan Ivanov", nickname="Ivan", phone_number="111", email="ivan@x.com", school=None),
            uid2: SimpleNamespace(full_name="Petr Petrov", nickname="Petr", phone_number="222", email="petr@x.com", school=None),
        }

    async def fake_list_for_users(user_ids):
        return {uid1: SimpleNamespace(status=ApplicantContactStatus.CALLED, custom_tag=None)}

    _override(app, "admissions_committee", ["read_applicant_contacts"])
    monkeypatch.setattr(admissions_router, "_load_finished_sessions", fake_load_finished)
    monkeypatch.setattr(UserDAO, "get_users_by_ids", fake_get_users_by_ids, raising=False)
    monkeypatch.setattr(ApplicantContactDAO, "list_for_users", staticmethod(fake_list_for_users), raising=False)

    res = client.get("/v1/admissions/contacts")

    assert res.status_code == 200
    body = res.json()
    assert body[0]["name"] == "Ivan Ivanov"
    assert body[0]["phone"] == "111"
    assert body[0]["status"] == "called"
    assert body[1]["status"] == "not_called"


def test_update_contact_forbidden_without_permission(client: TestClient, app: FastAPI):
    _override(app, "teacher", [])
    res = client.patch(f"/v1/admissions/contacts/{uuid4()}", json={"status": "called"})
    assert res.status_code == 403


def test_update_contact_invalid_status_returns_400(client: TestClient, app: FastAPI, monkeypatch):
    from app.repositories.dao.userdao import UserDAO

    async def fake_get_user_by_id(self, user_id):
        return SimpleNamespace(full_name="X", nickname="X", phone_number=None, email=None)

    _override(app, "admissions_committee", ["edit_applicant_contacts"])
    monkeypatch.setattr(UserDAO, "get_user_by_id", fake_get_user_by_id, raising=False)

    res = client.patch(f"/v1/admissions/contacts/{uuid4()}", json={"status": "bogus"})
    assert res.status_code == 400


def test_update_contact_success(client: TestClient, app: FastAPI, monkeypatch):
    from app.repositories.dao.userdao import UserDAO
    from app.repositories.dao.applicantcontactdao import ApplicantContactDAO
    from app.models.database import ApplicantContactStatus

    user_id = uuid4()

    async def fake_get_user_by_id(self, uid):
        return SimpleNamespace(full_name="Ivan Ivanov", nickname="Ivan", phone_number="111", email="i@x.com")

    async def fake_upsert(uid, status_enum, custom_tag=None):
        return SimpleNamespace(status=status_enum, custom_tag=custom_tag)

    _override(app, "admissions_committee", ["edit_applicant_contacts"])
    monkeypatch.setattr(UserDAO, "get_user_by_id", fake_get_user_by_id, raising=False)
    monkeypatch.setattr(ApplicantContactDAO, "upsert", staticmethod(fake_upsert), raising=False)

    res = client.patch(f"/v1/admissions/contacts/{user_id}", json={"status": "custom", "custom_tag": "VIP"})

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "custom"
    assert body["custom_tag"] == "VIP"


def test_export_contacts_returns_xlsx(client: TestClient, app: FastAPI, monkeypatch):
    from io import BytesIO

    from openpyxl import load_workbook

    from app.routers import admissions as admissions_router
    from app.repositories.dao.userdao import UserDAO
    from app.repositories.dao.applicantcontactdao import ApplicantContactDAO

    uid1 = uuid4()
    sessions = [SimpleNamespace(user_id=uid1, score=90.0, status=SessionStatus.FINISHED, time_finish=None)]

    async def fake_load_finished(test_id=None):
        return sessions

    async def fake_get_users_by_ids(self, user_ids):
        return {uid1: SimpleNamespace(full_name="Ivan Ivanov", nickname="Ivan", phone_number="111", email="i@x.com", school=None)}

    async def fake_list_for_users(user_ids):
        return {}

    _override(app, "admissions_committee", ["read_applicant_contacts"])
    monkeypatch.setattr(admissions_router, "_load_finished_sessions", fake_load_finished)
    monkeypatch.setattr(UserDAO, "get_users_by_ids", fake_get_users_by_ids, raising=False)
    monkeypatch.setattr(ApplicantContactDAO, "list_for_users", staticmethod(fake_list_for_users), raising=False)

    res = client.get("/v1/admissions/contacts/export", params={"columns": "rank,name,score"})

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/vnd.openxmlformats")
    sheet = load_workbook(BytesIO(res.content)).active
    assert [c.value for c in sheet[1]] == ["Место", "ФИО", "Балл"]
    assert [c.value for c in sheet[2]] == [1, "Ivan Ivanov", 90.0]


def test_export_contacts_unknown_column_returns_400(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import admissions as admissions_router

    async def fake_load_finished(test_id=None):
        return []

    _override(app, "admissions_committee", ["read_applicant_contacts"])
    monkeypatch.setattr(admissions_router, "_load_finished_sessions", fake_load_finished)

    res = client.get("/v1/admissions/contacts/export", params={"columns": "bogus"})
    assert res.status_code == 400
