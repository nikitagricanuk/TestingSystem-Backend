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


#Имитируем соединение с Redis
@pytest.fixture
def mock_redis_client():
    #Фикстура для моккирования клиента Redis с использованием fakeredis и имитации поведения `redis-py`
    from fakeredis import FakeStrictRedis
    r = FakeStrictRedis(decode_responses=True)
    yield r
    r.flushall()  #Очищаем базу данных после каждого теста


@pytest.fixture(autouse=True)
def mock_get_redis_connection(mock_redis_client):
    #Фикстура для перехвата вызова `get_redis_connection` и возврата мок-клиента.
    with patch('app.services.get_redis_connection', return_value=mock_redis_client):
        yield


@pytest.fixture
def setup_test_questions(mock_redis_client):
    #Фикстура для создания тестовых вопросов в мок-Redis.
    q_data = [
        {
            "question_id": "1a0e8d0e-2c9c-48b4-8b65-e11a2f64f43c",
            "question_text": "Вопрос 1?",
            "choices": '["a", "b", "c"]',
            "correct_answer": "a",
            "question_type": "single_choice",
            "index": 0,
            "category": "Math",
            "content": "Easy",
        },
        {
            "question_id": "2b1f9e1f-3d0d-49c5-9c76-f22b3f75f54d",
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
        q = QuestionRedis(**data)
        mock_redis_client.hset(f"question:{q.question_id}", mapping=q.model_dump(mode="json"))
        question_ids.append(q.question_id)
    return question_ids


def test_init_redis_connection_success():
    #Тест успешного подключения к Redis.
    with patch('app.services.get_redis_connection') as mock_conn:
        mock_conn.return_value.ping.return_value = True
        conn = init_redis_connection()
        assert conn is not None
        mock_conn.assert_called()


def test_init_redis_connection_failure():
    #Тест неудачного подключения к Redis.
    with patch('app.services.get_redis_connection') as mock_conn:
        mock_conn.side_effect = ConnectionError
        #Используем pytest.raises, чтобы проверить, что исключение выбрасывается
        with pytest.raises(ConnectionError):
            init_redis_connection()
        #Теперь мы можем проверить, что функция вызывалась
        assert mock_conn.call_count > 0


def test_load_questions_from_json_success(mock_redis_client):
    #Тест загрузки вопросов из JSON-файла.
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
    assert mock_redis_client.dbsize() == 2


def test_create_session_success(mock_redis_client, setup_test_questions):
    #Тест создания сессии.
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    session = create_session(user_id, test_id, setup_test_questions, False, "127.0.0.1")

    assert session is not None
    assert mock_redis_client.dbsize() == 3  # 2 вопроса + 1 сессия

    saved_session_data = mock_redis_client.hgetall(f"test_session:{session.sid}")
    assert saved_session_data['user_id'] == str(user_id)
    assert saved_session_data['status'] == SessionStatus.ACTIVE.value


def test_get_session_success(mock_redis_client, setup_test_questions):
    #Тест получения сессии по ID.
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    session = create_session(user_id, test_id, setup_test_questions, False, "127.0.0.1")

    retrieved_session = get_session(session.sid)

    assert retrieved_session is not None
    assert retrieved_session.sid == session.sid
    assert retrieved_session.user_id == user_id


def test_update_session_with_answer(mock_redis_client, setup_test_questions):
    #Тест обновления сессии ответом.
    session = create_session(uuid.uuid4(), uuid.uuid4(), setup_test_questions, False, "127.0.0.1")
    updated_session = update_session_with_answer(session.sid, 0, "a")

    assert updated_session is not None
    assert updated_session.questions_answered == 1
    assert json.loads(updated_session.answers).get("0") == "a"


def test_finish_session(mock_redis_client, setup_test_questions):
    #Тест завершения сессии и подсчёта очков.
    session = create_session(uuid.uuid4(), uuid.uuid4(), setup_test_questions, False, "127.0.0.1")
    session = update_session_with_answer(session.sid, 0, "a")  # Правильный ответ
    session = update_session_with_answer(session.sid, 1, "f")  # Неправильный ответ

    final_session = finish_session(session.sid)

    assert final_session is not None
    assert final_session.status == SessionStatus.FINISHED


def test_score_session(setup_test_questions):
    #Тест подсчёта очков.
    #Создаем сессию с ответами
    session = TestSession(
        sid=uuid.uuid4(),
        test_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        question_ids=json.dumps([str(qid) for qid in setup_test_questions]),
        questions_remaining=0,
        indefinite_questions=False,
        ip_address="127.0.0.1",
        answers=json.dumps({"0": "a", "1": "f"}),  # Правильный и неправильный ответы
        questions_answered=2,
        current_question_index=2,
    )

    #Получаем вопросы из фикстуры
    question1_data = {"question_id": setup_test_questions[0], "question_text": "Q1?", "choices": '["a"]',
                      "correct_answer": "a", "question_type": "single_choice"}
    question2_data = {"question_id": setup_test_questions[1], "question_text": "Q2?", "choices": '["d"]',
                      "correct_answer": "d", "question_type": "single_choice"}

    questions = [QuestionRedis(**question1_data), QuestionRedis(**question2_data)]

    score = score_session(session, questions)

    assert score == 50.0  #Один правильный ответ из двух


def test_get_current_question(mock_redis_client, setup_test_questions):
    #Тест получения текущего вопроса.
    session = create_session(uuid.uuid4(), uuid.uuid4(), setup_test_questions, False, "127.0.0.1")

    current_question = get_current_question(session)

    assert current_question is not None
    assert current_question.question_id == setup_test_questions[0]

    #Обновляем сессию, чтобы перейти ко второму вопросу
    update_session_with_answer(session.sid, 0, "a")
    updated_session = get_session(session.sid)

    next_question = get_current_question(updated_session)
    assert next_question is not None
    assert next_question.question_id == setup_test_questions[1]