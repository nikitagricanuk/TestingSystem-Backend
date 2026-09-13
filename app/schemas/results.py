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


class QuestionAnalysisOut(BaseModel):
    question_id: UUID
    category: str
    question_type: str
    attempts: int
    difficulty: float
    discrimination: float
    guess_score: float
    effective_discrimination: float
    std_dev: float
    intended_weight: float
    effective_weight: float


class TestAnalysisOut(BaseModel):
    test_id: UUID
    avg_discrimination: float
    avg_difficulty: float
    avg_attempts: float
    avg_effective_weight: float
    questions: List[QuestionAnalysisOut] = []


class SessionReviewQuestion(BaseModel):
    index: int
    prompt: Optional[str] = None
    choices: List[str] = []
    correct_answer: Optional[str] = None
    student_answer: Optional[str] = None
    is_correct: bool
    time_spent_seconds: float = 0


class SessionReview(BaseModel):
    sid: UUID
    test_id: UUID
    user_id: UUID
    score: Optional[float] = None
    questions: List[SessionReviewQuestion] = []


class LeaderboardEntry(BaseModel):
    rank: int
    nickname: str
    school: Optional[str] = None
    score: float
    test_id: UUID
    group_scores: List[GroupScore] = []
