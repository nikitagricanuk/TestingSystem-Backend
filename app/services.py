import json
import os
import uuid
import time
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime

from redis_om import get_redis_connection, NotFoundError
from redis.exceptions import ConnectionError
from redis import Redis
from uuid import UUID

from app.models import TestSession, Question, QuestionRedis, SessionStatus


def init_redis_connection() -> Redis:
    #Initializes the Redis connection based on environment variable with retries.
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable is not set.")

    retries = 5
    delay = 2
    for i in range(retries):
        try:
            conn = get_redis_connection(
                url=redis_url,
                decode_responses=True
            )
            conn.ping()
            print("Successfully connected to Redis!")
            return conn
        except ConnectionError as e:
            print(f"Attempt {i + 1} of {retries}: Could not connect to Redis. Retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= 2

    raise ConnectionError("Failed to connect to Redis after multiple attempts.")


def load_questions_from_json(file_path: str):
    #Загружает вопросы из JSON-файла и сохраняет их в Redis.
    with open(file_path, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    question_ids = []
    print("Starting to save questions.")

    for q_data in questions_data:
        #Убедимся, что все необходимые поля присутствуют
        q_data['choices'] = json.dumps(q_data.get('choices', []))
        question_obj = QuestionRedis(**q_data)
        question_obj.save() #ИСПОЛЬЗУЕМ .save()
        question_ids.append(question_obj.question_id)

    print(f"Loaded {len(question_ids)} questions into Redis.")
    return question_ids


def create_session(user_id: uuid.UUID, test_id: uuid.UUID, question_ids: List[uuid.UUID], indefinite_questions: bool,
                   ip_address: str) -> TestSession:
    #Creates and initializes a new test session in Redis.
    if not question_ids:
        raise ValueError("Cannot create a session without questions.")

    session = TestSession(
        sid=uuid.uuid4(),
        test_id=test_id,
        user_id=user_id,
        question_ids=json.dumps([str(qid) for qid in question_ids]),
        questions_remaining=len(question_ids),
        indefinite_questions=indefinite_questions,
        ip_address=ip_address,
        answers=json.dumps({}),
        questions_answered=0,
        current_question_index=0,
        status=SessionStatus.ACTIVE.value,
    )

    #Используем .save() от redis-om, убираем ручной hset
    session.save()
    return session


def get_session(session_id: uuid.UUID) -> Optional[TestSession]:
    #Retrieves a session from Redis by its ID.
    try:
        #Используем .get() от redis-om, убираем ручной hgetall
        return TestSession.get(session_id)
    except NotFoundError:
        print(f"Session with sid {session_id} not found.")
        return None
    except Exception as e:
        print(f"Error getting session: {e}")
        return None


def update_session_with_answer(session_id: uuid.UUID, question_index: int, answer: str) -> Optional[TestSession]:
    #Updates a session with an answer to the current question.
    session = get_session(session_id)
    if not session or session.status != SessionStatus.ACTIVE:
        return None

    #Десериализуем ответы из JSON-строки в словарь
    answers_dict = json.loads(session.answers)
    answers_dict[question_index] = answer

    session.questions_answered += 1
    session.questions_remaining -= 1
    session.current_question_index += 1
    session.last_activity = datetime.now()
    #Сериализуем словарь ответов обратно в JSON-строку
    session.answers = json.dumps(answers_dict)

    session.save()
    return session


def finish_session(session_id: uuid.UUID) -> Optional[TestSession]:
    # Завершает сессию, вычисляет длительность и оценивает ее.
    session = get_session(session_id)
    if not session or session.status == SessionStatus.FINISHED:
        return None

    session.status = SessionStatus.FINISHED
    session.time_finish = datetime.now()
    session.duration = int((session.time_finish - session.time_start).total_seconds())

    question_ids = json.loads(session.question_ids)
    questions = [QuestionRedis.get(qid) for qid in question_ids]

    score = score_session(session, questions)
    session.save()
    print(f"Session {session.sid} finished. Score: {score}")
    return session


def score_session(session: TestSession, questions: List[QuestionRedis]) -> float:
    #Вычисляет оценку для завершенной сессии.
    correct_answers = 0
    session_answers = json.loads(session.answers)
    question_map = {q.index: q.correct_answer for q in questions}

    for question_index, answer in session_answers.items():
        if question_map.get(int(question_index)) == answer:
            correct_answers += 1

    total_questions = len(questions)
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0


def get_current_question(session: TestSession) -> Optional[QuestionRedis]:
    # Получает текущий вопрос для сессии.
    if session.current_question_index >= len(session.question_ids):
        return None

    current_qid = session.question_ids[session.current_question_index]
    question_obj = QuestionRedis.get(str(current_qid))  #ОБРАТИТЕ ВНИМАНИЕ НА str(current_qid)
    question_obj.choices = json.loads(question_obj.choices)

    return question_obj