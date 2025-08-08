import json
import os
import uuid
import time
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime

from redis_om import get_redis_connection
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
    #Loads questions from a JSON file and saves them to Redis.
    redis_client = init_redis_connection()
    with open(file_path, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    question_ids = []

    print("Waiting 5 seconds for Redis to fully initialize...")
    time.sleep(5)
    print("Starting to save questions.")

    for q_data in questions_data:
        q_data['choices'] = json.dumps(q_data.get('choices', []))
        question_obj = QuestionRedis(**q_data)

        document = question_obj.dict()

        for key, value in document.items():
            if isinstance(value, UUID):
                document[key] = str(value)

        try:
            redis_client.hset(question_obj.key(), mapping=document)
            question_ids.append(question_obj.question_id)
        except ConnectionError as e:
            print(f"Failed to save question: {e}")
            raise

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
    )

    redis_client = init_redis_connection()
    document = session.dict()

    #Преобразуем все неподдерживаемые типы в строки
    for key, value in document.items():
        if value is None:
            document[key] = ""  # Преобразуем None в пустую строку
        elif isinstance(value, (uuid.UUID, datetime)):
            document[key] = str(value)
        elif isinstance(value, Enum):
            document[key] = value.value
        elif isinstance(value, bool):
            document[key] = str(value)

    try:
        redis_client.hset(session.key(), mapping=document)
    except ConnectionError as e:
        print(f"Failed to save session: {e}")
        raise

    return session


def get_session(session_id: uuid.UUID) -> Optional[TestSession]:
    #Retrieves a session from Redis by its ID.
    try:
        redis_client = init_redis_connection()
        session_key = f"{TestSession.Meta.model_key_prefix}:{session_id}"

        session_data = redis_client.hgetall(session_key)

        if not session_data:
            return None

        session_data['sid'] = uuid.UUID(session_data['sid'])
        session_data['test_id'] = uuid.UUID(session_data['test_id'])
        session_data['user_id'] = uuid.UUID(session_data['user_id'])
        session_data['status'] = SessionStatus(session_data['status'])

        # Десериализация datetime
        session_data['time_start'] = datetime.fromisoformat(session_data['time_start'])
        if session_data['time_finish']:
            session_data['time_finish'] = datetime.fromisoformat(session_data['time_finish'])
        if session_data['last_activity']:
            session_data['last_activity'] = datetime.fromisoformat(session_data['last_activity'])

        return TestSession(**session_data)

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
    session.last_activity = datetime.utcnow()
    #Сериализуем словарь ответов обратно в JSON-строку
    session.answers = json.dumps(answers_dict)

    session.save()
    return session


def finish_session(session_id: uuid.UUID) -> Optional[TestSession]:
    #Finishes a session, calculates duration, and scores the session.
    session = get_session(session_id)
    if not session or session.status == SessionStatus.FINISHED:
        return None

    session.status = SessionStatus.FINISHED
    session.time_finish = datetime.utcnow()
    session.duration = int((session.time_finish - session.time_start).total_seconds())

    #Десериализуем список question_ids из JSON-строки для получения вопросов
    question_ids = json.loads(session.question_ids)
    questions = [QuestionRedis.get(qid) for qid in question_ids]

    score = score_session(session, questions)
    #You might want to save the score in the session or a separate model
    session.save()
    print(f"Session {session.sid} finished. Score: {score}")
    return session


def score_session(session: TestSession, questions: List[QuestionRedis]) -> float:
    #Calculates the score for a finished session.
    correct_answers = 0

    #Десериализуем ответы из JSON-строки
    session_answers = json.loads(session.answers)

    question_map = {}
    for q in questions:
        question_map[q.index] = q.correct_answer

    for question_index, answer in session_answers.items():
        if question_map.get(int(question_index)) == answer:
            correct_answers += 1

    total_questions = len(questions)
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0


def get_current_question(session: TestSession) -> Optional[QuestionRedis]:
    #Gets the current question for the session.
    #Десериализуем список question_ids из JSON-строки
    question_ids = json.loads(session.question_ids)
    if session.current_question_index >= len(question_ids):
        return None

    current_qid = question_ids[session.current_question_index]
    question_obj = QuestionRedis.get(current_qid)

    #Десериализуем список choices из JSON-строки для возвращаемого объекта
    question_obj.choices = json.loads(question_obj.choices)

    return question_obj