from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.databases import async_session_maker
from app.repositories.dao.testdao import TestDAO
from app.repositories.question_bank.question_dao import QuestionDAO, CategoryDAO
from app.repositories.question_bank.exceptions import (
    QuestionNotFoundError,
    QuestionCreateError,
    QuestionUpdateError,
    QuestionDeleteError,
    CategoryNotFound,
    CategoryCreateError,
)
from app.schemas.tests import TestCreate, TestOut, TestUpdate, TestDelete
from app.schemas.question_bank import QuestionCreate, QuestionUpdate, QuestionOut
from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user


router = APIRouter()


def _test_out(test, total_questions: int) -> TestOut:
    created_at = getattr(test, "created_at", None)
    updated_at = getattr(test, "updated_at", None)
    return TestOut(
        id=test.id,
        name=test.name,
        description=getattr(test, "description", None),
        start_date=getattr(test, "start_date", None),
        end_date=getattr(test, "end_date", None),
        number_of_required_questions=getattr(test, "number_of_required_questions", None),
        shuffle=bool(getattr(test, "shuffle", True)),
        navigation_method=str(getattr(test, "navigation_method", "free")),
        can_be_reviewed=getattr(test, "can_be_reviewed", None),
        welcome_message=getattr(test, "welcome_message", None),
        config=getattr(test, "config", None),
        created_at=created_at,
        created_at_unix=int(created_at.timestamp()) if created_at else None,
        updated_at=updated_at,
        updated_at_unix=int(updated_at.timestamp()) if updated_at else None,
        total_questions=total_questions,
    )


def _question_out(question) -> QuestionOut:
    question_type = question.question_type
    if hasattr(question_type, "value"):
        question_type = question_type.value
    return QuestionOut(
        id=question.id,
        text=question.text,
        answer=question.answer,
        category_id=question.category_id,
        teacher_id=question.teacher_id,
        question_type=str(question_type),
        problem=question.problem,
        mark_out_of=question.mark_out_of,
        penalty=question.penalty,
        is_active=bool(question.is_active),
    )


def _validate_test_dates(start_date: datetime | None, end_date: datetime | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")


def _validate_required_questions(required: int | None, total: int) -> None:
    if required is not None and required > total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="number_of_required_questions must be <= total_questions",
        )


