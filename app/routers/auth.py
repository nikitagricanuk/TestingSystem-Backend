from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi import Security
from fastapi import Body
import re
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.repositories.dao.userdao import UserDAO, RoleEnum
from app.schemas.users import User, UserCreate, LoginResponse, LoginRequest, UserCreateStudent
from app.utils.password import get_hashed_password, verify_password
from app.services.auth.jwt_service import get_jwt_service, JWTService
from app.services.auth.sessions import Session
from typing import Optional

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

    db_user = await UserDAO().get_user_with_role_and_permissions(uid)
    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")

    # Build a detached Pydantic schema to avoid lazy-load after Session close
    role_name = None
    try:
        role = getattr(db_user, "role", None)
        if role is not None:
            # prefer `.name`, fall back to `.role` if your model uses that
            role_name = getattr(role, "name", None)
            if role_name is None:
                role_name = getattr(role, "role", None)
    except Exception as e:
        logger.warning(f"Error retrieving role for user {db_user.id}: {e}")
        role_name = None

    try:
        permissions_list = []
        # 1) direct user permissions (if your model has them)
        user_perms = getattr(db_user, "permissions", None)
        if user_perms:
            permissions_list.extend([
                getattr(p, "name", None) for p in user_perms if getattr(p, "name", None) is not None
            ])
        # 2) permissions via role
        role = getattr(db_user, "role", None)
        if role is not None:
            role_perms = getattr(role, "permissions", None)
            if role_perms:
                permissions_list.extend([
                    getattr(p, "name", None) for p in role_perms if getattr(p, "name", None) is not None
                ])
        # de-duplicate preserving order
        permissions_list = list(dict.fromkeys(permissions_list))
    except Exception:
        permissions_list = []

    created_at_unix = int(db_user.created_at.timestamp()) if getattr(db_user, "created_at", None) else None
    updated_at_unix = int(db_user.updated_at.timestamp()) if getattr(db_user, "updated_at", None) else None

    return User(
        id=db_user.id,
        email=db_user.email,
        is_active=db_user.is_active,
        role=role_name,
        permissions=permissions_list,
        created_at=db_user.created_at,
        created_at_unix=created_at_unix,
        updated_at=db_user.updated_at,
        updated_at_unix=updated_at_unix,
    )

def require_roles(*allowed_roles: int):
    """Factory for a role-checking dependency based on user.role_id."""
    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        if allowed_roles and current_user.role_id not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user
    return _dep

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, request: Request, jwt: JWTService = Depends(get_jwt_service)) -> LoginResponse:
    user = await UserDAO().get_user_by_email(credentials.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_extra = {
        "role": str(user.role_id) if user.role_id else None,
    }
    refresh_extra = {"uid": str(user.id),
                     "role": str(user.role_id) if user.role_id else None}

    # 4) Issue tokens
    pair = await jwt.create(subject=str(user.id), access_extra=access_extra, refresh_extra=refresh_extra, session_ip=request.client.host)

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
@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

@router.post("/signup", response_model=User)
async def create_student_account(user: UserCreateStudent) -> User:
    hashed_password = get_hashed_password(user.password)
    created_user = await UserDAO().create(
        first_name=user.first_name,
        middle_name=user.middle_name,
        second_name=user.second_name,
        age=user.age,
        email=user.email,
        phone=user.phone,
        password=hashed_password,
        role=await UserDAO().get_role_id(RoleEnum.STUDENT),
        school_id=user.school_id
    )
    return User(
        id=created_user.id,
        email=created_user.email,
        is_active=created_user.is_active,
        # Use helper to avoid leaking UUIDs as role
        role=_role_name_from_model(created_user),
        permissions=[],  # You might want to fetch and include permissions here
        created_at=created_user.created_at,
        created_at_unix=int(created_user.created_at.timestamp()),
        updated_at=created_user.updated_at,
        updated_at_unix=int(created_user.updated_at.timestamp()) if created_user.updated_at else None
    )

@router.post("/users/create", response_model=User)
async def create_user(user: dict = Body(...)) -> User:
    hashed_password = get_hashed_password(user["password"])  # tests stub this

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

    created_user = await UserDAO().create(
        first_name=user.get("first_name"),
        middle_name=user.get("middle_name"),
        second_name=user.get("second_name"),
        age=user.get("age"),
        email=user.get("email"),
        phone=user.get("phone"),
        password=hashed_password,
        role=role_id or user.get("role"),
        school_id=user.get("school_id"),
    )
    return User(
        id=created_user.id,
        email=created_user.email,
        is_active=created_user.is_active,
        role=_role_name_from_model(created_user),
        permissions=[],
        created_at=created_user.created_at,
        created_at_unix=int(created_user.created_at.timestamp()),
        updated_at=created_user.updated_at,
        updated_at_unix=int(created_user.updated_at.timestamp()) if created_user.updated_at else None,
    )