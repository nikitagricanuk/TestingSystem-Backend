from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)  # None, чтобы использовать только env контейнера

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "testing_system"
    db_user: str = "testing_system"
    db_password: str = "testing_system"

    # Redis settings
    redis_host: str = 'redis'
    redis_port: int = 6379
    redis_user: str = 'userAR'
    redis_password: str = '123AR'
    redis_om_url: str | None = None

    # Auth settings
    auth_session_expire_hours: int = 12

    auth_jwt_access_token_expire_minutes: int = 30  # 30 minutes
    auth_jwt_refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_secret_key: str = "f81b1e7ed4e9475481d71269232a0edd7217032ce17d4eccf13770680a7f4342"
    auth_jwt_refresh_secret_key: str = "e3b7f969145c8c041c8845e2f9f0e21a98fcc7c0f7ca8e71a7bf69aa69a14544"
    auth_jwt_issuer: str = "testing-system-api"
    auth_jwt_audience: str = "testing-system-spa"

    # Local filesystem directory for uploaded certificate templates/signatures.
    # A single-node MVP; swap for object storage (S3-compatible) if/when the
    # deployment moves beyond one server.
    certificate_storage_path: str = "data/certificates"

    @field_validator("db_host", "db_name", "db_user", "db_password", mode="before")
    @classmethod
    def _default_if_none(cls, value: str | None, info):
        if value in (None, "", "None"):
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("db_port", mode="before")
    @classmethod
    def _coerce_db_port(cls, value: int | str | None):
        if value in (None, "", "None"):
            return cls.model_fields["db_port"].default
        return value

    @field_validator("redis_om_url", mode="before")
    @classmethod
    def _coerce_redis_om_url(cls, value: str | None):
        if value in (None, "", "None"):
            return None
        return value

    @property
    def get_redis_url(self) -> str:
        if self.redis_om_url:
            return self.redis_om_url
        return (
            f"redis://{self.redis_user}:{self.redis_password}"
            f"@{self.redis_host}:{self.redis_port}"
        )

    @property
    def get_postgres_url(self):
        return (f"postgresql+asyncpg://{self.db_user}:{self.db_password}@"
                f"{self.db_host}:{self.db_port}/{self.db_name}")

settings = Settings()
