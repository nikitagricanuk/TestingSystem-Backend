from __future__ import annotations

import random
from typing import AsyncIterator, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncIterator, List, Iterable, ClassVar
from app.core.lazy_question import LazyQuestion
from app.core.question_cache import QuestionCache
from app.repositories.question_bank.question_dao import QuestionDAO, CategoryDAO
from app.repositories.question_bank.models import Question

class TestBank:
    _banks: ClassVar[dict[UUID, "TestBank"]] = {}
    def __init__(
        self,
        owner_id: UUID,
        question_ids: List[UUID],
        name: str | None = None,
        cache: QuestionCache | None = None,
    ) -> None:
        self.owner_id = owner_id
        self.name = name or "Unnamed test"
        self.question_ids = question_ids
        self.cache = cache or QuestionCache()

    def _get_question(self, question_id: UUID, session: AsyncSession) -> LazyQuestion:
        return LazyQuestion(question_id, session, self.cache)

    @classmethod
    async def for_owner(
            cls,
            owner_id: UUID,
            session: AsyncSession,
            name: str | None = None,
            cache: QuestionCache | None = None,
    ) -> "TestBank":
        if owner_id in cls._banks:
            return cls._banks[owner_id]
        questions = await QuestionDAO.get_by_teacher(owner_id, session=session)
        question_ids = [question.id for question in questions]
        bank = cls(owner_id=owner_id, question_ids=question_ids, name=name, cache=cache)
        cls._banks[owner_id] = bank
        return bank

    async def get_questions(
        self,
        session: AsyncSession,
        limit: int,
        random_order: bool = False,
        question_ids: List[UUID] | None = None,
    ) -> AsyncIterator[LazyQuestion]:
        ids = question_ids if question_ids is not None else self.question_ids.copy()
        if random_order:
            random.shuffle(ids)

        ids = ids[:limit]

        for question_id in ids:
            yield self._get_question(question_id, session)


    async def warmup_cache(self, session: AsyncSession, question_ids: List[UUID] | None = None) -> None:
        ids_to_load = question_ids or self.question_ids

        for question_id in ids_to_load:
            if self.cache.get(question_id) is None:
                question = await QuestionDAO.get(question_id, session=session)
                self.cache.set(question)


    async def get_all_teacher_questions(self, session: AsyncSession) -> List[Question]:
        return await QuestionDAO.get_by_teacher(self.owner_id, session=session)

    async def delete_question(self, question_id: UUID, session: AsyncSession) -> None:
        await QuestionDAO.delete(question_id, session=session)
        self.cache.invalidate(question_id)
        if question_id in self.question_ids:
            self.question_ids.remove(question_id)

    async def search_questions(self, session: AsyncSession, **filters) -> List[Question]:
        return await QuestionDAO.search(session=session, **filters)

    async def list_questions_by_category(
            self,
            session: AsyncSession,
            category_id: UUID | None = None,
            category_path: Iterable[str] | None = None,
            include_descendants: bool = False,
    ) -> List[Question]:
        if category_id is None and category_path is None:
            raise ValueError("category_id or category_path is required")
        resolved_category_id = category_id
        if resolved_category_id is None and category_path is not None:
            category = await CategoryDAO.get_by_path(category_path, session=session)
            resolved_category_id = category.id
        return await QuestionDAO.list_by_category(
            resolved_category_id,
            include_descendants=include_descendants,
            session=session,
        )

    async def create_question(
            self,
            question_data: dict,
            session: AsyncSession,
            category_path: Iterable[str] | None = None,
    ) -> Question:
        question_data["teacher_id"] = self.owner_id
        if question_data.get("category_id") is None:
            if not category_path:
                raise ValueError("category_id or category_path is required")
            category = await CategoryDAO.get_or_create_path(category_path, session=session)
            question_data["category_id"] = category.id
        question = await QuestionDAO.add_question(question_data, session=session)
        self.question_ids.append(question.id)
        return question

    async def update_question(self, question_id: UUID, data: dict, session: AsyncSession) -> Question:
        question = await QuestionDAO.update(question_id, data, session=session)
        self.cache.invalidate(question_id)
        return question

    async def get_question(self, question_id: UUID, session: AsyncSession) -> Question:
        return await QuestionDAO.get(question_id, session=session)

