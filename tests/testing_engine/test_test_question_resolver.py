from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.testing_engine import test_question_resolver as resolver_module
from app.services.testing_engine.test_question_resolver import resolve_session_question_ids


def _test(shuffle=False):
    return SimpleNamespace(id=uuid4(), shuffle=shuffle)


def _patch_dao(monkeypatch, *, test_questions=None, rules=None, category_pools=None):
    test_questions = test_questions or []
    rules = rules or []
    category_pools = category_pools or {}

    async def fake_list_questions(test_id):
        return test_questions

    async def fake_list_rules(test_id):
        return rules

    async def fake_list_by_category(category_id, include_descendants=False, teacher_id=None):
        return category_pools.get(category_id, [])

    monkeypatch.setattr(resolver_module.TestDAO, "list_questions", staticmethod(fake_list_questions))
    monkeypatch.setattr(resolver_module.TestDAO, "list_rules", staticmethod(fake_list_rules))
    monkeypatch.setattr(
        resolver_module.QuestionDAO, "list_by_category", staticmethod(fake_list_by_category)
    )


def _tq(question_id):
    return SimpleNamespace(question_id=question_id)


def _rule(category_id, *, is_mandatory=True, fixed_position=None):
    return SimpleNamespace(category_id=category_id, is_mandatory=is_mandatory, fixed_position=fixed_position)


@pytest.mark.asyncio
class TestResolveSessionQuestionIds:
    async def test_no_rules_returns_concrete_pool_unshuffled(self, monkeypatch):
        q1, q2, q3 = uuid4(), uuid4(), uuid4()
        _patch_dao(monkeypatch, test_questions=[_tq(q1), _tq(q2), _tq(q3)])

        result = await resolve_session_question_ids(_test(shuffle=False))

        assert result.question_ids == [q1, q2, q3]
        assert result.required_count == 0

    async def test_free_position_rule_is_appended_to_pool(self, monkeypatch):
        q1, q2 = uuid4(), uuid4()
        category_id = uuid4()
        rule_question = uuid4()
        _patch_dao(
            monkeypatch,
            test_questions=[_tq(q1), _tq(q2)],
            rules=[_rule(category_id, is_mandatory=True)],
            category_pools={category_id: [SimpleNamespace(id=rule_question)]},
        )

        result = await resolve_session_question_ids(_test(shuffle=False))

        assert set(result.question_ids) == {q1, q2, rule_question}
        assert len(result.question_ids) == 3
        assert result.required_count == 1

    async def test_fixed_position_rule_lands_at_requested_slot(self, monkeypatch):
        q1, q2, q3 = uuid4(), uuid4(), uuid4()
        category_id = uuid4()
        rule_question = uuid4()
        _patch_dao(
            monkeypatch,
            test_questions=[_tq(q1), _tq(q2), _tq(q3)],
            rules=[_rule(category_id, is_mandatory=True, fixed_position=2)],
            category_pools={category_id: [SimpleNamespace(id=rule_question)]},
        )

        result = await resolve_session_question_ids(_test(shuffle=False))

        # position 2 (1-indexed) -> index 1
        assert result.question_ids[1] == rule_question
        assert set(result.question_ids) == {q1, q2, q3, rule_question}
        assert result.required_count == 1

    async def test_rule_with_no_available_question_is_skipped(self, monkeypatch):
        q1 = uuid4()
        category_id = uuid4()
        _patch_dao(
            monkeypatch,
            test_questions=[_tq(q1)],
            rules=[_rule(category_id)],
            category_pools={category_id: []},
        )

        result = await resolve_session_question_ids(_test(shuffle=False))

        assert result.question_ids == [q1]
        assert result.required_count == 0

    async def test_optional_rule_does_not_count_toward_required(self, monkeypatch):
        q1 = uuid4()
        category_id = uuid4()
        rule_question = uuid4()
        _patch_dao(
            monkeypatch,
            test_questions=[_tq(q1)],
            rules=[_rule(category_id, is_mandatory=False)],
            category_pools={category_id: [SimpleNamespace(id=rule_question)]},
        )

        result = await resolve_session_question_ids(_test(shuffle=False))

        assert set(result.question_ids) == {q1, rule_question}
        assert result.required_count == 0

    async def test_shuffle_preserves_all_questions(self, monkeypatch):
        ids = [uuid4() for _ in range(10)]
        _patch_dao(monkeypatch, test_questions=[_tq(qid) for qid in ids])

        result = await resolve_session_question_ids(_test(shuffle=True))

        assert sorted(result.question_ids) == sorted(ids)
        assert len(result.question_ids) == len(ids)
