from uuid import UUID

from asyncpg import ForeignKeyViolationError, UniqueViolationError

from app.core.databases import connection
from app.core.log import setup_logger
from app.models.database import User, Role, Permission, role2permission, School, Settlement, Region
from sqlalchemy import select, exists, func
from sqlalchemy.orm import selectinload

from typing import Optional, Mapping, Any, Coroutine, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from enum import Enum

from app.repositories.dao.exceptions import SchoolNotFoundError, UserAlreadyExistsError

logger = setup_logger(__name__)

class RoleEnum(Enum):
    ADMIN = "admin"
    STUDENT = "student"
    TEACHER = "teacher"
    ADMISSIONS_COMMITTEE = "admissions_committee"

# Fields that can be updated via generic update methods (profile-level only)
_ALLOWED_UPDATE_FIELDS = {
    "full_name", "middle_name", "last_name", "age",
    "phone_number", "school", "school_id"
}

def _normalize_email(value: str | None) -> str | None:
    return value.strip().lower() if value else None


def _filter_update_payload(payload: Mapping[str, Any]) -> dict:
    """Return a copy of payload limited to allowed profile fields; log ignored keys."""
    safe = {}
    for k, v in payload.items():
        if k in _ALLOWED_UPDATE_FIELDS:
            safe[k] = v
        else:
            logger.debug("Ignoring disallowed update field: %s", k)
    return safe


async def _resolve_school(
    session: AsyncSession,
    *,
    school: School | None = None,
    school_id: UUID | str | None = None,
) -> School | None:
    if school is not None:
        return school
    if school_id is None:
        return None
    school_obj = await session.get(School, school_id)
    if not school_obj:
        raise SchoolNotFoundError(f"School with id {school_id} not found")
    return school_obj


