from uuid import UUID

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ResultWithQuestions(BaseModel):
    id: Optional[UUID] = Field(None)
    test_id: Optional[UUID] = Field(None)
    user_id: Optional[UUID] = Field(None)
    score: Optional[float] = Field(None)
    recommendations: Optional[List[str]] = Field(None)
    duration_seconds: Optional[int] = Field(None)
    rank: Optional[int] = Field(None)
    total_questions: Optional[int] = Field(None)
    correct_answers: Optional[int] = Field(None)
    questions: Optional[List[Dict[str, Any]]] = Field(None)

class ResultWithoutQuestions(BaseModel):
    id: Optional[UUID] = Field(None)
    test_id: Optional[UUID] = Field(None)
    user_id: Optional[UUID] = Field(None)
    score: Optional[float] = Field(None)
    recommendations: Optional[List[str]] = Field(None)
    duration_seconds: Optional[int] = Field(None)
    rank: Optional[int] = Field(None)
    total_questions: Optional[int] = Field(None)
    correct_answers: Optional[int] = Field(None)
    questions: Optional[List[Dict[str, Any]]] = Field(None)