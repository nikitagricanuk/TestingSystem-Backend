"""
Resolves a Test's final, session-ready question order from:
  - its concretely-assigned TestQuestion pool (position_in_test order), and
  - its TestQuestionRule slots ("random question from topic X", obligatory or
    not, pinned to a fixed position or placed anywhere) — see the Admin PDF's
    test-overview "Банк вопросов" cards.

A test with no rules behaves exactly as before this feature existed: the
concrete pool, shuffled if Test.shuffle else in position order.
"""
import random
from uuid import UUID

from app.models.database import Test
from app.repositories.dao.testdao import TestDAO
from app.repositories.question_bank.question_dao import QuestionDAO


class ResolvedQuestions:
    def __init__(self, question_ids: list[UUID], required_count: int) -> None:
        self.question_ids = question_ids
        self.required_count = required_count


async def resolve_session_question_ids(test: Test) -> ResolvedQuestions:
    test_questions = await TestDAO.list_questions(test.id)
    concrete_ids = [tq.question_id for tq in test_questions]

    rules = await TestDAO.list_rules(test.id)
    used_ids: set[UUID] = set(concrete_ids)

    resolved_rules: list[tuple] = []  # (rule, question_id)
    for rule in rules:
        candidates = await QuestionDAO.list_by_category(rule.category_id, include_descendants=True)
        pool = [q.id for q in candidates if q.id not in used_ids]
        if not pool:
            # No available question left for this rule; skip it rather than fail
            # the whole session-start (e.g. an under-stocked topic).
            continue
        chosen = random.choice(pool)
        used_ids.add(chosen)
        resolved_rules.append((rule, chosen))

    fixed_slots = [(rule.fixed_position, qid) for rule, qid in resolved_rules if rule.fixed_position is not None]
    free_rule_ids = [qid for rule, qid in resolved_rules if rule.fixed_position is None]

    remaining = list(concrete_ids) + free_rule_ids
    if test.shuffle:
        random.shuffle(remaining)

    total_slots = len(remaining) + len(fixed_slots)
    final: list[UUID | None] = [None] * total_slots

    for position, qid in fixed_slots:
        # Positions from the API are 1-indexed; clamp out-of-range values into
        # the slot list rather than raising, and resolve collisions by taking
        # the next free slot.
        index = min(max(position - 1, 0), total_slots - 1)
        if final[index] is not None:
            index = next((i for i in range(total_slots) if final[i] is None), index)
        final[index] = qid

    remaining_iter = iter(remaining)
    for i in range(total_slots):
        if final[i] is None:
            final[i] = next(remaining_iter)

    required_count = sum(1 for rule, _ in resolved_rules if rule.is_mandatory)
    return ResolvedQuestions(question_ids=final, required_count=required_count)
