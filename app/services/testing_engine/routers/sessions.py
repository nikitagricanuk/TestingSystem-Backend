import uuid
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException

from ..schemas.sessions import Session
from app.utils.helpers import load_questions_from_json
from ..session_service import SessionService
from app.core.log import setup_logger


router = APIRouter()

logger = setup_logger(__name__)

def serialize_session_question(session_question):
    """
    Convert a SessionQuestion-like object into a JSON-serializable dict.
    Expects an object with `.index` and `.question` attributes.
    """
    q = session_question.question
    # Try to get a dict representation from the underlying question model
    if hasattr(q, "dict"):
        data = q.dict()
    else:
        data = q.__dict__.copy()

    # Ensure id is a string where possible
    if "id" in data:
        try:
            data["id"] = str(data["id"])
        except Exception:
            pass

    return {
        "index": session_question.index,
        "question": data,
    }

@router.post("/tests/{test_id}/start")
async def create_session(test_id: UUID, request: Request) -> Session:
    """Start new test session"""
    mock_uid = UUID('20bf9faa-5399-4747-90c1-3bad4e8d4afc')
    questions = load_questions_from_json() # Mock loading questions

    question_ids = [qid for qid in (q.id for q in questions)]

    session = await SessionService.create(
        user_id=mock_uid,
        test_id=test_id,
        question_ids=question_ids,
        indefinite_questions=False,
        ip_address=request.client.host
    )
    logger.debug(f"Created new session with ID: {session.session.sid}")
    return await session.get()


@router.get("/tests/sessions")
async def get_session_list():
    """Get session list"""

    return {
        "status": "not_implemented",
        "operationId": "get_tests_sessions",
        "echo": {}
    }


@router.get("/tests/session/{session-id}")
async def get_tests_session_session_id(session_id: UUID):
    """Get session info"""
    session = await SessionService.load(str(session_id))
    if session is None:
        return HTTPException(status_code=404, detail="Session not found")

    return await session.get()


@router.delete("/tests/session/{session-id}")
async def delete_tests_session_session_id(session_id: UUID):
    """Cancel session"""
    session = await SessionService.load(str(session_id))
    if session is None:
        return HTTPException(status_code=404, detail="Session not found")

    await session.close()
    return None


@router.get("/tests/session/{session-id}/question/list")
async def get_tests_session_session_id_question_list(session_id: UUID):
    """List all questions"""
    session = await SessionService.load(str(session_id))
    if session is None:
        return HTTPException(status_code=404, detail="Session not found")

    question = session.question
    questions = await question.list()
    return questions


@router.get("/tests/session/{session-id}/question/{question-id}")
async def get_tests_session_session_id_question_question_id(session_id: UUID, question_id: UUID):
    """Get question with specified ID"""
    session_service = await SessionService.load(str(session_id))
    if session_service is None:
        return {
            "status": "error",
            "message": "Session not found",
            "operationId": "get_tests_session_session_id_question_question_id",
            "echo": {"session-id": session_id, "question-id": question_id}
        }

    question_ids = await session_service._get_question_ids()  # type: ignore[attr-defined]
    qid_str = str(question_id)
    try:
        index = question_ids.index(qid_str)
    except ValueError:
        return {
            "status": "error",
            "message": "Question not found in this session",
            "operationId": "get_tests_session_session_id_question_question_id",
            "echo": {"session-id": session_id, "question-id": question_id}
        }

    sq = await session_service.get_question_by_index(index)  # type: ignore[attr-defined]
    if sq is None:
        return {
            "status": "error",
            "message": "Question not found",
            "operationId": "get_tests_session_session_id_question_question_id",
            "echo": {"session-id": session_id, "question-id": question_id}
        }

    return {
        "status": "ok",
        "operationId": "get_tests_session_session_id_question_question_id",
        "echo": {"session-id": session_id, "question-id": question_id},
        "data": serialize_session_question(sq),
    }


@router.get("/tests/session/{session-id}/question/next")
async def get_tests_session_session_id_question_next(session_id: UUID):
    """Get next question in session"""
    session_service = await SessionService.load(str(session_id))
    if session_service is None:
        return {
            "status": "error",
            "message": "Session not found",
            "operationId": "get_tests_session_session_id_question_next",
            "echo": {"session-id": session_id}
        }

    current = await session_service.get_current_question()
    if current is None:
        return {
            "status": "error",
            "message": "No current question for this session",
            "operationId": "get_tests_session_session_id_question_next",
            "echo": {"session-id": session_id}
        }

    next_q = await current.next()
    if next_q is None:
        return {
            "status": "error",
            "message": "No next question",
            "operationId": "get_tests_session_session_id_question_next",
            "echo": {"session-id": session_id}
        }

    return {
        "status": "ok",
        "operationId": "get_tests_session_session_id_question_next",
        "echo": {"session-id": session_id},
        "data": serialize_session_question(next_q),
    }


@router.get("/tests/session/{session-id}/question/prev")
async def get_tests_session_session_id_question_prev(session_id: UUID):
    """Get previous question in session"""
    session_service = await SessionService.load(str(session_id))
    if session_service is None:
        return {
            "status": "error",
            "message": "Session not found",
            "operationId": "get_tests_session_session_id_question_prev",
            "echo": {"session-id": session_id}
        }

    current = await session_service.get_current_question()
    if current is None:
        return {
            "status": "error",
            "message": "No current question for this session",
            "operationId": "get_tests_session_session_id_question_prev",
            "echo": {"session-id": session_id}
        }

    prev_q = await current.prev()
    if prev_q is None:
        return {
            "status": "error",
            "message": "No previous question",
            "operationId": "get_tests_session_session_id_question_prev",
            "echo": {"session-id": session_id}
        }

    return {
        "status": "ok",
        "operationId": "get_tests_session_session_id_question_prev",
        "echo": {"session-id": session_id},
        "data": serialize_session_question(prev_q),
    }


@router.post("/tests/session/{session-id}/question/{question-id}/answer")
async def post_tests_session_session_id_question_question_id_answer(
    session_id: UUID,
    question_id: UUID,
    payload: dict,
):
    """Submit answer to the question"""
    session_service = await SessionService.load(str(session_id))
    if session_service is None:
        return {
            "status": "error",
            "message": "Session not found",
            "operationId": "post_tests_session_session_id_question_question_id_answer",
            "echo": {"session-id": session_id, "question-id": question_id}
        }

    answer = payload.get("answer")
    if answer is None:
        return {
            "status": "error",
            "message": "Missing 'answer' in request body",
            "operationId": "post_tests_session_session_id_question_question_id_answer",
            "echo": {"session-id": session_id, "question-id": question_id, "body": payload}
        }

    question_ids = await session_service._get_question_ids()  # type: ignore[attr-defined]
    qid_str = str(question_id)
    try:
        index = question_ids.index(qid_str)
    except ValueError:
        return {
            "status": "error",
            "message": "Question not found in this session",
            "operationId": "post_tests_session_session_id_question_question_id_answer",
            "echo": {"session-id": session_id, "question-id": question_id, "body": payload}
        }

    # Use the service method to record the answer
    await session_service.answer_current_question(index, answer)

    # Return updated session info
    return await session_service.get()


@router.post("/tests/session/{session-id}/submit")
async def post_tests_session_session_id_submit(session_id: UUID):
    """Submit answers and finish the session"""
    session = await SessionService.load(str(session_id))
    if session is None:
        return {
            "status": "error",
            "message": "Session not found",
            "operationId": "post_tests_session_session_id_submit",
            "echo": {"session-id": session_id}
        }
    await session.finish()
    return None