class UserDAO:
    @connection
    async def create(self, full_name: str, nickname: str, age: int | None, email: str | None, phone: str,
                     password: str, role: UUID, school: School | None = None,
                     school_id: UUID | str | None = None, is_guest: bool = False,
                     session = None) -> User:
        email = _normalize_email(email)
        school_obj = await _resolve_school(session, school=school, school_id=school_id)
        try:
            user = User(
                full_name=full_name,
                nickname=nickname,
                age=age,
                email=email,
                phone_number=phone,
                password=password,
                role_id=role,  # Use the same session
                school=school_obj,
                is_guest=is_guest,
            )
        except UniqueViolationError as e:
            logger.error("Failed to create user email=%s due to unique violation: %s", email, e)
            raise UserAlreadyExistsError(f"User with email {email} already exists") from e
        except ForeignKeyViolationError as e:
            logger.error("Failed to create user email=%s due to foreign key violation: %s", email, e)
            raise
        except IntegrityError as e:
            logger.error("Failed to create user email=%s due to integrity error: %s", email, e)
            raise
        except Exception as e:
            logger.error("Failed to create user email=%s due to unexpected error: %s", email, e)
            raise

        if password and not password.startswith("$"):
            logger.warning("Creating user with a password that does not look hashed.")
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
            logger.info("Created user id=%s email=%s", user.id, user.email)
            return user
        except IntegrityError as e:
            await session.rollback()
            logger.error("Failed to create user email=%s due to integrity error: %s", email, e)
            raise

    @connection
    async def get_role_id(self, role: RoleEnum, session: Optional[AsyncSession] = None) -> UUID:
        role_obj = await session.execute(
            select(Role).where(Role.role == role.value)
        )
        role_instance = role_obj.scalar_one_or_none()  # Retrieve the role instance
        if not role_instance:
            raise ValueError(f"Role {role.value} not found")
        logger.debug("Resolved role '%s' to id=%s", role.value, role_instance.id)
        return role_instance.id

    @connection
    async def get_user_by_id(self, user_id: UUID | str, session: Optional[AsyncSession] = None) -> Optional[User]:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.role).selectinload(Role.permissions),
                selectinload(User.school),
            )
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    # @connection
    # async def get_user_with_role_and_permissions(self, user_id: UUID | str, session: Optional[AsyncSession] = None) -> Optional[User]:
    #     result = await session.execute(
    #         select(User)
    #         .options(selectinload(User.role).selectinload(Role.permissions))
    #         .where(User.id == user_id)
    #     )
    #     return result.scalar_one_or_none()

    @connection
    async def get_user_by_email(self, email: str, session: Optional[AsyncSession] = None) -> Optional[User]:
        email = _normalize_email(email)
        user = await session.execute(select(User).where(User.email == email))
        return user.scalar_one_or_none()

    @connection
    async def update_user_by_id(self, user_id: UUID | str, user_data: Mapping[str, Any], session: Optional[AsyncSession] = None) -> User | None:
        user = await session.get(User, user_id)
        if not user:
            logger.warning("update_user_by_id: user %s not found", user_id)
            return None
        safe = _filter_update_payload(user_data)
        school_key = None
        if "school" in safe:
            school_key = "school"
        elif "school_id" in safe:
            school_key = "school_id"
        if school_key is not None:
            school_value = safe.pop(school_key)
            if school_value is None:
                user.school = None
            elif isinstance(school_value, School):
                user.school = school_value
            else:
                school_id = getattr(school_value, "id", None)
                if school_id is None and isinstance(school_value, Mapping):
                    school_id = school_value.get("id")
                if school_id is None:
                    school_id = school_value
                user.school = await _resolve_school(session, school_id=school_id)
        for key, value in safe.items():
            setattr(user, key, value)
        try:
            await session.commit()
            await session.refresh(user)
            logger.info("Updated user id=%s", user_id)
            return user
        except IntegrityError as e:
            await session.rollback()
            logger.error("Failed to update user id=%s due to integrity error: %s", user_id, e)
            raise

    @connection
    async def update_password(self, user_id: UUID | str, hashed_password: str, session: Optional[AsyncSession] = None) -> User | None:
        """Set an already-hashed password directly — deliberately bypasses
        _ALLOWED_UPDATE_FIELDS/update_user_by_id so the generic profile-update
        payload can never smuggle in a raw password."""
        user = await session.get(User, user_id)
        if not user:
            return None
        user.password = hashed_password
        await session.commit()
        await session.refresh(user)
        return user

    @connection
    async def update_user_by_email(self, email: str, user_data: Mapping[str, Any], session: Optional[AsyncSession] = None) -> Optional[User]:
        email = _normalize_email(email)
        user = await session.execute(select(User).where(User.email == email))
        user_instance = user.scalar_one_or_none()
        if not user_instance:
            logger.warning("update_user_by_email: user %s not found", email)
            return None
        safe = _filter_update_payload(user_data)
        school_key = None
        if "school" in safe:
            school_key = "school"
        elif "school_id" in safe:
            school_key = "school_id"
        if school_key is not None:
            school_value = safe.pop(school_key)
            if school_value is None:
                user_instance.school = None
            elif isinstance(school_value, School):
                user_instance.school = school_value
            else:
                school_id = getattr(school_value, "id", None)
                if school_id is None and isinstance(school_value, Mapping):
                    school_id = school_value.get("id")
                if school_id is None:
                    school_id = school_value
                user_instance.school = await _resolve_school(session, school_id=school_id)
        for key, value in safe.items():
            setattr(user_instance, key, value)
        try:
            await session.commit()
            await session.refresh(user_instance)
            logger.info("Updated user email=%s", email)
            return user_instance
        except IntegrityError as e:
            await session.rollback()
            logger.error("Failed to update user email=%s due to integrity error: %s", email, e)
            raise

    @connection
    async def delete_user_by_id(self, user_id: UUID | str, session: Optional[AsyncSession] = None) -> bool:
        user = await session.get(User, user_id)
        if not user:
            logger.warning("delete_user_by_id: user %s not found", user_id)
            return False
        await session.delete(user)
        await session.commit()
        logger.info("Deleted user id=%s", user_id)
        return True

    @connection
    async def delete_user_by_email(self, email: str, session: Optional[AsyncSession] = None) -> bool:
        email = _normalize_email(email)
        user = await session.execute(select(User).where(User.email == email))
        user_instance = user.scalar_one_or_none()
        if not user_instance:
            logger.warning("delete_user_by_email: user %s not found", email)
            return False
        await session.delete(user_instance)
        await session.commit()
        logger.info("Deleted user email=%s", email)
        return True

    @connection
    async def check_permission_by_id(self, user_id: UUID | str, permission_name: str, session: Optional[AsyncSession] = None) -> bool:
        q = select(exists().where(
            (User.id == user_id) &
            (User.role_id == Role.id) &
            Role.permissions.any(Permission.name == permission_name)
        ))
        return bool((await session.execute(q)).scalar())

    @connection
    async def check_permission_by_email(self, email: str, permission_name: str, session: Optional[AsyncSession] = None) -> bool:
        email = _normalize_email(email)
        q = select(exists().where(
            (User.email == email) &
            (User.role_id == Role.id) &
            Role.permissions.any(Permission.name == permission_name)
        ))
        return bool((await session.execute(q)).scalar())

    @connection
    async def change_email(self, user_id: UUID | str, new_email: str, session: Optional[AsyncSession] = None) -> Optional[User]:
        new_email = _normalize_email(new_email)
        user = await session.get(User, user_id)
        if not user:
            logger.warning("change_email: user %s not found", user_id)
            return None
        user.email = new_email
        try:
            await session.commit()
            await session.refresh(user)
            logger.info("Changed email for user id=%s to %s", user_id, new_email)
            return user
        except IntegrityError as e:
            await session.rollback()
            logger.error("Failed to change email for user id=%s to %s: %s", user_id, new_email, e)
            raise

    @connection
    async def set_password(self, user_id: UUID | str, hashed_password: str, session: Optional[AsyncSession] = None) -> bool:
        """Set an already-hashed password. Hash outside the DAO."""
        user = await session.get(User, user_id)
        if not user:
            logger.warning("set_password: user %s not found", user_id)
            return False
        if not hashed_password:
            logger.error("set_password: empty password for user %s", user_id)
            return False
        user.password = hashed_password
        await session.commit()
        logger.info("Password updated for user id=%s", user_id)
        return True

    @connection
    async def list_users(self, session: Optional[AsyncSession] = None) -> Sequence[User]:
        result = await session.execute(
            select(User).options(
                selectinload(User.role),
                selectinload(User.school),
            )
        )
        return result.scalars().all()

    @connection
    async def get_users_by_ids(
        self, user_ids: Sequence[UUID], session: Optional[AsyncSession] = None
    ) -> dict[UUID, User]:
        """Bulk-fetch users with school -> settlement -> region eager-loaded, for
        building region/city/school-scoped ratings without an N+1 query per row."""
        if not user_ids:
            return {}
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.school).selectinload(School.settlement).selectinload(Settlement.region),
            )
            .where(User.id.in_(user_ids))
        )
        return {user.id: user for user in result.scalars().all()}

    @classmethod
    def users_query(cls):
        return (
            select(User)
            .options(selectinload(User.role))
            .order_by(User.created_at.desc(), User.id.desc())  # stable ordering
        )
