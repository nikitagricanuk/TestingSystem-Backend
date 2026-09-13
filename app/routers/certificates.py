from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.core.permissions import Permissions
from app.models.database import CertificateKind
from app.repositories.dao.certificatedao import CertificateTemplateDAO
from app.repositories.dao.testdao import TestDAO
from app.repositories.dao.userdao import UserDAO
from app.schemas.certificates import (
    CertificateFieldsUpdate,
    CertificateTemplateOut,
)
from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user, require_permissions
from app.services.certificates import storage
from app.services.certificates.field_values import build_field_values, build_verification_code
from app.services.certificates.rendering import render_certificate, wrap_image_as_pdf
from .results import _load_session, _build_result, _load_finished_sessions

router = APIRouter()

_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg"}


def _template_out(template) -> CertificateTemplateOut:
    return CertificateTemplateOut(
        id=template.id,
        test_id=template.test_id,
        name=template.name,
        kind=template.kind.value if hasattr(template.kind, "value") else str(template.kind),
        fields=template.fields or [],
        has_signature=bool(template.signature_asset_path),
        signature_position=template.signature_position,
    )


@router.post("/certificates/templates", response_model=CertificateTemplateOut, status_code=status.HTTP_201_CREATED)
async def upload_certificate_template(
    file: UploadFile = File(...),
    name: str = Query(...),
    kind: CertificateKind = Query(CertificateKind.BASE),
    test_id: UUID | None = Query(None, description="Omit for the global default template"),
    current_user: UserFull = Depends(require_permissions(Permissions.Certificates.CREATE)),
) -> CertificateTemplateOut:
    """
    Upload a certificate background — a PDF, or an image (PNG/JPG), which gets
    wrapped into a single-page PDF so rendering only ever handles one format.
    """
    if test_id is not None:
        test = await TestDAO.get(test_id)
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    raw = await file.read()
    content_type = (file.content_type or "").lower()
    if content_type in _IMAGE_CONTENT_TYPES:
        try:
            pdf_bytes = wrap_image_as_pdf(raw)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid image: {exc}") from exc
    elif content_type == "application/pdf":
        pdf_bytes = raw
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type {content_type!r}; expected a PDF or PNG/JPG image",
        )

    relative_path = storage.save_bytes(pdf_bytes, suffix=".pdf")
    template = await CertificateTemplateDAO.create(
        name=name, kind=kind, asset_path=relative_path, test_id=test_id,
    )
    return _template_out(template)


@router.get("/certificates/templates", response_model=list[CertificateTemplateOut])
async def list_certificate_templates(
    test_id: UUID | None = None,
    current_user: UserFull = Depends(require_permissions(Permissions.Certificates.READ)),
) -> list[CertificateTemplateOut]:
    templates = await CertificateTemplateDAO.list(test_id=test_id)
    return [_template_out(t) for t in templates]


@router.patch("/certificates/templates/{template_id}/fields", response_model=CertificateTemplateOut)
async def update_certificate_template_fields(
    template_id: UUID,
    payload: CertificateFieldsUpdate,
    current_user: UserFull = Depends(require_permissions(Permissions.Certificates.UPDATE)),
) -> CertificateTemplateOut:
    """Persists field placements from the (future) drag-and-drop editor."""
    template = await CertificateTemplateDAO.update_fields(
        template_id,
        fields=[f.model_dump() for f in payload.fields],
        signature_position=payload.signature_position.model_dump() if payload.signature_position else None,
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _template_out(template)


@router.post("/certificates/templates/{template_id}/signature", response_model=CertificateTemplateOut)
async def upload_certificate_signature(
    template_id: UUID,
    file: UploadFile = File(...),
    current_user: UserFull = Depends(require_permissions(Permissions.Certificates.UPDATE)),
) -> CertificateTemplateOut:
    template = await CertificateTemplateDAO.get(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    content_type = (file.content_type or "").lower()
    if content_type not in _IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature must be a PNG/JPG image")

    raw = await file.read()
    suffix = ".png" if content_type == "image/png" else ".jpg"
    relative_path = storage.save_bytes(raw, suffix=suffix)

    updated = await CertificateTemplateDAO.update_fields(
        template_id, fields=template.fields or [], signature_asset_path=relative_path,
    )
    return _template_out(updated)


@router.delete("/certificates/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificate_template(
    template_id: UUID,
    current_user: UserFull = Depends(require_permissions(Permissions.Certificates.UPDATE)),
):
    deleted = await CertificateTemplateDAO.delete(template_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


async def _rank_for_test(test_id: UUID, user_id: UUID) -> int | None:
    sessions = await _load_finished_sessions(test_id=test_id)
    if not sessions:
        return None
    ranked = sorted(sessions, key=lambda s: s.score or 0.0, reverse=True)
    for position, session in enumerate(ranked, start=1):
        if str(session.user_id) == str(user_id):
            return position
    return None


@router.get("/results/{result_id}/certificate")
async def download_certificate(
    result_id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> Response:
    """
    Download the filled certificate PDF for one result. The result's own owner
    can always download their own certificate; admin/admissions_committee (via
    read_certificates) can download for any user — PV-A-1: "Админ должен иметь
    возможность скачать сертификат для конкретного пользователя". Guests never
    get certificates.
    """
    session = await _load_session(result_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")

    is_owner = str(session.user_id) == str(current_user.id) and not current_user.is_guest
    is_staff = "read_certificates" in (current_user.permissions or [])
    if not (is_owner or is_staff):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Certificate not available")

    result = await _build_result(session)
    if result.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test not finished yet")

    template = await CertificateTemplateDAO.get_for_test(result.test_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No certificate template configured")

    user = await UserDAO().get_user_by_id(result.user_id)
    rank = await _rank_for_test(result.test_id, result.user_id)
    field_values = build_field_values(user=user, result=result, rank=rank)
    if template.kind == CertificateKind.ADVANCED or str(getattr(template.kind, "value", template.kind)) == "advanced":
        field_values["verification_code"] = build_verification_code(result.id)

    signature_path = storage.resolve(template.signature_asset_path) if template.signature_asset_path else None

    try:
        pdf_bytes = render_certificate(
            storage.resolve(template.asset_path),
            template.fields or [],
            field_values,
            signature_path=signature_path,
            signature_position=template.signature_position,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Template asset missing") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificate-{result_id}.pdf"'},
    )
