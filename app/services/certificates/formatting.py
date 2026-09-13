"""Formatting helpers for certificate field values."""
from datetime import datetime

_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def format_short_name(full_name: str | None) -> str:
    """"Петров Петр Петрович" -> "Петров П. П.". Falls back to the input
    unchanged if it doesn't look like "Surname First [Middle]"."""
    if not full_name:
        return ""
    parts = full_name.split()
    if len(parts) < 2:
        return full_name
    surname, *rest = parts
    initials = " ".join(f"{p[0]}." for p in rest if p)
    return f"{surname} {initials}".strip()


def format_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_russian_date(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return f"{dt.day} {_MONTHS_RU[dt.month - 1]} {dt.year}"
