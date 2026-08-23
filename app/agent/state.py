from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class AssignmentState(TypedDict):
    assignment_id: str
    course_id: str
    due_at: datetime
    attachments: list[str]
    extracted_text: str | None
    digest: dict | None
    scaffold: dict | None
    user_files: list[str] | None
    attempt: int
    error: str | None
