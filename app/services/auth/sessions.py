import uuid
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.databases import init_redis_connection
from redis_om import HashModel, Field
from app.utils.time import get_current_time

redis = init_redis_connection()

class Session(HashModel):
    sid: uuid.UUID = Field(index=True, default_factory=uuid.uuid4)
    user_id: int
    ip_address: str
    user_agent: str | None = None  # browser / device info
    access_token: str = Field(default_factory=lambda: uuid.uuid4().hex)  # or session_token, JWT, UUID, etc.
    refresh_token: str | None = None  # if you use refresh cycles
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=settings.session_expire_hours))
    last_active: datetime | None = None  # for session timeout logic
    is_active: bool = True  # quick flag for logout / invalidation

    class Meta:
        database = redis

    @classmethod
    def create(cls, user_id: int, ip: str, ua: str) -> "Session":
        s = cls(
            user_id=user_id,
            ip_address=ip,
            user_agent=ua,
            # access_token, created_at, expires_at will be auto-filled by default_factory
            last_active=get_current_time(),
            is_active=True,
        ).save()
        return s

    def refresh(self, ttl_hours=12):
        """Extend session lifetime"""
        self.expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        self.last_active = datetime.utcnow()
        self.save()

    def invalidate(self):
        """Mark as logged out"""
        self.is_active = False
        self.save()

    @classmethod
    def validate(cls, sid: uuid.UUID) -> "Session | None":
        # Scan keys that belong to this model and compare stored `sid` values.
        pattern = f"{cls.__name__}:*"
        for key in redis.scan_iter(pattern):
            # handle bytes vs str depending on connection settings
            if isinstance(key, bytes):
                key = key.decode()
            pk = key.split(":")[-1]
            try:
                obj = cls.get(pk)
            except Exception:
                continue
            if obj and obj.sid == sid:
                return obj
        return None