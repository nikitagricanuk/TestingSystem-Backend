from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.databases import async_session_maker
from app.repositories.question_bank.exceptions import (
    CategoryNotFound,
    QuestionNotFoundError,
    QuestionCreateError,
    QuestionUpdateError,
    QuestionDeleteError,
    CategoryCreateError,
    CategoryUpdateError,
    CategoryDeleteError,
)
from app.repositories.question_bank.question_dao import QuestionDAO, CategoryDAO
from app.schemas.question_bank import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
)
from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user


router = APIRouter()


def _category_out(category) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        name=category.category,
        parent_id=category.parent_id,
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


def _question_type_matches(question, expected: str) -> bool:
    question_type = question.question_type
    if hasattr(question_type, "value"):
        return question_type.value == expected
    return str(question_type) == expected


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    current_user: UserFull = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[CategoryOut]:
    categories = await CategoryDAO.list(owner_id=current_user.id, offset=offset, limit=limit)
    return [_category_out(category) for category in categories]


@router.get("/categories/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> CategoryOut:
    try:
        category = await CategoryDAO.get(category_id)
    except CategoryNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if category.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Category not available")
    return _category_out(category)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    current_user: UserFull = Depends(get_current_user),
) -> CategoryOut:
    async with async_session_maker() as session:
        try:
            category = await CategoryDAO.create(
                payload.name,
                owner_id=current_user.id,
                parent_id=payload.parent_id,
                session=session,
            )
            await session.commit()
        except CategoryCreateError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _category_out(category)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    current_user: UserFull = Depends(get_current_user),
) -> CategoryOut:
    if payload.name is None and payload.parent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided")
    async with async_session_maker() as session:
        try:
            existing = await CategoryDAO.get(category_id, session=session)
        except CategoryNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if existing.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Category not available")
        try:
            category = await CategoryDAO.update(
                category_id,
                new_name=payload.name,
                parent_id=payload.parent_id,
                session=session,
            )
            await session.commit()
        except CategoryNotFound as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except CategoryUpdateError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _category_out(category)


@router.delete("/categories/{category_id}", response_model=CategoryOut)
async def delete_category(
    category_id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> CategoryOut:
    async with async_session_maker() as session:
        try:
            category = await CategoryDAO.get(category_id, session=session)
        except CategoryNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if category.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Category not available")
        try:
            await CategoryDAO.delete(category_id, session=session)
            await session.commit()
        except CategoryNotFound as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except CategoryDeleteError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _category_out(category)


@router.get("/questions", response_model=list[QuestionOut])
async def list_questions(
    current_user: UserFull = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category_id: UUID | None = None,
    category_path: list[str] | None = Query(None),
    include_descendants: bool = False,
    question_type: str | None = None,
    mark_out_of: int | None = None,
    is_active: bool | None = None,
) -> list[QuestionOut]:
    questions = []
    category_filter_id = category_id
    if category_filter_id is None and category_path:
        try:
            category = await CategoryDAO.get_by_path(category_path, owner_id=current_user.id)
        except CategoryNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        category_filter_id = category.id

    if category_filter_id is not None and include_descendants:
        questions = await QuestionDAO.list_by_category(
            category_filter_id,
            include_descendants=True,
            teacher_id=current_user.id,
        )
        if question_type is not None:
            questions = [q for q in questions if _question_type_matches(q, question_type)]
        if mark_out_of is not None:
            questions = [q for q in questions if q.mark_out_of == mark_out_of]
        if is_active is not None:
            questions = [q for q in questions if bool(q.is_active) == is_active]
    elif category_filter_id is not None:
        questions = await QuestionDAO.list_by_category(
            category_filter_id,
            include_descendants=False,
            teacher_id=current_user.id,
        )
        if question_type is not None:
            questions = [q for q in questions if _question_type_matches(q, question_type)]
        if mark_out_of is not None:
            questions = [q for q in questions if q.mark_out_of == mark_out_of]
        if is_active is not None:
            questions = [q for q in questions if bool(q.is_active) == is_active]
    else:
        filters: dict[str, Any] = {"teacher_id": current_user.id}
        if question_type is not None:
            filters["question_type"] = question_type
        if mark_out_of is not None:
            filters["mark_out_of"] = mark_out_of
        if is_active is not None:
            filters["is_active"] = is_active
        questions = await QuestionDAO.search(**filters)

    sliced = questions[offset:offset + limit]
    return [_question_out(question) for question in sliced]


@router.get("/questions/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> QuestionOut:
    try:
        question = await QuestionDAO.get(question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if str(question.teacher_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Question not available")
    return _question_out(question)


@router.post("/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionCreate,
    current_user: UserFull = Depends(get_current_user),
) -> QuestionOut:
    data = payload.dict(exclude_unset=True)
    category_id = data.pop("category_id", None)
    category_path = data.pop("category_path", None)
    async with async_session_maker() as session:
        if category_id is None and category_path:
            try:
                category = await CategoryDAO.get_or_create_path(
                    category_path, owner_id=current_user.id, session=session
                )
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
            await session.commit()
        except QuestionCreateError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _question_out(question)


@router.patch("/questions/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: UUID,
    payload: QuestionUpdate,
    current_user: UserFull = Depends(get_current_user),
) -> QuestionOut:
    data = payload.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided")
    async with async_session_maker() as session:
        if "category_path" in data:
            category_path = data.pop("category_path")
            if category_path:
                try:
                    category = await CategoryDAO.get_or_create_path(
                        category_path, owner_id=current_user.id, session=session
                    )
                except CategoryCreateError as exc:
                    await session.rollback()
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
                data["category_id"] = category.id
        try:
            question = await QuestionDAO.get(question_id, session=session)
        except QuestionNotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if str(question.teacher_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Question not available")
        try:
            updated = await QuestionDAO.update(question_id, data, session=session)
            await session.commit()
        except QuestionUpdateError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _question_out(updated)


@router.delete("/questions/{question_id}", response_model=QuestionOut)
async def delete_question(
    question_id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> QuestionOut:
    async with async_session_maker() as session:
        try:
            question = await QuestionDAO.get(question_id, session=session)
        except QuestionNotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if str(question.teacher_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Question not available")
        try:
            await QuestionDAO.delete(question_id, session=session)
            await session.commit()
        except QuestionDeleteError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _question_out(question)
