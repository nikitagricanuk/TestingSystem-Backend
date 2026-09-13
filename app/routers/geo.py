from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.repositories.dao.geodao import RegionDAO, SettlementDAO, SchoolDAO
from app.schemas.geo import RegionOut, SettlementOut, SchoolOut

router = APIRouter()


@router.get("/regions", response_model=list[RegionOut])
async def list_regions(
    q: str | None = Query(None, description="Filter by region name substring"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[RegionOut]:
    regions = await RegionDAO.list(q=q, offset=offset, limit=limit)
    return [RegionOut(id=r.id, region=r.region) for r in regions]


@router.get("/settlements", response_model=list[SettlementOut])
async def list_settlements(
    region_id: UUID | None = None,
    q: str | None = Query(None, description="Filter by settlement name substring"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[SettlementOut]:
    settlements = await SettlementDAO.list(region_id=region_id, q=q, offset=offset, limit=limit)
    return [
        SettlementOut(id=s.id, name=s.name, type=s.type, region_id=s.region_id)
        for s in settlements
    ]


@router.get("/schools", response_model=list[SchoolOut])
async def list_schools(
    settlement_id: UUID | None = None,
    q: str | None = Query(None, description="Filter by school name substring"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[SchoolOut]:
    schools = await SchoolDAO.list(settlement_id=settlement_id, q=q, offset=offset, limit=limit)
    return [
        SchoolOut(id=s.id, full_name=s.full_name, short_name=s.short_name, city_id=s.city_id)
        for s in schools
    ]
