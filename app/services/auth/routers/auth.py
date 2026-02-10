from enum import Enum
from uuid import UUID

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi import Security
from fastapi import Body
import re
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.databases import async_session_maker
from app.core.permissions import Permissions
from app.repositories.dao.exceptions import SchoolNotFoundError, UserAlreadyExistsError
from app.repositories.dao.userdao import UserDAO, RoleEnum
from app.schemas.users import User, UserCreate, LoginResponse, LoginRequest, UserCreateStudent, UserFull, UserShort, School as SchoolSchema, UserDelete
from app.utils.password import get_hashed_password, verify_password
from app.services.auth.jwt_service import get_jwt_service, JWTService
from app.services.auth.sessions import Session
from typing import Optional, cast, Any, Mapping

from app.core.log import setup_logger

logger = setup_logger(__name__)

# Helper to normalize role name for API responses (avoid leaking UUIDs)
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")


def _role_name_from_model(obj) -> Optional[str]:
    # Try relation object attributes first
    name = getattr(getattr(obj, "role", None), "name", None)
    if name:
        return name
    alt = getattr(getattr(obj, "role", None), "role", None)
    if alt and not UUID_RE.match(str(alt)):
        return alt
    # If `role` itself is a UUID-like string, hide it in responses
    val = getattr(obj, "role", None)
    if isinstance(val, str) and UUID_RE.match(val):
        return None
    return None


def _build_user_schema(db_user, *, include_permissions: bool = False) -> UserFull:
    role_name = _role_name_from_model(db_user)
    created_at = cast(Optional[datetime], getattr(db_user, "created_at", None))
    updated_at = cast(Optional[datetime], getattr(db_user, "updated_at", None))
    created_at_unix = int(created_at.timestamp()) if created_at else None
    updated_at_unix = int(updated_at.timestamp()) if updated_at else None

    permissions_list: list[str] = []
    if include_permissions:
        try:
            user_perms = getattr(db_user, "permissions", None)
            if user_perms:
                permissions_list.extend(
                    [getattr(p, "name", None) for p in user_perms if getattr(p, "name", None) is not None]
                )
            role = getattr(db_user, "role", None)
            if role is not None:
                role_perms = getattr(role, "permissions", None)
                if role_perms:
                    permissions_list.extend(
                        [getattr(p, "name", None) for p in role_perms if getattr(p, "name", None) is not None]
                    )
            permissions_list = list(dict.fromkeys(permissions_list))
        except Exception:
            permissions_list = []

    school_schema = None
    try:
        school_obj = getattr(db_user, "school", None)
        if school_obj is not None:
            school_schema = SchoolSchema(
                id=school_obj.id,
                full_name=school_obj.full_name,
                short_name=getattr(school_obj, "short_name", None),
                city_id=school_obj.city_id,
            )
    except Exception:
        school_schema = None

    return UserFull(
        id=db_user.id,
        email=db_user.email,
        is_active=db_user.is_active,
        role=role_name,
        created_at=created_at,
        created_at_unix=created_at_unix or 0,
        updated_at=updated_at,
        updated_at_unix=updated_at_unix,
        permissions=permissions_list,
        full_name=cast(Optional[str], getattr(db_user, "full_name", None)) or "",
        nickname=cast(Optional[str], getattr(db_user, "nickname", None)),
        age=cast(Optional[int], getattr(db_user, "age", None)),
        phone=cast(Optional[str], getattr(db_user, "phone_number", None)),
        school=school_schema,
    )


def _normalize_user_update(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)

    if "phone" in data and "phone_number" not in data:
        data["phone_number"] = data.pop("phone")

    if "full_name" not in data:
        name_parts = []
        for key in ("first_name", "middle_name", "last_name"):
            value = data.pop(key, None)
            if value:
                name_parts.append(value)
        if name_parts:
            data["full_name"] = " ".join(name_parts)
    else:
        for key in ("first_name", "middle_name", "last_name"):
            data.pop(key, None)

    return data


router = APIRouter()

# HTTP Bearer (Authorization: Bearer <access_token>)
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
        creds: HTTPAuthorizationCredentials = Security(bearer_scheme),
        jwt: JWTService = Depends(get_jwt_service)
) -> User:
    """
    Extract and validate the *access* JWT from the Authorization header and return the user entity.
    """
    token = creds.credentials
    try:
        claims = await jwt.validate(token, expected_scope="access")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e

    uid_str: Optional[str] = claims.get("sub")
    if not uid_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    try:
        uid = uid_str
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject type")

    db_user = await UserDAO().get_user_by_id(uid)
    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")

    return _build_user_schema(db_user, include_permissions=True)


def require_permissions(*perms: Enum):
    async def _check(user: UserFull = Depends(get_current_user)) -> UserFull:
        user_perms = set(user.permissions or [])
        missing = [p.value for p in perms if p.value not in user_perms]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing)}",
            )
        return user
    return _check


