import hashlib
from uuid import UUID

from app.core.config import settings
from .formatting import format_duration, format_russian_date, format_short_name


def build_field_values(*, user, result, rank: int | None = None) -> dict[str, str]:
    school = getattr(user, "school", None) if user is not None else None
    school_name = ""
    if school is not None:
        school_name = getattr(school, "short_name", None) or getattr(school, "full_name", None) or ""

    return {
        "full_name_short": format_short_name(getattr(user, "full_name", None) if user else None),
        "score": f"{result.score:.1f}" if getattr(result, "score", None) is not None else "",
        "rank": str(rank) if rank is not None else "",
        "duration": format_duration(getattr(result, "duration_seconds", None)),
        "date": format_russian_date(getattr(result, "time_finish", None)),
        "school": school_name,
    }


def build_verification_code(result_id: UUID) -> str:
    """A short, deterministic verification code for "advanced" (anti-cheat)
    certificates (PV-A-1: "продвинутый ... с античитинг-функциями"). Not a
    cryptographic guarantee against forgery on its own — it's a printed code
    an institution can ask to see and cross-check against this same formula;
    a public verify-by-code endpoint would be the natural next step."""
    digest = hashlib.sha256(f"{result_id}:{settings.auth_jwt_secret_key}".encode()).hexdigest()
    return digest[:10].upper()
