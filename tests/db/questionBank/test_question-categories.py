import os
os.environ["TESTING"] = "1"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["DB_NAME"] = "test"
os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"

from uuid import UUID, uuid4
import pytest
from unittest.mock import patch

from app.repositories.question_bank.models import Category, Question
from app.repositories.question_bank.question_dao import CategoryDAO, QuestionDAO
from app.repositories.question_bank.exceptions import (
    CategoryNotFound,
    CategoryCreateError,
    CategoryUpdateError,
    CategoryDeleteError,
    CategoryDAOError,
    QuestionNotFoundError,
    QuestionCreateError,
    QuestionUpdateError,
    QuestionDeleteError
)
from app.core.config import Settings

@pytest.fixture(autouse=True)
def patch_settings():
    with patch("app.core.config.Settings") as MockSettings:
        MockSettings.return_value = Settings(
            db_host="localhost",
            db_port=5432,
            db_name="test",
            db_user="test",
            db_password="test"
        )
        yield

@pytest.mark.asyncio
async def test_category_crud(async_test_session):
    #Create
    category = await CategoryDAO.create("Math", session=async_test_session)
    await async_test_session.commit()
    category_id = category.id
    assert isinstance(category_id, UUID)

    #Attempt to duplicate a category
    with pytest.raises(CategoryCreateError):
        await CategoryDAO.create("Math", session=async_test_session)
    await async_test_session.rollback()

    #Incorrect data
    with pytest.raises(CategoryCreateError):
        await CategoryDAO.create(None, session=async_test_session)
    await async_test_session.rollback()

    #Get by ID
    got = await CategoryDAO.get(category_id, session=async_test_session)
    assert got.id == category_id
    assert got.category == "Math"

    #Non-existent ID
    with pytest.raises(CategoryNotFound):
        await CategoryDAO.get(uuid4(), session=async_test_session)

    #List
    categories = await CategoryDAO.list(session=async_test_session)
    assert any(cat.id == category_id for cat in categories)

    empty_list = await CategoryDAO.list(offset=1000, limit=10, session=async_test_session)
    assert empty_list == []

    #Update
    updated = await CategoryDAO.update(category_id, new_name="Physics", session=async_test_session)
    await async_test_session.commit()
    fresh_category = await CategoryDAO.get(category_id, session=async_test_session)
    assert fresh_category.category == "Physics"

    #Update a non-existent category
    with pytest.raises(CategoryNotFound):
        await CategoryDAO.update(uuid4(), new_name="Bio", session=async_test_session)
    await async_test_session.rollback()

    #Update new_name=None
    with pytest.raises(CategoryUpdateError):
        await CategoryDAO.update(category_id, new_name=None, session=async_test_session)
    await async_test_session.rollback()

    #Updat to an existing name
    category2 = await CategoryDAO.create("Biology", session=async_test_session)
    await async_test_session.commit()

    with pytest.raises(CategoryUpdateError):
        await CategoryDAO.update(category_id, new_name="Biology", session=async_test_session)
    await async_test_session.rollback()

    #Delete
    await CategoryDAO.delete(category_id, session=async_test_session)
    await async_test_session.commit()

    with pytest.raises(CategoryNotFound):
        await CategoryDAO.get(category_id, session=async_test_session)

    #Repeate delete
    with pytest.raises(CategoryDeleteError):
        await CategoryDAO.delete(category_id, session=async_test_session)
    await async_test_session.rollback()

    #Deleting a category with questions
    category = await CategoryDAO.create("Geography", session=async_test_session)
    await async_test_session.commit()

    question_data = {
        "text": "Capital of France?",
        "answer": {"correct": "Paris"},
        "category_id": category.id,
        "teacher_id": uuid4(),
        "question_type": "text",
        "problem": "Europe capitals",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True
    }
    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    try:
        await CategoryDAO.delete(category.id, session=async_test_session)
        await async_test_session.commit()
    except Exception as e:
        assert isinstance(e, CategoryDeleteError)
    else:
        with pytest.raises(QuestionNotFoundError):
            await QuestionDAO.get(question.id, session=async_test_session)

@pytest.mark.asyncio
async def test_question_crud(async_test_session):

    category = await CategoryDAO.create("Math", session=async_test_session)
    await async_test_session.commit()

    data = {
        "text": "2+2=?",
        "answer": {"correct": 4},
        "category_id": category.id,
        "teacher_id": uuid4(),
        "question_type": "text",
        "problem": "Simple addition",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True
    }

    #Create
    question = await QuestionDAO.add_question(data, session=async_test_session)
    await async_test_session.commit()

    assert isinstance(question.id, UUID)
    assert question.text == "2+2=?"

    #Incorrect data
    bad_data = data.copy()
    bad_data["text"] = None

    with pytest.raises(QuestionCreateError):
        await QuestionDAO.add_question(bad_data, session=async_test_session)
    await async_test_session.rollback()

    #Question with a non-existent category
    data3 = data.copy()
    data3["category_id"] = uuid4()
    with pytest.raises(QuestionCreateError):
        await QuestionDAO.add_question(data3, session=async_test_session)

    #Get a question
    got = await QuestionDAO.get(question.id, session=async_test_session)
    assert got.id == question.id
    assert got.text == "2+2=?"

    #Non-existent question
    with pytest.raises(QuestionNotFoundError):
        await QuestionDAO.get(uuid4(), session=async_test_session)

    #Update
    updated = await QuestionDAO.update(
        question.id,
        {"text": "3+3=?"},
        session=async_test_session
    )
    await async_test_session.commit()

    assert updated.text == "3+3=?"

    #Update non-existent question
    with pytest.raises(QuestionNotFoundError):
        await QuestionDAO.update(uuid4(), {"text": "5+5=?"}, session=async_test_session)

    #Delete
    await QuestionDAO.delete(question.id, session=async_test_session)
    await async_test_session.commit()

    with pytest.raises(QuestionNotFoundError):
        await QuestionDAO.get(question.id, session=async_test_session)

    #Repeate Delete
    with pytest.raises(QuestionDeleteError):
        await QuestionDAO.delete(question.id, session=async_test_session)
        await async_test_session.rollback()

    #Deleting a category with questions
    category = await CategoryDAO.create("Algebra", session=async_test_session)
    await async_test_session.commit()

    data = {
        "text": "5+5=?",
        "answer": {"correct": 10},
        "category_id": category.id,
        "teacher_id": uuid4(),
        "question_type": "text",
        "problem": "Addition",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True
    }
    question = await QuestionDAO.add_question(data, session=async_test_session)
    await async_test_session.commit()

    await QuestionDAO.delete(question.id, session=async_test_session)
    await async_test_session.commit()

    with pytest.raises(QuestionNotFoundError):
        await QuestionDAO.get(question.id, session=async_test_session)
    cat = await CategoryDAO.get(category.id, session=async_test_session)
    assert cat.id == category.id
    assert cat.category == "Algebra"