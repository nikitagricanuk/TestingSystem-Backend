from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str


class CategoryCreate(CategoryBase):
    parent_id: UUID | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: UUID | None = None


class CategoryOut(CategoryBase):
    id: UUID
    parent_id: UUID | None = None


class QuestionBase(BaseModel):
    text: str
    answer: dict[str, Any]
    question_type: str
    problem: str
    mark_out_of: int
    penalty: int
    is_active: bool = True


class QuestionCreate(QuestionBase):
    category_id: UUID | None = None
    category_path: list[str] | None = None


class QuestionUpdate(BaseModel):
    text: str | None = None
    answer: dict[str, Any] | None = None
    category_id: UUID | None = None
    category_path: list[str] | None = None
    question_type: str | None = None
    problem: str | None = None
    mark_out_of: int | None = None
    penalty: int | None = None
    is_active: bool | None = None


class QuestionOut(QuestionBase):
    id: UUID
    teacher_id: UUID
    category_id: UUID | None = None
