import uuid
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.databases import init_redis_connection
from redis_om import HashModel, Field
from app.utils.time import get_current_time

# Lazy Redis getter to avoid connecting at import time (helps tests)
_redis = None

def get_redis():
    global _redis
    if _redis is None:
        _redis = init_redis_connection()
    return _redis


class Session(HashModel):
    sid: uuid.UUID = Field(index=True, default_factory=uuid.uuid4)
    user_id: str
    ip_address: str
    user_agent: str | None = None  # browser / device info
    refresh_token: str | None = Field(index=True, default=None)  # if you use refresh cycles
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=settings.auth_session_expire_hours))
    last_active: datetime | None = None  # for session timeout logic
    is_active: bool = True  # quick flag for logout / invalidation

    class Meta:
        database = None  # set lazily to avoid import-time connection

    @classmethod
    def _ensure_db(cls):
        if getattr(cls.Meta, "database", None) is None:
            cls.Meta.database = get_redis()

    @classmethod
    def create(cls, user_id: str, ip: str, refresh_token: str, ua: str | None) -> "Session":
        cls._ensure_db()
        s = cls(
            user_id=user_id,
            ip_address=ip,
            user_agent=ua,
            refresh_token=refresh_token,
            last_active=get_current_time(),
            is_active=True,
        ).save()
        return s

    def invalidate(self):
        """Mark as logged out"""
        self.__class__._ensure_db()
        self.is_active = False
        self.save()

    @classmethod
    def validate(cls, refresh_token: str) -> "Session | None":
        """
        Validate a *refresh token* and return the owning session if it's active and not expired.
        Returns None when no matching/valid session exists.
        """
        cls._ensure_db()
        if not refresh_token:
            return None

        # Query by indexed refresh_token (fast) and then apply safety checks.
        try:
            matches = cls.find(cls.refresh_token == refresh_token).all()
        except Exception:
            matches = []

        if not matches:
            return None

        now = get_current_time()
        for s in matches:
            # Accept the first session that is marked active and whose expiry is in the future
            if s.is_active and (s.expires_at is None or s.expires_at > now):
                return s

        return None
