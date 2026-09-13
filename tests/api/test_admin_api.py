from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user
from app.services.testing_engine.models.redis import SessionStatus


def _make_user(role: str) -> UserFull:
    now = datetime.now(timezone.utc)
    return UserFull(
        id=uuid4(), nickname="tester", email="t@example.com", is_active=True, role=role,
        created_at=now, created_at_unix=int(now.timestamp()), updated_at=None, updated_at_unix=None,
        full_name="Test", age=None, phone=None, school=None, permissions=[],
    )


@pytest.fixture()
def app():
    app = FastAPI()
    from app.routers import admin as admin_router

    app.include_router(admin_router.router, prefix="/v1")
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


def _override(app: FastAPI, role: str):
    async def _fn():
        return _make_user(role)

    app.dependency_overrides[get_current_user] = _fn


def test_admin_stats_forbidden_for_non_admin(client: TestClient, app: FastAPI):
    _override(app, "student")
    res = client.get("/v1/admin/stats")
    assert res.status_code == 403


def test_admin_stats_counts_active_and_avg_score(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import admin as admin_router

    now = datetime.now(timezone.utc)
    active_session = SimpleNamespace(
        user_id=uuid4(), status=SessionStatus.ACTIVE, last_activity=now, time_start=now, score=None,
    )
    finished_session = SimpleNamespace(
        user_id=uuid4(), status=SessionStatus.FINISHED, last_activity=now - timedelta(hours=2),
        time_start=now - timedelta(hours=2), score=80.0,
    )

    async def fake_load_all():
        return [active_session, finished_session]

    async def fake_load_finished(test_id=None):
        return [finished_session]

    _override(app, "admin")
    monkeypatch.setattr(admin_router, "_load_all_sessions", fake_load_all)
    monkeypatch.setattr(admin_router, "_load_finished_sessions", fake_load_finished)

    res = client.get("/v1/admin/stats")

    assert res.status_code == 200
    body = res.json()
    assert body["active_now"] == 1
    assert body["avg_score"] == 80.0
    assert body["total_finished_attempts"] == 1


def test_admin_load_by_weekday_buckets_sessions(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import admin as admin_router

    monday = datetime(2026, 1, 5, tzinfo=timezone.utc)  # a known Monday
    sessions = [
        SimpleNamespace(time_start=monday, status=SessionStatus.FINISHED, last_activity=monday, user_id=uuid4(), score=1),
        SimpleNamespace(time_start=monday, status=SessionStatus.FINISHED, last_activity=monday, user_id=uuid4(), score=1),
        SimpleNamespace(time_start=monday + timedelta(days=1), status=SessionStatus.FINISHED, last_activity=monday, user_id=uuid4(), score=1),
    ]

    async def fake_load_all():
        return sessions

    _override(app, "admin")
    monkeypatch.setattr(admin_router, "_load_all_sessions", fake_load_all)

    res = client.get("/v1/admin/stats/load")

    assert res.status_code == 200
    body = res.json()
    assert body[0]["label"] == "Пн"
    assert body[0]["count"] == 2
    assert body[1]["count"] == 1


def test_admin_demographics_groups_by_region_and_age(client: TestClient, app: FastAPI, monkeypatch):
    from app.routers import admin as admin_router
    from app.repositories.dao.userdao import UserDAO

    uid1, uid2 = uuid4(), uuid4()
    sessions = [
        SimpleNamespace(user_id=uid1, status=SessionStatus.FINISHED, last_activity=None, time_start=None, score=1),
        SimpleNamespace(user_id=uid2, status=SessionStatus.FINISHED, last_activity=None, time_start=None, score=1),
    ]

    region = SimpleNamespace(region="Иркутская область")
    settlement = SimpleNamespace(region=region)
    school = SimpleNamespace(settlement=settlement)

    async def fake_load_all():
        return sessions

    async def fake_get_users_by_ids(self, user_ids):
        return {
            uid1: SimpleNamespace(school=school, age=17),
            uid2: SimpleNamespace(school=school, age=19),
        }

    _override(app, "admin")
    monkeypatch.setattr(admin_router, "_load_all_sessions", fake_load_all)
    monkeypatch.setattr(UserDAO, "get_users_by_ids", fake_get_users_by_ids, raising=False)

    res = client.get("/v1/admin/stats/demographics")

    assert res.status_code == 200
    body = res.json()
    assert body["by_region"] == [{"region": "Иркутская область", "count": 2}]
    ages = {b["bucket"]: b["count"] for b in body["by_age"]}
    assert ages["16-17"] == 1
    assert ages["19+"] == 1
