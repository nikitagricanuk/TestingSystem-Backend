from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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