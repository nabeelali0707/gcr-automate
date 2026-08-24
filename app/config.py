from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database — defaults to in-memory SQLite for local dev/tests without a .env
    database_url: str = "sqlite+pysqlite:///:memory:"

    # Token encryption (Fernet key, base64-urlsafe 32-byte key)
    fernet_key: str | None = None

    # LLM APIs
    gemini_api_key: str | None = None
    openai_api_key: str | None = None

    # Google OAuth 2.0
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/oauth/google/callback"

    # Telegram
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None  # your personal chat ID for notifications

    # Scheduler
    poll_interval_minutes: int = Field(default=15, ge=5, le=60)
    deadline_threshold_hours: int = Field(default=24, ge=1, le=168)
    app_timezone: str = "UTC"

    # Supabase project info (informational; connection goes through DATABASE_URL)
    supabase_url: str = "https://yfzvrqpztppwebzavlch.supabase.co"
    supabase_anon_key: str = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlmenZycXB6dHBwd2ViemF2bGNoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc1MDgyNTgsImV4cCI6MjEwMzA4NDI1OH0"
        ".V3b607sAKylKDwdpKLiKi4h6Fs4Eumy8WMuf0pO5htQ"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
