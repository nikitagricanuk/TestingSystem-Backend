from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from enum import Enum

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

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
from app.services.question_bank.question_import import QuestionImportError, parse_questions_xml
from app.schemas.tests import (
    TestCreate,
    TestOut,
    TestUpdate,
    TestDelete,
    TestQuestionRuleCreate,
    TestQuestionRuleOut,
)
from app.schemas.question_bank import QuestionCreate, QuestionUpdate, QuestionOut
from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user


router = APIRouter()


def _navigation_method_value(test) -> str:
    nav = getattr(test, "navigation_method", "free")
    return nav.value if hasattr(nav, "value") else str(nav)


def _test_out(test, total_questions: int) -> TestOut:
    created_at = getattr(test, "created_at", None)
    updated_at = getattr(test, "updated_at", None)
    return TestOut(
        id=test.id,
        owner_id=getattr(test, "owner_id", None),
        name=test.name,
        description=getattr(test, "description", None),
        start_date=getattr(test, "start_date", None),
        end_date=getattr(test, "end_date", None),
        number_of_required_questions=getattr(test, "number_of_required_questions", None),
        shuffle=bool(getattr(test, "shuffle", True)),
        navigation_method=_navigation_method_value(test),
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
    mine: bool = Query(False, description="Only tests owned by the current user (for \"Мои тесты\")"),
    current_user: UserFull = Depends(get_current_user),
) -> list[TestOut]:
    owner_id = current_user.id if mine else None
    tests = await TestDAO.list(offset=offset, limit=limit, owner_id=owner_id)
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
            test_data = payload.dict(exclude={"question_ids"})
            test_data["owner_id"] = current_user.id
            test = await TestDAO.create(test_data, session=session)
            await TestDAO.add_questions(test.id, question_ids, session=session)
            await session.commit()
        except QuestionNotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _test_out(test, len(question_ids))


def _assert_can_manage_test(test, current_user: UserFull) -> None:
    # owner_id IS NULL is a legacy/unowned test (predates ownership tracking) —
    # any teacher may manage it rather than permanently orphaning it.
    owner_id = getattr(test, "owner_id", None)
    if owner_id is not None and str(owner_id) != str(current_user.id) and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Test not available")


@router.patch("/tests/{test_id}", response_model=TestOut)
async def update_test(
    test_id: UUID,
    payload: TestUpdate,
    current_user: UserFull = Depends(get_current_user),
) -> TestOut:
    data = payload.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided")
    _validate_test_dates(data.get("start_date"), data.get("end_date"))
    async with async_session_maker() as session:
        test = await TestDAO.get(test_id, session=session)
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        _assert_can_manage_test(test, current_user)
        if "number_of_required_questions" in data:
            total_questions = len(await TestDAO.list_questions(test_id, session=session))
            _validate_required_questions(data.get("number_of_required_questions"), total_questions)
        updated = await TestDAO.update(test_id, data, session=session)
        questions = await TestDAO.list_questions(test_id, session=session)
        await session.commit()
        await session.refresh(updated)
        return _test_out(updated, len(questions))


@router.delete("/tests/{test_id}", response_model=TestDelete)
async def delete_test(test_id: UUID, current_user: UserFull = Depends(get_current_user)) -> TestDelete:
    async with async_session_maker() as session:
        test = await TestDAO.get(test_id, session=session)
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        _assert_can_manage_test(test, current_user)
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
                    category = await CategoryDAO.get_or_create_path(
                        category_path, owner_id=current_user.id, session=session
                    )
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


def _rule_out(rule) -> TestQuestionRuleOut:
    return TestQuestionRuleOut(
        id=rule.id,
        test_id=rule.test_id,
        category_id=rule.category_id,
        is_mandatory=rule.is_mandatory,
        fixed_position=rule.fixed_position,
    )


@router.get("/tests/{test_id}/rules", response_model=list[TestQuestionRuleOut])
async def list_test_question_rules(test_id: UUID) -> list[TestQuestionRuleOut]:
    test = await TestDAO.get(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    rules = await TestDAO.list_rules(test_id)
    return [_rule_out(rule) for rule in rules]


@router.post("/tests/{test_id}/rules", response_model=TestQuestionRuleOut, status_code=status.HTTP_201_CREATED)
async def create_test_question_rule(
    test_id: UUID,
    payload: TestQuestionRuleCreate,
    current_user: UserFull = Depends(get_current_user),
) -> TestQuestionRuleOut:
    test = await TestDAO.get(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    try:
        category = await CategoryDAO.get(payload.category_id)
    except CategoryNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if category.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Category not available")

    rule = await TestDAO.add_rule(
        test_id,
        payload.category_id,
        is_mandatory=payload.is_mandatory,
        fixed_position=payload.fixed_position,
    )
    return _rule_out(rule)


@router.delete("/tests/{test_id}/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_question_rule(
    test_id: UUID,
    rule_id: UUID,
    current_user: UserFull = Depends(get_current_user),
):
    rules = await TestDAO.list_rules(test_id)
    rule = next((r for r in rules if r.id == rule_id), None)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    try:
        category = await CategoryDAO.get(rule.category_id)
    except CategoryNotFound:
        category = None
    if category is not None and category.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rule not available")
    await TestDAO.remove_rule(rule_id)


class UploadMode(str, Enum):
    APPEND = "append"
    OVERWRITE = "overwrite"


@router.put("/tests/{test_id}/question/upload", response_model=list[QuestionOut])
async def upload_test_questions(
    test_id: UUID,
    file: UploadFile = File(...),
    mode: UploadMode = Query(UploadMode.APPEND),
    current_user: UserFull = Depends(get_current_user),
) -> list[QuestionOut]:
    """
    Bulk-import questions from an XML document (see
    app.services.question_bank.question_import for the format: one <question>
    element per question, LaTeX-formatted choices via this school's
    \\begin{multi}...\\end{multi} convention). mode=overwrite first deletes this
    teacher's existing questions in every category the upload touches.
    """
    test = await TestDAO.get(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    raw = await file.read()
    try:
        parsed_questions = parse_questions_xml(raw)
    except QuestionImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    async with async_session_maker() as session:
        try:
            category_ids: list[UUID] = []
            for parsed in parsed_questions:
                category = await CategoryDAO.get_or_create_path(
                    parsed.category_path, owner_id=current_user.id, session=session
                )
                category_ids.append(category.id)

            if mode == UploadMode.OVERWRITE:
                for category_id in set(category_ids):
                    existing = await QuestionDAO.list_by_category(
                        category_id, include_descendants=False, teacher_id=current_user.id, session=session
                    )
                    for question in existing:
                        await QuestionDAO.delete(question.id, session=session)

            created: list[QuestionOut] = []
            for parsed, category_id in zip(parsed_questions, category_ids):
                question = await QuestionDAO.add_question(
                    {
                        "text": parsed.text,
                        "problem": parsed.problem,
                        "answer": parsed.answer,
                        "question_type": parsed.question_type,
                        "mark_out_of": parsed.mark_out_of,
                        "penalty": parsed.penalty,
                        "category_id": category_id,
                        "teacher_id": current_user.id,
                        "is_active": True,
                    },
                    session=session,
                )
                await TestDAO.add_questions(test_id, [question.id], session=session)
                created.append(_question_out(question))

            await session.commit()
        except (CategoryCreateError, QuestionCreateError) as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return created
