import pytest
from uuid import uuid4
from app.repositories.question_bank.exceptions import QuestionNotFoundError

from app.core.lazy_question import LazyQuestion
from app.core.question_cache import QuestionCache
from app.repositories.question_bank.question_dao import CategoryDAO, QuestionDAO
from app.repositories.question_bank.testBank import TestBank
from pydantic.v1 import UUID1


@pytest.mark.asyncio
async def test_lazy_loading_from_database(async_test_session):
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


@pytest.mark.asyncio
async def test_lazy_loading_from_cache(async_test_session):
    category = await CategoryDAO.create("Physics", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "What is gravity?",
        "answer": {"correct": "Force"},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Physics basics",
        "mark_out_of": 10,
        "penalty": 2,
        "is_active": True,
    }

    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    cache.set(question)

    lazy_q = LazyQuestion(question.id, async_test_session, cache)

    assert not lazy_q._loaded

    text = await lazy_q.text()
    assert text == "What is gravity?"
    assert lazy_q._loaded


@pytest.mark.asyncio
async def test_multiple_properties_single_load(async_test_session):
    category = await CategoryDAO.create("Chemistry", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "H2O formula?",
        "answer": {"correct": "Water"},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Chemical formulas",
        "mark_out_of": 3,
        "penalty": 1,
        "is_active": True,
    }

    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    lazy_q = LazyQuestion(question.id, async_test_session, cache)

    text = await lazy_q.text()
    answer = await lazy_q.answer()
    penalty = await lazy_q.penalty()
    mark = await lazy_q.mark_out_of()
    problem = await lazy_q.problem()
    q_type = await lazy_q.question_type()

    assert text == "H2O formula?"
    assert answer == {"correct": "Water"}
    assert penalty == 1
    assert mark == 3
    assert problem == "Chemical formulas"
    assert q_type == "text"
    assert lazy_q._loaded