# def permissions_required(*perms: Permissions):
#     def wrapper(route):
#         dep = require_permissions(*perms)   # <- return the callable, don’t run it
#         route.dependencies = getattr(route, "dependencies", []) + [Depends(dep)]
#         return route
#     return wrapper


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, request: Request,
                jwt: JWTService = Depends(get_jwt_service)) -> LoginResponse:
    user = await UserDAO().get_user_by_email(credentials.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    try:
        if not verify_password(credentials.password, user.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except Exception:
        # Hash invalid or cannot be verified → treat as invalid login
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


    # access_extra = {
    #     "role": str(user.role_id) if user.role_id else None,
    # }
    # refresh_extra = {"uid": str(user.id),
    #                  "role": str(user.role_id) if user.role_id else None}

    # 4) Issue tokens
    pair = await jwt.create(subject=str(user.id), session_ip=request.client.host)

    return LoginResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type="bearer",
        access_token_expires_at=pair.access_token_expires_at.isoformat(),
        access_token_expires_at_unix=int(pair.access_token_expires_at.timestamp()),
        refresh_token_expires_at=pair.refresh_token_expires_at.isoformat(),
        refresh_token_expires_at_unix=int(pair.refresh_token_expires_at.timestamp())
    )


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, jwt: JWTService = Depends(get_jwt_service)):
    """Logout by revoking the refresh token (deny future refreshes) and invalidating the server session."""
    try:
        claims, sess = await jwt.validate_refresh_and_get_session(payload.refresh_token)
    except ValueError as e:
        # Treat invalid/unknown refresh as already logged out
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e

    # Revoke allow-list entry by jti and mark session inactive
    jti = claims.get("jti")
    if jti:
        await jwt.revoke_refresh(jti)
    try:
        sess.invalidate()
    except Exception:
        # Best effort; even if session update fails, token is revoked
        pass
    return


# Example protected endpoint
# @permissions_required(Permissions.Users.READ)
@router.get("/users/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/users/me", response_model=User)
async def update_me(
    payload: dict = Body(...),
    current_user: UserFull = Depends(get_current_user),
) -> User:
    update_payload = _normalize_user_update(payload)
    if not update_payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided")
    updated_user = await UserDAO().update_user_by_id(current_user.id, update_payload)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _build_user_schema(updated_user)


@router.post("/signup", response_model=User)
async def create_student_account(user: UserCreateStudent) -> User:
    hashed_password = get_hashed_password(user.password)
    try:
        created_user = await UserDAO().create(
            full_name=user.full_name,
            nickname=user.nickname,  # <- pass through
            age=user.age,
            email=user.email,
            phone=user.phone,
            password=hashed_password,
            role=await UserDAO().get_role_id(RoleEnum.STUDENT),
            school_id=user.school.id if user.school is not None else None,
        )
    except SchoolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create user") from e


    return User(
        id=created_user.id,
        email=created_user.email,
        nickname=created_user.nickname,
        is_active=created_user.is_active,
        # Use helper to avoid leaking UUIDs as role
        role=RoleEnum.STUDENT.value,
        created_at=created_user.created_at,
        created_at_unix=int(created_user.created_at.timestamp()),
        updated_at=created_user.updated_at,
        updated_at_unix=int(created_user.updated_at.timestamp()) if created_user.updated_at else None
    )


@router.post("/users/create", response_model=User)
async def create_user(user: dict = Body(...)) -> User:
    hashed_password = get_hashed_password(user["password"])  # tests stub this
    school_id = None
    if user.get("school") is not None:
        school_value = user["school"]
        school_id = school_value.get("id") if isinstance(school_value, dict) else school_value
    elif user.get("school_id") is not None:
        school_id = user.get("school_id")

    # Resolve role: allow enum string like "ADMIN"/"STUDENT" or a raw UUID
    role_value = user.get("role")
    role_id: Optional[UUID] = None
    if isinstance(role_value, str):
        try:
            # Try enum name first
            enum_val = RoleEnum[role_value]
            role_id = await UserDAO().get_role_id(enum_val)
        except Exception:
            # Treat as raw UUID string if provided
            try:
                role_id = UUID(role_value)
            except Exception:
                role_id = None

    try:
        created_user = await UserDAO().create(
            full_name=user.get("full_name"),
            nickname=user.get("nickname"),
            age=user.get("age"),
            email=user.get("email"),
            phone=user.get("phone"),
            password=hashed_password,
            role=role_id or user.get("role"),
            school_id=school_id,
        )
    except SchoolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return User(
        id=created_user.id,
        nickname=created_user.nickname,
        email=created_user.email,
        is_active=created_user.is_active,
        role=_role_name_from_model(created_user),
        created_at=created_user.created_at,
        created_at_unix=int(created_user.created_at.timestamp()),
        updated_at=created_user.updated_at,
        updated_at_unix=int(created_user.updated_at.timestamp()) if created_user.updated_at else None,
    )


@router.get("/users", response_model=list[User])
async def list_users() -> list[User]:
    users = await UserDAO().list_users()
    return [_build_user_schema(user) for user in users]


@router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: UUID) -> User:
    user = await UserDAO().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _build_user_schema(user)


@router.patch("/users/{user_id}", response_model=User)
async def update_user(user_id: UUID, payload: dict = Body(...)) -> User:
    update_payload = _normalize_user_update(payload)
    if not update_payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided")
    updated_user = await UserDAO().update_user_by_id(user_id, update_payload)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _build_user_schema(updated_user)


@router.delete("/users/{user_id}", response_model=UserDelete)
async def delete_user(user_id: UUID) -> UserDelete:
    user = await UserDAO().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await UserDAO().delete_user_by_id(user_id)
    return UserDelete(id=user_id, username=getattr(user, "email", None))



# @router.get("/users", response_model=Page[UserShort])
# async def list_users(
#     params: Params = Depends(),
# ):
#     query = UserDAO().users_query()   # returns a Select[User]
#     async with async_session_maker() as session:
#         page = await paginate(session, query)  # items are ORM Users
#
#     items = [
#         UserShort(
#             id=u.id,
#             email=u.email,
#             is_active=u.is_active,
#             full_name=getattr(u, "full_name", None),
#             role=getattr(getattr(u, "role", None), "name", None),   # <- Role -> str
#         )
#         for u in page.items
#     ]
#
#     # rebuild a proper Page[...] with your DTOs
#     return create_page(items, total=page.total, params=params)
