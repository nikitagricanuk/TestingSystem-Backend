from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.database import Test, TestQuestion
from app.repositories.dao.testdao import TestDAO
from app.repositories.question_bank.question_dao import CategoryDAO, QuestionDAO


@pytest.mark.asyncio
async def test_create_and_get_test(async_test_session):
    data = {
        "name": "Sample Test",
        "description": "Desc",
        "shuffle": True,
        "navigation_method": "free",
    }

    test = await TestDAO.create(data, session=async_test_session)
    await async_test_session.commit()

    fetched = await TestDAO.get(test.id, session=async_test_session)
    assert fetched is not None
    assert fetched.name == "Sample Test"


@pytest.mark.asyncio
async def test_update_test(async_test_session):
    test = await TestDAO.create({"name": "Old", "shuffle": True}, session=async_test_session)
    await async_test_session.commit()

    updated = await TestDAO.update(test.id, {"name": "New"}, session=async_test_session)
    await async_test_session.commit()

    assert updated.name == "New"


@pytest.mark.asyncio
async def test_delete_test(async_test_session):
    test = await TestDAO.create({"name": "To delete", "shuffle": True}, session=async_test_session)
    await async_test_session.commit()

    deleted = await TestDAO.delete(test.id, session=async_test_session)
    await async_test_session.commit()

    assert deleted is True
    assert await TestDAO.get(test.id, session=async_test_session) is None


@pytest.mark.asyncio
async def test_add_and_list_questions(async_test_session):
    category = await CategoryDAO.create("Math", session=async_test_session)
    await async_test_session.commit()

    question = await QuestionDAO.add_question(
        {
            "text": "2+2",
            "answer": {"correct": 4},
            "category_id": category.id,
            "teacher_id": uuid4(),
            "question_type": "text",
            "problem": "P",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        },
        session=async_test_session,
    )
    await async_test_session.commit()

    test = await TestDAO.create({"name": "With Q", "shuffle": True}, session=async_test_session)
    await async_test_session.commit()

    await TestDAO.add_questions(test.id, [question.id], session=async_test_session)
    await async_test_session.commit()

    test_questions = await TestDAO.list_questions(test.id, session=async_test_session)
    assert len(test_questions) == 1
    assert test_questions[0].question_id == question.id


@pytest.mark.asyncio
async def test_remove_question(async_test_session):
    category = await CategoryDAO.create("Physics", session=async_test_session)
    await async_test_session.commit()

    question = await QuestionDAO.add_question(
        {
            "text": "Q",
            "answer": {"correct": "A"},
            "category_id": category.id,
            "teacher_id": uuid4(),
            "question_type": "text",
            "problem": "P",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        },
        session=async_test_session,
    )
    await async_test_session.commit()

    test = await TestDAO.create({"name": "Test", "shuffle": True}, session=async_test_session)
    await async_test_session.commit()

    await TestDAO.add_questions(test.id, [question.id], session=async_test_session)
    await async_test_session.commit()

    removed = await TestDAO.remove_question(test.id, question.id, session=async_test_session)
    await async_test_session.commit()

    assert removed is True
    assert await TestDAO.get_question(test.id, question.id, session=async_test_session) is None
