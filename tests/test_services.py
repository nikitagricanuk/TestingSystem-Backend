import pytest
import uuid
import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.services import (
    init_redis_connection,
    load_questions_from_json,
    create_session,
    get_session,
    update_session_with_answer,
    finish_session,
    score_session,
    get_current_question,
)
from app.models import TestSession, QuestionRedis, SessionStatus
from redis_om import get_redis_connection, NotFoundError

@pytest.fixture(scope="function", autouse=True)
def redis_client():
    conn = get_redis_connection(url=os.getenv("REDIS_URL", "redis://redis:6379/13"))

    # Явное удаление всех индексов до и после каждого теста
    QuestionRedis.Meta.database = conn
    TestSession.Meta.database = conn

    try:
        QuestionRedis.drop_indexes()
        TestSession.drop_indexes()
    except:
        pass # Игнорирование ошибки, если индексы еще не существуют

    conn.flushall()

    yield conn

    conn.flushall()


def test_load_questions_from_json_success(redis_client):
    test_questions = [
        {"question_id": str(uuid.uuid4()), "question_text": "Q1?", "choices": ["a"], "correct_answer": "a",
         "question_type": "single_choice", "index": 0, "category": "General", "content": "TestContent"},
        {"question_id": str(uuid.uuid4()), "question_text": "Q2?", "choices": ["b"], "correct_answer": "b",
         "question_type": "single_choice", "index": 1, "category": "General", "content": "TestContent"},
    ]
    with patch('builtins.open', new_callable=MagicMock) as mock_file:
        mock_file.return_value.__enter__.return_value.read.return_value = json.dumps(test_questions)
        question_ids = load_questions_from_json("dummy_path.json", redis_client)

    assert len(question_ids) == 2


def test_create_session_success(redis_client):
    q1 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q1?", choices=json.dumps(["a"]),
                       correct_answer="a", question_type="single_choice", index=0, category="Test", content="Easy")
    q2 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q2?", choices=json.dumps(["b"]),
                       correct_answer="b", question_type="single_choice", index=1, category="Test", content="Easy")
    q1.save()
    q2.save()
    question_ids = [q1.pk, q2.pk]

    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    session = create_session(user_id, test_id, question_ids, False, "127.0.0.1", redis_client)

    assert session is not None
    assert isinstance(session.sid, uuid.UUID)
    assert session.user_id == user_id
    assert session.status == SessionStatus.ACTIVE.value

    retrieved_session = TestSession.get(session.pk)
    assert retrieved_session is not None
    assert json.loads(retrieved_session.question_ids) == question_ids


def test_get_session_success(redis_client):
    q1 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q1?", choices=json.dumps(["a"]),
                       correct_answer="a", question_type="single_choice", index=0, category="Test", content="Easy")
    q1.save()
    question_ids = [q1.pk]
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    session = create_session(user_id, test_id, question_ids, False, "127.0.0.1", redis_client)
    retrieved_session = get_session(session.pk, redis_client)

    assert retrieved_session is not None
    assert retrieved_session.sid == session.sid
    assert str(retrieved_session.user_id) == str(user_id)


def test_update_session_with_answer(redis_client):
    q1 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q1?", choices=json.dumps(["a"]),
                       correct_answer="a", question_type="single_choice", index=0, category="Test", content="Easy")
    q1.save()
    question_ids = [q1.pk]

    session = create_session(uuid.uuid4(), uuid.uuid4(), question_ids, False, "127.0.0.1", redis_client)
    updated_session = update_session_with_answer(session.pk, 0, "a", redis_client)

    assert updated_session is not None
    assert updated_session.questions_answered == 1
    assert json.loads(updated_session.answers).get("0") == "a"


def test_finish_session(redis_client):
    q1 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q1?", choices=json.dumps(["a"]),
                       correct_answer="a", question_type="single_choice", index=0, category="Test", content="Easy")
    q2 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q2?", choices=json.dumps(["d"]),
                       correct_answer="d", question_type="single_choice", index=1, category="Test", content="Hard")
    q1.save()
    q2.save()

    assert QuestionRedis.get(q1.pk) is not None
    assert QuestionRedis.get(q2.pk) is not None

    question_ids = [q1.pk, q2.pk]

    # Создаем сессию и получаем объект
    session = create_session(uuid.uuid4(), uuid.uuid4(), question_ids, False, "127.0.0.1", redis_client)

    # Обновляем сессию и работаем с возвращаемым объектом
    session = update_session_with_answer(session.pk, 0, "a", redis_client)
    session = update_session_with_answer(session.pk, 1, "f", redis_client)

    # Передаем сам объект сессии в finish_session
    final_session = finish_session(session, redis_client)

    assert final_session is not None
    assert final_session.status == SessionStatus.FINISHED.value


def test_score_session(redis_client):
    q1 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q1?", choices=json.dumps(["a"]),
                       correct_answer="a", question_type="single_choice", index=0, category="Test", content="Easy")
    q2 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q2?", choices=json.dumps(["d"]),
                       correct_answer="d", question_type="single_choice", index=1, category="Test", content="Hard")
    q1.save()
    q2.save()
    # Измените эту строку
    question_ids = [q1.pk, q2.pk]

    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    session = create_session(user_id, test_id, question_ids, False, "127.0.0.1", redis_client)

    session.answers = json.dumps({"0": "a", "1": "d"})
    session.questions_answered = 2
    session.current_question_index = 2
    session.status = SessionStatus.FINISHED.value
    session.time_finish = datetime.utcnow()
    session.save()

    # Получаем объекты вопросов для score_session
    questions = [QuestionRedis.get(qid) for qid in question_ids]
    # Передаем объекты сессии и вопросов
    score = score_session(session, questions, redis_client)
    assert score == 100.0


def test_get_current_question(redis_client):
    q1 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q1?", choices=json.dumps(["a", "b", "c"]),
                       correct_answer="a", question_type="single_choice", index=0, category="Test", content="Easy")
    q2 = QuestionRedis(question_id=uuid.uuid4(), question_text="Q2?", choices=json.dumps(["d", "e", "f"]),
                       correct_answer="d", question_type="single_choice", index=1, category="Test", content="Hard")
    q1.save()
    q2.save()

    question_ids = [q1.pk, q2.pk]

    # Создаем сессию и получаем объект
    session = create_session(uuid.uuid4(), uuid.uuid4(), question_ids, False, "127.0.0.1", redis_client)

    # Передаем объект сессии напрямую в get_current_question
    current_question = get_current_question(session, redis_client)
    assert current_question is not None
    assert current_question.pk == question_ids[0]
    assert current_question.choices == ["a", "b", "c"]

    # Обновляем сессию и получаем новый объект
    updated_session = update_session_with_answer(session.pk, 0, "a", redis_client)
    # Передаем обновленный объект
    next_question = get_current_question(updated_session, redis_client)
    assert next_question is not None
    assert next_question.pk == question_ids[1]
    assert next_question.choices == ["d", "e", "f"]