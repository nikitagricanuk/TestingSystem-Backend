import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aredis_om import NotFoundError

from app.services.testing_engine import question_snapshot as snapshot_module
from app.services.testing_engine.question_snapshot import QuestionSnapshotService


def _fake_question(*, question_type, answer, category="линейная алгебра", text="Q", mark_out_of=1, penalty=0):
    return SimpleNamespace(
        id=uuid4(),
        question_type=question_type,
        answer=answer,
        category=SimpleNamespace(category=category),
        text=text,
        mark_out_of=mark_out_of,
        penalty=penalty,
    )


def _install_fake_question_redis(monkeypatch, *, existing: dict | None = None):
    """Replace snapshot_module.QuestionRedis with a fake: `.get` raises NotFoundError
    unless `existing` (a {question_id: obj} map) has that id; instantiating + .save()
    records the kwargs it was constructed with into the returned `saved` dict."""
    existing = existing or {}
    saved: dict = {}

    class FakeQuestionRedis:
        def __init__(self, **kwargs):
            self._kwargs = kwargs

        async def save(self):
            saved.update(self._kwargs)

        @staticmethod
        async def get(question_id):
            if question_id in existing:
                return existing[question_id]
            raise NotFoundError()

    monkeypatch.setattr(snapshot_module, "QuestionRedis", FakeQuestionRedis)
    return saved


@pytest.mark.asyncio
class TestQuestionSnapshotService:
    async def test_skips_empty_question_ids(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            snapshot_module.QuestionDAO, "get_many", staticmethod(lambda ids: calls.append(ids))
        )
        await QuestionSnapshotService.snapshot_for_session([])
        assert calls == []

    async def test_writes_single_choice_snapshot(self, monkeypatch):
        question = _fake_question(question_type="single", answer={"choices": ["4", "8"], "correct": [1]})
        saved = _install_fake_question_redis(monkeypatch)

        async def fake_get_many(ids):
            assert ids == [question.id]
            return [question]

        monkeypatch.setattr(snapshot_module.QuestionDAO, "get_many", staticmethod(fake_get_many))

        await QuestionSnapshotService.snapshot_for_session([question.id])

        assert saved["index"] == "0"
        assert saved["category"] == "линейная алгебра"
        assert saved["content"] == "Q"
        assert json.loads(saved["choices"]) == ["4", "8"]
        assert saved["correct_answer"] == "1"
        assert saved["question_type"] == "single"
        assert saved["mark_out_of"] == 1
        assert saved["penalty"] == 0

    async def test_writes_multiple_choice_snapshot_as_sorted_json_list(self, monkeypatch):
        question = _fake_question(
            question_type="multiple", answer={"choices": ["a", "b", "c"], "correct": [2, 0]}
        )
        saved = _install_fake_question_redis(monkeypatch)

        async def fake_get_many(ids):
            return [question]

        monkeypatch.setattr(snapshot_module.QuestionDAO, "get_many", staticmethod(fake_get_many))

        await QuestionSnapshotService.snapshot_for_session([question.id])

        assert json.loads(saved["correct_answer"]) == ["0", "2"]

    async def test_writes_text_question_snapshot(self, monkeypatch):
        question = _fake_question(question_type="text", answer={"correct_text": "Paris"})
        saved = _install_fake_question_redis(monkeypatch)

        async def fake_get_many(ids):
            return [question]

        monkeypatch.setattr(snapshot_module.QuestionDAO, "get_many", staticmethod(fake_get_many))

        await QuestionSnapshotService.snapshot_for_session([question.id])

        assert saved["correct_answer"] == "Paris"
        assert json.loads(saved["choices"]) == []

    async def test_does_not_overwrite_existing_snapshot(self, monkeypatch):
        question_id = uuid4()
        existing_record = SimpleNamespace(question_id=question_id)
        _install_fake_question_redis(monkeypatch, existing={question_id: existing_record})

        get_many_calls = []

        async def fake_get_many(ids):
            get_many_calls.append(ids)
            return []

        monkeypatch.setattr(snapshot_module.QuestionDAO, "get_many", staticmethod(fake_get_many))

        await QuestionSnapshotService.snapshot_for_session([question_id])

        assert get_many_calls == []
