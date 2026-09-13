import json
import uuid
from typing import List, Optional, Self
from datetime import datetime, timezone
from uuid import UUID

from aredis_om import NotFoundError

from .models.redis import Session, QuestionRedis, SessionStatus
from .question_bank.question_bank import QuestionBank, Question
from .schemas.sessions import Session as SessionSchema
from .grading import is_correct_answer
from .question_snapshot import QuestionSnapshotService



class SessionService:
    """
    Service class to manage testing sessions. Creates and manages sessions,
    computes final score. Delegates question-related operations to QuestionManager.
    """

    def __init__(self, session: Session, qb: QuestionBank) -> None:
        self.session: Session = session
        self.qb: QuestionBank = qb

    # --------- Factory methods (OOP constructor helpers) ---------

    @classmethod
    async def create(
            cls,
            *,
            user_id: UUID,
            test_id: UUID,
            question_ids: list[UUID],
            indefinite_questions: bool,
            ip_address: str,
            qb: QuestionBank,
            device_type: Optional[str] = None,
            required_count: int = 0,
            navigation_method: str = "free",
    ) -> Self:
        """
        Create a new testing session and wrap it in SessionService.
        """
        if not question_ids:
            raise ValueError("Cannot create a session without questions.")

        await QuestionSnapshotService.snapshot_for_session(question_ids)

        sid = str(uuid.uuid4())
        session = Session(
            # aredis_om's `primary_key=True` on a non-`pk`-named field (`sid`) doesn't
            # actually rewire the model's real Redis key under this pydantic version —
            # it silently keeps using the base class's auto-generated ULID `pk`, so
            # `Session.get(sid)` would 404 unless `pk` is set explicitly to match.
            pk=sid,
            sid=sid,
            test_id=test_id,
            user_id=user_id,
            question_ids=json.dumps([str(qid) for qid in question_ids]),
            questions_remaining=len(question_ids),
            indefinite_questions=indefinite_questions,
            ip_address=ip_address,
            device_type=device_type,
            answers=json.dumps({}),
            questions_answered=0,
            current_question_index=0,
            status=SessionStatus.ACTIVE,
            time_start=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            required_count=required_count,
            question_times=json.dumps({}),
            navigation_method=navigation_method,
        )
        await session.save()
        return cls(session, qb)

    @classmethod
    async def load(
            cls,
            session_id: str,
            qb: QuestionBank
    ) -> Optional[Self]:
        """
        Load an existing session and wrap it in SessionService.
        """
        try:
            session = await Session.get(session_id)
        except NotFoundError:
            session = None

        if session is not None:
            return cls(session, qb)

        try:
            pk_iter = await Session.all_pks()
            async for pk in pk_iter:
                try:
                    candidate = await Session.get(pk)
                except NotFoundError:
                    continue
                if str(candidate.sid) == str(session_id):
                    return cls(candidate, qb)
        except Exception:
            return None

        return None

    @classmethod
    async def user_sessions(cls, user_id: UUID) -> List[Session]:
        """
        Get all sessions for a given user.
        """
        try:
            query = Session.find(Session.user_id == str(user_id))
            return await query.all()
        except Exception:
            pass

        sessions: list[Session] = []
        try:
            pk_iter = await Session.all_pks()
            async for pk in pk_iter:
                try:
                    session = await Session.get(pk)
                except NotFoundError:
                    continue
                if str(session.user_id) == str(user_id):
                    sessions.append(session)
        except Exception:
            return []
        return sessions

    # --------- Object methods (no session_id argument) ---------

    async def get_current_question(self) -> QuestionRedis:
        return await self.get_question_by_index(self.session.current_question_index)

    async def get_question_by_index(self, question_index: int) -> QuestionRedis:
        """
        Fetch the question at `question_index` in this session's own ordering.

        Reads from the QuestionRedis snapshot taken at session-creation time
        (see QuestionSnapshotService), not the legacy `self.qb` mock bank, so
        students see the real question-bank content their test was built from.
        """
        question_ids = await self._get_question_ids()
        return await QuestionRedis.get(question_ids[question_index])

    async def answer_current_question(
            self,
            question_index: int,
            answer: str,
    ) -> Session:
        """
        Update this session with an answer to a given question index.
        """
        session = self.session

        if session.status != SessionStatus.ACTIVE:
            raise ValueError("Cannot answer questions in a non-active session.")

        answers_dict = json.loads(session.answers or "{}")

        # If this question is being answered for the first time, update counters.
        is_first_answer = str(question_index) not in answers_dict

        answers_dict[str(question_index)] = answer

        if is_first_answer:
            session.questions_answered += 1
            if session.questions_remaining > 0:
                session.questions_remaining -= 1

        now = datetime.now(timezone.utc)
        self.accumulate_time_for_question(question_index, now)

        # Answering does NOT move current_question_index — advancing is the sole
        # responsibility of /next, /prev and /question/{id} (see the sessions
        # router). A student can pick an answer, change their mind, and only
        # move on when they explicitly navigate; auto-advancing here would also
        # push the pointer out of bounds when answering the last question.
        session.last_activity = now
        session.answers = json.dumps(answers_dict)

        await session.save()
        return session

    def accumulate_time_for_question(self, question_index: int, now: Optional[datetime] = None) -> None:
        """Add the time since the session's last recorded activity to this
        question's running total (a simple approximation of time-spent-per-question,
        used for teacher attempt review — see PV-A-1's "сколько времени потратил на
        каждый вопрос"). Called both when answering and when navigating away from
        a question (see the sessions router's /next and /prev handlers)."""
        now = now or datetime.now(timezone.utc)
        session = self.session
        last_activity = session.last_activity
        if last_activity is None:
            return
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        elapsed = max(0.0, (now - last_activity).total_seconds())

        times = json.loads(getattr(session, "question_times", None) or "{}")
        key = str(question_index)
        times[key] = times.get(key, 0) + elapsed
        session.question_times = json.dumps(times)

    async def next_question(self) -> Question:
        now = datetime.now(timezone.utc)
        self.accumulate_time_for_question(self.session.current_question_index, now)
        self.session.current_question_index += 1
        self.session.last_activity = now
        await self.session.save()
        return await self.get_current_question()

    async def prev_question(self) -> Question:
        now = datetime.now(timezone.utc)
        self.accumulate_time_for_question(self.session.current_question_index, now)
        self.session.current_question_index -= 1
        self.session.last_activity = now
        await self.session.save()
        return await self.get_current_question()

    async def get(self) -> SessionSchema:
        """
        Get the current session info.
        """
        status_value = self.session.status
        if isinstance(status_value, SessionStatus):
            status_value = status_value.value
        status_map = {
            SessionStatus.ACTIVE.value: "active",
            SessionStatus.FINISHED.value: "completed",
            SessionStatus.CLOSED.value: "expired",
            SessionStatus.CREATED.value: "active",
        }
        normalized_status = status_map.get(str(status_value), "active")
        score = getattr(self.session, "score", None)
        duration_seconds = getattr(self.session, "duration", None)
        if duration_seconds is None and normalized_status == "active":
            duration_seconds = int(
                datetime.now(timezone.utc).timestamp()
                - self.session.time_start.replace(tzinfo=timezone.utc).timestamp()
            )
        return SessionSchema(
            sid=self.session.sid,
            test_id=self.session.test_id,
            user_id=self.session.user_id,
            time_start=self.session.time_start,
            time_start_unix=int(self.session.time_start.replace(tzinfo=timezone.utc).timestamp()),
            time_finish=self.session.time_finish,
            time_finish_unix=int(self.session.time_finish.replace(
                tzinfo=timezone.utc).timestamp()) if self.session.time_finish else None,
            duration_seconds=duration_seconds,
            time_left_seconds=None,
            total_questions=self.session.questions_answered + self.session.questions_remaining,
            questions_answered=self.session.questions_answered,
            questions_remaining=self.session.questions_remaining,
            current_question_index=self.session.current_question_index,
            status=normalized_status,
            required_count=getattr(self.session, "required_count", 0),
            required_complete=self.is_required_complete(),
            is_submitted=normalized_status == "completed",
            score=score,
            ip_address=self.session.ip_address,
            device_type=getattr(self.session, "device_type", None),
            last_activity_unix=int(self.session.last_activity.replace(tzinfo=timezone.utc).timestamp()),
            answers=json.loads(self.session.answers or "{}"),
        )

    def is_required_complete(self) -> bool:
        """
        Whether enough questions have been answered to allow finishing early.

        `required_count` (set at session creation from Test.number_of_required_questions
        and any obligatory TestQuestionRule slots) is treated as a simple threshold on
        the number of answered questions — matching PV-A-1's "N mandatory questions,
        then the student may continue or finish" flow — rather than requiring specific
        question indices, since navigation can be free-form.
        """
        required = getattr(self.session, "required_count", 0) or 0
        if required <= 0:
            return True
        answers = json.loads(self.session.answers or "{}")
        return len(answers) >= required

    # --------- Question helpers ---------

    async def _get_question_ids(self) -> list[UUID]:
        """
        Return the list of question IDs for this session.
        """
        question_ids: list[str] = json.loads(self.session.question_ids or "[]")
        return [UUID(qid) for qid in question_ids]

    # async def get_question_by_index(
    #     self,
    #     index: int,
    # ) -> Optional['SessionQuestion']:
    #     """
    #     Return a SessionQuestion wrapper for the given index, or None if out of range.
    #     """
    #     question_ids = await self._get_question_ids()
    #
    #     if index < 0 or index >= len(question_ids):
    #         return None
    #
    #     qid = question_ids[index]
    #     question_obj = await QuestionRedis.get(qid)
    #     # Assuming choices is stored as JSON string
    #     question_obj.choices = json.loads(question_obj.choices)
    #     return SessionQuestion(service=self, index=index, question=question_obj)

    # async def get_question(self) -> Optional['SessionQuestion']:
    #     """
    #     Get object to work with questions in this session.
    #     """
    #     question_ids = await self._get_question_ids()
    #     index = self.session.current_question_index
    #
    #     if index < 0 or index >= len(question_ids):
    #         return None
    #
    #     qid = question_ids[index]
    #     question_obj = await QuestionRedis.get(qid)
    #     # Assuming choices is stored as JSON string
    #     question_obj.choices = json.loads(question_obj.choices)
    #     return SessionQuestion(service=self, index=index, question=question_obj)

    async def finish(self) -> Session:
        """
        Finish this session: compute score and persist final state.
        """
        session = self.session

        if session.status in (SessionStatus.FINISHED, SessionStatus.FINISHED.value):
            # Already finished; you can also raise if you prefer.
            return session

        if session.questions_remaining > 0 and not self.is_required_complete():
            raise ValueError(
                "Cannot finish: required questions are not all answered yet "
                f"({getattr(session, 'required_count', 0)} required)."
            )

        session.status = SessionStatus.FINISHED
        time_finish = datetime.now(timezone.utc)
        time_start = session.time_start or time_finish
        if time_start.tzinfo is None:
            time_start = time_start.replace(tzinfo=timezone.utc)
        session.time_finish = time_finish
        session.duration = int((time_finish - time_start).total_seconds())

        question_ids = await self._get_question_ids()
        # Load questions from Redis
        questions = [await QuestionRedis.get(qid) for qid in question_ids]

        score = self._score_session(session, question_ids, questions)
        session.score = score
        await session.save()
        return session

    async def close(self) -> Session:
        """
        Close this session without finishing it.
        """
        session = self.session

        if session.status in (SessionStatus.CLOSED, SessionStatus.CLOSED.value):
            return session

        session.status = SessionStatus.CLOSED
        time_finish = datetime.now(timezone.utc)
        time_start = session.time_start or time_finish
        if time_start.tzinfo is None:
            time_start = time_start.replace(tzinfo=timezone.utc)
        session.time_finish = time_finish
        session.duration = int((time_finish - time_start).total_seconds())
        await session.save()
        return session

    # --------- Helpers / properties ---------

    @property
    def id(self) -> UUID:
        return self.session.sid

    # @property
    # def question(self) -> QuestionManager:
    #     """
    #     Accessor for question-related operations.
    #
    #     Usage:
    #         q = await service.question.current()
    #         await q.answer("A")
    #     """
    #     return QuestionManager(self.session)

    @staticmethod
    def _score_session(session: Session, question_ids: List[UUID], questions: List[QuestionRedis]) -> float:
        """
        Calculate session score in percent.

        `question_ids` is this session's own ordering (position -> question_id);
        `QuestionRedis.index` is NOT used here because that record is cached
        globally per-question and may have been written by a different session
        that presented the same bank question at a different position.
        """
        correct_answers = 0
        session_answers = json.loads(session.answers or "{}")
        question_map = {q.question_id: q for q in questions}

        for question_index, answer in session_answers.items():
            try:
                question_id = question_ids[int(question_index)]
            except (ValueError, IndexError):
                continue
            question = question_map.get(question_id)
            if question is None:
                continue
            question_type = getattr(question, "question_type", "single")
            if is_correct_answer(question_type, question.correct_answer, answer):
                correct_answers += 1

        total_questions = len(questions)
        return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0
