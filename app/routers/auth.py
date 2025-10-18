from uuid import UUID

from fastapi import APIRouter, Depends

from app.repositories.dao.userdao import UserDAO
from app.schemas.users import User, UserCreate
from app.utils.password import get_hashed_password

router = APIRouter()

@router.post("/users/create", response_model=UserCreate)
async def create_user(user: UserCreate) -> User:
    hashed_password = get_hashed_password(user.password)
    created_user = await UserDAO().create(
        first_name=user.first_name,
        middle_name=user.middle_name,
        second_name=user.second_name,
        age=user.age,
        email=user.email,
        phone=user.phone,
        password=hashed_password,
        role=user.role,
        school_id=user.school_id
    )
    return User(
        id=created_user.id,
        email=created_user.email,
        is_active=created_user.is_active,
        role=None,  # You might want to fetch and include the role name here
        permissions=[],  # You might want to fetch and include permissions here
        created_at=created_user.created_at,
        created_at_unix=int(created_user.created_at.timestamp()),
        updated_at=created_user.updated_at,
        updated_at_unix=int(created_user.updated_at.timestamp()) if created_user.updated_at else None
    )