import time
import uuid
from datetime import timezone, datetime
from ipaddress import ip_address
from uuid import UUID

from fastapi import APIRouter
from redis.asyncio import Redis

from app.core.databases import init_redis_connection
from app.schemas.sessions import Session
from app.utils.helpers import load_questions_from_json
from app.services.sessions import create_session, get_session

router = APIRouter()

@router.post("/tests/{test-id}/start")
async def post_tests_test_id_start(test_id: UUID) -> Session:
    """Start new test session"""
    print("Loading questions from JSON...")
    # Убедитесь, что путь к файлу верен
    question_ids = load_questions_from_json('questions.json')

    print("Creating a new test session...")
    session = create_session(
        user_id=uuid.uuid4(),
        test_id=uuid.uuid4(),
        question_ids=question_ids,
        indefinite_questions=False,
        ip_address="127.0.0.1"
    )
    print(f"Session created with ID: {session.sid}")
    return Session(sid=session.sid, test_id=session.test_id, user_id=session.user_id,
                   time_start=datetime.now(timezone.utc).isoformat(), time_start_unix=datetime.now(timezone.utc).timestamp(),
                   time_finish=None, time_finish_unix=None, duration_seconds=None,
                   indefinite_questions=session.indefinite_questions, ip_address="127.0.0.1",
                   questions_remaining=session.questions_remaining, current_question_index=session.current_question_index,
                   status=session.status, device_type=session.device_type, last_activity_unix=datetime.now(timezone.utc).timestamp())

@router.get("/tests/sessions")
async def get_tests_sessions():
    """Get session list"""
    # init_redis_connection() больше не нужен здесь
    redis_connection: Redis = init_redis_connection()
    print("Loading questions from JSON...")
    # Убедитесь, что путь к файлу верен
    question_ids = load_questions_from_json('questions.json', redis_connection)

    print("Creating a new test session...")
    session = create_session(
        user_id=uuid.uuid4(),
        test_id=uuid.uuid4(),
        question_ids=question_ids,
        indefinite_questions=False,
        ip_address="127.0.0.1",
        redis_client=redis_connection
    )
    print(f"Session created with ID: {session.sid}")

    try:
        print("Verifying data from within the application...")
        retrieved_session = get_session(session.sid, redis_connection)
        if retrieved_session:
            print(f"Successfully retrieved session with ID: {retrieved_session.sid}")
        else:
            print("Failed to retrieve the session.")

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Application stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
    return {
        "status": "not_implemented",
        "operationId": "get_tests_sessions",
        "echo": {}
    }

@router.get("/tests/session/{session-id}")
async def get_tests_session_session_id(session_id: UUID):
    """Get session info"""
    get_session(session_id=session_id);

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
