"""
Snapshots question-bank questions (Postgres) into the per-session Redis cache
(QuestionRedis) at session-creation time.

Without this, a session referencing real question-bank questions would 404 at
grading time, because QuestionRedis is otherwise never populated (the only thing
that ever wrote it was the disconnected `questions.json` mock bank). Snapshotting
at session-start also means edits to the question bank never retroactively change
a test a student is already taking.

`Question.answer` (Postgres JSONB) convention, chosen here since nothing in the
codebase previously interpreted its contents:
    - single/multiple choice: {"choices": ["4", "8", ...], "correct": [0]}
      `correct` is always a list of choice indices, even for single-choice (len 1).
    - text (free response):   {"correct_text": "expected answer"}

Students then submit answers (AnswerPayload.answer) as:
    - single/text: the choice index, or the free-text answer, as a plain string.
    - multiple:    a JSON-encoded list of choice indices, e.g. '["0", "2"]'.
"""
import json
from uuid import UUID

from aredis_om import NotFoundError

from app.repositories.question_bank.models import Question
from app.repositories.question_bank.question_dao import QuestionDAO
from .models.redis import QuestionRedis


def _question_type_value(question: Question) -> str:
    question_type = question.question_type
    return question_type.value if hasattr(question_type, "value") else str(question_type)


def _correct_answer_field(question: Question, question_type: str) -> str:
    answer = question.answer or {}
    if question_type == "text":
        return str(answer.get("correct_text", ""))

    correct_indices = [str(i) for i in answer.get("correct", [])]
    if question_type == "multiple":
        return json.dumps(sorted(correct_indices))
    # single
    return correct_indices[0] if correct_indices else ""


def _choices_field(question: Question, question_type: str) -> str:
    if question_type == "text":
        return json.dumps([])
    answer = question.answer or {}
    return json.dumps(answer.get("choices", []))


class QuestionSnapshotService:
    @staticmethod
    async def snapshot_for_session(question_ids: list[UUID]) -> None:
        """Fetch `question_ids` from Postgres (in order) and write one QuestionRedis
        record per question, indexed by their position in the given list.

        QuestionRedis is keyed globally by question_id (not per-session), since many
        concurrent sessions commonly reference the same bank question. To avoid one
        session's start clobbering the snapshot an already-in-progress session relies
        on, this only writes a snapshot the first time a question is seen — it never
        overwrites an existing one. (Known limitation: an edit to a question that
        already has a cached snapshot won't be picked up by new sessions either,
        until that snapshot is evicted/expires.)
        """
        if not question_ids:
            return

        missing_ids: list[UUID] = []
        for question_id in question_ids:
            try:
                await QuestionRedis.get(question_id)
            except NotFoundError:
                missing_ids.append(question_id)

        if not missing_ids:
            return

        questions = await QuestionDAO.get_many(missing_ids)
        by_id = {question.id: question for question in questions}

        for position, question_id in enumerate(question_ids):
            question = by_id.get(question_id)
            if question is None:
                continue
            question_type = _question_type_value(question)
            category_name = question.category.category if question.category is not None else ""
            await QuestionRedis(
                # See the matching note in session_service.py: aredis_om doesn't
                # honor a custom-named primary_key=True field as the real Redis
                # key under this pydantic version, so `pk` must be set explicitly
                # or QuestionRedis.get(question_id) below will always 404.
                pk=str(question.id),
                question_id=question.id,
                index=str(position),
                category=category_name,
                content=question.text,
                choices=_choices_field(question, question_type),
                correct_answer=_correct_answer_field(question, question_type),
                question_type=question_type,
                mark_out_of=question.mark_out_of,
                penalty=question.penalty,
            ).save()
