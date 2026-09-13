from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.databases import connection
from app.models.database import Region, Settlement, School


class RegionDAO:
    @staticmethod
    @connection
    async def list(
        q: str | None = None,
        offset: int = 0,
        limit: int = 100,
        session: AsyncSession = None,
    ) -> Sequence[Region]:
        stmt = select(Region).order_by(Region.region.asc())
        if q:
            stmt = stmt.where(Region.region.ilike(f"%{q}%"))
        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()


class SettlementDAO:
    @staticmethod
    @connection
    async def list(
        region_id: UUID | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 100,
        session: AsyncSession = None,
    ) -> Sequence[Settlement]:
        stmt = select(Settlement).order_by(Settlement.name.asc())
        if region_id is not None:
            stmt = stmt.where(Settlement.region_id == region_id)
        if q:
            stmt = stmt.where(Settlement.name.ilike(f"%{q}%"))
        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    @connection
    async def get(settlement_id: UUID, session: AsyncSession = None) -> Settlement | None:
        return await session.get(Settlement, settlement_id)


class SchoolDAO:
    @staticmethod
    @connection
    async def list(
        settlement_id: UUID | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 100,
        session: AsyncSession = None,
    ) -> Sequence[School]:
        stmt = select(School).order_by(School.full_name.asc())
        if settlement_id is not None:
            stmt = stmt.where(School.city_id == settlement_id)
        if q:
            stmt = stmt.where(
                School.full_name.ilike(f"%{q}%") | School.short_name.ilike(f"%{q}%")
            )
        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    @connection
    async def get(school_id: UUID, session: AsyncSession = None) -> School | None:
        return await session.get(School, school_id)
