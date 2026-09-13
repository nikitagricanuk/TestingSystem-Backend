from uuid import UUID
from datetime import datetime, timezone

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..schemas.sessions import Session, SessionDelete, SessionQuestion
from ..session_service import SessionService
from ..test_question_resolver import resolve_session_question_ids
from app.core.log import setup_logger
from ..question_bank.question_bank import get_qb
from app.models.database import NavigationMethod
from app.repositories.dao.testdao import TestDAO
from app.services.auth.routers.auth import get_current_user
from app.schemas.users import UserFull


router = APIRouter()

logger = setup_logger(__name__)

class AnswerPayload(BaseModel):
    answer: str


async def _load_user_session(sid: UUID, current_user: UserFull) -> SessionService | None:
    qb = get_qb()
    try:
        loaded = await SessionService.load(str(sid), qb)
        if loaded and str(loaded.session.user_id) == str(current_user.id):
            return loaded
    except Exception:
        loaded = None

    sessions = await SessionService.user_sessions(current_user.id)
    for session in sessions:
        if str(session.sid) == str(sid):
            return SessionService(session, qb)
    return None


def _question_text(question: object) -> str:
    for attr in ("content", "question"):
        value = getattr(question, attr, None)
        if isinstance(value, str):
            return value
    return str(question)


def _question_choices(question: object) -> list[str]:
    raw = getattr(question, "choices", None)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _question_status(answers: dict[str, str], index: int) -> str:
    return "answered" if str(index) in answers else "unanswered"


def _question_type(question: object) -> str | None:
    value = getattr(question, "question_type", None)
    return value if isinstance(value, str) else None


def _is_linear(session_service: SessionService) -> bool:
    return getattr(session_service.session, "navigation_method", "free") == NavigationMethod.LINEAR.value


@router.post("/tests/{testId}/start", response_model=Session, status_code=status.HTTP_201_CREATED)
async def create_session(
    testId: UUID,
    request: Request,
    current_user: UserFull = Depends(get_current_user),
) -> Session:
    """Start new test session"""
    test = await TestDAO.get(testId)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    resolved = await resolve_session_question_ids(test)
    if not resolved.question_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test has no questions")

    required_count = max(test.number_of_required_questions or 0, resolved.required_count)
    navigation_method = test.navigation_method
    if hasattr(navigation_method, "value"):
        navigation_method = navigation_method.value

    session = await SessionService.create(
        user_id=current_user.id,
        test_id=testId,
        question_ids=resolved.question_ids,
        indefinite_questions=False,
        ip_address=request.client.host,
        device_type=request.headers.get("User-Agent"),
        qb=get_qb(),
        required_count=required_count,
        navigation_method=str(navigation_method or "free"),
    )
    logger.debug(f"Created new session with ID: {session.session.sid}")
    return await session.get()


@router.get("/tests/session/list", response_model=list[Session])
async def get_session_list(current_user: UserFull = Depends(get_current_user)):
    """Get session list"""
    qb = get_qb()
    sessions = await SessionService.user_sessions(current_user.id)
    return [await SessionService(session, qb).get() for session in sessions]


@router.get("/tests/session/{sid}", response_model=Session)
async def get_tests_session_session_id(sid: UUID, current_user: UserFull = Depends(get_current_user)):
    """Get session info"""
    session = await _load_user_session(sid, current_user)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return await session.get()


@router.delete("/tests/session/{sid}", response_model=SessionDelete)
async def delete_tests_session_session_id(sid: UUID, current_user: UserFull = Depends(get_current_user)):
    """Cancel session"""
    session = await _load_user_session(sid, current_user)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    closed = await session.close()
    deleted_at = closed.time_finish
    deleted_at_unix = int(deleted_at.timestamp()) if deleted_at else None
    return SessionDelete(
        sid=closed.sid,
        deleted_at=deleted_at,
        deleted_at_unix=deleted_at_unix,
    )


@router.get("/tests/session/{sid}/question/list", response_model=list[SessionQuestion])
async def get_tests_session_session_id_question_list(
    sid: UUID,
    current_user: UserFull = Depends(get_current_user),
):
    """List all questions"""
    session_service = await _load_user_session(sid, current_user)
    if session_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    question_ids = await session_service._get_question_ids()  # type: ignore[attr-defined]
    answers = json.loads(session_service.session.answers or "{}")
    questions: list[SessionQuestion] = []

    for index, question_id in enumerate(question_ids):
        question = await session_service.get_question_by_index(index)
        questions.append(
            SessionQuestion(
                index=index,
                question_id=question_id,
                question=_question_text(question),
                question_type=_question_type(question),
                choices=_question_choices(question),
                status=_question_status(answers, index),
            )
        )

    return questions


