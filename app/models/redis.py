import json
import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import Field, validator
from aredis_om import HashModel, JsonModel


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CLOSED = "CLOSED"


class TestSession(HashModel):
    sid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    test_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True)
    user_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True)
    time_start: datetime = Field(default_factory=datetime.utcnow)
    time_finish: Optional[datetime] = None
    duration: int = 0
    indefinite_questions: int = Field(index=False)
    # Это поле будет хранить список ID вопросов (как строка JSON в Redis)
    question_ids: str = Field(index=False, default=json.dumps([]))
    # Это поле хранит ответы пользователя (как строка JSON в Redis)
    answers: str = Field(default="{}", index=False)
    questions_answered: int = 0
    questions_remaining: int = Field(index=False)
    current_question_index: int = 0
    status: SessionStatus = SessionStatus.CREATED
    ip_address: Optional[str] = Field(index=True)
    last_activity: datetime = Field(default_factory=datetime.utcnow, index=False)

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

    # Добавляем валидаторы для автоматического преобразования при чтении/записи
    @validator('question_ids', 'answers', pre=True)
    def validate_json_fields(cls, v):
        # Если приходит список/словарь (из кода), сериализуем в строку
        if isinstance(v, (list, dict)):
            return json.dumps(v)
        # Если приходит строка (из Redis), просто возвращаем
        return v

    # При получении объекта из Redis (использование property для десериализации)
    @property
    def questions_list(self) -> List[str]:
        return json.loads(self.question_ids)

    class Meta:
        model_key_prefix = "test_session"


class QuestionRedis(HashModel):
    question_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True, primary_key=True)
    index: int = Field(index=True)
    category: str = Field(index=False)
    content: str = Field(index=True)
    choices: str = Field(default="{}", index=False)
    correct_answer: str = Field(index=False)

    class Meta:
        model_key_prefix = "question"
