import pytest
from uuid import uuid4

from app.core.lazy_question import LazyQuestion
from app.core.question_cache import QuestionCache
from app.repositories.question_bank.question_dao import CategoryDAO, QuestionDAO
from app.repositories.question_bank.testBank import TestBank


@pytest.mark.asyncio
async def test_lazy_loading(async_test_session):
    category = await CategoryDAO.create("Math", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "2+2=?",
        "answer": {"correct": 4},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Simple addition",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }

    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=[question.id], cache=cache)

    questions = [
        question async for question in bank.get_questions(session=async_test_session, limit=1)
    ]

    assert len(questions) == 1

    lazy_q = questions[0]
    assert isinstance(lazy_q, LazyQuestion)
    assert not lazy_q._loaded

    text = await lazy_q.text()
    assert text == "2+2=?"
    assert lazy_q._loaded
    assert cache.get(question.id) is not None

    answer = await lazy_q.answer()
    assert answer == {"correct": 4}
