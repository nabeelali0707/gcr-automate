from datetime import datetime, timedelta, timezone

from app.agent.state import AssignmentState
from app.agent.workflow import route_after_await_user_files, route_after_deadline_check


def make_state(*, due_at: datetime, user_files: list[str] | None = None) -> AssignmentState:
    return {
        "assignment_id": "a1",
        "course_id": "c1",
        "due_at": due_at,
        "attachments": [],
        "extracted_text": None,
        "digest": None,
        "scaffold": None,
        "user_files": user_files,
        "attempt": 0,
        "error": None,
    }


def test_deadline_route_downloads_due_soon_assignment() -> None:
    state = make_state(due_at=datetime.now(timezone.utc) + timedelta(hours=2))

    assert route_after_deadline_check(state, threshold_hours=24) == "DOWNLOAD"


def test_deadline_route_skips_later_assignment() -> None:
    state = make_state(due_at=datetime.now(timezone.utc) + timedelta(days=3))

    assert route_after_deadline_check(state, threshold_hours=24) == "SKIP"


def test_submit_path_requires_user_files() -> None:
    assert route_after_await_user_files(make_state(due_at=datetime.now(timezone.utc))) == "AWAIT_USER_FILES"
    assert (
        route_after_await_user_files(
            make_state(due_at=datetime.now(timezone.utc), user_files=["/tmp/my-work.py"])
        )
        == "SANDBOX_CHECK"
    )
