from datetime import datetime
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


class GroupScore(BaseModel):
    group: str
    score: float
    total: int


class Result(BaseModel):
    id: UUID
    score: Optional[float] = None
    certificate_available: bool
    certificate_link: Optional[str] = None
    recommendations: List[str] = []
    test_id: UUID
    user_id: UUID
    status: str
    time_start: Optional[datetime] = None
    time_finish: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    rank: Optional[int] = None
    total_questions: int
    correct_answers: int
    group_scores: List[GroupScore] = []


class LeaderboardEntry(BaseModel):
    rank: int
    nickname: str
    score: float
    test_id: UUID
    group_scores: List[GroupScore] = []
