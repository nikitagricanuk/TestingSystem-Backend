import json
import os
import uuid
import time
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime

from redis_om import get_redis_connection, NotFoundError
from redis.exceptions import ConnectionError
from redis import Redis
from uuid import UUID

from app.models.redis import TestSession, QuestionRedis, SessionStatus


def create_session(user_id: uuid.UUID, test_id: uuid.UUID, question_ids: List[str], indefinite_questions: bool,
                   ip_address: str, redis_client: Redis) -> TestSession:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    if not question_ids:
        raise ValueError("Cannot create a session without questions.")

    session = TestSession(
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
    )
    session.save()
    return session


def get_session(session_id: UUID, redis_client: Redis) -> Optional[TestSession]:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    try:
        return TestSession.get(session_id)
    except NotFoundError:
        print(f"Session with sid {session_id} not found.")
        return None
    except Exception as e:
        print(f"Error getting session: {e}")
        return None


def update_session_with_answer(session_id: str, question_index: int, answer: str, redis_client: Redis) -> Optional[TestSession]:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    session = get_session(session_id, redis_client)
    if not session or session.status != SessionStatus.ACTIVE.value:
        return None

    answers_dict = json.loads(session.answers)
    answers_dict[str(question_index)] = answer

    session.questions_answered += 1
    session.questions_remaining -= 1
    session.current_question_index += 1
    session.last_activity = datetime.now()
    session.answers = json.dumps(answers_dict)

    session.save()
    return session


def finish_session(session: TestSession, redis_client: Redis) -> Optional[TestSession]:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    QuestionRedis.Meta.database = redis_client
    # УДАЛЯЕМ вызов get_session, так как мы уже получили объект
    if session.status == SessionStatus.FINISHED.value:
        return None

    session.status = SessionStatus.FINISHED.value
    session.time_finish = datetime.now()
    session.duration = int((session.time_finish - session.time_start).total_seconds())

    question_ids = json.loads(session.question_ids)

    # Получаем вопросы, явно устанавливая базу данных
    questions = [QuestionRedis.get(qid) for qid in question_ids]

    score = score_session(session, questions, redis_client)
    session.score = score
    session.save()
    print(f"Session {session.sid} finished. Score: {score}")
    return session


def score_session(session: TestSession, questions: List[QuestionRedis], redis_client: Redis) -> float:
    correct_answers = 0
    session_answers = json.loads(session.answers)
    question_map = {q.index: q.correct_answer for q in questions}

    for question_index, answer in session_answers.items():
        if question_map.get(int(question_index)) == answer:
            correct_answers += 1

    total_questions = len(questions)
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0


def get_current_question(session: TestSession, redis_client: Redis) -> Optional[QuestionRedis]:
    # Явно устанавливаем базу данных перед использованием модели
    QuestionRedis.Meta.database = redis_client
    question_ids = json.loads(session.question_ids)
    if session.current_question_index >= len(question_ids):
        return None

    current_qid = question_ids[session.current_question_index]

    # Получаем вопрос, используя явно установленную базу данных
    question_obj = QuestionRedis.get(current_qid)
    question_obj.choices = json.loads(question_obj.choices)
    return question_obj