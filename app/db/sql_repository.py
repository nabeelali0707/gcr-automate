"""SQLAlchemy implementation of AssignmentRepository.

Fulfills the same Protocol as InMemoryRepository so it's a drop-in swap
for production use.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Assignment, AssignmentStatus, Course, GeneratedFile, GeneratedFileKind
from app.db.orm import (
    AssignmentRow,
    CourseRow,
    GeneratedFileRow,
    OAuthTokenRow,
)
from app.integrations.oauth import EncryptedOAuthTokenBundle, OAuthTokenBundle, TokenCipher


class SqlRepository:
    """Postgres-backed implementation of AssignmentRepository."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Courses
    # ------------------------------------------------------------------

    def upsert_course(self, course: Course) -> Course:
        row = self.db.get(CourseRow, course.id)
        if row is None:
            row = CourseRow(
                id=course.id,
                user_id=course.user_id,
                name=course.name,
                section=course.section,
            )
            self.db.add(row)
        else:
            row.name = course.name
            row.section = course.section
        self.db.commit()
        self.db.refresh(row)
        return _course_from_row(row)

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------

    def upsert_assignment(self, assignment: Assignment) -> Assignment:
        row = self.db.get(AssignmentRow, assignment.id)
        now = datetime.now(timezone.utc)
        if row is None:
            row = AssignmentRow(
                id=assignment.id,
                course_id=assignment.course_id,
                title=assignment.title,
                due_at=assignment.due_at,
                submission_state=assignment.submission_state,
                status=assignment.status.value,
                created_at=now,
                updated_at=now,
            )
            self.db.add(row)
        else:
            row.course_id = assignment.course_id
            row.title = assignment.title
            row.due_at = assignment.due_at
            row.submission_state = assignment.submission_state
            row.updated_at = now
        self.db.commit()
        self.db.refresh(row)
        return _assignment_from_row(row)

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        row = self.db.get(AssignmentRow, assignment_id)
        return _assignment_from_row(row) if row else None

    def list_open_assignments(self) -> list[Assignment]:
        closed = {AssignmentStatus.SUBMITTED.value, AssignmentStatus.SKIPPED.value}
        rows = self.db.query(AssignmentRow).filter(AssignmentRow.status.notin_(closed)).all()
        return [_assignment_from_row(r) for r in rows]

    def update_assignment_status(self, assignment_id: str, status: AssignmentStatus) -> Assignment:
        row = self.db.get(AssignmentRow, assignment_id)
        if row is None:
            raise KeyError(f"Assignment {assignment_id!r} not found.")
        row.status = status.value
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return _assignment_from_row(row)

    # ------------------------------------------------------------------
    # Generated files
    # ------------------------------------------------------------------

    def add_generated_file(self, file: GeneratedFile) -> GeneratedFile:
        row = GeneratedFileRow(
            id=file.id,
            assignment_id=file.assignment_id,
            kind=file.kind.value,
            filename=file.filename,
            storage_path=file.storage_path,
            created_at=file.created_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _file_from_row(row)

    def add_generated_files(self, files: Iterable[GeneratedFile]) -> list[GeneratedFile]:
        return [self.add_generated_file(f) for f in files]

    def list_generated_files(
        self,
        assignment_id: str,
        kind: GeneratedFileKind | None = None,
    ) -> list[GeneratedFile]:
        q = self.db.query(GeneratedFileRow).filter(GeneratedFileRow.assignment_id == assignment_id)
        if kind is not None:
            q = q.filter(GeneratedFileRow.kind == kind.value)
        return [_file_from_row(r) for r in q.all()]


# ---------------------------------------------------------------------------
# OAuth token persistence (separate concern but same session)
# ---------------------------------------------------------------------------

class OAuthTokenRepository:
    def __init__(self, db: Session, cipher: TokenCipher) -> None:
        self.db = db
        self.cipher = cipher

    def store(self, user_id: UUID, bundle: OAuthTokenBundle) -> None:
        enc = self.cipher.encrypt_bundle(bundle)
        existing = (
            self.db.query(OAuthTokenRow)
            .filter(OAuthTokenRow.user_id == user_id, OAuthTokenRow.provider == bundle.provider)
            .first()
        )
        if existing:
            existing.access_token_enc = enc.access_token_enc
            existing.refresh_token_enc = enc.refresh_token_enc
            existing.expires_at = enc.expires_at
        else:
            row = OAuthTokenRow(
                user_id=user_id,
                provider=bundle.provider,
                access_token_enc=enc.access_token_enc,
                refresh_token_enc=enc.refresh_token_enc,
                expires_at=enc.expires_at,
            )
            self.db.add(row)
        self.db.commit()

    def load(self, user_id: UUID, provider: str = "google") -> OAuthTokenBundle | None:
        row = (
            self.db.query(OAuthTokenRow)
            .filter(OAuthTokenRow.user_id == user_id, OAuthTokenRow.provider == provider)
            .first()
        )
        if row is None:
            return None
        enc = EncryptedOAuthTokenBundle(
            provider=row.provider,
            access_token_enc=row.access_token_enc,
            refresh_token_enc=row.refresh_token_enc,
            expires_at=row.expires_at,
        )
        return self.cipher.decrypt_bundle(enc)


# ---------------------------------------------------------------------------
# Row → domain object converters
# ---------------------------------------------------------------------------

def _course_from_row(row: CourseRow) -> Course:
    return Course(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        section=row.section,
    )


def _assignment_from_row(row: AssignmentRow) -> Assignment:
    due_at = row.due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return Assignment(
        id=row.id,
        course_id=row.course_id,
        title=row.title,
        due_at=due_at,
        submission_state=row.submission_state,
        status=AssignmentStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _file_from_row(row: GeneratedFileRow) -> GeneratedFile:
    return GeneratedFile(
        id=row.id,
        assignment_id=row.assignment_id,
        kind=GeneratedFileKind(row.kind),
        filename=row.filename,
        storage_path=row.storage_path,
        created_at=row.created_at,
    )
