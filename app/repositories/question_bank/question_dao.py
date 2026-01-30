# app/repositories/question_bank/question_dao.py

from typing import Optional, Mapping, Any, Sequence
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.question_bank.models import Question, Category
from app.core.connection import async_session
from app.repositories.question_bank.exceptions import (
    DAOException,
    QuestionDAOError,
    QuestionNotFoundError,
    QuestionCreateError,
    QuestionUpdateError,
    QuestionDeleteError,
    CategoryNotFound,
)
from app.core.log import setup_logger

logger = setup_logger(__name__)


class QuestionDAO:
    @staticmethod
    async def add_question(data: Mapping[str, Any], session: Optional[AsyncSession] = None) -> Question:
        async with (session or async_session()) as s:
            try:
                async with s.begin():
                    question = Question(**data)
                    s.add(question)
                await s.refresh(question)
                logger.info(f"Question {question.id} added")
                return question
            except IntegrityError as e:
                logger.error(f"Failed to create question: {e}")
                raise QuestionCreateError("Failed to create question") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise QuestionDAOError("Database error") from e

    @staticmethod
    async def get(question_id: UUID, session: Optional[AsyncSession] = None) -> Question:
        async with (session or async_session()) as s:
            result = await s.execute(select(Question).where(Question.id == question_id))
            question = result.scalar_one_or_none()
            if not question:
                raise QuestionNotFoundError(f"Question {question_id} not found")
            return question

    @staticmethod
    async def list(offset: int = 0, limit: int = 100, session: Optional[AsyncSession] = None) -> Sequence[Question]:
        async with (session or async_session()) as s:
            result = await s.execute(select(Question).offset(offset).limit(limit))
            return result.scalars().all()

    @staticmethod
    async def update(question_id: UUID, data: Mapping[str, Any], session: Optional[AsyncSession] = None) -> Question:
        async with (session or async_session()) as s:
            try:
                question = await QuestionDAO.get(question_id, session=s)
                for key, value in data.items():
                    setattr(question, key, value)
                async with s.begin():
                    s.add(question)
                await s.refresh(question)
                logger.info(f"Question {question.id} updated")
                return question
            except IntegrityError as e:
                logger.error(f"Failed to update question: {e}")
                raise QuestionUpdateError(f"Failed to update question {question_id}") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise QuestionDAOError("Database error") from e

    @staticmethod
    async def delete(question_id: UUID, session: Optional[AsyncSession] = None) -> None:
        async with (session or async_session()) as s:
            try:
                question = await QuestionDAO.get(question_id, session=s)
                async with s.begin():
                    await s.delete(question)
                logger.info(f"Question {question.id} deleted")
            except SQLAlchemyError as e:
                logger.error(f"Failed to delete question: {e}")
                raise QuestionDeleteError(f"Failed to delete question {question_id}") from e


class CategoryDAO:
    @staticmethod
    async def create(name: str, parent_id: Optional[UUID] = None, session: Optional[AsyncSession] = None) -> Category:
        async with (session or async_session()) as s:
            try:
                async with s.begin():
                    category = Category(id=uuid4(), category=name, parent_id=parent_id)
                    s.add(category)
                await s.refresh(category)
                logger.info(f"Category {category.id} created")
                return category
            except IntegrityError as e:
                logger.error(f"Failed to create category: {e}")
                raise DAOException(f"Failed to create category '{name}'") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise DAOException("Database error") from e

    @staticmethod
    async def get_by_id(category_id: UUID, session: Optional[AsyncSession] = None) -> Category:
        async with (session or async_session()) as s:
            result = await s.execute(select(Category).where(Category.id == category_id))
            category = result.scalar_one_or_none()
            if not category:
                raise CategoryNotFound(f"Category {category_id} not found")
            return category

    @staticmethod
    async def list(offset: int = 0, limit: int = 100, session: Optional[AsyncSession] = None) -> Sequence[Category]:
        async with (session or async_session()) as s:
            result = await s.execute(select(Category).offset(offset).limit(limit))
            return result.scalars().all()

    @staticmethod
    async def update(category_id: UUID, new_name: Optional[str] = None, parent_id: Optional[UUID] = None,
                     session: Optional[AsyncSession] = None) -> Category:
        async with (session or async_session()) as s:
            try:
                category = await CategoryDAO.get_by_id(category_id, session=s)
                if new_name:
                    category.category = new_name
                if parent_id is not None:
                    category.parent_id = parent_id
                async with s.begin():
                    s.add(category)
                await s.refresh(category)
                logger.info(f"Category {category.id} updated")
                return category
            except IntegrityError as e:
                logger.error(f"Failed to update category: {e}")
                raise DAOException(f"Failed to update category {category_id}") from e
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise DAOException("Database error") from e

    @staticmethod
    async def delete(category_id: UUID, session: Optional[AsyncSession] = None) -> None:
        async with (session or async_session()) as s:
            try:
                category = await CategoryDAO.get_by_id(category_id, session=s)
                async with s.begin():
                    await s.delete(category)
                logger.info(f"Category {category.id} deleted")
            except SQLAlchemyError as e:
                logger.error(f"Failed to delete category: {e}")
                raise DAOException(f"Failed to delete category {category_id}") from e
