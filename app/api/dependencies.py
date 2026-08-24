"""FastAPI dependency providers.

Injects the Postgres-backed SqlRepository when a database URL is configured
in settings, falling back to the InMemoryRepository for local development/tests.
Also manages background job sessions.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.repository import AssignmentRepository, InMemoryRepository
from app.db.session import get_db
from app.db.sql_repository import SqlRepository
from app.services.storage import LocalFileStorage

# Module-level singletons used as fallbacks in dev/test.
_repository: AssignmentRepository = InMemoryRepository()
_storage: LocalFileStorage = LocalFileStorage()

USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_repository(db: Session = Depends(get_db)) -> AssignmentRepository:
    """Dependency that returns the appropriate repository.

    Uses SQL-backed repository if a live database is configured, otherwise
    falls back to the in-memory singleton.
    """
    settings = get_settings()
    if "sqlite:///:memory:" not in settings.database_url:
        return SqlRepository(db)
    return _repository


def get_storage() -> LocalFileStorage:
    return _storage


def get_monitor(db: Session | None = None) -> Any:
    """Build a DeadlineMonitor using either a live Classroom client (if OAuth
    credentials and a stored token are available) or the demo client.
    """
    from app.services.monitor import DeadlineMonitor

    settings = get_settings()

    # Determine repository to use
    repo = _repository
    if "sqlite:///:memory:" not in settings.database_url and db is not None:
        repo = SqlRepository(db)

    if settings.google_client_id and settings.fernet_key:
        try:
            from app.db.session import SessionLocal
            from app.db.sql_repository import OAuthTokenRepository
            from app.integrations.oauth import (
                TokenCipher,
                build_classroom_service,
                build_credentials,
            )
            from app.integrations.classroom import GoogleClassroomClient

            # If no db session provided but database is configured, open a temporary one
            temp_db = None
            if db is None and "sqlite:///:memory:" not in settings.database_url:
                temp_db = SessionLocal()
                active_db = temp_db
                repo = SqlRepository(active_db)
            else:
                active_db = db

            if active_db is not None:
                cipher = TokenCipher(settings.fernet_key)
                token_repo = OAuthTokenRepository(active_db, cipher)
                bundle = token_repo.load(USER_ID)
            else:
                bundle = None

            if temp_db is not None:
                temp_db.close()

            if bundle:
                creds = build_credentials(bundle, settings.google_client_id, settings.google_client_secret)
                service = build_classroom_service(creds)
                classroom = GoogleClassroomClient(service)
                return DeadlineMonitor(
                    classroom=classroom,
                    repository=repo,
                    user_id=USER_ID,
                    threshold_hours=settings.deadline_threshold_hours,
                    telegram_bot_token=settings.telegram_bot_token,
                    telegram_chat_id=settings.telegram_chat_id,
                )
        except Exception:  # noqa: BLE001
            pass  # Fall through to demo client

    # Fallback: demo client (no Google credentials required)
    from app.services.demo import DemoClassroomClient
    return DeadlineMonitor(
        classroom=DemoClassroomClient(),
        repository=repo,
        user_id=USER_ID,
        threshold_hours=settings.deadline_threshold_hours,
        telegram_bot_token=settings.telegram_bot_token,
        telegram_chat_id=settings.telegram_chat_id,
    )


def run_background_poll() -> None:
    """Entrypoint for the scheduler job.

    Opens a fresh DB session, retrieves a live monitor, and polls Classroom.
    This avoids stale connection / thread-safety issues with SQLAlchemy.
    """
    from app.db.session import SessionLocal

    settings = get_settings()
    if "sqlite:///:memory:" not in settings.database_url:
        with SessionLocal() as db:
            monitor = get_monitor(db)
            monitor.poll_once()
    else:
        monitor = get_monitor()
        monitor.poll_once()
