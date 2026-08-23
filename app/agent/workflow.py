from __future__ import annotations

from datetime import datetime, timezone

from app.agent.state import AssignmentState

SUBMIT_PREREQUISITES = ("user_files",)


def is_due_soon(state: AssignmentState, threshold_hours: int) -> bool:
    now = datetime.now(timezone.utc)
    seconds_until_due = (state["due_at"] - now).total_seconds()
    return 0 <= seconds_until_due <= threshold_hours * 60 * 60


def can_route_to_submit(state: AssignmentState) -> bool:
    return bool(state.get("user_files"))


def route_after_deadline_check(state: AssignmentState, threshold_hours: int = 24) -> str:
    return "DOWNLOAD" if is_due_soon(state, threshold_hours) else "SKIP"


def route_after_await_user_files(state: AssignmentState) -> str:
    return "SANDBOX_CHECK" if can_route_to_submit(state) else "AWAIT_USER_FILES"
