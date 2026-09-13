from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.databases import connection
from app.models.database import CertificateTemplate, CertificateKind


class CertificateTemplateDAO:
    @staticmethod
    @connection
    async def create(
        *,
        name: str,
        kind: CertificateKind,
        asset_path: str,
        test_id: UUID | None = None,
        fields: list | None = None,
        session: AsyncSession = None,
    ) -> CertificateTemplate:
        template = CertificateTemplate(
            name=name, kind=kind, asset_path=asset_path, test_id=test_id, fields=fields or []
        )
        session.add(template)
        await session.flush()
        await session.commit()
        await session.refresh(template)
        return template

    @staticmethod
    @connection
    async def get(template_id: UUID, session: AsyncSession = None) -> CertificateTemplate | None:
        return await session.get(CertificateTemplate, template_id)

    @staticmethod
    @connection
    async def list(test_id: UUID | None = None, session: AsyncSession = None) -> list[CertificateTemplate]:
        stmt = select(CertificateTemplate)
        if test_id is not None:
            stmt = stmt.where(CertificateTemplate.test_id == test_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    @connection
    async def get_for_test(test_id: UUID | None, session: AsyncSession = None) -> CertificateTemplate | None:
        """The template for `test_id` if it has one, else the global default
        (test_id IS NULL) template, if any."""
        if test_id is not None:
            result = await session.execute(
                select(CertificateTemplate).where(CertificateTemplate.test_id == test_id)
            )
            template = result.scalars().first()
            if template is not None:
                return template
        result = await session.execute(
            select(CertificateTemplate).where(CertificateTemplate.test_id.is_(None))
        )
        return result.scalars().first()

    @staticmethod
    @connection
    async def update_fields(
        template_id: UUID,
        fields: list,
        signature_asset_path: str | None = None,
        signature_position: dict | None = None,
        session: AsyncSession = None,
    ) -> CertificateTemplate | None:
        template = await session.get(CertificateTemplate, template_id)
        if template is None:
            return None
        template.fields = fields
        if signature_asset_path is not None:
            template.signature_asset_path = signature_asset_path
        if signature_position is not None:
            template.signature_position = signature_position
        await session.flush()
        await session.commit()
        await session.refresh(template)
        return template

    @staticmethod
    @connection
    async def delete(template_id: UUID, session: AsyncSession = None) -> bool:
        template = await session.get(CertificateTemplate, template_id)
        if template is None:
            return False
        await session.delete(template)
        await session.commit()
        return True
