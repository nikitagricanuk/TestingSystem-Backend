from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel

from app.utils.time import get_current_time


class User(BaseModel):
    id: UUID
    email: str
    is_active: bool
    role: str | None = None
    permissions: list[str] = []
    created_at: datetime
    created_at_unix: int
    updated_at: datetime | None = None
    updated_at_unix: int | None = None

class UserCreate(BaseModel):
    first_name: str
    middle_name: str | None = None
    second_name: str
    age: int | None = None
    phone: str | None = None
    school_id: str | None = None
    email: str
    password: str
    is_active: bool = True
    role: UUID | None = None
    additional_permissions: list[str] = []

class UserCreateStudent(BaseModel):
    first_name: str
    middle_name: str | None = None
    second_name: str
    age: int | None = None
    phone: str | None = None
    school_id: str | None = None
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    access_token_expires_at: str
    access_token_expires_at_unix: int

    refresh_token_expires_at: str
    refresh_token_expires_at_unix: int

    issued_at: str = get_current_time().isoformat()
    issued_at_unix: int = get_current_time().timestamp()