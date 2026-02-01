from typing import Optional, Mapping, Any, Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.databases import connection
from app.repositories.question_bank.models import Question, Category
from app.repositories.question_bank.exceptions import (
    QuestionDAOError,
    QuestionNotFoundError,
    QuestionCreateError,
    QuestionUpdateError,
    QuestionDeleteError,
    CategoryNotFound,
    CategoryCreateError,
    CategoryUpdateError,
    CategoryDeleteError,
    CategoryDAOError
)
from app.core.log import setup_logger

logger = setup_logger(__name__)


class QuestionDAO:
    @staticmethod
    @connection
    async def add_question(data: dict, session: AsyncSession) -> Question:
        if not session:
            raise QuestionDAOError("Session is required")
        if not data.get("text"):
            raise QuestionCreateError("Question text cannot be None")
        category_id = data.get("category_id")
        if not category_id:
            raise QuestionCreateError("Category ID is required")
        try:
            await CategoryDAO.get(category_id, session=session)
        except Exception:
            raise QuestionCreateError(f"Category {category_id} not found")
        question = Question(**data)
        session.add(question)
        try:
            await session.flush()
            logger.info(f"Question {question.id} created")
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Failed to add question: {e}")
            raise QuestionCreateError("Failed to add question due to DB constraint") from e
        return question

    @staticmethod
    @connection
    async def get(question_id: UUID, session: AsyncSession) -> Question:
        if not session:
            raise QuestionDAOError("Session is required")
        result = await session.execute(select(Question).where(Question.id == question_id))
        question = result.scalar_one_or_none()
        if not question:
            raise QuestionNotFoundError(f"Question {question_id} not found")
        return question

    @staticmethod
    @connection
    async def list(offset: int = 0, limit: int = 100, session: AsyncSession = None) -> Sequence[Question]:
        if not session:
            raise QuestionDAOError("Session is required")
        result = await session.execute(select(Question).offset(offset).limit(limit))
        return result.scalars().all()

    @staticmethod
    @connection
    async def update(question_id: UUID, data: Mapping[str, Any], session: AsyncSession) -> Question:
        if not session:
            raise QuestionDAOError("Session is required")
        if not data:
            raise QuestionUpdateError("Nothing to update: data is empty")

        try:
            question = await QuestionDAO.get(question_id, session=session)
            for key, value in data.items():
                setattr(question, key, value)
            await session.flush()
            logger.info(f"Question {question.id} updated")
            return question
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Failed to update question: {e}")
            raise QuestionUpdateError(f"Failed to update question {question_id}") from e
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise QuestionDAOError("Database error") from e

    @staticmethod
    @connection
    async def delete(question_id: UUID, session: AsyncSession) -> None:
        if not session:
            raise QuestionDAOError("Session is required")
        try:
            question = await QuestionDAO.get(question_id, session=session)
            await session.delete(question)
            await session.flush()
            logger.info(f"Question {question.id} deleted")
        except QuestionNotFoundError:
            raise QuestionDeleteError(f"Question {question_id} already deleted")
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Failed to delete question {question_id}: {e}")
            raise QuestionDeleteError(f"Failed to delete question {question_id}") from e


class CategoryDAO:
    @staticmethod
    @connection
    async def create(name: str, session: AsyncSession) -> Category:
        if not session:
            raise CategoryDAOError("Session is required")
        if not name:
            raise CategoryCreateError("Category name cannot be None")

        category = Category(category=name)
        session.add(category)
        try:
            await session.flush()
            logger.info(f"Category {category.id} created")
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Failed to create category: {e}")
            raise CategoryCreateError(f"Category '{name}' already exists") from e

        return category

    @staticmethod
    @connection
    async def get(category_id: UUID, session: AsyncSession) -> Category:
        if not session:
            raise CategoryDAOError("Session is required")
        result = await session.execute(select(Category).where(Category.id == category_id))
        category = result.scalar_one_or_none()
        if not category:
            raise CategoryNotFound(f"Category {category_id} not found")
        return category

    @staticmethod
    @connection
    async def list(offset: int = 0, limit: int = 100, session: AsyncSession = None) -> Sequence[Category]:
        if not session:
            raise CategoryDAOError("Session is required")
        result = await session.execute(select(Category).offset(offset).limit(limit))
        return result.scalars().all()

    @staticmethod
    @connection
    async def update(category_id: UUID, new_name: Optional[str] = None, parent_id: Optional[UUID] = None,
                     session: AsyncSession = None) -> Category:
        if not session:
            raise CategoryDAOError("Session is required")
        if new_name is None and parent_id is None:
            raise CategoryUpdateError("Nothing to update: new_name and parent_id are both None")

        try:
            category = await CategoryDAO.get(category_id, session=session)
            if new_name:
                existing = await session.execute(
                    select(Category).where(
                        Category.category == new_name,
                        Category.id != category_id
                    )
                )
                if existing.scalar_one_or_none():
                    raise CategoryUpdateError(f"Category '{new_name}' already exists")
                category.category = new_name
            if parent_id is not None:
                category.parent_id = parent_id
            await session.flush()
            logger.info(f"Category {category.id} updated")
            return category
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Failed to update category {category_id}: {e}")
            raise CategoryUpdateError(f"Failed to update category {category_id}") from e
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise CategoryDAOError("Database error") from e

    @staticmethod
    @connection
    async def delete(category_id: UUID, session: AsyncSession) -> None:
        if not session:
            raise CategoryDAOError("Session is required")
        try:
            category = await CategoryDAO.get(category_id, session=session)
            await session.delete(category)
            await session.flush()
            logger.info(f"Category {category.id} deleted")
        except CategoryNotFound:
            raise CategoryDeleteError(f"Category {category_id} already deleted")
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Failed to delete category {category_id}: {e}")
            raise CategoryDeleteError(f"Failed to delete category {category_id}") from e
