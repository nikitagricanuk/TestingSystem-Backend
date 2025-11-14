from datetime import datetime, timezone


def get_current_time() -> datetime:
    return datetime.now(timezone.utc)

def datetime_to_unix(dt: datetime) -> int:
    return int(dt.timestamp())
