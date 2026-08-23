"""FastAPI application factory with full lifespan management.

Startup:
  - Initialises the DB (creates tables if missing — dev convenience)
  - Starts the APScheduler deadline-poll job

Shutdown:
  - Gracefully stops the scheduler
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage scheduler and DB init on startup; clean up on shutdown."""
    settings = get_settings()

    # --- DB initialisation (no-op if tables already exist) ---
    try:
        from app.db.session import init_db
        init_db()
        logger.info("Database tables ensured.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB init skipped (no DB configured?): %s", exc)

    # --- Scheduler ---
    scheduler = None
    if settings.telegram_bot_token and settings.google_client_id:
        try:
            from app.api.dependencies import get_monitor
            from app.scheduler import create_scheduler
            monitor = get_monitor()
            scheduler = create_scheduler(monitor, settings.poll_interval_minutes)
            scheduler.start()
            logger.info(
                "Scheduler started — polling every %d min.", settings.poll_interval_minutes
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduler not started: %s", exc)
    else:
        logger.info(
            "Scheduler disabled — set GOOGLE_CLIENT_ID and TELEGRAM_BOT_TOKEN to enable."
        )

    yield  # --- application is running ---

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Classroom Deadline Assistant",
        description=(
            "Deadline radar, requirement digest, scaffold, and manual-submit assistant "
            "for Google Classroom. Human-in-the-loop: the user always supplies the work."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
