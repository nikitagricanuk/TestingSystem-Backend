from __future__ import annotations

import random
from typing import AsyncIterator, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lazy_question import LazyQuestion
from app.core.question_cache import QuestionCache


class TestBank:
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

    async def get_questions(
        self,
        session: AsyncSession,
        limit: int,
        random_order: bool = False,
    ) -> AsyncIterator[LazyQuestion]:
        ids = self.question_ids.copy()

        if random_order:
            random.shuffle(ids)

        ids = ids[:limit]

        for question_id in ids:
            yield self._get_question(question_id, session)
