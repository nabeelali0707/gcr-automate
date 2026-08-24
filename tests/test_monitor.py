from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db.repository import InMemoryRepository
from app.services.monitor import DeadlineMonitor, parse_classroom_due_at


class FakeClassroom:
    def __init__(self, submission_state: str = "CREATED") -> None:
        self.submission_state = submission_state

    def list_courses(self) -> list[dict]:
        return [{"id": "course-1", "name": "Math"}]

    def list_coursework(self, course_id: str) -> list[dict]:
        due = datetime.now(timezone.utc) + timedelta(hours=3)
        return [
            {
                "id": "assignment-1",
                "title": "Worksheet",
                "dueDate": {"year": due.year, "month": due.month, "day": due.day},
                "dueTime": {"hours": due.hour, "minutes": due.minute},
            }
        ]

    def get_submission_status(self, course_id: str, coursework_id: str) -> str:
        return self.submission_state


def test_monitor_finds_urgent_unsubmitted_assignment() -> None:
    repository = InMemoryRepository()
    monitor = DeadlineMonitor(
        classroom=FakeClassroom(),
        repository=repository,
        user_id=uuid4(),
        threshold_hours=24,
    )

    result = monitor.poll_once()

    assert result.scanned == 1
    assert [assignment.id for assignment in result.urgent] == ["assignment-1"]
    assert repository.get_assignment("assignment-1") is not None


def test_monitor_skips_submitted_assignment() -> None:
    repository = InMemoryRepository()
    monitor = DeadlineMonitor(
        classroom=FakeClassroom(submission_state="TURNED_IN"),
        repository=repository,
        user_id=uuid4(),
        threshold_hours=24,
    )

    result = monitor.poll_once()

    assert result.urgent == ()


def test_parse_classroom_due_at_defaults_to_end_of_day() -> None:
    due_at = parse_classroom_due_at({"dueDate": {"year": 2026, "month": 8, "day": 23}})

    assert due_at.isoformat() == "2026-08-23T23:59:00+00:00"


class FakeClassroomMultiple:
    def list_courses(self) -> list[dict]:
        return [{"id": "course-1", "name": "Math"}]

    def list_coursework(self, course_id: str) -> list[dict]:
        due = datetime.now(timezone.utc) + timedelta(hours=3)
        return [
            {
                "id": f"assignment-{i}",
                "title": f"Worksheet {i}",
                "dueDate": {"year": due.year, "month": due.month, "day": due.day},
                "dueTime": {"hours": due.hour, "minutes": due.minute},
            }
            for i in range(3)
        ]

    def get_submission_status(self, course_id: str, coursework_id: str) -> str:
        return "CREATED"


def test_monitor_processes_multiple_urgent_assignments_in_parallel() -> None:
    repository = InMemoryRepository()
    monitor = DeadlineMonitor(
        classroom=FakeClassroomMultiple(),
        repository=repository,
        user_id=uuid4(),
        threshold_hours=24,
        telegram_bot_token="fake-token",
        telegram_chat_id="fake-chat-id",
    )

    sent_notifs = []
    def mock_send(assignment):
        sent_notifs.append(assignment.id)
    monitor._send_telegram_notification = mock_send

    result = monitor.poll_once()

    assert result.scanned == 3
    assert len(result.urgent) == 3
    assert result.notified == 3
    assert set(sent_notifs) == {"assignment-0", "assignment-1", "assignment-2"}
