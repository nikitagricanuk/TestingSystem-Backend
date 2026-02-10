from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repositories.question_bank.models import Question

from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, Text,
    UniqueConstraint, Table, Column, Index, Enum, DateTime
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid
from datetime import datetime
from . import Base
import enum


# Association table for role and permission (many-to-many)
role2permission = Table(
    "role2permission",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    role: Mapped[str] = mapped_column(String, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="role")
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=role2permission, back_populates="roles"
    )


class Permission(Base):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=role2permission, back_populates="permissions"
    )


class Region(Base):
    __tablename__ = "regions"
    __table_args__ = (
        Index('regions_region_key', 'region', unique=True),
    )

    region: Mapped[str] = mapped_column(String, nullable=False)

    settlements: Mapped[list["Settlement"]] = relationship("Settlement", back_populates="region")


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        Index('settlements_natural_key', 'name', 'type', 'region_id', unique=True),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)

    region: Mapped["Region"] = relationship("Region", back_populates="settlements")
    schools: Mapped[list["School"]] = relationship("School", back_populates="settlement")


class School(Base):
    __tablename__ = "schools"

    full_name: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str] = mapped_column(String, nullable=True)
    city_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False)

    settlement: Mapped["Settlement"] = relationship("Settlement", back_populates="schools")
    users: Mapped[list["User"]] = relationship("User", back_populates="school")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email"),
        UniqueConstraint("phone_number"),
    )

    full_name: Mapped[str] = mapped_column(String, nullable=False)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    school: Mapped["School"] = relationship("School", back_populates="users")
    role: Mapped["Role"] = relationship("Role", back_populates="users")

    questions: Mapped[list["Question"]] = relationship("Question", back_populates="teacher")


class NavigationMethod(enum.Enum):
    FREE = "free"
    LINEAR = "linear"


class Test(Base):
    __tablename__ = "tests"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    number_of_required_questions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shuffle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    navigation_method: Mapped[NavigationMethod] = mapped_column(
        Enum(
            NavigationMethod,
            name="navigation_method_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=NavigationMethod.FREE,
    )
    can_be_reviewed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    questions: Mapped[list["TestQuestion"]] = relationship(
        "TestQuestion",
        back_populates="test",
        cascade="all, delete-orphan",
    )


class TestQuestion(Base):
    __tablename__ = "test_questions"
    __table_args__ = (
        UniqueConstraint("test_id", "question_id"),
        UniqueConstraint("test_id", "position_in_test"),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    position_in_test: Mapped[int] = mapped_column(Integer, nullable=False)

    test: Mapped["Test"] = relationship("Test", back_populates="questions")
    question: Mapped["Question"] = relationship("Question")
