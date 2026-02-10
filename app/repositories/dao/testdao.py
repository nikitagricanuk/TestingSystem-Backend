from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.databases import connection
from app.core.log import setup_logger
from app.models.database import Test, TestQuestion, NavigationMethod

logger = setup_logger(__name__)


class TestDAO:
    @staticmethod
    def _normalize_navigation(value: str | None) -> NavigationMethod | None:
        if value is None:
            return None
        try:
            return NavigationMethod(value)
        except Exception:
            return None

    @staticmethod
    @connection
    async def create(data: dict[str, Any], session: AsyncSession = None) -> Test:
        nav = TestDAO._normalize_navigation(data.get("navigation_method"))
        if nav is not None:
            data["navigation_method"] = nav
        test = Test(**data)
        session.add(test)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            logger.error("Failed to create test: %s", exc)
            raise
        return test

    @staticmethod
    @connection
    async def get(test_id: UUID, session: AsyncSession = None) -> Test | None:
        result = await session.execute(select(Test).where(Test.id == test_id))
        return result.scalar_one_or_none()

    @staticmethod
    @connection
    async def list(offset: int = 0, limit: int = 100, session: AsyncSession = None) -> Sequence[Test]:
        result = await session.execute(select(Test).offset(offset).limit(limit))
        return result.scalars().all()

    @staticmethod
    @connection
    async def update(test_id: UUID, data: dict[str, Any], session: AsyncSession = None) -> Test | None:
        test = await session.get(Test, test_id)
        if not test:
            return None
        if "navigation_method" in data:
            nav = TestDAO._normalize_navigation(data.get("navigation_method"))
            if nav is not None:
                data["navigation_method"] = nav
        for key, value in data.items():
            setattr(test, key, value)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            logger.error("Failed to update test %s: %s", test_id, exc)
            raise
        return test

    @staticmethod
    @connection
    async def delete(test_id: UUID, session: AsyncSession = None) -> bool:
        test = await session.get(Test, test_id)
        if not test:
            return False
        await session.delete(test)
        await session.flush()
        return True

    @staticmethod
    @connection
    async def add_questions(
        test_id: UUID,
        question_ids: list[UUID],
        session: AsyncSession = None,
    ) -> None:
        if not question_ids:
            return
        result = await session.execute(
            select(func.max(TestQuestion.position_in_test)).where(TestQuestion.test_id == test_id)
        )
        last_position = result.scalar_one_or_none() or 0
        for idx, question_id in enumerate(question_ids, start=1):
            session.add(
                TestQuestion(
                    test_id=test_id,
                    question_id=question_id,
                    position_in_test=last_position + idx,
                )
            )
        await session.flush()

    @staticmethod
    @connection
    async def list_questions(test_id: UUID, session: AsyncSession = None) -> Sequence[TestQuestion]:
        result = await session.execute(
            select(TestQuestion).where(TestQuestion.test_id == test_id).order_by(TestQuestion.position_in_test.asc())
        )
        return result.scalars().all()

    @staticmethod
    @connection
    async def get_question(test_id: UUID, question_id: UUID, session: AsyncSession = None) -> TestQuestion | None:
        result = await session.execute(
            select(TestQuestion).where(
                TestQuestion.test_id == test_id,
                TestQuestion.question_id == question_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    @connection
    async def remove_question(test_id: UUID, question_id: UUID, session: AsyncSession = None) -> bool:
        result = await session.execute(
            select(TestQuestion).where(
                TestQuestion.test_id == test_id,
                TestQuestion.question_id == question_id,
            )
        )
        test_question = result.scalar_one_or_none()
        if not test_question:
            return False
        await session.delete(test_question)
        await session.flush()
        return True