@router.get("/tests", response_model=list[TestOut])
async def list_tests(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[TestOut]:
    tests = await TestDAO.list(offset=offset, limit=limit)
    results: list[TestOut] = []
    for test in tests:
        questions = await TestDAO.list_questions(test.id)
        results.append(_test_out(test, len(questions)))
    return results


@router.get("/tests/{test_id}", response_model=TestOut)
async def get_test(test_id: UUID) -> TestOut:
    test = await TestDAO.get(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    questions = await TestDAO.list_questions(test_id)
    return _test_out(test, len(questions))


@router.post("/tests/create", response_model=TestOut, status_code=status.HTTP_201_CREATED)
async def create_test(
    payload: TestCreate,
    current_user: UserFull = Depends(get_current_user),
) -> TestOut:
    _validate_test_dates(payload.start_date, payload.end_date)
    question_ids = payload.question_ids or []
    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate question_ids are not allowed")
    _validate_required_questions(payload.number_of_required_questions, len(question_ids))

    async with async_session_maker() as session:
        try:
            for question_id in question_ids:
                await QuestionDAO.get(question_id, session=session)
            test = await TestDAO.create(payload.dict(exclude={"question_ids"}), session=session)
            await TestDAO.add_questions(test.id, question_ids, session=session)
            await session.commit()
        except QuestionNotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _test_out(test, len(question_ids))


@router.patch("/tests/{test_id}", response_model=TestOut)
async def update_test(
    test_id: UUID,
    payload: TestUpdate,
) -> TestOut:
    data = payload.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided")
    _validate_test_dates(data.get("start_date"), data.get("end_date"))
    async with async_session_maker() as session:
        test = await TestDAO.get(test_id, session=session)
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        if "number_of_required_questions" in data:
            total_questions = len(await TestDAO.list_questions(test_id, session=session))
            _validate_required_questions(data.get("number_of_required_questions"), total_questions)
        updated = await TestDAO.update(test_id, data, session=session)
        await session.commit()
    questions = await TestDAO.list_questions(test_id)
    return _test_out(updated, len(questions))


@router.delete("/tests/{test_id}", response_model=TestDelete)
async def delete_test(test_id: UUID) -> TestDelete:
    async with async_session_maker() as session:
        test = await TestDAO.get(test_id, session=session)
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        await TestDAO.delete(test_id, session=session)
        await session.commit()
    deleted_at = datetime.now(timezone.utc)
    return TestDelete(
        id=test_id,
        name=getattr(test, "name", None),
        deleted_at=deleted_at,
        deleted_at_unix=int(deleted_at.timestamp()),
    )


@router.get("/tests/{test_id}/question/list", response_model=list[QuestionOut])
async def list_test_questions(test_id: UUID) -> list[QuestionOut]:
    test = await TestDAO.get(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    test_questions = await TestDAO.list_questions(test_id)
    async with async_session_maker() as session:
        questions = []
        for test_question in test_questions:
            question = await QuestionDAO.get(test_question.question_id, session=session)
            questions.append(_question_out(question))
    return questions


@router.get("/tests/{test_id}/question/{question_id}", response_model=QuestionOut)
async def get_test_question(test_id: UUID, question_id: UUID) -> QuestionOut:
    test_question = await TestDAO.get_question(test_id, question_id)
    if not test_question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    async with async_session_maker() as session:
        question = await QuestionDAO.get(question_id, session=session)
    return _question_out(question)


@router.post("/tests/{test_id}/question/create", response_model=QuestionOut)
async def create_test_question(
    test_id: UUID,
    payload: QuestionCreate,
    current_user: UserFull = Depends(get_current_user),
) -> QuestionOut:
    async with async_session_maker() as session:
        test = await TestDAO.get(test_id, session=session)
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        data = payload.dict(exclude_unset=True)
        category_id = data.pop("category_id", None)
        category_path = data.pop("category_path", None)
        if category_id is None and category_path:
            try:
                category = await CategoryDAO.get_or_create_path(category_path, session=session)
            except CategoryCreateError as exc:
                await session.rollback()
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            category_id = category.id
        if category_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="category_id or category_path is required")
        data["category_id"] = category_id
        data["teacher_id"] = current_user.id
        try:
            question = await QuestionDAO.add_question(data, session=session)
            await TestDAO.add_questions(test_id, [question.id], session=session)
            await session.commit()
        except QuestionCreateError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _question_out(question)


@router.patch("/tests/{test_id}/question/{question_id}", response_model=QuestionOut)
async def update_test_question(
    test_id: UUID,
    question_id: UUID,
    payload: QuestionUpdate,
    current_user: UserFull = Depends(get_current_user),
) -> QuestionOut:
    data = payload.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided")
    async with async_session_maker() as session:
        test_question = await TestDAO.get_question(test_id, question_id, session=session)
        if not test_question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        if "category_path" in data:
            category_path = data.pop("category_path")
            if category_path:
                try:
                    category = await CategoryDAO.get_or_create_path(category_path, session=session)
                except CategoryCreateError as exc:
                    await session.rollback()
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
                data["category_id"] = category.id
        question = await QuestionDAO.get(question_id, session=session)
        if str(question.teacher_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Question not available")
        try:
            updated = await QuestionDAO.update(question_id, data, session=session)
            await session.commit()
        except QuestionUpdateError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _question_out(updated)


@router.delete("/tests/{test_id}/question/{question_id}", response_model=QuestionOut)
async def delete_test_question(
    test_id: UUID,
    question_id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> QuestionOut:
    async with async_session_maker() as session:
        test_question = await TestDAO.get_question(test_id, question_id, session=session)
        if not test_question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        question = await QuestionDAO.get(question_id, session=session)
        if str(question.teacher_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Question not available")
        try:
            await TestDAO.remove_question(test_id, question_id, session=session)
            await QuestionDAO.delete(question_id, session=session)
            await session.commit()
        except QuestionDeleteError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _question_out(question)


@router.put("/tests/{test_id}/question/upload")
async def upload_test_questions(test_id: UUID):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Upload not implemented")
