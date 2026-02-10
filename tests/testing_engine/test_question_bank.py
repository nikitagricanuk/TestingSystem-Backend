from uuid import uuid4

import pytest

from app.services.testing_engine.question_bank.question_bank import Question, QuestionBank, get_qb


@pytest.fixture(autouse=True)
def clear_bank():
    bank = get_qb()
    bank._questions.clear()
    yield
    bank._questions.clear()


@pytest.mark.asyncio
async def test_add_and_get_from_cache():
    bank = get_qb()
    qid = uuid4()
    question = Question(
        id=qid,
        category="math",
        content="2+2",
        choices=["3", "4"],
        correct_answer="4",
        marked_out_of=5,
        penalty=0,
    )
    await bank.add(question)

    fetched = await QuestionBank.get(qid)

    assert fetched.id == qid
    assert fetched.content == "2+2"


@pytest.mark.asyncio
async def test_update_replaces_question():
    bank = get_qb()
    qid = uuid4()
    original = Question(
        id=qid,
        category="math",
        content="2+2",
        choices=["3", "4"],
        correct_answer="4",
        marked_out_of=5,
        penalty=0,
    )
    updated = Question(
        id=qid,
        category="math",
        content="3+3",
        choices=["5", "6"],
        correct_answer="6",
        marked_out_of=5,
        penalty=0,
    )
    await bank.add(original)
    await bank.update(updated)

    fetched = await QuestionBank.get(qid)

    assert fetched.content == "3+3"
    assert fetched.correct_answer == "6"


@pytest.mark.asyncio
async def test_update_missing_raises():
    bank = get_qb()
    qid = uuid4()
    question = Question(
        id=qid,
        category="math",
        content="2+2",
        choices=["3", "4"],
        correct_answer="4",
        marked_out_of=5,
        penalty=0,
    )
    with pytest.raises(KeyError):
        await bank.update(question)


@pytest.mark.asyncio
async def test_delete_removes_question(monkeypatch):
    bank = get_qb()
    qid = uuid4()
    question = Question(
        id=qid,
        category="math",
        content="2+2",
        choices=["3", "4"],
        correct_answer="4",
        marked_out_of=5,
        penalty=0,
    )
    await bank.add(question)
    await bank.delete(question)

    monkeypatch.setattr(
        "app.services.testing_engine.question_bank.question_bank.load_questions_from_json",
        lambda: [],
    )

    with pytest.raises(ValueError):
        await QuestionBank.get(qid)


@pytest.mark.asyncio
async def test_delete_missing_raises():
    bank = get_qb()
    question = Question(
        id=uuid4(),
        category="math",
        content="2+2",
        choices=["3", "4"],
        correct_answer="4",
        marked_out_of=5,
        penalty=0,
    )
    with pytest.raises(KeyError):
        await bank.delete(question)
