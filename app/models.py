import uuid
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum

from pydantic import BaseModel, Field
from redis_om import HashModel

class Question(BaseModel):
    index: int
    category: str
    content: str
    choices: List[str]
    correct_answer: str

class SessionStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CLOSED = "CLOSED"

class TestSession(HashModel):
    pk: str = Field(..., primary_key=True)
    sid: uuid.UUID = Field(default_factory=uuid.uuid4)
    test_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    time_start: datetime = Field(default_factory=datetime.utcnow)
    time_finish: Optional[datetime] = None
    duration: int = 0
    indefinite_questions: bool = False
    question_ids: List[uuid.UUID] = Field(default_factory=list)
    answers: Dict[int, str] = Field(default_factory=dict)
    questions_answered: int = 0
    questions_remaining: int
    current_question_index: int = 0
    status: SessionStatus = SessionStatus.CREATED
    ip_address: Optional[str] = None
    last_activity: datetime = Field(default_factory=datetime.utcnow)

    class Meta:
        model_key_prefix = "test_session"

class QuestionRedis(HashModel):
    question_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    index: int
    category: str
    content: str
    choices: List[str]
    correct_answer: str

    class Meta:
        model_key_prefix = "question"