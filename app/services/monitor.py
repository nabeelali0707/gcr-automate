from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from uuid import UUID

from app.agent.workflow import is_due_soon
from app.db.models import Assignment, AssignmentStatus, Course
from app.db.repository import AssignmentRepository
from app.integrations.classroom import ClassroomClient

SUBMITTED_STATES = {"TURNED_IN", "RETURNED"}


@dataclass(frozen=True)
class MonitorResult:
    scanned: int
    urgent: tuple[Assignment, ...]


class DeadlineMonitor:
    def __init__(
        self,
        *,
        classroom: ClassroomClient,
        repository: AssignmentRepository,
        user_id: UUID,
        threshold_hours: int = 24,
    ) -> None:
        self.classroom = classroom
        self.repository = repository
        self.user_id = user_id
        self.threshold_hours = threshold_hours

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

        return MonitorResult(scanned=scanned, urgent=tuple(urgent))

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
