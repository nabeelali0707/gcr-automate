"""SQLAlchemy 2.0 ORM table definitions (mapped_column + Mapped style).

Maps 1-to-1 to the tables in scripts/schema.sql.
The in-memory dataclasses in db/models.py remain the domain objects;
ORM rows are only used for persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OAuthTokenRow(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CourseRow(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assignments: Mapped[list["AssignmentRow"]] = relationship("AssignmentRow", back_populates="course")


class AssignmentRow(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    course_id: Mapped[str] = mapped_column(String, ForeignKey("courses.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submission_state: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    course: Mapped["CourseRow"] = relationship("CourseRow", back_populates="assignments")
    agent_runs: Mapped[list["AgentRunRow"]] = relationship("AgentRunRow", back_populates="assignment")
    generated_files: Mapped[list["GeneratedFileRow"]] = relationship("GeneratedFileRow", back_populates="assignment")


class AgentRunRow(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[str] = mapped_column(String, ForeignKey("assignments.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment: Mapped["AssignmentRow"] = relationship("AssignmentRow", back_populates="agent_runs")


class GeneratedFileRow(Base):
    __tablename__ = "generated_files"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[str] = mapped_column(String, ForeignKey("assignments.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    assignment: Mapped["AssignmentRow"] = relationship("AssignmentRow", back_populates="generated_files")


class ApprovalRequestRow(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    responded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


# ── Indexes (mirror schema.sql) ───────────────────────────────────────────────
Index("idx_assignments_due_at", AssignmentRow.due_at)
Index("idx_agent_runs_assignment_started", AgentRunRow.assignment_id, AgentRunRow.started_at)
Index("idx_generated_files_assignment_kind", GeneratedFileRow.assignment_id, GeneratedFileRow.kind)
