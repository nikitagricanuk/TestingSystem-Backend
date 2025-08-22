import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import Field, validator
from redis_om import HashModel

class SessionStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CLOSED = "CLOSED"

class TestSession(HashModel):
    sid: str = Field(primary_key=True)
    test_id: str = Field(index=True)
    user_id: str = Field(index=True)
    time_start: datetime = Field(default_factory=datetime.utcnow)
    time_finish: Optional[datetime] = None
    duration: int = 0
    indefinite_questions: int = Field(index=False, default=0)
    question_ids: str  # Вернуть тип на 'str'
    answers: str = Field(index=False)
    questions_answered: int = 0
    questions_remaining: int = Field(index=False)
    current_question_index: int = 0
    status: SessionStatus = SessionStatus.CREATED
    ip_address: Optional[str] = Field(index=False)
    last_activity: datetime = Field(default_factory=datetime.utcnow, index=False)

    @validator('time_start', 'time_finish', pre=True)
    def parse_datetime(cls, v):
        if v is None or v == "":  # <--- Добавили проверку на пустую строку
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(v)
        except (ValueError, TypeError):
            # Попробуйте другие форматы, если fromisoformat не сработал
            return datetime.strptime(v, "%Y-%m-%d %H:%M:%S.%f")

    class Meta:
        model_key_prefix = "test_session"

class QuestionRedis(HashModel):
    question_id: str = Field(index=True, primary_key=True)
    index: int = Field(index=True)
    category: str = Field(index=False)
    content: str = Field(index=False)
    choices: str  # Вернуть тип на 'str'
    correct_answer: str = Field(index=False)

    class Meta:
        model_key_prefix = "question"