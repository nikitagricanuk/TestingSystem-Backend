from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories.dao.userdao import UserDAO
from app.schemas.users import User, UserCreate, LoginResponse, LoginRequest
from app.utils.password import get_hashed_password, verify_password
from app.services.auth.jwt_service import get_jwt_service, JWTService

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, jwt: JWTService = Depends(get_jwt_service)) -> LoginResponse:
    user = await UserDAO().get_user_by_email(credentials.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # if not verify_password(credentials.password, user.password):
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_extra = {
        "uid": str(user.id),
    }
    refresh_extra = {"uid": str(user.id)}

    # 4) Issue tokens
    pair = await jwt.create(subject=str(user.id), access_extra=access_extra, refresh_extra=refresh_extra)

    return LoginResponse(access_token=pair.access_token, refresh_token=pair.refresh_token, token_type="bearer",
                         access_token_expires_at=pair.refresh_token_expires_at.isoformat(),
                         access_token_expires_at_unix=int(pair.refresh_token_expires_at.timestamp()),
                         refresh_token_expires_at=pair.refresh_token_expires_at.isoformat(),
                         refresh_token_expires_at_unix=int(pair.refresh_token_expires_at.timestamp()))

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