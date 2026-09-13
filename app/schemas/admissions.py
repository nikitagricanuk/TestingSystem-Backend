from uuid import UUID

from pydantic import BaseModel


class ApplicantContactOut(BaseModel):
    rank: int
    user_id: UUID
    name: str
    phone: str | None = None
    email: str | None = None
    score: float
    status: str
    custom_tag: str | None = None


class ApplicantContactUpdate(BaseModel):
    status: str
    custom_tag: str | None = None
