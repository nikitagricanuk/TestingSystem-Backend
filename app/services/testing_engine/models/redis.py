import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import Field, validator
from aredis_om import HashModel


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CLOSED = "CLOSED"


class Session(HashModel):
    sid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    test_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True)
    user_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True)
    time_start: datetime = Field(default_factory=datetime.utcnow)
    time_finish: Optional[datetime] = None
    indefinite_questions: int = Field(index=False, default=0)
    question_ids: str  # JSON list of UUIDs
    questions_remaining: int = 0
    questions_answered: int = 0
    answers: str = Field(default="{}")
    current_question_index: int = 0
    status: SessionStatus = SessionStatus.CREATED
    ip_address: Optional[str] = Field(index=False)
    device_type: Optional[str] = Field(index=False)
    last_activity: datetime = Field(default_factory=datetime.utcnow, index=False)
    duration: Optional[int] = Field(index=False, default=None)
    score: Optional[float] = Field(index=False, default=None)

    @validator('time_start', 'time_finish', pre=True)
    def parse_datetime(cls, v):
        if v is None or v == "":  # Проверка на пустую строку
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(v)
        except (ValueError, TypeError):
            return datetime.strptime(v, "%Y-%m-%d %H:%M:%S.%f")

    class Meta:
        model_key_prefix = "test_session"


class QuestionRedis(HashModel):
    question_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True, primary_key=True)
    index: str = Field(index=True)
    category: str = Field(index=False)
    content: str = Field(index=False)
    choices: str  # Вернуть тип на 'str'
    correct_answer: str = Field(index=False)

    class Meta:
        model_key_prefix = "question"
