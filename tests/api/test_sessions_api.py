from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user
from app.services.testing_engine.session_service import SessionService, SessionStatus


class FakeSession:
    def __init__(self, **fields):
        self.__dict__.update(fields)
        self.saved = False

    async def save(self):  # pragma: no cover - trivial
        self.saved = True


class FakeQuestionBank:
    def __init__(self, mapping):
        self.mapping = mapping

    async def get_question(self, qid: UUID):
        return self.mapping[qid]


def _patch_question_redis(monkeypatch, mapping: dict[UUID, object]):
    """Question content is now served from QuestionRedis (the session-start
    snapshot), not the legacy qb mock — patch it to read from the same mapping
    the test already set up."""
    from app.services.testing_engine import session_service

    async def fake_get(question_id: UUID):
        return mapping[question_id]

    monkeypatch.setattr(session_service.QuestionRedis, "get", staticmethod(fake_get), raising=False)


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


def _make_session(
    *,
    sid: UUID,
    test_id: UUID,
    user_id: UUID,
    question_ids: list[UUID],
    answers: dict[str, str] | None = None,
    current_index: int = 0,
    status: SessionStatus = SessionStatus.ACTIVE,
    time_start: datetime | None = None,
    time_finish: datetime | None = None,
    duration: int | None = None,
    score: float | None = None,
    navigation_method: str = "free",
    required_count: int = 0,
) -> FakeSession:
    now = datetime.now(timezone.utc)
    return FakeSession(
        sid=str(sid),
        test_id=test_id,
        user_id=user_id,
        time_start=time_start or now,
        time_finish=time_finish,
        question_ids=json.dumps([str(qid) for qid in question_ids]),
        questions_remaining=len(question_ids),
        questions_answered=0,
        answers=json.dumps(answers or {}),
        current_question_index=current_index,
        status=status,
        ip_address="127.0.0.1",
        device_type="pytest",
        last_activity=now,
        duration=duration,
        score=score,
        indefinite_questions=False,
        navigation_method=navigation_method,
        required_count=required_count,
        question_times=json.dumps({}),
    )


@pytest.fixture()
def app():
    app = FastAPI()
    from app.services.testing_engine.routers import sessions as sessions_router

    app.include_router(sessions_router.router)
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


def test_start_session_creates_session(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router
    from app.repositories.dao.testdao import TestDAO

    test_id = uuid4()
    question_ids = [uuid4(), uuid4()]

    qb = FakeQuestionBank({qid: SimpleNamespace(content=f"Q-{i}") for i, qid in enumerate(question_ids)})

    async def fake_create(
        cls, *, user_id, test_id, question_ids, indefinite_questions, ip_address, device_type, qb,
        required_count=0, navigation_method="free",
    ):
        session = _make_session(
            sid=uuid4(),
            test_id=test_id,
            user_id=user_id,
            question_ids=question_ids,
        )
        return SessionService(session, qb)

    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)
    monkeypatch.setattr(SessionService, "create", classmethod(fake_create), raising=False)
    async def fake_get_test(_id):
        return SimpleNamespace(
            id=test_id, shuffle=False, number_of_required_questions=None, navigation_method="free"
        )

    async def fake_list_questions(_id):
        return [SimpleNamespace(question_id=qid) for qid in question_ids]

    async def fake_list_rules(_id):
        return []

    monkeypatch.setattr(TestDAO, "get", staticmethod(fake_get_test), raising=False)
    monkeypatch.setattr(TestDAO, "list_questions", staticmethod(fake_list_questions), raising=False)
    monkeypatch.setattr(TestDAO, "list_rules", staticmethod(fake_list_rules), raising=False)

    res = client.post(f"/tests/{test_id}/start")

    assert res.status_code == 201
    body = res.json()
    assert body["test_id"] == str(test_id)
    assert body["user_id"] == str(override_user)
    assert body["status"] == "active"


def test_get_session_list_returns_sessions(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    question_ids = [uuid4()]
    sessions = [
        _make_session(sid=uuid4(), test_id=uuid4(), user_id=override_user, question_ids=question_ids),
        _make_session(sid=uuid4(), test_id=uuid4(), user_id=override_user, question_ids=question_ids),
    ]

    async def fake_user_sessions(cls, user_id):
        assert str(user_id) == str(override_user)
        return sessions

    monkeypatch.setattr(SessionService, "user_sessions", classmethod(fake_user_sessions), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: FakeQuestionBank({}))

    res = client.get("/tests/session/list")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert all(item["user_id"] == str(override_user) for item in body)


def test_get_session_info_returns_session(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4()]
    session = _make_session(sid=sid, test_id=uuid4(), user_id=override_user, question_ids=question_ids)
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1")})

    async def fake_load(cls, session_id, qb):
        assert session_id == str(sid)
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.get(f"/tests/session/{sid}")

    assert res.status_code == 200
    body = res.json()
    assert body["sid"] == str(sid)
    assert body["user_id"] == str(override_user)


def test_delete_session_returns_delete_payload(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        time_start=datetime.utcnow(),
    )
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1")})

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.delete(f"/tests/session/{sid}")

    assert res.status_code == 200
    body = res.json()
    assert body["sid"] == str(sid)
    assert body["deleted_at"] is not None
    assert body["deleted_at_unix"] is not None


def test_question_list_returns_statuses(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    answers = {"0": "A"}
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        answers=answers,
    )
    qb = FakeQuestionBank(
        {
            question_ids[0]: SimpleNamespace(content="Q1", question_type="single"),
            question_ids[1]: SimpleNamespace(content="Q2", question_type="multiple"),
        }
    )
    _patch_question_redis(monkeypatch, qb.mapping)

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.get(f"/tests/session/{sid}/question/list")

    assert res.status_code == 200
    body = res.json()
    assert body[0]["index"] == 0
    assert body[0]["status"] == "answered"
    assert body[1]["status"] == "unanswered"
    # question_id/question_type must round-trip — the frontend needs question_id
    # to submit an answer and question_type to know whether to render radio
    # buttons, checkboxes, or a free-text field.
    assert body[0]["question_id"] == str(question_ids[0])
    assert body[0]["question_type"] == "single"
    assert body[1]["question_id"] == str(question_ids[1])
    assert body[1]["question_type"] == "multiple"


def test_get_question_by_id_returns_question(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(sid=sid, test_id=uuid4(), user_id=override_user, question_ids=question_ids)
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})
    _patch_question_redis(monkeypatch, qb.mapping)

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.get(f"/tests/session/{sid}/question/{question_ids[1]}")

    assert res.status_code == 200
    body = res.json()
    assert body["index"] == 1
    assert body["question"] == "Q2"


