from uuid import UUID

from pydantic import BaseModel


class RegionOut(BaseModel):
    id: UUID
    region: str


class SettlementOut(BaseModel):
    id: UUID
    name: str
    type: str
    region_id: UUID


class SchoolOut(BaseModel):
    id: UUID
    full_name: str
    short_name: str | None = None
    city_id: UUID
