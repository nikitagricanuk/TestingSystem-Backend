from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.schemas.admissions import ApplicantContactOut, ApplicantContactUpdate
from app.schemas.users import UserFull
from app.services.auth.routers.auth import require_permissions
from app.core.permissions import Permissions
from app.repositories.dao.userdao import UserDAO
from app.repositories.dao.applicantcontactdao import ApplicantContactDAO
from app.models.database import ApplicantContactStatus
from app.services.export.excel_export import build_workbook, UnknownColumnError
from .results import RatingScope, RatingPeriod, _PERIOD_DELTAS, _load_finished_sessions
from datetime import datetime, timezone

router = APIRouter()

_EXPORT_HEADERS = {
    "rank": "Место",
    "name": "ФИО",
    "phone": "Телефон",
    "email": "Эл. почта",
    "score": "Балл",
    "status": "Статус",
    "custom_tag": "Тэг",
}


async def _build_contact_entries(
    *,
    scope: RatingScope,
    period: RatingPeriod,
    test_id: UUID | None,
    region_id: UUID | None,
    settlement_id: UUID | None,
    school_id: UUID | None,
    q: str | None,
) -> list[ApplicantContactOut]:
    sessions = await _load_finished_sessions(test_id=test_id)

    delta = _PERIOD_DELTAS.get(period)
    if delta is not None:
        cutoff = datetime.now(timezone.utc) - delta

        def _after_cutoff(s) -> bool:
            finish = s.time_finish
            if finish is None:
                return False
            if finish.tzinfo is None:
                finish = finish.replace(tzinfo=timezone.utc)
            return finish >= cutoff

        sessions = [s for s in sessions if _after_cutoff(s)]

    if not sessions:
        return []

    user_ids = {UUID(str(s.user_id)) for s in sessions}
    users_by_id = await UserDAO().get_users_by_ids(list(user_ids))

    if scope != RatingScope.GLOBAL:
        def _in_scope(session) -> bool:
            user = users_by_id.get(UUID(str(session.user_id)))
            school = getattr(user, "school", None)
            settlement = getattr(school, "settlement", None) if school else None
            if scope == RatingScope.SCHOOL:
                return school_id is not None and school is not None and school.id == school_id
            if scope == RatingScope.CITY:
                return settlement_id is not None and school is not None and school.city_id == settlement_id
            if scope == RatingScope.REGION:
                return region_id is not None and settlement is not None and settlement.region_id == region_id
            return True

        sessions = [s for s in sessions if _in_scope(s)]

    # Best score per user (a user may have multiple finished attempts).
    best_score_by_user: dict[UUID, float] = {}
    for session in sessions:
        uid = UUID(str(session.user_id))
        score = session.score or 0.0
        if uid not in best_score_by_user or score > best_score_by_user[uid]:
            best_score_by_user[uid] = score

    contacts_by_user = await ApplicantContactDAO.list_for_users(list(best_score_by_user.keys()))

    ranked = sorted(best_score_by_user.items(), key=lambda item: item[1], reverse=True)

    entries: list[ApplicantContactOut] = []
    for rank, (user_id, score) in enumerate(ranked, start=1):
        user = users_by_id.get(user_id)
        name = getattr(user, "full_name", None) or getattr(user, "nickname", None) or "—"
        if q and q.lower() not in name.lower():
            continue
        contact = contacts_by_user.get(user_id)
        entries.append(
            ApplicantContactOut(
                rank=rank,
                user_id=user_id,
                name=name,
                phone=getattr(user, "phone_number", None) if user else None,
                email=getattr(user, "email", None) if user else None,
                score=score,
                status=(contact.status.value if contact else ApplicantContactStatus.NOT_CALLED.value),
                custom_tag=contact.custom_tag if contact else None,
            )
        )

    return entries


@router.get("/admissions/contacts", response_model=list[ApplicantContactOut])
async def list_applicant_contacts(
    current_user: UserFull = Depends(require_permissions(Permissions.ApplicantContacts.READ)),
    scope: RatingScope = Query(RatingScope.GLOBAL),
    period: RatingPeriod = Query(RatingPeriod.ALL),
    test_id: UUID | None = None,
    region_id: UUID | None = None,
    settlement_id: UUID | None = None,
    school_id: UUID | None = None,
    q: str | None = Query(None, description="Filter by name substring"),
) -> list[ApplicantContactOut]:
    """
    Admissions-committee "Общий рейтинг": same scope/period rating as students
    see, but with contact info (phone/email) and a call-status/tag workflow —
    never exposed to teachers or students.
    """
    return await _build_contact_entries(
        scope=scope, period=period, test_id=test_id, region_id=region_id,
        settlement_id=settlement_id, school_id=school_id, q=q,
    )


@router.get("/admissions/contacts/export")
async def export_applicant_contacts(
    current_user: UserFull = Depends(require_permissions(Permissions.ApplicantContacts.READ)),
    scope: RatingScope = Query(RatingScope.GLOBAL),
    period: RatingPeriod = Query(RatingPeriod.ALL),
    test_id: UUID | None = None,
    region_id: UUID | None = None,
    settlement_id: UUID | None = None,
    school_id: UUID | None = None,
    q: str | None = None,
    columns: str = Query(
        "rank,name,phone,email,score,status,custom_tag",
        description="Comma-separated column list, in export order",
    ),
) -> Response:
    """Excel export of the same rating the JSON endpoint returns, with the
    admissions committee choosing which columns to include and their order."""
    column_list = [c.strip() for c in columns.split(",") if c.strip()]
    entries = await _build_contact_entries(
        scope=scope, period=period, test_id=test_id, region_id=region_id,
        settlement_id=settlement_id, school_id=school_id, q=q,
    )
    rows = [entry.model_dump() for entry in entries]
    try:
        content = build_workbook(rows, columns=column_list, headers=_EXPORT_HEADERS, sheet_title="Рейтинг")
    except UnknownColumnError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="rating.xlsx"'},
    )


@router.patch("/admissions/contacts/{user_id}", response_model=ApplicantContactOut)
async def update_applicant_contact(
    user_id: UUID,
    payload: ApplicantContactUpdate,
    current_user: UserFull = Depends(require_permissions(Permissions.ApplicantContacts.UPDATE)),
) -> ApplicantContactOut:
    try:
        status_enum = ApplicantContactStatus(payload.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status; expected one of {[s.value for s in ApplicantContactStatus]}",
        )

    user = await UserDAO().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    contact = await ApplicantContactDAO.upsert(user_id, status_enum, payload.custom_tag)

    return ApplicantContactOut(
        rank=0,
        user_id=user_id,
        name=getattr(user, "full_name", None) or getattr(user, "nickname", None) or "—",
        phone=getattr(user, "phone_number", None),
        email=getattr(user, "email", None),
        score=0.0,
        status=contact.status.value,
        custom_tag=contact.custom_tag,
    )
