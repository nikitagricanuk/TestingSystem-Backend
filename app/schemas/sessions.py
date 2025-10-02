from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Optional, List

class Session(BaseModel):
    sid: Optional[UUID] = Field(None)
    test_id: Optional[UUID] = Field(None)
    user_id: Optional[UUID] = Field(None)
    time_start: Optional[datetime] = Field(None)
    time_start_unix: Optional[int] = Field(None)
    time_finish: Optional[datetime] = Field(None)
    time_finish_unix: Optional[int] = Field(None)
    duration_seconds: Optional[int] = Field(None)
    indefinite_questions: Optional[bool] = Field(None)
    total_questions: Optional[int] = Field(None)
    questions_answered: Optional[int] = Field(None)
    questions_remaining: Optional[int] = Field(None)
    current_question_index: Optional[int] = Field(None)
    status: Optional[str] = Field(None)
    ip_address: Optional[str] = Field(None)
    device_type: Optional[str] = Field(None)
    last_activity_unix: Optional[int] = Field(None)

class SessionDelete(BaseModel):
    sid: Optional[UUID] = Field(None)
    deleted_at: Optional[datetime] = Field(None)
    deleted_at_unix: Optional[int] = Field(None)

class SessionQuestion(BaseModel):
    index: Optional[int] = Field(None)
    question: Optional[str] = Field(None)
    category: Optional[str] = Field(None)
    choices: Optional[List[str]] = Field(None)
    status: Optional[str] = Field(None)
