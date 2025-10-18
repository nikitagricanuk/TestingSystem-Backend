from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # Postgres settings
    db_host: str = 'db'
    db_port: int = 5432
    db_name: str = 'testingsystem'
    db_user: str
    db_password: str

    # Redis settings
    redis_host: str = 'redis'
    redis_port: int = 6379
    redis_user: str
    redis_password: str

    # Auth settings
    auth_session_expire_hours: int = 12

    auth_jwt_access_token_expire_minutes: int = 30  # 30 minutes
    auth_jwt_refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_secret_key: str = "f81b1e7ed4e9475481d71269232a0edd7217032ce17d4eccf13770680a7f4342"
    auth_jwt_refresh_secret_key: str = "e3b7f969145c8c041c8845e2f9f0e21a98fcc7c0f7ca8e71a7bf69aa69a14544"
    auth_jwt_issuer: str = "testing-system-api"
    auth_jwt_audience: str = "testing-system-spa"

    @property
    def get_redis_url(self) -> str:
        return (
            f"redis://{self.redis_user}:{self.redis_password}"
            f"@{self.redis_host}:{self.redis_port}"
        )

    @property
    def get_postgres_url(self):
        return (f"postgresql+asyncpg://{self.db_user}:{self.db_password}@"
                f"{self.db_host}:{self.db_port}/{self.db_name}")

settings = Settings()