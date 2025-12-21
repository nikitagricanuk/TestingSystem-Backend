import json
import uuid
from typing import List, Optional, Self
from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis  # async redis client
from aredis_om import NotFoundError

from app.models.redis import Session, QuestionRedis, SessionStatus


class SessionService:
    """
    Real OOP-style session service:
    - Each instance works with ONE concrete session (self.session).
    - Provides methods to answer questions, finish the session, etc.
    """

    def __init__(self, redis_client: Redis, session: Session) -> None:
        self.redis_client = redis_client

        # Configure models to use this Redis connection
        Session.Meta.database = redis_client
        QuestionRedis.Meta.database = redis_client

        self.session: Session = session

    # --------- Factory methods (OOP constructor helpers) ---------

    @classmethod
    async def create(
        cls,
        redis_client: Redis,
        *,
        user_id: uuid.UUID,
        test_id: uuid.UUID,
        question_ids: List[str],
        indefinite_questions: bool,
        ip_address: str,
    ) -> Self:
        """
        Create a new testing session and wrap it in SessionService.
        """
        if not question_ids:
            raise ValueError("Cannot create a session without questions.")

        Session.Meta.database = redis_client
        QuestionRedis.Meta.database = redis_client

        session = Session(
            sid=str(uuid.uuid4()),
            test_id=test_id,
            user_id=user_id,
            question_ids=json.dumps(question_ids),
            questions_remaining=len(question_ids),
            indefinite_questions=int(indefinite_questions),
            ip_address=ip_address,
            answers=json.dumps({}),
            questions_answered=0,
            current_question_index=0,
            status=SessionStatus.ACTIVE.value,
            time_start=datetime.now(),
            last_activity=datetime.now(),
        )
        await session.save()
        return cls(redis_client, session)

    @classmethod
    async def load(
        cls,
        redis_client: Redis,
        session_id: str,
    ) -> Optional[Self]:
        """
        Load an existing session and wrap it in SessionService.
        """
        Session.Meta.database = redis_client
        QuestionRedis.Meta.database = redis_client

        try:
            session = await Session.get(session_id)
        except NotFoundError:
            return None

        return cls(redis_client, session)

    # --------- Object methods (no session_id argument) ---------

    async def answer_question(
        self,
        question_index: int,
        answer: str,
    ) -> Session:
        """
        Update this session with an answer to a given question index.
        """
        session = self.session

        if session.status != SessionStatus.ACTIVE.value:
            raise ValueError("Cannot answer questions in a non-active session.")

        answers_dict = json.loads(session.answers or "{}")
        answers_dict[str(question_index)] = answer

        session.questions_answered += 1
        session.questions_remaining -= 1
        session.current_question_index += 1
        session.last_activity = datetime.now()
        session.answers = json.dumps(answers_dict)

        await session.save()
        return session

    async def finish(self) -> Session:
        """
        Finish this session: compute score and persist final state.
        """
        session = self.session

        if session.status == SessionStatus.FINISHED.value:
            # Already finished; you can also raise if you prefer.
            return session

        session.status = SessionStatus.FINISHED
        session.time_finish = datetime.now()
        session.duration = int(
            (session.time_finish - session.time_start).total_seconds()
        )

        question_ids = json.loads(session.question_ids)
        # Load questions from Redis
        questions = [await QuestionRedis.get(qid) for qid in question_ids]

        score = self._score_session(session, questions)
        session.score = score
        await session.save()
        return session

    async def get_current_question(self) -> Optional[QuestionRedis]:
        """
        Get the current question for this session.
        """
        session = self.session
        question_ids = json.loads(session.question_ids)

        if session.current_question_index >= len(question_ids):
            return None

        current_qid = question_ids[session.current_question_index]

        question_obj = await QuestionRedis.get(current_qid)
        # Assuming choices is stored as JSON string
        question_obj.choices = json.loads(question_obj.choices)
        return question_obj

    # --------- Helpers / properties ---------

    @property
    def id(self) -> UUID:
        return self.session.sid

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