def test_get_next_question_advances_index(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        current_index=0,
    )
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})
    _patch_question_redis(monkeypatch, qb.mapping)

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.get(f"/tests/session/{sid}/question/next")

    assert res.status_code == 200
    body = res.json()
    assert body["index"] == 1
    assert body["question"] == "Q2"


def test_get_prev_question_moves_back(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        current_index=1,
    )
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})
    _patch_question_redis(monkeypatch, qb.mapping)

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.get(f"/tests/session/{sid}/question/prev")

    assert res.status_code == 200
    body = res.json()
    assert body["index"] == 0
    assert body["question"] == "Q1"


def test_linear_navigation_blocks_prev(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        current_index=1,
        navigation_method="linear",
    )
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})
    _patch_question_redis(monkeypatch, qb.mapping)

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.get(f"/tests/session/{sid}/question/prev")

    assert res.status_code == 403


def test_linear_navigation_blocks_jumping_to_other_question(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        current_index=0,
        navigation_method="linear",
    )
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})
    _patch_question_redis(monkeypatch, qb.mapping)

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    # Jumping ahead to question index 1 while sitting at index 0 must be blocked.
    res = client.get(f"/tests/session/{sid}/question/{question_ids[1]}")
    assert res.status_code == 403

    # Viewing the current question is still fine.
    res = client.get(f"/tests/session/{sid}/question/{question_ids[0]}")
    assert res.status_code == 200


def test_linear_navigation_blocks_answering_other_question(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        current_index=0,
        navigation_method="linear",
    )
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.post(
        f"/tests/session/{sid}/question/{question_ids[1]}/answer",
        json={"answer": "A"},
    )

    assert res.status_code == 403


def test_answer_question_updates_session(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(sid=sid, test_id=uuid4(), user_id=override_user, question_ids=question_ids)
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.post(
        f"/tests/session/{sid}/question/{question_ids[0]}/answer",
        json={"answer": "A"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["questions_answered"] == 1
    assert body["questions_remaining"] == len(question_ids) - 1


def test_submit_session_finishes_and_scores(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router
    from app.services.testing_engine import session_service

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        answers={"0": "A", "1": "B"},
        time_start=datetime.now(timezone.utc),
    )
    qb = FakeQuestionBank({question_ids[0]: SimpleNamespace(content="Q1"), question_ids[1]: SimpleNamespace(content="Q2")})

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    async def fake_question_get(question_id):
        index = question_ids.index(question_id)
        correct = "A" if index == 0 else "B"
        return SimpleNamespace(question_id=question_id, index=index, correct_answer=correct, question_type="single")

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)
    monkeypatch.setattr(session_service.QuestionRedis, "get", staticmethod(fake_question_get), raising=False)

    res = client.post(f"/tests/session/{sid}/submit")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    assert body["score"] == 100.0


def test_submit_blocked_until_required_questions_answered(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router

    sid = uuid4()
    question_ids = [uuid4(), uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        answers={"0": "A"},  # only 1 of 2 required questions answered
        required_count=2,
    )
    # questions_remaining must reflect that 2 of 3 are still open for the gate to apply.
    session.questions_remaining = 2
    qb = FakeQuestionBank({qid: SimpleNamespace(content=f"Q{i}") for i, qid in enumerate(question_ids)})

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)

    res = client.post(f"/tests/session/{sid}/submit")

    assert res.status_code == 400
    assert session.status == SessionStatus.ACTIVE


def test_submit_allowed_once_required_questions_answered(client: TestClient, override_user, monkeypatch):
    from app.services.testing_engine.routers import sessions as sessions_router
    from app.services.testing_engine import session_service

    sid = uuid4()
    question_ids = [uuid4(), uuid4(), uuid4()]
    session = _make_session(
        sid=sid,
        test_id=uuid4(),
        user_id=override_user,
        question_ids=question_ids,
        answers={"0": "A", "1": "A"},  # meets required_count, third question left open
        required_count=2,
    )
    session.questions_remaining = 1
    qb = FakeQuestionBank({qid: SimpleNamespace(content=f"Q{i}") for i, qid in enumerate(question_ids)})

    async def fake_load(cls, session_id, qb):
        return SessionService(session, qb)

    async def fake_question_get(question_id):
        return SimpleNamespace(question_id=question_id, correct_answer="A", question_type="single")

    monkeypatch.setattr(SessionService, "load", classmethod(fake_load), raising=False)
    monkeypatch.setattr(sessions_router, "get_qb", lambda: qb)
    monkeypatch.setattr(session_service.QuestionRedis, "get", staticmethod(fake_question_get), raising=False)

    res = client.post(f"/tests/session/{sid}/submit")

    assert res.status_code == 200
    assert res.json()["status"] == "completed"
