from uuid import UUID

from app.core.databases import connection
from app.core.log import setup_logger
from app.models.database import User, Role, Permission, role2permission
from sqlalchemy import select, exists, func
from sqlalchemy.orm import selectinload

from typing import Optional, Mapping, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from enum import Enum

logger = setup_logger(__name__)

class RoleEnum(Enum):
    ADMIN = "admin"
    STUDENT = "student"
    # Add other roles as needed

# Fields that can be updated via generic update methods (profile-level only)
_ALLOWED_UPDATE_FIELDS = {
    "first_name", "middle_name", "second_name", "age",
    "phone_number", "school_id"
}

def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _filter_update_payload(payload: Mapping[str, Any]) -> dict:
    """Return a copy of payload limited to allowed profile fields; log ignored keys."""
    safe = {}
    for k, v in payload.items():
        if k in _ALLOWED_UPDATE_FIELDS:
            safe[k] = v
        else:
            logger.debug("Ignoring disallowed update field: %s", k)
    return safe


class UserDAO:
    @connection
    async def create(self, first_name: str, middle_name: str, second_name: str,
                    age: int, email: str, phone: str, password: str,
                     role: UUID, school_id: str | None = None, session = None) -> User:
        email = _normalize_email(email)
        user = User(
            first_name=first_name,
            middle_name=middle_name,
            second_name=second_name,
            age=age,
            email=email,
            phone_number=phone,
            password=password,
            role_id=role,  # Use the same session
            school_id=school_id
        )
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
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @connection
    async def get_user_with_role_and_permissions(self, user_id: UUID | str, session: Optional[AsyncSession] = None) -> Optional[User]:
        result = await session.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

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
    async def update_user_by_email(self, email: str, user_data: Mapping[str, Any], session: Optional[AsyncSession] = None) -> Optional[User]:
        email = _normalize_email(email)
        user = await session.execute(select(User).where(User.email == email))
        user_instance = user.scalar_one_or_none()
        if not user_instance:
            logger.warning("update_user_by_email: user %s not found", email)
            return None
        safe = _filter_update_payload(user_data)
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
