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

    async def fake_get_users_by_ids(self, user_ids):
        return {
            uid: SimpleNamespace(
                nickname="Top" if uid == session_fast.user_id else "Runner",
                school=None,
            )
            for uid in user_ids
        }

    monkeypatch.setattr(SessionModel, "find", staticmethod(fake_find), raising=False)
    monkeypatch.setattr(QuestionRedis, "get", staticmethod(fake_question_get), raising=False)
    monkeypatch.setattr(UserDAO, "get_user_by_id", fake_get_user_by_id, raising=False)
    monkeypatch.setattr(UserDAO, "get_users_by_ids", fake_get_users_by_ids, raising=False)

    res = client.get("/v1/tests/leaderboard")

    assert res.status_code == 200
    body = res.json()
    assert body[0]["rank"] == 1
    assert body[0]["nickname"] == "Top"
    assert body[0]["score"] == 100.0
    assert body[1]["rank"] == 2


def test_leaderboard_school_scope_restricts_students_to_their_own_school(
    client: TestClient, monkeypatch, app: FastAPI
):
    from app.services.testing_engine.models.redis import Session as SessionModel, QuestionRedis
    from app.repositories.dao.userdao import UserDAO

    my_school_id = uuid4()
    other_school_id = uuid4()
    me_id = uuid4()
    classmate_id = uuid4()
    other_school_student_id = uuid4()
    question_ids = [uuid4()]

    def _session(user_id, score):
        return _make_session(
            sid=uuid4(), test_id=uuid4(), user_id=user_id, question_ids=question_ids,
            answers={"0": "A"}, score=score,
        )

    sessions = [
        _session(me_id, 90.0),
        _session(classmate_id, 80.0),
        _session(other_school_student_id, 100.0),
    ]

    class FakeQuery:
        async def all(self):
            return sessions

    async def fake_question_get(question_id):
        return SimpleNamespace(index="0", category="math", correct_answer="A", question_type="single")

    async def fake_get_users_by_ids(self, user_ids):
        schools = {
            me_id: SimpleNamespace(id=my_school_id, city_id=uuid4(), short_name="My School"),
            classmate_id: SimpleNamespace(id=my_school_id, city_id=uuid4(), short_name="My School"),
            other_school_student_id: SimpleNamespace(id=other_school_id, city_id=uuid4(), short_name="Other"),
        }
        return {
            uid: SimpleNamespace(nickname=str(uid), school=schools[uid])
            for uid in user_ids
        }

    async def _override_me():
        from app.schemas.users import School as SchoolSchema

        now = datetime.now(timezone.utc)
        return UserFull(
            id=me_id, nickname="Me", email="me@example.com", is_active=True, role="student",
            created_at=now, created_at_unix=int(now.timestamp()), updated_at=None, updated_at_unix=None,
            full_name="Me", age=None, phone=None,
            school=SchoolSchema(id=my_school_id, city_id=uuid4(), full_name="My School", short_name="My School"),
            permissions=[],
        )

    from app.repositories.dao.geodao import SettlementDAO

    async def fake_settlement_get(settlement_id):
        return SimpleNamespace(id=settlement_id, region_id=uuid4())

    app.dependency_overrides[get_current_user] = _override_me
    monkeypatch.setattr(SessionModel, "find", staticmethod(lambda *a, **k: FakeQuery()), raising=False)
    monkeypatch.setattr(QuestionRedis, "get", staticmethod(fake_question_get), raising=False)
    monkeypatch.setattr(UserDAO, "get_users_by_ids", fake_get_users_by_ids, raising=False)
    monkeypatch.setattr(SettlementDAO, "get", staticmethod(fake_settlement_get), raising=False)

    res = client.get("/v1/tests/leaderboard", params={"scope": "school"})

    assert res.status_code == 200
    body = res.json()
    returned_ids = {entry["nickname"] for entry in body}
    assert returned_ids == {str(me_id), str(classmate_id)}
    assert str(other_school_student_id) not in returned_ids


def test_session_review_forbidden_for_other_students_session(client: TestClient, monkeypatch, override_user):
    from app.services.testing_engine.models.redis import Session as SessionModel

    sid = uuid4()
    session = SimpleNamespace(
        sid=str(sid),
        test_id=uuid4(),
        user_id=uuid4(),  # someone else's session, not override_user's
        question_ids=json.dumps([]),
        answers=json.dumps({}),
        score=50.0,
    )

    async def fake_get(session_id: str):
        return session

    monkeypatch.setattr(SessionModel, "get", staticmethod(fake_get), raising=False)

    res = client.get(f"/v1/tests/session/{sid}/review")
    assert res.status_code == 403


def test_session_review_forbidden_when_test_disallows_review(client: TestClient, monkeypatch, override_user):
    from app.services.testing_engine.models.redis import Session as SessionModel
    from app.repositories.dao.testdao import TestDAO

    sid = uuid4()
    session = SimpleNamespace(
        sid=str(sid),
        test_id=uuid4(),
        user_id=override_user,  # this IS the caller's own session
        question_ids=json.dumps([]),
        answers=json.dumps({}),
        score=50.0,
    )

    async def fake_get(session_id: str):
        return session

    async def fake_test_get(test_id):
        return SimpleNamespace(id=test_id, can_be_reviewed=False)

    monkeypatch.setattr(SessionModel, "get", staticmethod(fake_get), raising=False)
    monkeypatch.setattr(TestDAO, "get", staticmethod(fake_test_get), raising=False)

    res = client.get(f"/v1/tests/session/{sid}/review")
    assert res.status_code == 403