@router.get("/tests/session/{sid}/question/next", response_model=SessionQuestion)
async def get_tests_session_session_id_question_next(
    sid: UUID,
    current_user: UserFull = Depends(get_current_user),
):
    """Get next question in session"""
    session_service = await _load_user_session(sid, current_user)
    if session_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    question_ids = await session_service._get_question_ids()  # type: ignore[attr-defined]
    current_index = session_service.session.current_question_index
    next_index = current_index + 1
    if next_index >= len(question_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No next question")

    now = datetime.now(timezone.utc)
    session_service.accumulate_time_for_question(current_index, now)
    session_service.session.current_question_index = next_index
    session_service.session.last_activity = now
    await session_service.session.save()

    question = await session_service.get_question_by_index(next_index)
    answers = json.loads(session_service.session.answers or "{}")
    return SessionQuestion(
        index=next_index,
        question_id=question_ids[next_index],
        question=_question_text(question),
        question_type=_question_type(question),
        choices=_question_choices(question),
        status=_question_status(answers, next_index),
    )


@router.get("/tests/session/{sid}/question/prev", response_model=SessionQuestion)
async def get_tests_session_session_id_question_prev(
    sid: UUID,
    current_user: UserFull = Depends(get_current_user),
):
    """Get previous question in session"""
    session_service = await _load_user_session(sid, current_user)
    if session_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if _is_linear(session_service):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This test uses linear navigation: you cannot go back to a previous question",
        )

    current_index = session_service.session.current_question_index
    prev_index = current_index - 1
    if prev_index < 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No previous question")

    now = datetime.now(timezone.utc)
    session_service.accumulate_time_for_question(current_index, now)
    session_service.session.current_question_index = prev_index
    session_service.session.last_activity = now
    await session_service.session.save()

    question = await session_service.get_question_by_index(prev_index)
    answers = json.loads(session_service.session.answers or "{}")
    return SessionQuestion(
        index=prev_index,
        question_id=getattr(question, "question_id", None),
        question=_question_text(question),
        question_type=_question_type(question),
        choices=_question_choices(question),
        status=_question_status(answers, prev_index),
    )


@router.get("/tests/session/{sid}/question/{question_id}", response_model=SessionQuestion)
async def get_tests_session_session_id_question_question_id(
    sid: UUID,
    question_id: UUID,
    current_user: UserFull = Depends(get_current_user),
):
    """Get question with specified ID"""
    session_service = await _load_user_session(sid, current_user)
    if session_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    question_ids = await session_service._get_question_ids()  # type: ignore[attr-defined]
    try:
        index = question_ids.index(question_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found") from exc

    if _is_linear(session_service) and index != session_service.session.current_question_index:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This test uses linear navigation: you can only view the current question",
        )

    question = await session_service.get_question_by_index(index)
    answers = json.loads(session_service.session.answers or "{}")
    return SessionQuestion(
        index=index,
        question_id=question_id,
        question=_question_text(question),
        question_type=_question_type(question),
        choices=_question_choices(question),
        status=_question_status(answers, index),
    )


@router.post("/tests/session/{sid}/question/{question_id}/answer", response_model=Session)
async def post_tests_session_session_id_question_question_id_answer(
    sid: UUID,
    question_id: UUID,
    payload: AnswerPayload = Body(...),
    current_user: UserFull = Depends(get_current_user),
):
    """Submit answer to the question"""
    session_service = await _load_user_session(sid, current_user)
    if session_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    question_ids = await session_service._get_question_ids()  # type: ignore[attr-defined]
    try:
        index = question_ids.index(question_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found") from exc

    if _is_linear(session_service) and index != session_service.session.current_question_index:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This test uses linear navigation: you can only answer the current question",
        )

    # Use the service method to record the answer
    await session_service.answer_current_question(index, payload.answer)

    # Return updated session info
    return await session_service.get()


@router.post("/tests/session/{sid}/submit", response_model=Session)
async def post_tests_session_session_id_submit(
    sid: UUID,
    current_user: UserFull = Depends(get_current_user),
):
    """Submit answers and finish the session"""
    session = await _load_user_session(sid, current_user)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    try:
        await session.finish()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return await session.get()
