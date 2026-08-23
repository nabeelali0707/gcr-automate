from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class AssignmentStatus(StrEnum):
    PENDING = "pending"
    DIGESTED = "digested"
    SCAFFOLDED = "scaffolded"
    AWAITING_FILES = "awaiting_files"
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTED = "submitted"
    SKIPPED = "skipped"
    FAILED = "failed"


class GeneratedFileKind(StrEnum):
    DIGEST = "digest"
    SCAFFOLD = "scaffold"
    USER_SUBMISSION = "user_submission"


@dataclass(frozen=True)
class Course:
    id: str
    user_id: UUID
    name: str
    section: str | None = None


@dataclass
class Assignment:
    id: str
    course_id: str
    title: str
    due_at: datetime
    submission_state: str
    status: AssignmentStatus = AssignmentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class GeneratedFile:
    assignment_id: str
    kind: GeneratedFileKind
    filename: str
    storage_path: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentRun:
    assignment_id: str
    state: str
    attempt: int = 0
    error: str | None = None
    id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
