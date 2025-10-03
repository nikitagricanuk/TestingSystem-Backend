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

    @property
    def get_redis_url(self) -> str:
        return (
            f"redis://{self.redis_user}:{self.redis_password}"
            f"@{self.redis_host}:{self.redis_port}"
        )

settings = Settings()