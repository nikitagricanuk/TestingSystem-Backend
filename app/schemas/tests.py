from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel


class TestBase(BaseModel):
    name: str
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    number_of_required_questions: int | None = None
    shuffle: bool = True
    navigation_method: str = "free"
    can_be_reviewed: bool | None = None
    welcome_message: str | None = None
    config: dict[str, Any] | None = None


class TestCreate(TestBase):
    question_ids: list[UUID] | None = None


class TestUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    number_of_required_questions: int | None = None
    shuffle: bool | None = None
    navigation_method: str | None = None
    can_be_reviewed: bool | None = None
    welcome_message: str | None = None
    config: dict[str, Any] | None = None


class TestOut(TestBase):
    id: UUID
    owner_id: UUID | None = None
    created_at: datetime | None = None
    created_at_unix: int | None = None
    updated_at: datetime | None = None
    updated_at_unix: int | None = None
    total_questions: int = 0


class TestDelete(BaseModel):
    id: UUID
    name: str | None = None
    deleted_at: datetime | None = None
    deleted_at_unix: int | None = None


class TestQuestionOut(BaseModel):
    question_id: UUID
    position_in_test: int


class TestQuestionRuleCreate(BaseModel):
    category_id: UUID
    is_mandatory: bool = True
    fixed_position: int | None = None


class TestQuestionRuleOut(BaseModel):
    id: UUID
    test_id: UUID
    category_id: UUID
    is_mandatory: bool
    fixed_position: int | None = None
