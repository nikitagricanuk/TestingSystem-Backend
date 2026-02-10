from typing import Optional, Mapping, Any, Sequence, Iterable
from uuid import UUID
from sqlalchemy.orm import aliased
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


    @staticmethod
    @connection
    async def get_by_teacher(teacher_id: UUID, session:AsyncSession) -> Sequence[Question]:
        if not session:
            raise QuestionDAOError("Session is required")
        result = await session.execute(select(Question).where(Question.teacher_id == teacher_id))
        return result.scalars().all()

    @staticmethod
    @connection
    async def search(session: AsyncSession, **filters) -> Sequence[Question]:
        if not session:
            raise QuestionDAOError("Session is required")
        query = select(Question)
        for field, value in filters.items():
            if value is not None and hasattr(Question, field):
                query = query.where(getattr(Question, field) == value)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    @connection
    async def list_by_category(
            category_id: UUID,
            include_descendants: bool,
            session: AsyncSession,
            teacher_id: UUID | None = None,
    ) -> Sequence[Question]:
        if not session:
            raise QuestionDAOError("Session is required")
        if include_descendants:
            category_cte = select(Category.id).where(Category.id == category_id).cte(recursive=True)
            category_alias = aliased(Category)
            category_cte = category_cte.union_all(
                select(category_alias.id).where(category_alias.parent_id == category_cte.c.id)
            )
            query = select(Question).where(Question.category_id.in_(select(category_cte.c.id)))
        else:
            query = select(Question).where(Question.category_id == category_id)
        if teacher_id is not None:
            query = query.where(Question.teacher_id == teacher_id)
        result = await session.execute(query)
        return result.scalars().all()

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
    async def get_by_name(name: str, parent_id: Optional[UUID], session: AsyncSession) -> Optional[Category]:
        if not session:
            raise CategoryDAOError("Session is required")
        query = select(Category).where(Category.category == name)
        if parent_id is None:
            query = query.where(Category.parent_id.is_(None))
        else:
            query = query.where(Category.parent_id == parent_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    @connection
    async def get_by_path(path: Iterable[str], session: AsyncSession) -> Category:
        if not session:
            raise CategoryDAOError("Session is required")
        path_list = list(path)
        parent_id: Optional[UUID] = None
        category: Optional[Category] = None
        for name in path_list:
            category = await CategoryDAO.get_by_name(name, parent_id, session=session)
            if not category:
                raise CategoryNotFound(f"Category path {'/'.join(path_list)} not found")
            parent_id = category.id
        if not category:
            raise CategoryNotFound("Category path is empty")
        return category

    @staticmethod
    @connection
    async def get_or_create_path(path: Iterable[str], session: AsyncSession) -> Category:
        if not session:
            raise CategoryDAOError("Session is required")
        path_list = list(path)
        parent_id: Optional[UUID] = None
        category: Optional[Category] = None
        for name in path_list:
            category = await CategoryDAO.get_by_name(name, parent_id, session=session)
            if not category:
                category = Category(category=name, parent_id=parent_id)
                session.add(category)
                try:
                    await session.flush()
                    logger.info(f"Category {category.id} created")
                except IntegrityError as e:
                    await session.rollback()
                    logger.error(f"Failed to create category: {e}")
                    raise CategoryCreateError(f"Category '{name}' already exists") from e
            parent_id = category.id
        if not category:
            raise CategoryCreateError("Category path is empty")
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
