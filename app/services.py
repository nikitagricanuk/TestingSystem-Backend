import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from redis_om import get_redis_connection

from .models import TestSession, Question, QuestionRedis, SessionStatus


def init_redis_connection():
    """Initializes the Redis connection based on .env file."""
    return get_redis_connection(
        url="redis://localhost:6379",
        decode_responses=True
    )


def load_questions_from_json(file_path: str):
    """Loads questions from a JSON file and saves them to Redis."""
    redis = init_redis_connection()
    with open(file_path, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    question_ids = []
    for q_data in questions_data:
        question_obj = QuestionRedis(**q_data)
        question_obj.save()
        question_ids.append(question_obj.question_id)
    print(f"Loaded {len(question_ids)} questions into Redis.")
    return question_ids


def create_session(user_id: uuid.UUID, test_id: uuid.UUID, question_ids: List[uuid.UUID], indefinite_questions: bool,
                   ip_address: str) -> TestSession:
    """Creates and initializes a new test session in Redis."""
    if not question_ids:
        raise ValueError("Cannot create a session without questions.")

    session = TestSession(
        sid=uuid.uuid4(),
        test_id=test_id,
        user_id=user_id,
        question_ids=question_ids,
        questions_remaining=len(question_ids),
        indefinite_questions=indefinite_questions,
        ip_address=ip_address
    )
    session.save()
    return session


def get_session(session_id: uuid.UUID) -> Optional[TestSession]:
    """Retrieves a session from Redis by its ID."""
    try:
        session = TestSession.get(f"{TestSession.Meta.model_key_prefix}:{session_id}")
        return session
    except TestSession.DoesNotExist:
        return None


def update_session_with_answer(session_id: uuid.UUID, question_index: int, answer: str) -> Optional[TestSession]:
    """Updates a session with an answer to the current question."""
    session = get_session(session_id)
    if not session or session.status != SessionStatus.ACTIVE:
        return None

    session.answers[question_index] = answer
    session.questions_answered += 1
    session.questions_remaining -= 1
    session.current_question_index += 1
    session.last_activity = datetime.utcnow()
    session.save()
    return session


def finish_session(session_id: uuid.UUID) -> Optional[TestSession]:
    """Finishes a session, calculates duration, and scores the session."""
    session = get_session(session_id)
    if not session or session.status == SessionStatus.FINISHED:
        return None

    session.status = SessionStatus.FINISHED
    session.time_finish = datetime.utcnow()
    session.duration = int((session.time_finish - session.time_start).total_seconds())

    # Get all questions associated with the session for scoring
    questions = [QuestionRedis.get(str(qid)) for qid in session.question_ids]

    score = score_session(session, questions)
    # You might want to save the score in the session or a separate model
    session.save()
    print(f"Session {session.sid} finished. Score: {score}")
    return session


def score_session(session: TestSession, questions: List[QuestionRedis]) -> float:
    """Calculates the score for a finished session."""
    correct_answers = 0
    question_map = {q.index: q.correct_answer for q in questions}

    for question_index, answer in session.answers.items():
        if question_map.get(question_index) == answer:
            correct_answers += 1

    total_questions = len(session.question_ids)
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0


def get_current_question(session: TestSession) -> Optional[QuestionRedis]:
    """Gets the current question for the session."""
    if session.current_question_index >= len(session.question_ids):
        return None

    current_qid = session.question_ids[session.current_question_index]
    return QuestionRedis.get(str(current_qid))