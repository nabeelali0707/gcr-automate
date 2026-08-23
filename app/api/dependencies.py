"""FastAPI dependency providers.

For local development / tests the in-memory singletons are used by default.
When a real DB and Google credentials are present the SQL-backed versions
are returned instead.
"""
from __future__ import annotations

from app.db.repository import AssignmentRepository, InMemoryRepository
from app.services.storage import LocalFileStorage

# Module-level singletons used as defaults in dev/test.
_repository: AssignmentRepository = InMemoryRepository()
_storage: LocalFileStorage = LocalFileStorage()


def get_repository() -> AssignmentRepository:
    return _repository


def get_storage() -> LocalFileStorage:
    return _storage


def get_monitor():
    """Build a DeadlineMonitor using either a live Classroom client (if OAuth
    credentials and a stored token are available) or the demo client.

    Used by the lifespan scheduler.
    """
    from uuid import UUID
    from app.config import get_settings
    from app.services.monitor import DeadlineMonitor

    settings = get_settings()
    USER_ID = UUID("00000000-0000-0000-0000-000000000001")

    if settings.google_client_id and settings.fernet_key:
        try:
            from app.db.session import SessionLocal
            from app.db.sql_repository import OAuthTokenRepository
            from app.integrations.oauth import (
                TokenCipher,
                build_credentials,
                build_classroom_service,
            )
            from app.integrations.classroom import GoogleClassroomClient

            cipher = TokenCipher(settings.fernet_key)
            with SessionLocal() as db:
                token_repo = OAuthTokenRepository(db, cipher)
                bundle = token_repo.load(USER_ID)

            if bundle:
                creds = build_credentials(bundle, settings.google_client_id, settings.google_client_secret)
                service = build_classroom_service(creds)
                classroom = GoogleClassroomClient(service)
                return DeadlineMonitor(
                    classroom=classroom,
                    repository=_repository,
                    user_id=USER_ID,
                    threshold_hours=settings.deadline_threshold_hours,
                )
        except Exception:  # noqa: BLE001
            pass  # Fall through to demo client

    # Fallback: demo client (no Google credentials required)
    from app.services.demo import DemoClassroomClient
    return DeadlineMonitor(
        classroom=DemoClassroomClient(),
        repository=_repository,
        user_id=USER_ID,
        threshold_hours=settings.deadline_threshold_hours,
    )
