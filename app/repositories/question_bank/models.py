##в QuestionType какие типы??
from app.models.database import User
import sys
import os
from sqlalchemy.orm import remote
import enum

class QuestionType(enum.Enum):
    single = "single"
    multiple = "multiple"
    text = "text"

from sqlalchemy import Enum
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, Text,
    UniqueConstraint, Table, Column, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid

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
        back_populates="category"
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
        JSONB,
        nullable=False
    )

    market_out_of: Mapped[int] = mapped_column(
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

