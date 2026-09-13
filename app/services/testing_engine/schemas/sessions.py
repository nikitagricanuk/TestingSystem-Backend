from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Optional, Dict

class Session(BaseModel):
    sid: Optional[UUID] = Field(None)
    test_id: Optional[UUID] = Field(None)
    user_id: Optional[UUID] = Field(None)
    time_start: Optional[datetime] = Field(None)
    time_start_unix: Optional[int] = Field(None)
    time_finish: Optional[datetime] = Field(None)
    time_finish_unix: Optional[int] = Field(None)
    duration_seconds: Optional[int] = Field(None)
    time_left_seconds: Optional[int] = Field(None)
    total_questions: Optional[int] = Field(None)
    questions_answered: Optional[int] = Field(None)
    questions_remaining: Optional[int] = Field(None)
    current_question_index: Optional[int] = Field(None)
    status: Optional[str] = Field(None)
    required_count: Optional[int] = Field(None)
    required_complete: Optional[bool] = Field(None)
    is_submitted: Optional[bool] = Field(None)
    score: Optional[float] = Field(None)
    ip_address: Optional[str] = Field(None)
    device_type: Optional[str] = Field(None)
    last_activity_unix: Optional[int] = Field(None)
    # Keyed by question index (as a string), matching how answers are stored
    # internally — lets the UI restore a previously-picked choice when a
    # student navigates back to a question they've already answered.
    answers: Optional[Dict[str, str]] = Field(None)

class SessionDelete(BaseModel):
    sid: Optional[UUID] = Field(None)
    deleted_at: Optional[datetime] = Field(None)
    deleted_at_unix: Optional[int] = Field(None)

class SessionQuestion(BaseModel):
    index: Optional[int] = Field(None)
    question_id: Optional[UUID] = Field(None)
    question: Optional[str] = Field(None)
    question_type: Optional[str] = Field(None)
    choices: Optional[list[str]] = Field(None)
    status: Optional[str] = Field(None)
