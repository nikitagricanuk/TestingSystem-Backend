from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, Text,
    UniqueConstraint, Table, Column
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid
from . import Base


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

    region: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    settlements: Mapped[list["Settlement"]] = relationship("Settlement", back_populates="region")


class Settlement(Base):
    __tablename__ = "settlements"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
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

    first_name: Mapped[str] = mapped_column(String, nullable=False)
    second_name: Mapped[str] = mapped_column(String, nullable=False)
    middle_name: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    school: Mapped["School"] = relationship("School", back_populates="users")
    role: Mapped["Role"] = relationship("Role", back_populates="users")