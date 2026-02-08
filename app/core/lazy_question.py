from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.question_cache import QuestionCache
from app.repositories.question_bank.models import Question, QuestionType
from app.repositories.question_bank.question_dao import QuestionDAO


class LazyQuestion:
    def __init__(self, question_id: UUID, session: AsyncSession, cache: QuestionCache) -> None:
        self.id = question_id
        self._session = session
        self._cache = cache
        self._loaded = False
        self._question: Optional[Question] = None

    async def _load(self) -> None:
        if self._loaded:
            return
        cached = self._cache.get(self.id)
        if cached:
            self._question = cached
        else:
            self._question = await QuestionDAO.get(self.id, session=self._session)
            self._cache.set(self._question)
        self._loaded = True

    async def text(self) -> str:
        await self._load()
        return self._question.text

    async def answer(self) -> dict:
        await self._load()
        return self._question.answer

    async def mark_out_of(self) -> int:
        await self._load()
        return self._question.mark_out_of

    async def problem(self) -> str:
        await self._load()
        return self._question.problem

    async def question_type(self) -> QuestionType:
        await self._load()
        return self._question.question_type

    async def penalty(self) -> int:
        await self._load()
        return self._question.penalty