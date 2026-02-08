from __future__ import annotations

from uuid import UUID

from app.repositories.question_bank.models import Question


class QuestionCache:
    def __init__(self) -> None:
        self._storage: dict[UUID, Question] = {}

    def get(self, question_id: UUID) -> Question | None:
        return self._storage.get(question_id)

    def set(self, question: Question) -> None:
        self._storage[question.id] = question

    def invalidate(self, question_id: UUID) -> None:
        self._storage.pop(question_id, None)

    def clear(self) -> None:
        self._storage.clear()
