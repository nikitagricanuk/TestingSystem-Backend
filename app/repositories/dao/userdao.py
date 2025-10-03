from app.core.databases import connection
from app.models.database import User
from sqlalchemy import select

from enum import Enum
from app.models.database import Role

class RoleEnum(Enum):
    ADMIN = "admin"
    STUDENT = "student"
    # Add other roles as needed

class UserDAO:
    @connection
    async def create(self, first_name: str, middle_name: str, second_name: str,
                    age: int, email: str, phone: str, password: str,
                     role: RoleEnum, school_id: str | None = None, session = None) -> User:
        user = User(
            first_name=first_name,
            middle_name=middle_name,
            second_name=second_name,
            age=age,
            email=email,
            phone_number=phone,
            password=password,
            role_id=await self.get_role_id(role, session=session),  # Use the same session
            school_id=school_id
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @connection
    async def get_role_id(self, role, session=None):
        role_obj = await session.execute(
            select(Role).where(Role.role == role.value)
        )
        role_instance = role_obj.scalar_one_or_none()  # Retrieve the role instance
        if not role_instance:
            raise ValueError(f"Role {role.value} not found")
        return role_instance.id

    @connection
    async def get_user_by_id(self, user_id, session=None):
        return await session.get(User, user_id)

    @connection
    async def get_user_by_email(self, email, session=None):
        user = await session.execute(
            select(User).where(User.email == email)
        )
        return user.scalar_one_or_none()

    @connection
    async def update_user_by_id(self, user_id, user_data, session=None):
        user = await session.get(User, user_id)
        if not user:
            return None
        for key, value in user_data.items():
            setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return user

    @connection
    async def update_user_by_email(self, email, user_data, session=None):
        user = await session.execute(
            select(User).where(User.email == email)
        )
        user_instance = user.scalar_one_or_none()
        if not user_instance:
            return None
        for key, value in user_data.items():
            setattr(user_instance, key, value)
        await session.commit()
        await session.refresh(user_instance)
        return user_instance

    @connection
    async def delete_user_by_id(self, user_id, session=None):
        user = await session.get(User, user_id)
        if not user:
            return False
        await session.delete(user)
        await session.commit()
        return True

    @connection
    async def delete_user_by_email(self, email, session=None):
        user = await session.execute(
            select(User).where(User.email == email)
        )
        user_instance = user.scalar_one_or_none()
        if not user_instance:
            return False
        await session.delete(user_instance)
        await session.commit()
        return True