from __future__ import annotations

from app.db.repository import AssignmentRepository, InMemoryRepository
from app.services.storage import LocalFileStorage

repository = InMemoryRepository()
storage = LocalFileStorage()


def get_repository() -> AssignmentRepository:
    return repository


def get_storage() -> LocalFileStorage:
    return storage
