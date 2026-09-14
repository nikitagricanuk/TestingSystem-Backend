from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repositories.question_bank.models import Question

# User.questions below references "Question" by string name; SQLAlchemy only
# resolves that at mapper-configuration time (on first query), so the class must
# already be registered by then regardless of which module happens to run first.
# Importing it here (not just under TYPE_CHECKING) guarantees that whenever this
# canonical models module is imported, the mapper registry is complete.
import app.repositories.question_bank.models  # noqa: F401

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
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_graduated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    school: Mapped["School"] = relationship("School", back_populates="users")
    role: Mapped["Role"] = relationship("Role", back_populates="users")

    questions: Mapped[list["Question"]] = relationship("Question", back_populates="teacher")


class NavigationMethod(enum.Enum):
    FREE = "free"
    LINEAR = "linear"


class Test(Base):
    __tablename__ = "tests"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
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


class TestQuestionRule(Base):
    """A "random question from topic X" slot on a test (Admin PDF's test-overview
    "Банк вопросов" cards: obligatory/optional, fixed or free position). Resolved
    into a concrete question pick at session-creation time — see
    app.services.testing_engine.test_question_resolver."""

    __tablename__ = "test_question_rules"

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fixed_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    test: Mapped["Test"] = relationship("Test")


class ApplicantContactStatus(enum.Enum):
    CALLED = "called"
    NOT_CALLED = "not_called"
    CUSTOM = "custom"


class ApplicantContact(Base):
    """Admissions-committee call status/tag for one applicant (Admin PDF's
    "Общий рейтинг" — Обзвонен/Необзвонен/Свой тэг)."""

    __tablename__ = "applicant_contacts"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ApplicantContactStatus] = mapped_column(
        Enum(
            ApplicantContactStatus,
            name="applicant_contact_status_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ApplicantContactStatus.NOT_CALLED,
    )
    custom_tag: Mapped[str | None] = mapped_column(String, nullable=True)


class CertificateKind(enum.Enum):
    BASE = "base"
    ADVANCED = "advanced"


class CertificateTemplate(Base):
    """A certificate background (admin-uploaded PDF/image) plus where to draw
    each field on it (Admin PDF's "Редактор сертификатов" — Фамилия И.О.,
    Результат, Место, Длительность, Дата, Уч. заведение, Класс, Подпись).
    test_id NULL means this is the global default template."""

    __tablename__ = "certificate_templates"

    test_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[CertificateKind] = mapped_column(
        Enum(
            CertificateKind,
            name="certificate_kind_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CertificateKind.BASE,
    )
    # Always a PDF on disk — image uploads are wrapped into a 1-page PDF at
    # upload time so rendering only ever deals with one format.
    asset_path: Mapped[str] = mapped_column(String, nullable=False)
    # list[{"key": str, "page": int, "x": float, "y": float, "font_size": float}]
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    signature_asset_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # {"page": int, "x": float, "y": float, "width": float, "height": float}
    signature_position: Mapped[dict | None] = mapped_column(JSON, nullable=True)
