import json
import uuid
from typing import List, Optional, Self
from datetime import datetime, timezone
from uuid import UUID

from aredis_om import NotFoundError

from .models.redis import Session, QuestionRedis, SessionStatus
from .question_bank.question_bank import QuestionBank, Question
from .schemas.sessions import Session as SessionSchema



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
    ) -> Self:
        """
        Create a new testing session and wrap it in SessionService.
        """
        if not question_ids:
            raise ValueError("Cannot create a session without questions.")

        session = Session(
            sid=str(uuid.uuid4()),
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
            return None

        return cls(session, qb)

    @classmethod
    async def user_sessions(cls, user_id: UUID) -> List[Session]:
        """
        Get all sessions for a given user.
        """
        sessions = await Session.find(Session.user_id == str(user_id)).all()
        return sessions

    # --------- Object methods (no session_id argument) ---------

    async def get_current_question(self) -> Question:
        questions = await self._get_question_ids()
        return await self.qb.get_question(questions[self.session.current_question_index])

    async def get_question_by_index(self, question_index: int) -> Question:
        questions = await self._get_question_ids()
        return await self.qb.get_question(questions[question_index])

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

        # Move pointer to the next question after this one
        session.current_question_index = question_index + 1
        session.last_activity = datetime.now(timezone.utc)
        session.answers = json.dumps(answers_dict)

        await session.save()
        return session

    async def next_question(self) -> Question:
        self.session.current_question_index += 1
        self.session.last_activity = datetime.now(timezone.utc)
        await self.session.save()
        return await self.get_current_question()

    async def prev_question(self) -> Question:
        self.session.current_question_index -= 1
        self.session.last_activity = datetime.now(timezone.utc)
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
            is_submitted=normalized_status == "completed",
            score=score,
            ip_address=self.session.ip_address,
            device_type=getattr(self.session, "device_type", None),
            last_activity_unix=int(self.session.last_activity.replace(tzinfo=timezone.utc).timestamp()),
        )

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

        session.status = SessionStatus.FINISHED
        session.time_finish = datetime.now(timezone.utc)
        session.duration = int(
            (session.time_finish - session.time_start).total_seconds()
        )

        question_ids = await self._get_question_ids()
        # Load questions from Redis
        questions = [await QuestionRedis.get(qid) for qid in question_ids]

        score = self._score_session(session, questions)
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
        session.time_finish = datetime.utcnow()
        session.duration = int(
            (session.time_finish - session.time_start).total_seconds()
        )
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
    def _score_session(session: Session, questions: List[QuestionRedis]) -> float:
        """
        Calculate session score in percent.
        """
        correct_answers = 0
        session_answers = json.loads(session.answers or "{}")
        question_map = {q.index: q.correct_answer for q in questions}

        for question_index, answer in session_answers.items():
            if question_map.get(int(question_index)) == answer:
                correct_answers += 1

        total_questions = len(questions)
        return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0
