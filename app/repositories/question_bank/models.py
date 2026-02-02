from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.database import User
import os
import enum
from sqlalchemy import Enum
class QuestionType(enum.Enum):
    single = "single"
    multiple = "multiple"
    text = "text"

from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

if os.environ.get("TESTING", False):
    JSON_TYPE = JSON       #для тестов
else:
    JSON_TYPE = JSONB

from app.models import Base
class Category(Base):
    __tablename__ = 'categories'

    category: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True
    )

    parent: Mapped["Category"] = relationship(
        "Category",
        remote_side="Category.id",
        backref="children"
    )

    questions: Mapped[list["Question"]] = relationship(
        "Question",
        back_populates="category",
        cascade="all, delete-orphan"
    )

class Question(Base):
    __tablename__ = 'questions'

    text: Mapped[str] = mapped_column(String, nullable=False)

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True
    )

    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type_enum"),
        nullable=False
    )

    problem: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    answer: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False
    )

    mark_out_of: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    penalty: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True, default=True)

    teacher = relationship("User", back_populates="questions")
    category = relationship("Category", back_populates="questions")

