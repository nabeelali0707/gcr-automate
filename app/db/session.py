"""Database engine and session factory.

Usage:
    from app.db.session import engine, SessionLocal, get_db

    with SessionLocal() as session:
        ...

Or as a FastAPI dependency:

    from fastapi import Depends
    from sqlalchemy.orm import Session
    from app.db.session import get_db

    def endpoint(db: Session = Depends(get_db)):
        ...
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _make_engine():
    settings = get_settings()
    connect_args: dict = {}
    # SQLite needs check_same_thread=False for multi-threaded FastAPI
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, connect_args=connect_args, echo=False)


engine = _make_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency that yields a DB session and closes it after the request."""
    with SessionLocal() as db:
        yield db


def init_db() -> None:
    """Create all tables if they don't exist (idempotent).

    For production, prefer running scripts/schema.sql via psql instead.
    """
    from app.db.orm import Base  # noqa: F401 — import all ORM models so Base knows them
    Base.metadata.create_all(bind=engine)
