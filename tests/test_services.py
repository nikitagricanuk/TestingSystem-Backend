import pytest
import uuid
import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

#Импортируем тестируемые функции и модели
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
from redis_om import get_redis_connection

# Фикстура для создания реального, но временного соединения с Redis
@pytest.fixture(scope="session")
def redis_client():
    # Эта фикстура использует реальный Redis,
    # что устраняет проблемы совместимости с fakeredis.
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        conn = get_redis_connection(url=redis_url, decode_responses=True)
        conn.ping()
        print("Connected to Redis for testing.")
        yield conn
        conn.flushall()  # Очищаем базу данных после всех тестов в сессии
    except Exception as e:
        pytest.skip(f"Could not connect to Redis at {redis_url}: {e}")


@pytest.fixture(autouse=True)
def set_redis_db(redis_client):
    # Убеждаемся, что все модели redis-om используют этот клиент.
    TestSession.Meta.database = redis_client
    QuestionRedis.Meta.database = redis_client
    yield
    redis_client.flushall()  # Очищаем базу данных после каждого теста


@pytest.fixture
def setup_test_questions():
    # Фикстура для создания тестовых вопросов в Redis.
    q_data = [
        {
            "question_id": str(uuid.uuid4()),
            "question_text": "Вопрос 1?",
            "choices": '["a", "b", "c"]',
            "correct_answer": "a",
            "question_type": "single_choice",
            "index": 0,
            "category": "Math",
            "content": "Easy",
        },
        {
            "question_id": str(uuid.uuid4()),
            "question_text": "Вопрос 2?",
            "choices": '["d", "e", "f"]',
            "correct_answer": "d",
            "question_type": "single_choice",
            "index": 1,
            "category": "History",
            "content": "Hard",
        },
    ]
    question_ids = []
    for data in q_data:
        q_obj = QuestionRedis(**data)
        q_obj.save()
        question_ids.append(q_obj.question_id)
    return question_ids


def test_init_redis_connection_success():
    # Тест успешного подключения к Redis.
    conn = init_redis_connection()
    assert conn is not None
    assert conn.ping()


def test_init_redis_connection_failure():
    # Тест неудачного подключения к Redis.
    with patch('app.services.get_redis_connection') as mock_conn:
        mock_conn.side_effect = ConnectionError
        with pytest.raises(ConnectionError):
            init_redis_connection()


def test_load_questions_from_json_success():
    # Тест загрузки вопросов из JSON-файла.
    test_questions = [
        {"question_id": str(uuid.uuid4()), "question_text": "Q1?", "choices": ["a"], "correct_answer": "a",
         "question_type": "single_choice", "index": 0, "category": "General", "content": "TestContent"},
        {"question_id": str(uuid.uuid4()), "question_text": "Q2?", "choices": ["b"], "correct_answer": "b",
         "question_type": "single_choice", "index": 1, "category": "General", "content": "TestContent"},
    ]
    with patch('builtins.open', new_callable=MagicMock) as mock_file:
        mock_file.return_value.__enter__.return_value.read.return_value = json.dumps(test_questions)
        question_ids = load_questions_from_json("dummy_path.json")

    assert len(question_ids) == 2


def test_create_session_success(setup_test_questions):
    # Тест создания сессии.
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    session = create_session(user_id, test_id, setup_test_questions, False, "127.0.0.1")

    assert session is not None
    assert session.sid
    assert session.user_id == user_id
    assert session.status == SessionStatus.ACTIVE


def test_get_session_success(setup_test_questions):
    # Тест получения сессии по ID.
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    session = create_session(user_id, test_id, setup_test_questions, False, "127.0.0.1")
    retrieved_session = get_session(session.sid)

    assert retrieved_session is not None
    assert retrieved_session.sid == session.sid
    assert retrieved_session.user_id == user_id


def test_update_session_with_answer(setup_test_questions):
    # Тест обновления сессии ответом.
    session = create_session(uuid.uuid4(), uuid.uuid4(), setup_test_questions, False, "127.0.0.1")
    updated_session = update_session_with_answer(session.sid, 0, "a")

    assert updated_session is not None
    assert updated_session.questions_answered == 1
    assert json.loads(updated_session.answers).get("0") == "a"


def test_finish_session(setup_test_questions):
    # Тест завершения сессии и подсчёта очков.
    session = create_session(uuid.uuid4(), uuid.uuid4(), setup_test_questions, False, "127.0.0.1")
    session = update_session_with_answer(session.sid, 0, "a")
    session = update_session_with_answer(session.sid, 1, "f")
    final_session = finish_session(session.sid)

    assert final_session is not None
    assert final_session.status == SessionStatus.FINISHED


def test_score_session(setup_test_questions):
    # Тест подсчёта очков.
    session = TestSession(
        sid=uuid.uuid4(),
        test_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        question_ids=json.dumps([str(qid) for qid in setup_test_questions]),
        questions_remaining=0,
        indefinite_questions=False,
        ip_address="127.0.0.1",
        answers=json.dumps({"0": "a", "1": "f"}),
        questions_answered=2,
        current_question_index=2,
        status=SessionStatus.FINISHED
    )

    session.save()

    questions = [QuestionRedis.get(qid) for qid in json.loads(session.question_ids)]
    score = score_session(session, questions)
    assert score == 50.0


def test_get_current_question(setup_test_questions):
    # Тест получения текущего вопроса.
    session = create_session(uuid.uuid4(), uuid.uuid4(), setup_test_questions, False, "127.0.0.1")

    current_question = get_current_question(session)
    assert current_question is not None
    assert current_question.question_id == setup_test_questions[0]

    update_session_with_answer(session.sid, 0, "a")
    updated_session = get_session(session.sid)
    next_question = get_current_question(updated_session)
    assert next_question is not None
    assert next_question.question_id == setup_test_questions[1]