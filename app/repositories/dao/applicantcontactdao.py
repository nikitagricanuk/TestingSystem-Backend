from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.databases import connection
from app.models.database import ApplicantContact, ApplicantContactStatus


class ApplicantContactDAO:
    @staticmethod
    @connection
    async def list_for_users(
        user_ids: list[UUID], session: AsyncSession = None
    ) -> dict[UUID, ApplicantContact]:
        if not user_ids:
            return {}
        result = await session.execute(
            select(ApplicantContact).where(ApplicantContact.user_id.in_(user_ids))
        )
        return {contact.user_id: contact for contact in result.scalars().all()}

    @staticmethod
    @connection
    async def upsert(
        user_id: UUID,
        status: ApplicantContactStatus,
        custom_tag: str | None = None,
        session: AsyncSession = None,
    ) -> ApplicantContact:
        result = await session.execute(select(ApplicantContact).where(ApplicantContact.user_id == user_id))
        contact = result.scalar_one_or_none()
        if contact is None:
            contact = ApplicantContact(user_id=user_id, status=status, custom_tag=custom_tag)
            session.add(contact)
        else:
            contact.status = status
            contact.custom_tag = custom_tag
        await session.flush()
        await session.commit()
        await session.refresh(contact)
        return contact
