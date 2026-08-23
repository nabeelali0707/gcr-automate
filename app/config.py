from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite+pysqlite:///:memory:"
    fernet_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/oauth/google/callback"
    telegram_bot_token: str | None = None
    poll_interval_minutes: int = Field(default=15, ge=5, le=60)
    deadline_threshold_hours: int = Field(default=24, ge=1, le=168)
    app_timezone: str = "UTC"


@lru_cache
def get_settings() -> Settings:
    return Settings()
