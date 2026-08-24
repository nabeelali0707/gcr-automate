"""Deadline monitor — polls Google Classroom for upcoming unsubmitted work
and optionally fires Telegram notifications.

When a Telegram bot + chat_id are configured, urgent assignments automatically
trigger a digest+scaffold run and a Telegram message with inline buttons.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from uuid import UUID

from app.agent.workflow import is_due_soon
from app.db.models import Assignment, AssignmentStatus, Course
from app.db.repository import AssignmentRepository
from app.integrations.classroom import ClassroomClient

logger = logging.getLogger(__name__)

SUBMITTED_STATES = {"TURNED_IN", "RETURNED"}


@dataclass(frozen=True)
class MonitorResult:
    scanned: int
    urgent: tuple[Assignment, ...]
    notified: int = 0


class DeadlineMonitor:
    def __init__(
        self,
        *,
        classroom: ClassroomClient,
        repository: AssignmentRepository,
        user_id: UUID,
        threshold_hours: int = 24,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
        storage_dir: str = "storage/digests",
    ) -> None:
        self.classroom = classroom
        self.repository = repository
        self.user_id = user_id
        self.threshold_hours = threshold_hours
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.storage_dir = storage_dir

    def poll_once(self) -> MonitorResult:
        scanned = 0
        urgent: list[Assignment] = []

        for course_payload in self.classroom.list_courses():
            course = self.repository.upsert_course(
                Course(
                    id=str(course_payload["id"]),
                    user_id=self.user_id,
                    name=course_payload.get("name", "Untitled course"),
                    section=course_payload.get("section"),
                )
            )
            for coursework in self.classroom.list_coursework(course.id):
                scanned += 1
                assignment = self._assignment_from_payload(course.id, coursework)
                assignment = self.repository.upsert_assignment(assignment)
                if assignment.submission_state in SUBMITTED_STATES:
                    self.repository.update_assignment_status(assignment.id, AssignmentStatus.SKIPPED)
                    continue
                state = {
                    "assignment_id": assignment.id,
                    "course_id": assignment.course_id,
                    "due_at": assignment.due_at,
                    "attachments": [],
                    "extracted_text": None,
                    "digest": None,
                    "scaffold": None,
                    "user_files": None,
                    "attempt": 0,
                    "error": None,
                }
                if is_due_soon(state, self.threshold_hours):
                    urgent.append(assignment)

        notified = 0
        if urgent:
            notified = self._process_urgent(urgent)

        return MonitorResult(scanned=scanned, urgent=tuple(urgent), notified=notified)

    def _process_urgent(self, assignments: list[Assignment]) -> int:
        """Run digest+scaffold for each urgent assignment and optionally notify via Telegram in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        pending_assignments = [
            a for a in assignments if a.status == AssignmentStatus.PENDING
        ]
        if not pending_assignments:
            return 0

        notified = 0

        def process_single(assignment: Assignment) -> bool:
            from app.db.sql_repository import SqlRepository
            from app.db.session import SessionLocal

            repo = self.repository
            db = None
            if isinstance(repo, SqlRepository):
                db = SessionLocal()
                repo = SqlRepository(db)

            try:
                self._run_digest(assignment, repo)
            except Exception as exc:
                logger.error("Digest failed for %s: %s", assignment.id, exc)
                return False
            finally:
                if db is not None:
                    db.close()

            if self.telegram_bot_token and self.telegram_chat_id:
                try:
                    self._send_telegram_notification(assignment)
                    return True
                except Exception as exc:
                    logger.error("Telegram notify failed for %s: %s", assignment.id, exc)
            return False

        max_workers = min(5, len(pending_assignments))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_single, a): a for a in pending_assignments
            }
            for future in as_completed(futures):
                if future.result():
                    notified += 1

        return notified

    def _run_digest(self, assignment: Assignment, repository: AssignmentRepository) -> None:
        """Run the digest+scaffold pipeline for *assignment* using *repository*."""
        from pathlib import Path
        import tempfile
        from app.agent.runner import AssignmentDigestRunner

        # Use a stub text if no real attachments available.
        tmp = Path(tempfile.mkdtemp())
        stub = tmp / "assignment.txt"
        stub.write_text(
            f"Assignment: {assignment.title}\nDue: {assignment.due_at.isoformat()}\n",
            encoding="utf-8",
        )
        runner = AssignmentDigestRunner(repository=repository, storage_dir=self.storage_dir)
        runner.run_from_attachment_paths(assignment.id, [str(stub)])
        logger.info("Digest completed for assignment %s.", assignment.id)

    def _send_telegram_notification(self, assignment: Assignment) -> None:
        from app.integrations.telegram import TelegramBotClient, digest_ready_message

        bot = TelegramBotClient(self.telegram_bot_token)  # type: ignore[arg-type]
        msg = digest_ready_message(
            assignment_title=assignment.title,
            course_name=assignment.course_id,
            due_at=assignment.due_at,
            agent_run_id=assignment.id,
        )
        asyncio.run(bot.send_message(self.telegram_chat_id, msg))  # type: ignore[arg-type]
        logger.info("Telegram notification sent for assignment %s.", assignment.id)

    def _assignment_from_payload(self, course_id: str, payload: dict) -> Assignment:
        due_at = parse_classroom_due_at(payload)
        submission_state = self.classroom.get_submission_status(course_id, str(payload["id"]))
        return Assignment(
            id=str(payload["id"]),
            course_id=course_id,
            title=payload.get("title", "Untitled assignment"),
            due_at=due_at,
            submission_state=submission_state,
        )


def parse_classroom_due_at(payload: dict) -> datetime:
    due_date = payload.get("dueDate")
    if not due_date:
        return datetime.max.replace(tzinfo=timezone.utc)

    due_time = payload.get("dueTime") or {}
    parsed_time = time(
        hour=int(due_time.get("hours", 23)),
        minute=int(due_time.get("minutes", 59)),
        second=int(due_time.get("seconds", 0)),
        tzinfo=timezone.utc,
    )
    return datetime(
        year=int(due_date["year"]),
        month=int(due_date["month"]),
        day=int(due_date["day"]),
        hour=parsed_time.hour,
        minute=parsed_time.minute,
        second=parsed_time.second,
        tzinfo=timezone.utc,
    )
