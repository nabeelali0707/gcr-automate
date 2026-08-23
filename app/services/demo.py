from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.agent.runner import AssignmentDigestRunner
from app.db.models import Assignment, AssignmentStatus, Course
from app.db.repository import InMemoryRepository
from app.services.monitor import DeadlineMonitor

DEMO_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class DemoClassroomClient:
    def __init__(self, *, due_in_hours: int = 3, submission_state: str = "CREATED") -> None:
        self.due_at = datetime.now(timezone.utc) + timedelta(hours=due_in_hours)
        self.submission_state = submission_state

    def list_courses(self) -> list[dict]:
        return [{"id": "demo-course", "name": "Demo Classroom"}]

    def list_coursework(self, course_id: str) -> list[dict]:
        return [
            {
                "id": "demo-assignment",
                "title": "Demo Deadline Assignment",
                "dueDate": {
                    "year": self.due_at.year,
                    "month": self.due_at.month,
                    "day": self.due_at.day,
                },
                "dueTime": {
                    "hours": self.due_at.hour,
                    "minutes": self.due_at.minute,
                    "seconds": self.due_at.second,
                },
            }
        ]

    def get_submission_status(self, course_id: str, coursework_id: str) -> str:
        return self.submission_state


def seed_demo_repository(repository: InMemoryRepository | None = None) -> InMemoryRepository:
    repository = repository or InMemoryRepository()
    repository.upsert_course(Course(id="demo-course", user_id=DEMO_USER_ID, name="Demo Classroom"))
    repository.upsert_assignment(
        Assignment(
            id="demo-assignment",
            course_id="demo-course",
            title="Demo Deadline Assignment",
            due_at=datetime.now(timezone.utc) + timedelta(hours=3),
            submission_state="CREATED",
            status=AssignmentStatus.PENDING,
        )
    )
    return repository


def run_demo_poll(repository: InMemoryRepository | None = None):
    repository = repository or InMemoryRepository()
    monitor = DeadlineMonitor(
        classroom=DemoClassroomClient(),
        repository=repository,
        user_id=DEMO_USER_ID,
        threshold_hours=24,
    )
    return monitor.poll_once()


def run_demo_digest(repository: InMemoryRepository, attachment_path: str, storage_dir: str):
    runner = AssignmentDigestRunner(repository=repository, storage_dir=storage_dir)
    return runner.run_from_attachment_paths("demo-assignment", [attachment_path])