@pytest.mark.asyncio
async def test_get_questions_with_limit(async_test_session):
    category = await CategoryDAO.create("Biology", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(5):
        question_data = {
            "text": f"Question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    questions = [
        q async for q in bank.get_questions(session=async_test_session, limit=3)
    ]

    assert len(questions) == 3


@pytest.mark.asyncio
async def test_random_order_shuffles_questions(async_test_session):
    category = await CategoryDAO.create("History", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(10):
        question_data = {
            "text": f"Question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    run1_ids = [
        q.id async for q in bank.get_questions(session=async_test_session, limit=10, random_order=True)
    ]
    run2_ids = [
        q.id async for q in bank.get_questions(session=async_test_session, limit=10, random_order=True)
    ]

    assert set(run1_ids) == set(question_ids)
    assert set(run2_ids) == set(question_ids)


@pytest.mark.asyncio
async def test_non_random_order_preserves_sequence(async_test_session):
    category = await CategoryDAO.create("Geography", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(5):
        question_data = {
            "text": f"Question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    run1_ids = [
        q.id async for q in bank.get_questions(session=async_test_session, limit=5, random_order=False)
    ]
    run2_ids = [
        q.id async for q in bank.get_questions(session=async_test_session, limit=5, random_order=False)
    ]

    assert run1_ids == question_ids
    assert run2_ids == question_ids


@pytest.mark.asyncio
async def test_cache_stores_loaded_questions(async_test_session):
    category = await CategoryDAO.create("Art", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(3):
        question_data = {
            "text": f"Art question {i}",
            "answer": {"correct": f"Answer {i}"},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    questions = [
        q async for q in bank.get_questions(session=async_test_session, limit=3)
    ]

    for q in questions:
        await q.text()

    for q_id in question_ids:
        assert cache.get(q_id) is not None


@pytest.mark.asyncio
async def test_lazy_question_id_available_before_load(async_test_session):
    category = await CategoryDAO.create("Music", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "Music theory",
        "answer": {"correct": "C major"},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Scales",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }

    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    lazy_q = LazyQuestion(question.id, async_test_session, cache)

    assert lazy_q.id == question.id
    assert not lazy_q._loaded


@pytest.mark.asyncio
async def test_limit_zero_returns_empty(async_test_session):
    category = await CategoryDAO.create("Sports", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "Sports question",
        "answer": {"correct": "Goal"},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Rules",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }

    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=[question.id], cache=cache)

    questions = [
        q async for q in bank.get_questions(session=async_test_session, limit=0)
    ]

    assert len(questions) == 0


@pytest.mark.asyncio
async def test_limit_exceeds_available_questions(async_test_session):
    category = await CategoryDAO.create("Literature", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(3):
        question_data = {
            "text": f"Literature {i}",
            "answer": {"correct": f"Answer {i}"},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    questions = [
        q async for q in bank.get_questions(session=async_test_session, limit=10)
    ]

    assert len(questions) == 3


@pytest.mark.asyncio
async def test_empty_question_bank(async_test_session):
    teacher_id = uuid4()
    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=[], cache=cache)

    questions = [
        q async for q in bank.get_questions(session=async_test_session, limit=5)
    ]

    assert len(questions) == 0


@pytest.mark.asyncio
async def test_warmup_cache_loads_all_questions(async_test_session):
    category = await CategoryDAO.create("Science", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(5):
        question_data = {
            "text": f"Science question {i}",
            "answer": {"correct": f"Answer {i}"},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    await bank.warmup_cache(session=async_test_session)

    for q_id in question_ids:
        assert cache.get(q_id) is not None


@pytest.mark.asyncio
async def test_warmup_cache_specific_questions(async_test_session):
    category = await CategoryDAO.create("Economics", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(5):
        question_data = {
            "text": f"Economics {i}",
            "answer": {"correct": f"Answer {i}"},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    warmup_ids = question_ids[:2]
    await bank.warmup_cache(session=async_test_session, question_ids=warmup_ids)

    assert cache.get(question_ids[0]) is not None
    assert cache.get(question_ids[1]) is not None
    assert cache.get(question_ids[2]) is None
    assert cache.get(question_ids[3]) is None
    assert cache.get(question_ids[4]) is None


@pytest.mark.asyncio
async def test_warmup_cache_skips_already_cached(async_test_session):
    category = await CategoryDAO.create("Philosophy", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(3):
        question_data = {
            "text": f"Philosophy {i}",
            "answer": {"correct": f"Answer {i}"},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    first_question = await QuestionDAO.get(question_ids[0], session=async_test_session)
    cache.set(first_question)

    await bank.warmup_cache(session=async_test_session)

    assert cache.get(question_ids[0]) is not None
    assert cache.get(question_ids[1]) is not None
    assert cache.get(question_ids[2]) is not None


@pytest.mark.asyncio
async def test_lazy_loading_uses_warmed_cache(async_test_session):
    category = await CategoryDAO.create("Engineering", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(3):
        question_data = {
            "text": f"Engineering {i}",
            "answer": {"correct": f"Answer {i}"},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    await bank.warmup_cache(session=async_test_session)

    questions = [
        q async for q in bank.get_questions(session=async_test_session, limit=3)
    ]

    for q in questions:
        assert not q._loaded
        text = await q.text()
        assert q._loaded
        assert "Engineering" in text

@pytest.mark.asyncio
async def test_get_all_teacher_questions(async_test_session):
    category = await CategoryDAO.create("Biology", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(4):
        question_data = {
            "text": f"Biology question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    questions = await bank.get_all_teacher_questions(session=async_test_session)

    assert len(questions) == 4
    for q in questions:
        assert q.teacher_id == teacher_id

@pytest.mark.asyncio
async def test_delete_question_removes_from_cache(async_test_session):
    category = await CategoryDAO.create("Chemistry", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "Chemistry question",
        "answer": {"correct": "H2O"},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Problem",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }
    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    cache.set(question)
    bank = TestBank(owner_id=teacher_id, question_ids=[question.id], cache=cache)

    assert cache.get(question.id) is not None

    await bank.delete_question(question.id, session=async_test_session)
    await async_test_session.commit()

    assert cache.get(question.id) is None

@pytest.mark.asyncio
async def test_delete_question_removes_from_question_ids(async_test_session):
    category = await CategoryDAO.create("Art", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "Art question",
        "answer": {"correct": "Picasso"},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Problem",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }
    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=[question.id], cache=cache)

    assert question.id in bank.question_ids

    await bank.delete_question(question.id, session=async_test_session)
    await async_test_session.commit()

    assert question.id not in bank.question_ids

@pytest.mark.asyncio
async def test_delete_question_from_database(async_test_session):
    category = await CategoryDAO.create("Music", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "Music question",
        "answer": {"correct": "Bach"},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Problem",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }
    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=[question.id], cache=cache)

    await bank.delete_question(question.id, session=async_test_session)
    await async_test_session.commit()

    with pytest.raises(QuestionNotFoundError):
        await QuestionDAO.get(question.id, session=async_test_session)

@pytest.mark.asyncio
async def test_search_questions_by_category(async_test_session):
    category1 = await CategoryDAO.create("English", session=async_test_session)
    category2 = await CategoryDAO.create("Spanish", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(2):
        question_data = {
            "text": f"English question {i}",
            "answer": {"correct": i},
            "category_id": category1.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    question_data = {
        "text": "Spanish question",
        "answer": {"correct": 1},
        "category_id": category2.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Problem",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }
    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    questions = await bank.search_questions(session=async_test_session, category_id=category1.id)

    assert len(questions) == 2
    for q in questions:
        assert q.category_id == category1.id

@pytest.mark.asyncio
async def test_search_questions_by_multiple_filters(async_test_session):
    category = await CategoryDAO.create("Programming", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(3):
        question_data = {
            "text": f"Programming question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text" if i < 2 else "multiple_choice",
            "problem": f"Problem {i}",
            "mark_out_of": 10 if i == 0 else 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    questions = await bank.search_questions(
        session=async_test_session,
        question_type="text",
        mark_out_of=10
    )

    assert len(questions) == 1
    assert questions[0].question_type.value == "text"
    assert questions[0].mark_out_of == 10

@pytest.mark.asyncio
async def test_search_questions_returns_empty_when_no_matches(async_test_session):
    category = await CategoryDAO.create("Statistics", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()

    question_data = {
        "text": "Statistics question",
        "answer": {"correct": 1},
        "category_id": category.id,
        "teacher_id": teacher_id,
        "question_type": "text",
        "problem": "Problem",
        "mark_out_of": 5,
        "penalty": 0,
        "is_active": True,
    }
    question = await QuestionDAO.add_question(question_data, session=async_test_session)
    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=[question.id], cache=cache)

    questions = await bank.search_questions(session=async_test_session, mark_out_of=100)

    assert len(questions) == 0

@pytest.mark.asyncio
async def test_get_specific_questions_by_ids(async_test_session):
    category = await CategoryDAO.create("Computer Science", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(5):
        question_data = {
            "text": f"CS question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    specific_ids = [question_ids[1], question_ids[3]]
    questions = [
        q async for q in bank.get_questions(
            session=async_test_session,
            limit=2,
            question_ids=specific_ids
        )
    ]

    assert len(questions) == 2
    assert questions[0].id == question_ids[1]
    assert questions[1].id == question_ids[3]


@pytest.mark.asyncio
async def test_get_specific_questions_with_limit(async_test_session):
    category = await CategoryDAO.create("Mathematics", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(5):
        question_data = {
            "text": f"Math question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    specific_ids = [question_ids[0], question_ids[2], question_ids[4]]
    questions = [
        q async for q in bank.get_questions(
            session=async_test_session,
            limit=2,
            question_ids=specific_ids
        )
    ]

    assert len(questions) == 2
    assert questions[0].id in specific_ids
    assert questions[1].id in specific_ids


@pytest.mark.asyncio
async def test_get_specific_questions_random_order(async_test_session):
    category = await CategoryDAO.create("Physics", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(5):
        question_data = {
            "text": f"Physics question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    specific_ids = [question_ids[0], question_ids[1], question_ids[2]]
    questions = [
        q async for q in bank.get_questions(
            session=async_test_session,
            limit=3,
            question_ids=specific_ids,
            random_order=True
        )
    ]

    assert len(questions) == 3
    result_ids = [q.id for q in questions]
    assert set(result_ids) == set(specific_ids)


@pytest.mark.asyncio
async def test_get_questions_without_specific_ids_uses_bank_ids(async_test_session):
    category = await CategoryDAO.create("Chemistry", session=async_test_session)
    await async_test_session.commit()

    teacher_id = uuid4()
    question_ids = []

    for i in range(3):
        question_data = {
            "text": f"Chemistry question {i}",
            "answer": {"correct": i},
            "category_id": category.id,
            "teacher_id": teacher_id,
            "question_type": "text",
            "problem": f"Problem {i}",
            "mark_out_of": 5,
            "penalty": 0,
            "is_active": True,
        }
        question = await QuestionDAO.add_question(question_data, session=async_test_session)
        question_ids.append(question.id)

    await async_test_session.commit()

    cache = QuestionCache()
    bank = TestBank(owner_id=teacher_id, question_ids=question_ids, cache=cache)

    questions = [
        q async for q in bank.get_questions(session=async_test_session, limit=3)
    ]

    assert len(questions) == 3
    result_ids = [q.id for q in questions]
    assert result_ids == question_ids