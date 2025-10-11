import time
import uuid
from datetime import timezone, datetime
import asyncio # Импорт для асинхронной задержки
from ipaddress import ip_address
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis as AsyncRedis # Используем AsyncRedis
from loguru import logger

from app.core.databases import inject_redis_connection
from app.schemas.sessions import Session
from app.utils.helpers import load_questions_from_json
from app.services.sessions import create_session, get_session

router = APIRouter()

@inject_redis_connection
@router.post("/tests/{test-id}/start")
# Используем AsyncRedis для хинтинга
async def post_tests_test_id_start(redis_client: AsyncRedis, test_id: UUID) -> Session:
    """Start new test session"""
    logger.info("Loading questions from JSON and connecting to Redis...")
    try:
        # Убедитесь, что путь к файлу верен
        question_ids = load_questions_from_json('questions.json', redis_client)

        logger.info("Creating a new test session...")
        # AWAIT асинхронной функции сервиса
        session = await create_session(
            redis_client, # Передаем redis_client первым аргументом из-за декоратора
            user_id=uuid.uuid4(),
            test_id=test_id,
            question_ids=question_ids,
            indefinite_questions=False,
            ip_address="127.0.0.1"
        )
        logger.info(f"Session created with ID: {session.sid} for test {test_id}")
        return Session(sid=session.sid, test_id=session.test_id, user_id=session.user_id,
                       time_start=datetime.now(timezone.utc), time_start_unix=int(datetime.now(timezone.utc).timestamp()),
                       time_finish=None, time_finish_unix=None, duration_seconds=None,
                       indefinite_questions=bool(session.indefinite_questions), ip_address="127.0.0.1",
                       questions_remaining=session.questions_remaining,
                       current_question_index=session.current_question_index,
                       status=session.status, last_activity_unix=int(datetime.now(timezone.utc).timestamp()),
                       total_questions=None, questions_answered=session.questions_answered)
    except Exception as e:
        logger.error(f"Error starting test session {test_id}: {e}", exc_info=True)
        # Используем HTTPException из fastapi
        raise HTTPException(status_code=500, detail=f"Error starting test session {test_id}: {e}")

@inject_redis_connection
@router.get("/tests/sessions")
# Используем AsyncRedis для хинтинга
async def get_tests_sessions(redis_client: AsyncRedis,):
    """Get session list"""
    logger.info("Starting test session creation for session list demonstration.") # INFO

    try:
        # Убедитесь, что путь к файлу верен
        question_ids = load_questions_from_json('questions.json', redis_client)

        logger.info("Creating a new test session...") # INFO
        # AWAIT асинхронной функции сервиса
        session = await create_session(
            redis_client, # Передаем redis_client первым аргументом из-за декоратора
            user_id=uuid.uuid4(),
            test_id=uuid.uuid4(),
            question_ids=question_ids,
            indefinite_questions=False,
            ip_address="127.0.0.1"
        )
        logger.info(f"Test session created with ID: {session.sid}") # INFO


        logger.debug("Verifying data from within the application...") # Проверка данных - DEBUG
        # AWAIT асинхронной функции сервиса
        retrieved_session = await get_session(redis_client, session.sid)
        if retrieved_session:
            logger.info(f"Successfully retrieved session with ID: {retrieved_session.sid}") # INFO
        else:
            logger.warning("Failed to retrieve the session.") # WARNING

        while True:
            await asyncio.sleep(3600) # Асинхронная задержка
    except KeyboardInterrupt:
        logger.info("Application stopped.") # INFO
    except Exception as e:
        logger.error(f"An error occurred in get_tests_sessions: {e}", exc_info=True) # ERROR
    return {
        "status": "not_implemented",
        "operationId": "get_tests_sessions",
        "echo": {}
    }


@inject_redis_connection
@router.get("/tests/session/{session-id}")
async def get_tests_session_session_id(redis_client: AsyncRedis, session_id: UUID):
    """Get session info"""
    # AWAIT асинхронной функции сервиса
    session = await get_session(redis_client, session_id)
    if session:
        # Здесь должна быть логика форматирования и возврата данных сессии
        return session
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/tests/session/{session-id}")
async def delete_tests_session_session_id(session_id: UUID):
    """Cancel session"""
    return {
        "status": "not_implemented",
        "operationId": "delete_tests_session_session_id",
        "echo": {"session-id": session_id}
    }


@router.get("/tests/session/{session-id}/question/list")
async def get_tests_session_session_id_question_list(session_id: UUID):
    """List all questions"""
    return {
        "status": "not_implemented",
        "operationId": "get_tests_session_session_id_question_list",
        "echo": {"session-id": session_id}
    }


@router.get("/tests/session/{session-id}/question/{question-id}")
async def get_tests_session_session_id_question_question_id(session_id: UUID, question_id: UUID):
    """Get question with specified ID"""
    return {
        "status": "not_implemented",
        "operationId": "get_tests_session_session_id_question_question_id",
        "echo": {"session-id": session_id, "question-id": question_id}
    }


@router.get("/tests/session/{session-id}/question/next")
async def get_tests_session_session_id_question_next(session_id: UUID):
    """Get next question in session"""
    return {
        "status": "not_implemented",
        "operationId": "get_tests_session_session_id_question_next",
        "echo": {"session-id": session_id}
    }


@router.get("/tests/session/{session-id}/question/prev")
async def get_tests_session_session_id_question_prev(session_id: UUID):
    """Get previous question in session"""
    return {
        "status": "not_implemented",
        "operationId": "get_tests_session_session_id_question_prev",
        "echo": {"session-id": session_id}
    }


@router.post("/tests/session/{session-id}/question/{question-id}/answer")
async def post_tests_session_session_id_question_question_id_answer(session_id: UUID, question_id: UUID, payload: dict):
    """Submit answer to the question"""
    return {
        "status": "not_implemented",
        "operationId": "post_tests_session_session_id_question_question_id_answer",
        "echo": {"session-id": session_id, "question-id": question_id, "body": payload}
    }


@router.post("/tests/session/{session-id}/submit")
async def post_tests_session_session_id_submit(session_id: UUID):
    """Submit answers and finish the session"""
    return {
        "status": "not_implemented",
        "operationId": "post_tests_session_session_id_submit",
        "echo": {"session-id": session_id}
    }
