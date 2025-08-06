import uuid
import pytest
from datetime import datetime

from app.models import TestSession, SessionStatus
from app.services import create_session, get_session, update_session_with_answer, finish_session, \
    score_session, load_questions_from_json


# This will connect to a test Redis instance or a mock, depending on your setup.
# For simplicity, this example assumes a connection to a local Redis.
# In a real scenario, you would use a mock for Redis.

@pytest.fixture(scope="session", autouse=True)
def setup_questions():
    """Fixture to load questions once for all tests."""
    questions_file = "questions.json"
    question_ids = load_questions_from_json(questions_file)
    return question_ids


@pytest.fixture
def session(setup_questions):
    """Fixture to create a new session for each test."""
    question_ids = setup_questions
    session = create_session(
        user_id=uuid.uuid4(),
        test_id=uuid.uuid4(),
        question_ids=question_ids,
        indefinite_questions=False,
        ip_address="127.0.0.1"
    )
    yield session
    # Cleanup session after test
    TestSession.delete(session.pk)


def test_create_session(session):
    """Test that a session is created correctly."""
    assert isinstance(session, TestSession)
    assert session.status == SessionStatus.CREATED
    assert session.questions_answered == 0
    assert len(session.question_ids) > 0


def test_get_session(session):
    """Test retrieving a session by its ID."""
    retrieved_session = get_session(session.sid)
    assert retrieved_session is not None
    assert retrieved_session.sid == session.sid


def test_update_session_with_answer(session):
    """Test answering a question and updating the session state."""
    session.status = SessionStatus.ACTIVE
    session.save()

    updated_session = update_session_with_answer(session.sid, 0, "correct_answer_1")
    assert updated_session is not None
    assert updated_session.questions_answered == 1
    assert updated_session.questions_remaining == len(updated_session.question_ids) - 1
    assert updated_session.answers.get(0) == "correct_answer_1"
    assert updated_session.last_activity > session.last_activity


def test_finish_session(session):
    """Test finishing a session and score calculation."""
    session.status = SessionStatus.ACTIVE
    session.answers = {0: "answer", 1: "answer"}
    session.save()

    finished_session = finish_session(session.sid)
    assert finished_session is not None
    assert finished_session.status == SessionStatus.FINISHED
    assert finished_session.time_finish is not None
    assert finished_session.duration >= 0


def test_score_session():
    """Test the score calculation function with dummy data."""
    # This is a simplified test without Redis interaction
    questions = [
        {"index": 0, "correct_answer": "A"},
        {"index": 1, "correct_answer": "B"},
        {"index": 2, "correct_answer": "C"}
    ]

    mock_session = TestSession(
        sid=uuid.uuid4(),
        answers={0: "A", 1: "D"},  # 1 correct, 1 incorrect
        question_ids=["q1", "q2"],
        questions_answered=2,
        questions_remaining=0,
    )

    # We need to create a list of QuestionRedis objects
    mock_questions = [
        QuestionRedis(index=0, correct_answer="A", question_id="q1", category="", content="", choices=[]),
        QuestionRedis(index=1, correct_answer="B", question_id="q2", category="", content="", choices=[])
    ]

    score = score_session(mock_session, mock_questions)
    assert score == 50.0