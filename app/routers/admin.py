from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from aredis_om import NotFoundError
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.admin import AdminStatsOut, WeekdayLoad, AdminDemographicsOut, RegionCount, AgeBucketCount
from app.schemas.users import UserFull
from app.services.auth.routers.auth import get_current_user
from app.services.testing_engine.models.redis import Session as SessionModel, SessionStatus
from app.repositories.dao.userdao import UserDAO
from .results import _load_finished_sessions

router = APIRouter()

_WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
_ACTIVE_NOW_WINDOW = timedelta(minutes=5)


def _require_admin(current_user: UserFull = Depends(get_current_user)) -> UserFull:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


async def _load_all_sessions() -> list[SessionModel]:
    sessions: list[SessionModel] = []
    try:
        pk_iter = await SessionModel.all_pks()
        async for pk in pk_iter:
            try:
                sessions.append(await SessionModel.get(pk))
            except NotFoundError:
                continue
    except Exception:
        return []
    return sessions


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.get("/admin/stats", response_model=AdminStatsOut)
async def get_admin_stats(current_user: UserFull = Depends(_require_admin)) -> AdminStatsOut:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    sessions = await _load_all_sessions()

    active_now = 0
    active_today_users: set[str] = set()
    for session in sessions:
        status_value = session.status.value if isinstance(session.status, SessionStatus) else str(session.status)
        last_activity = _aware(getattr(session, "last_activity", None))
        if status_value == SessionStatus.ACTIVE.value and last_activity and (now - last_activity) <= _ACTIVE_NOW_WINDOW:
            active_now += 1
        if last_activity and last_activity >= today_start:
            active_today_users.add(str(session.user_id))

    finished = await _load_finished_sessions()
    scores = [s.score for s in finished if s.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    return AdminStatsOut(
        active_now=active_now,
        active_today=len(active_today_users),
        avg_score=avg_score,
        total_finished_attempts=len(finished),
    )


@router.get("/admin/stats/load", response_model=list[WeekdayLoad])
async def get_admin_load_by_weekday(current_user: UserFull = Depends(_require_admin)) -> list[WeekdayLoad]:
    """Sessions started per day of the week (all-time distribution), for the
    Admin PDF dashboard's "Распределение нагрузки по дням недели" chart."""
    sessions = await _load_all_sessions()
    counts = [0] * 7
    for session in sessions:
        started = _aware(getattr(session, "time_start", None))
        if started is None:
            continue
        counts[started.weekday()] += 1

    return [
        WeekdayLoad(weekday=i, label=_WEEKDAY_LABELS[i], count=counts[i])
        for i in range(7)
    ]


@router.get("/admin/stats/demographics", response_model=AdminDemographicsOut)
async def get_admin_demographics(current_user: UserFull = Depends(_require_admin)) -> AdminDemographicsOut:
    """Counts by region and age bracket among students who have taken at least
    one test — PV-A-1's "Сколько человек прошло тест? Из каких регионов...
    Возраст участников?"."""
    sessions = await _load_all_sessions()
    user_ids = {UUID(str(s.user_id)) for s in sessions}
    users_by_id = await UserDAO().get_users_by_ids(list(user_ids))

    region_counts: dict[str, int] = {}
    age_counts: dict[str, int] = {}

    def _age_bucket(age: int | None) -> str:
        if age is None:
            return "Неизвестно"
        if age < 14:
            return "<14"
        if age <= 15:
            return "14-15"
        if age <= 17:
            return "16-17"
        if age <= 18:
            return "18"
        return "19+"

    for user in users_by_id.values():
        school = getattr(user, "school", None)
        settlement = getattr(school, "settlement", None) if school else None
        region = getattr(settlement, "region", None) if settlement else None
        region_name = getattr(region, "region", None) if region else None
        region_counts[region_name] = region_counts.get(region_name, 0) + 1

        bucket = _age_bucket(getattr(user, "age", None))
        age_counts[bucket] = age_counts.get(bucket, 0) + 1

    return AdminDemographicsOut(
        by_region=[RegionCount(region=region, count=count) for region, count in region_counts.items()],
        by_age=[AgeBucketCount(bucket=bucket, count=count) for bucket, count in age_counts.items()],
    )
