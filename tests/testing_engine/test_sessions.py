import pytest
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.testing_engine import session_service
from app.services.testing_engine.session_service import SessionService, SessionStatus


class DummyQuestionBank:
    """Minimal async question bank used to verify interactions.

    Here we deliberately avoid real QuestionBank/Redis/JSON and only check that
    SessionService passes the right UUIDs and returns some object.
    """

    def __init__(self) -> None:
        self.requested_questions: list[uuid.UUID] = []

    async def get_question(self, question_id: uuid.UUID):
        self.requested_questions.append(question_id)
        # The concrete type is irrelevant for these tests
        return f"question-{question_id}"


class FakeSession:
    """Plain in‑memory replacement for the Redis Session model used in tests."""

    def __init__(self, **fields):
        # Store all provided fields as attributes
        self.__dict__.update(fields)
        # Flag so tests can assert that save() was called
        self.saved = fields.get("saved", False)

    async def save(self):  # pragma: no cover - trivial
        self.saved = True


@pytest.mark.asyncio
class TestSession:
    async def test_create_initializes_session_and_saves(self, monkeypatch):
        """`create` should build a new Session, save it and wrap it in SessionService.

        We monkeypatch the Redis Session model with FakeSession so that the
        method under test doesn't touch the real database layer at all.
        """

        # Make SessionService.create use our in‑memory FakeSession instead of Redis model
        monkeypatch.setattr(session_service, "Session", FakeSession)

        # Snapshotting hits Postgres/Redis for real; irrelevant to what this test
        # verifies (Session construction/save), so make it a no-op.
        async def fake_snapshot(question_ids):
            return None

        monkeypatch.setattr(
            session_service.QuestionSnapshotService, "snapshot_for_session", staticmethod(fake_snapshot)
        )

        qb = DummyQuestionBank()
        user_id = uuid.uuid4()
        test_id = uuid.uuid4()
        question_ids = [uuid.uuid4(), uuid.uuid4()]

        service = await SessionService.create(
            user_id=user_id,
            test_id=test_id,
            question_ids=question_ids,
            indefinite_questions=False,
            ip_address="127.0.0.1",
            qb=qb,
        )

        session = service.session

        assert isinstance(service, SessionService)
        assert isinstance(session, FakeSession)
        assert session.saved is True  # save() was awaited

        # Basic field invariants
        assert session.test_id == test_id
        assert session.user_id == user_id
        assert json.loads(session.question_ids) == [str(qid) for qid in question_ids]
        assert session.questions_remaining == len(question_ids)
        assert session.questions_answered == 0
        assert session.current_question_index == 0
        assert session.status == SessionStatus.ACTIVE
        assert session.answers == json.dumps({})

    async def test_answer_current_question_updates_counters(self):
        """First answer to a question should update counters (not the pointer — advancing
        is /next's/prev's job, so the student can change their mind before navigating on),
        second answer to the same question should not change the counters again."""

        qb = DummyQuestionBank()
        question_ids = [uuid.uuid4() for _ in range(3)]

        session = FakeSession(
            sid=str(uuid.uuid4()),
            test_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            question_ids=json.dumps([str(q) for q in question_ids]),
            questions_remaining=len(question_ids),
            indefinite_questions=False,
            ip_address="127.0.0.1",
            answers=json.dumps({}),
            questions_answered=0,
            current_question_index=0,
            status=SessionStatus.ACTIVE,
            time_start=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
        )

        service = SessionService(session, qb)

        # First answer to question 0
        await service.answer_current_question(0, "A")
        answers = json.loads(session.answers)

        assert answers == {"0": "A"}
        assert session.questions_answered == 1
        assert session.questions_remaining == len(question_ids) - 1
        assert session.current_question_index == 0
        assert session.saved is True

        # Second answer to the same question should not change counters
        session.saved = False  # reset flag to see if save() is called again
        await service.answer_current_question(0, "B")
        answers2 = json.loads(session.answers)

        assert answers2 == {"0": "B"}
        assert session.questions_answered == 1
        assert session.questions_remaining == len(question_ids) - 1
        assert session.current_question_index == 0
        assert session.saved is True

    async def test_get_current_question_uses_question_bank(self, monkeypatch):
        """get_current_question should fetch the QuestionRedis snapshot for the
        UUID at the session's current index (not the legacy qb mock)."""

        qb = DummyQuestionBank()
        question_ids = [uuid.uuid4() for _ in range(3)]
        requested: list[uuid.UUID] = []

        async def fake_get(question_id):
            requested.append(question_id)
            return f"question-{question_id}"

        monkeypatch.setattr(session_service.QuestionRedis, "get", staticmethod(fake_get))

        session = FakeSession(
            sid=str(uuid.uuid4()),
            test_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            question_ids=json.dumps([str(q) for q in question_ids]),
            questions_remaining=len(question_ids),
            indefinite_questions=False,
            ip_address="127.0.0.1",
            answers=json.dumps({}),
            questions_answered=0,
            current_question_index=1,  # second question
            status=SessionStatus.ACTIVE,
            time_start=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
        )

        service = SessionService(session, qb)
        result = await service.get_current_question()

        assert requested  # at least one call
        assert requested[0] == question_ids[1]
        assert result == f"question-{question_ids[1]}"

    async def test_next_and_prev_question_update_index_and_last_activity(self, monkeypatch):
        """next_question/prev_question should move the pointer and touch last_activity."""

        qb = DummyQuestionBank()
        question_ids = [uuid.uuid4() for _ in range(2)]
        now = datetime.now(timezone.utc)
        requested: list[uuid.UUID] = []

        async def fake_get(question_id):
            requested.append(question_id)
            return f"question-{question_id}"

        monkeypatch.setattr(session_service.QuestionRedis, "get", staticmethod(fake_get))

        session = FakeSession(
            sid=str(uuid.uuid4()),
            test_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            question_ids=json.dumps([str(q) for q in question_ids]),
            questions_remaining=len(question_ids),
            indefinite_questions=False,
            ip_address="127.0.0.1",
            answers=json.dumps({}),
            questions_answered=0,
            current_question_index=0,
            status=SessionStatus.ACTIVE,
            time_start=now,
            last_activity=now,
        )

        service = SessionService(session, qb)

        old_last_activity = session.last_activity
        await service.next_question()

        assert session.current_question_index == 1
        assert session.last_activity >= old_last_activity
        assert requested[-1] == question_ids[1]

        before_prev_last_activity = session.last_activity
        await service.prev_question()

        assert session.current_question_index == 0
        assert session.last_activity >= before_prev_last_activity
        assert requested[-1] == question_ids[0]

    async def test_finish_computes_score_and_sets_finished_status(self, monkeypatch):
        """finish() should compute percent score and update status/time fields.

        We patch QuestionRedis.get so that scoring logic can run without touching
        a real Redis backend or QuestionRedis model.
        """

        qb = DummyQuestionBank()
        question_ids = [uuid.uuid4(), uuid.uuid4()]
        correct_answers = ["A", "B"]

        # One correct, one incorrect
        session = FakeSession(
            sid=str(uuid.uuid4()),
            test_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            question_ids=json.dumps([str(q) for q in question_ids]),
            questions_remaining=0,
            indefinite_questions=False,
            ip_address="127.0.0.1",
            answers=json.dumps({"0": "A", "1": "X"}),
            questions_answered=2,
            current_question_index=2,
            status=SessionStatus.ACTIVE,
            time_start=datetime.now(timezone.utc) - timedelta(seconds=60),
            last_activity=datetime.now(timezone.utc),
            time_finish=None,
            duration=None,
            score=None,
        )

        async def fake_get(question_id):
            # Map question UUID to its index and correct answer
            idx = question_ids.index(question_id)
            return SimpleNamespace(
                question_id=question_id, index=idx, correct_answer=correct_answers[idx], question_type="single"
            )

        # Patch QuestionRedis.get to avoid talking to real Redis for questions
        monkeypatch.setattr(session_service.QuestionRedis, "get", staticmethod(fake_get))

        service = SessionService(session, qb)
        await service.finish()

        assert session.status == SessionStatus.FINISHED
        assert session.time_finish is not None
        assert session.duration is not None
        assert 0 <= session.duration <= 120
        assert session.score == 50.0
        assert session.saved is True

    async def test_finish_scores_multiple_choice_and_string_indexed_questions(self, monkeypatch):
        """Real QuestionRedis.index is a str field; finish() must still match answers
        keyed by string index, and must grade "multiple"-type questions as a set
        rather than exact string equality.
        """

        qb = DummyQuestionBank()
        question_ids = [uuid.uuid4(), uuid.uuid4()]

        session = FakeSession(
            sid=str(uuid.uuid4()),
            test_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            question_ids=json.dumps([str(q) for q in question_ids]),
            questions_remaining=0,
            indefinite_questions=False,
            ip_address="127.0.0.1",
            # Question 0: multi-select, submitted in a different order but same set -> correct.
            # Question 1: multi-select, missing one of the correct choices -> incorrect.
            answers=json.dumps({"0": json.dumps(["2", "0"]), "1": json.dumps(["0"])}),
            questions_answered=2,
            current_question_index=2,
            status=SessionStatus.ACTIVE,
            time_start=datetime.now(timezone.utc) - timedelta(seconds=60),
            last_activity=datetime.now(timezone.utc),
            time_finish=None,
            duration=None,
            score=None,
        )

        by_id = {
            question_ids[0]: SimpleNamespace(
                question_id=question_ids[0], index="0", correct_answer=json.dumps(["0", "2"]), question_type="multiple"
            ),
            question_ids[1]: SimpleNamespace(
                question_id=question_ids[1], index="1", correct_answer=json.dumps(["0", "1"]), question_type="multiple"
            ),
        }

        async def fake_get(question_id):
            return by_id[question_id]

        monkeypatch.setattr(session_service.QuestionRedis, "get", staticmethod(fake_get))

        service = SessionService(session, qb)
        await service.finish()

        assert session.score == 50.0

    async def test_close_sets_closed_status_and_duration(self):
        """close() should mark session as CLOSED and set finish/duration."""

        qb = DummyQuestionBank()

        start = datetime.utcnow() - timedelta(seconds=30)
        session = FakeSession(
            sid=str(uuid.uuid4()),
            test_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            question_ids=json.dumps([]),
            questions_remaining=0,
            indefinite_questions=False,
            ip_address="127.0.0.1",
            answers=json.dumps({}),
            questions_answered=0,
            current_question_index=0,
            status=SessionStatus.ACTIVE,
            time_start=start,  # naive to match close() implementation
            last_activity=start,
            time_finish=None,
            duration=None,
        )

        service = SessionService(session, qb)
        await service.close()

        assert session.status == SessionStatus.CLOSED
        assert session.time_finish is not None
        assert session.duration is not None
        assert session.duration >= 0
        assert session.saved is True

    async def test_load_returns_none_for_missing_session(self, monkeypatch):
        """load() should return None when underlying Session.get raises NotFoundError."""

        qb = DummyQuestionBank()

        async def fake_get_missing(sid: str):  # pragma: no cover - trivial
            raise session_service.NotFoundError

        monkeypatch.setattr(session_service.Session, "get", staticmethod(fake_get_missing))

        loaded = await SessionService.load("non-existent", qb)
        assert loaded is None

    async def test_load_wraps_existing_session(self, monkeypatch):
        """load() should return a SessionService when session exists."""

        qb = DummyQuestionBank()
        fake_session = FakeSession(sid="session-1")

        async def fake_get_existing(sid: str):  # pragma: no cover - trivial
            assert sid == "session-1"
            return fake_session

        monkeypatch.setattr(session_service.Session, "get", staticmethod(fake_get_existing))

        loaded = await SessionService.load("session-1", qb)

        assert isinstance(loaded, SessionService)
        assert loaded.session is fake_session

    async def test_user_sessions_queries_by_user_id(self, monkeypatch):
        """user_sessions() should delegate to Session.find and return its result.

        Instead of hitting Redis, we replace Session with a dummy class that
        records the equality expression and returns a fixed list from .all().
        """

        expected_user_id = uuid.uuid4()
        returned_sessions = [FakeSession(sid="1"), FakeSession(sid="2")]

        class DummyField:
            def __init__(self):
                self.last_compared_with = None

            def __eq__(self, other):  # pragma: no cover - simple comparator
                self.last_compared_with = other
                return ("user_id_eq", other)

        class DummyQuery:
            async def all(self):  # pragma: no cover - trivial
                return returned_sessions

        dummy_field = DummyField()

        class DummySession:
            user_id = dummy_field

            @classmethod
            def find(cls, expr):  # pragma: no cover - trivial
                # Ensure we compare against the stringified UUID
                assert expr == ("user_id_eq", str(expected_user_id))
                return DummyQuery()

        monkeypatch.setattr(session_service, "Session", DummySession)

        sessions = await SessionService.user_sessions(expected_user_id)

        assert sessions == returned_sessions
        assert dummy_field.last_compared_with == str(expected_user_id)
