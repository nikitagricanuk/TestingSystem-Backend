from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aredis_om import NotFoundError

from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user
from app.services.testing_engine.models.redis import SessionStatus


def _make_user(user_id: UUID) -> UserFull:
    now = datetime.now(timezone.utc)
    return UserFull(
        id=user_id,
        nickname="tester",
        email="tester@example.com",
        is_active=True,
        role="student",
        created_at=now,
        created_at_unix=int(now.timestamp()),
        updated_at=None,
        updated_at_unix=None,
        full_name="Test User",
        age=None,
        phone=None,
        school=None,
        permissions=[],
    )


def _make_session(*, sid: UUID, test_id: UUID, user_id: UUID, question_ids: list[UUID], answers: dict[str, str], score: float | None):
    return SimpleNamespace(
        sid=str(sid),
        test_id=test_id,
        user_id=user_id,
        question_ids=json.dumps([str(qid) for qid in question_ids]),
        answers=json.dumps(answers),
        score=score,
        duration=None,
        time_start=datetime.now(timezone.utc),
        time_finish=None,
        status=SessionStatus.FINISHED,
    )


@pytest.fixture()
def app():
    app = FastAPI()
    from app.routers import results as results_router

    app.include_router(results_router.router, prefix="/v1")
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


def test_get_result_not_found(client: TestClient, monkeypatch, override_user):
    from app.services.testing_engine.models.redis import Session as SessionModel

    async def fake_get(session_id: str):
        raise NotFoundError()

    monkeypatch.setattr(SessionModel, "get", staticmethod(fake_get), raising=False)

    res = client.get(f"/v1/tests/result/{uuid4()}")

    assert res.status_code == 404
    assert res.json()["detail"] == "Result not found"


def test_get_result_forbidden(client: TestClient, monkeypatch, override_user):
    from app.services.testing_engine.models.redis import Session as SessionModel

    session = _make_session(
        sid=uuid4(),
        test_id=uuid4(),
        user_id=uuid4(),
        question_ids=[uuid4()],
        answers={"0": "A"},
        score=100.0,
    )

    async def fake_get(session_id: str):
        return session

    monkeypatch.setattr(SessionModel, "get", staticmethod(fake_get), raising=False)

    res = client.get(f"/v1/tests/result/{uuid4()}")

    assert res.status_code == 403
    assert res.json()["detail"] == "Result not available"


def test_get_result_success(client: TestClient, monkeypatch, override_user):
    from app.services.testing_engine.models.redis import Session as SessionModel, QuestionRedis

    question_ids = [uuid4(), uuid4()]
    session = _make_session(
        sid=uuid4(),
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        answers={"0": "A", "1": "C"},
        score=None,
    )

    async def fake_get(session_id: str):
        return session

    async def fake_question_get(question_id: UUID):
        index = question_ids.index(question_id)
        category = "math" if index == 0 else "history"
        correct = "A" if index == 0 else "B"
        return SimpleNamespace(index=str(index), category=category, correct_answer=correct)

    monkeypatch.setattr(SessionModel, "get", staticmethod(fake_get), raising=False)
    monkeypatch.setattr(QuestionRedis, "get", staticmethod(fake_question_get), raising=False)

    res = client.get(f"/v1/tests/result/{session.sid}")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    assert body["total_questions"] == 2
    assert body["correct_answers"] == 1
    assert body["score"] == 50.0
    assert len(body["group_scores"]) == 2


def test_get_leaderboard_sorted(client: TestClient, monkeypatch, override_user):
    from app.services.testing_engine.models.redis import Session as SessionModel, QuestionRedis
    from app.repositories.dao.userdao import UserDAO

    question_ids = [uuid4()]
    session_fast = _make_session(
        sid=uuid4(),
        test_id=uuid4(),
        user_id=uuid4(),
        question_ids=question_ids,
        answers={"0": "A"},
        score=100.0,
    )
    session_slow = _make_session(
        sid=uuid4(),
        test_id=uuid4(),
        user_id=uuid4(),
        question_ids=question_ids,
        answers={"0": "B"},
        score=50.0,
    )
    sessions = [session_slow, session_fast]

    class FakeQuery:
        async def all(self):
            return sessions

    def fake_find(*args, **kwargs):
        return FakeQuery()

    async def fake_question_get(question_id: UUID):
        return SimpleNamespace(index="0", category="math", correct_answer="A")

    async def fake_get_user_by_id(self, user_id: str):
        nickname = "Top" if user_id == str(session_fast.user_id) else "Runner"
        return SimpleNamespace(nickname=nickname)

    monkeypatch.setattr(SessionModel, "find", staticmethod(fake_find), raising=False)
    monkeypatch.setattr(QuestionRedis, "get", staticmethod(fake_question_get), raising=False)
    monkeypatch.setattr(UserDAO, "get_user_by_id", fake_get_user_by_id, raising=False)

    res = client.get("/v1/tests/leaderboard")

    assert res.status_code == 200
    body = res.json()
    assert body[0]["rank"] == 1
    assert body[0]["nickname"] == "Top"
    assert body[0]["score"] == 100.0
    assert body[1]["rank"] == 2
