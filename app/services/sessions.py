import json
import os
import uuid
import time
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

from redis_om import get_redis_connection, NotFoundError
from redis.asyncio import Redis as AsyncRedis # Используем AsyncRedis
from redis.exceptions import ConnectionError
from redis import Redis
from uuid import UUID

from app.models.redis import TestSession, QuestionRedis, SessionStatus
from app.core.databases import inject_redis_connection

@inject_redis_connection
async def create_session(redis_client: AsyncRedis, user_id: uuid.UUID, test_id: uuid.UUID, question_ids: List[str], indefinite_questions: bool,
                   ip_address: str) -> TestSession:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    if not question_ids:
        logger.error("Attempt to create a session without questions.")
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
    await session.save()
    logger.debug(f"Session object saved to Redis with SID: {session.sid}")
    return session

@inject_redis_connection
async def get_session(redis_client: AsyncRedis, session_id: UUID) -> Optional[TestSession]:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    try:
        return await TestSession.get(session_id)
    except NotFoundError:
        logger.warning(f"Session with sid {session_id} not found.")
        return None
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}", exc_info=True)
        return None

@inject_redis_connection
async def update_session_with_answer(redis_client: AsyncRedis, session_id: str, question_index: int, answer: str) -> Optional[TestSession]:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    # get_session теперь асинхронная и требует await
    session = await get_session(redis_client, session_id)
    if not session or session.status != SessionStatus.ACTIVE.value:
        return None

    answers_dict = json.loads(session.answers)
    answers_dict[str(question_index)] = answer

    session.questions_answered += 1
    session.questions_remaining -= 1
    session.current_question_index += 1
    session.last_activity = datetime.now()
    session.answers = json.dumps(answers_dict)

    await session.save()
    return session


@inject_redis_connection
async def finish_session(redis_client: AsyncRedis, session: TestSession) -> Optional[TestSession]:
    # Явно устанавливаем базу данных перед использованием модели
    TestSession.Meta.database = redis_client
    QuestionRedis.Meta.database = redis_client

    if session.status == SessionStatus.FINISHED.value:
        return None

    session.status = SessionStatus.FINISHED.value
    session.time_finish = datetime.now()
    session.duration = int((session.time_finish - session.time_start).total_seconds())

    question_ids = json.loads(session.question_ids)

    # Получаем вопросы асинхронно
    questions = []
    for qid in question_ids:
        questions.append(await QuestionRedis.get(qid))

    # score_session теперь асинхронная и требует await
    score = await score_session(redis_client, session, questions)
    session.score = score
    await session.save()
    logger.info(f"Session {session.sid} finished. Score: {session.score}")
    return session

@inject_redis_connection
async def score_session(redis_client: AsyncRedis, session: TestSession, questions: List[QuestionRedis]) -> float:
    # Эта функция является чистым вычислением, но помечена как async для согласованности с декоратором.
    correct_answers = 0
    session_answers = json.loads(session.answers)
    question_map = {q.index: q.correct_answer for q in questions}

    for question_index, answer in session_answers.items():
        if question_map.get(int(question_index)) == answer:
            correct_answers += 1

    total_questions = len(questions)
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0

@inject_redis_connection
async def get_current_question(redis_client: AsyncRedis, session: TestSession) -> Optional[QuestionRedis]:
    # Явно устанавливаем базу данных перед использованием модели
    QuestionRedis.Meta.database = redis_client
    question_ids = json.loads(session.question_ids)
    if session.current_question_index >= len(question_ids):
        return None

    current_qid = question_ids[session.current_question_index]

    question_obj = await QuestionRedis.get(current_qid)
    question_obj.choices = json.loads(question_obj.choices)
    return question_obj