def test_session_review_allowed_for_own_session_when_test_allows_review(
    client: TestClient, monkeypatch, override_user
):
    from app.services.testing_engine.models.redis import Session as SessionModel, QuestionRedis
    from app.repositories.dao.testdao import TestDAO

    sid = uuid4()
    session = SimpleNamespace(
        sid=str(sid),
        test_id=uuid4(),
        user_id=override_user,
        question_ids=json.dumps([]),
        answers=json.dumps({}),
        score=90.0,
    )

    async def fake_get(session_id: str):
        return session

    async def fake_test_get(test_id):
        return SimpleNamespace(id=test_id, can_be_reviewed=True)

    monkeypatch.setattr(SessionModel, "get", staticmethod(fake_get), raising=False)
    monkeypatch.setattr(TestDAO, "get", staticmethod(fake_test_get), raising=False)

    res = client.get(f"/v1/tests/session/{sid}/review")
    assert res.status_code == 200
    assert res.json()["score"] == 90.0


def test_session_review_returns_per_question_breakdown(client: TestClient, monkeypatch, app: FastAPI):
    from app.services.testing_engine.models.redis import Session as SessionModel, QuestionRedis

    sid = uuid4()
    question_ids = [uuid4(), uuid4()]
    session = SimpleNamespace(
        sid=str(sid),
        test_id=uuid4(),
        user_id=uuid4(),
        question_ids=json.dumps([str(q) for q in question_ids]),
        answers=json.dumps({"0": "A", "1": json.dumps(["1"])}),
        question_times=json.dumps({"0": 12.5, "1": 30.0}),
        score=75.0,
    )

    questions_by_id = {
        question_ids[0]: SimpleNamespace(
            content="Prompt 1", choices=json.dumps(["A", "B"]), correct_answer="A", question_type="single"
        ),
        question_ids[1]: SimpleNamespace(
            content="Prompt 2", choices=json.dumps(["X", "Y"]), correct_answer=json.dumps(["0"]), question_type="multiple"
        ),
    }

    async def fake_get(session_id: str):
        return session

    async def fake_question_get(question_id):
        return questions_by_id[question_id]

    now = datetime.now(timezone.utc)

    async def _override_teacher():
        return UserFull(
            id=uuid4(), nickname="Teacher", email="t@example.com", is_active=True, role="teacher",
            created_at=now, created_at_unix=int(now.timestamp()), updated_at=None, updated_at_unix=None,
            full_name="Teacher", age=None, phone=None, school=None,
            permissions=["read_any_sessions"],
        )

    app.dependency_overrides[get_current_user] = _override_teacher
    monkeypatch.setattr(SessionModel, "get", staticmethod(fake_get), raising=False)
    monkeypatch.setattr(QuestionRedis, "get", staticmethod(fake_question_get), raising=False)

    res = client.get(f"/v1/tests/session/{sid}/review")

    assert res.status_code == 200
    body = res.json()
    assert body["score"] == 75.0
    assert len(body["questions"]) == 2
    assert body["questions"][0]["prompt"] == "Prompt 1"
    assert body["questions"][0]["student_answer"] == "A"
    assert body["questions"][0]["is_correct"] is True
    assert body["questions"][0]["time_spent_seconds"] == 12.5
    # question 1 is multi-select: submitted ["1"] vs correct ["0"] -> wrong
    assert body["questions"][1]["is_correct"] is False


def test_test_analysis_forbidden_for_student(client: TestClient, override_user):
    res = client.get(f"/v1/tests/{uuid4()}/analysis")
    assert res.status_code == 403


def test_test_analysis_returns_per_question_stats(client: TestClient, monkeypatch, app: FastAPI):
    from app.services.testing_engine.models.redis import Session as SessionModel, QuestionRedis
    from app.repositories.dao.testdao import TestDAO

    test_id = uuid4()
    question_id = uuid4()

    def _session(score, correct):
        return SimpleNamespace(
            sid=str(uuid4()),
            test_id=test_id,
            user_id=uuid4(),
            question_ids=json.dumps([str(question_id)]),
            answers=json.dumps({"0": "A" if correct else "B"}),
            score=score,
            status=SessionStatus.FINISHED,
            time_finish=datetime.now(timezone.utc),
        )

    sessions = [_session(90, True), _session(80, True), _session(20, False), _session(10, False)]

    class FakeQuery:
        async def all(self):
            return sessions

    snapshot = SimpleNamespace(
        category="Topic", question_type="single", correct_answer="A",
        choices=json.dumps(["A", "B", "C", "D"]), mark_out_of=1,
    )

    async def fake_question_get(qid):
        return snapshot

    async def fake_get_test(_id):
        return SimpleNamespace(id=test_id)

    now = datetime.now(timezone.utc)

    async def _override_teacher():
        return UserFull(
            id=uuid4(), nickname="Teacher", email="t@example.com", is_active=True, role="teacher",
            created_at=now, created_at_unix=int(now.timestamp()), updated_at=None, updated_at_unix=None,
            full_name="Teacher", age=None, phone=None, school=None,
            permissions=["read_test_analysis"],
        )

    app.dependency_overrides[get_current_user] = _override_teacher
    monkeypatch.setattr(SessionModel, "find", staticmethod(lambda *a, **k: FakeQuery()), raising=False)
    monkeypatch.setattr(QuestionRedis, "get", staticmethod(fake_question_get), raising=False)
    monkeypatch.setattr(TestDAO, "get", staticmethod(fake_get_test), raising=False)

    res = client.get(f"/v1/tests/{test_id}/analysis")

    assert res.status_code == 200
    body = res.json()
    assert len(body["questions"]) == 1
    q = body["questions"][0]
    assert q["attempts"] == 4
    assert q["difficulty"] == 0.5
    assert q["discrimination"] == 1.0
    assert q["guess_score"] == 0.25
