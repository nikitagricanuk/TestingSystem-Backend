import sys
import os
from typing import Optional, Mapping, Any, Sequence
from typing import Optional, Sequence
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.repositories.question_bank.models import Category
from app.core.connection import async_session
from .exceptions import DAOException, CategoryNotFound
from app.core.log import setup_logger

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from app.core.connection import async_session
from app.repositories.question_bank.models import Question, Category
from .exceptions import (
    QuestionDAOError,
    QuestionNotFoundError,
    QuestionCreateError,
    QuestionUpdateError,
    QuestionDeleteError
)
from app.core.log import setup_logger

logger = setup_logger(__name__)


class QuestionDAO:
    @staticmethod
    async def add_question(data: Mapping[str, Any]) -> Question:
        """Add a new question"""
        async with async_session() as session:
            try:
                async with session.begin():
                    question = Question(**data)
                    session.add(question)
                await session.refresh(question)
                logger.info(f"Question {question.id} added")
                return question
            except IntegrityError as e:
                logger.error(f"Failed to create question: {e}")
                raise QuestionCreateError("Failed to create question") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise QuestionDAOError("Database error") from e

    @staticmethod
    async def get(question_id: UUID) -> Question:
        """Get a question by ID"""
        async with async_session() as session:
            result = await session.execute(select(Question).where(Question.id == question_id))
            question = result.scalar_one_or_none()
            if not question:
                logger.warning(f"Question {question_id} not found")
                raise QuestionNotFoundError(f"Question {question_id} not found")
            return question

    @staticmethod
    async def list(offset: int = 0, limit: int = 100) -> Sequence[Question]:
        """Get a list of paginated questions"""
        async with async_session() as session:
            result = await session.execute(select(Question).offset(offset).limit(limit))
            return result.scalars().all()

    @staticmethod
    async def update(question_id: UUID, data: Mapping[str, Any]) -> Question:
        """Updating the question"""
        async with async_session() as session:
            question = await QuestionDAO.get(question_id)
            for key, value in data.items():
                setattr(question, key, value)
            try:
                async with session.begin():
                    session.add(question)
                await session.refresh(question)
                logger.info(f"Question {question.id} updated")
                return question
            except IntegrityError as e:
                logger.error(f"Failed to update question: {e}")
                raise QuestionUpdateError(f"Failed to update question {question_id}") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise QuestionDAOError("Database error") from e

    @staticmethod
    async def delete(question_id: UUID) -> None:
        """Deleting a question"""
        async with async_session() as session:
            question = await QuestionDAO.get(question_id)
            try:
                async with session.begin():
                    await session.delete(question)
                logger.info(f"Question {question.id} deleted")
            except SQLAlchemyError as e:
                logger.error(f"Failed to delete question: {e}")
                raise QuestionDeleteError(f"Failed to delete question {question_id}") from e

class CategoryDAO:
    @staticmethod
    async def create(name: str, parent_id: Optional[UUID] = None) -> Category:
        """Creating a new category"""
        async with async_session() as session:
            category = Category(id=uuid4(), category=name, parent_id=parent_id)
            try:
                async with session.begin():
                    session.add(category)
                await session.refresh(category)
                logger.info(f"Category {category.id} created")
                return category
            except IntegrityError as e:
                logger.error(f"Failed to create category: {e}")
                raise DAOException(f"Failed to create category '{name}'") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise DAOException("Database error") from e

    @staticmethod
    async def get_by_id(category_id: UUID) -> Category:
        """Getting a category by ID"""
        async with async_session() as session:
            result = await session.execute(select(Category).where(Category.id == category_id))
            category = result.scalar_one_or_none()
            if not category:
                logger.warning(f"Category {category_id} not found")
                raise CategoryNotFound(f"Category {category_id} not found")
            return category

    @staticmethod
    async def list(offset: int = 0, limit: int = 100) -> Sequence[Category]:
        """List of categories with pagination"""
        async with async_session() as session:
            result = await session.execute(select(Category).offset(offset).limit(limit))
            return result.scalars().all()

    @staticmethod
    async def update(category_id: UUID, new_name: Optional[str] = None, parent_id: Optional[UUID] = None) -> Category:
        """Updating a category"""
        category = await CategoryDAO.get_by_id(category_id)
        if new_name:
            category.category = new_name
        if parent_id is not None:
            category.parent_id = parent_id
        async with async_session() as session:
            try:
                async with session.begin():
                    session.add(category)
                await session.refresh(category)
                logger.info(f"Category {category.id} updated")
                return category
            except IntegrityError as e:
                logger.error(f"Failed to update category: {e}")
                raise DAOException(f"Failed to update category {category_id}") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise DAOException("Database error") from e

    @staticmethod
    async def delete(category_id: UUID) -> None:
        """Deleting a category"""
        category = await CategoryDAO.get_by_id(category_id)
        async with async_session() as session:
            try:
                async with session.begin():
                    await session.delete(category)
                logger.info(f"Category {category.id} deleted")
            except SQLAlchemyError as e:
                logger.error(f"Failed to delete category: {e}")
                raise DAOException(f"Failed to delete category {category_id}") from e
