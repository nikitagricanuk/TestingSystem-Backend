
import os
os.environ["TESTING"] = "1"

os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["DB_NAME"] = "test"
os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"

from uuid import UUID
from uuid import uuid4
from app.repositories.question_bank.models import Category, Question
from app.repositories.question_bank.question_dao import CategoryDAO, QuestionDAO
from app.repositories.question_bank.exceptions import (
    CategoryNotFound,
    QuestionNotFoundError
)
import pytest
from unittest.mock import patch
from app.core.config import Settings
from app.models.database import Base
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
    # Create
    category = await CategoryDAO.create("Math", session=async_test_session)
    assert isinstance(category.id, UUID)
    assert category.category == "Math"

    # Get
    got = await CategoryDAO.get_by_id(category.id, session=async_test_session)
    assert got.id == category.id
    assert got.category == "Math"

    # List
    categories = await CategoryDAO.list(session=async_test_session)
    # Сравниваем по id
    assert any(cat.id == category.id for cat in categories)

    # Update
    updated = await CategoryDAO.update(category.id, new_name="Physics", session=async_test_session)
    assert updated.category == "Physics"

    # Delete
    await CategoryDAO.delete(category.id, session=async_test_session)
    with pytest.raises(CategoryNotFound):
        await CategoryDAO.get_by_id(category.id, session=async_test_session)


@pytest.mark.asyncio
async def test_question_crud(async_test_session):
    # --- подготовим категорию ---
    category = await CategoryDAO.create("Math", session=async_test_session)

    # Data для вопроса
    data = {
        "text": "2+2=?",
        "answer": {"correct": 4},
        "category_id": category.id,
        "teacher_id": uuid4(),
        "question_type": "text",
        "problem": "Simple addition",
        "market_out_of": 5,
        "penalty": 0,
        "is_active": True
    }

    # Add question
    question = await QuestionDAO.add_question(data, session=async_test_session)
    assert isinstance(question.id, UUID)
    assert question.text == "2+2=?"

    # Get question
    got = await QuestionDAO.get(question.id, session=async_test_session)
    assert got.id == question.id
    assert got.text == "2+2=?"

    # List questions
    questions = await QuestionDAO.list(session=async_test_session)
    # Сравниваем по id
    assert any(q.id == question.id for q in questions)

    # Update question
    updated_data = {"text": "3+3=?"}
    updated = await QuestionDAO.update(question.id, updated_data, session=async_test_session)
    assert updated.text == "3+3=?"

    # Delete question
    await QuestionDAO.delete(question.id, session=async_test_session)
    with pytest.raises(QuestionNotFoundError):
        await QuestionDAO.get(question.id, session=async_test_session)