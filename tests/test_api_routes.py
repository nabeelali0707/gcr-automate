from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_repository, get_storage
from app.db.models import Assignment, AssignmentStatus, GeneratedFileKind
from app.db.repository import InMemoryRepository
from app.main import create_app
from app.services.storage import LocalFileStorage


def test_upload_user_file_marks_assignment_ready(tmp_path) -> None:
    repository = InMemoryRepository()
    repository.upsert_assignment(
        Assignment(
            id="assignment-1",
            course_id="course-1",
            title="Project",
            due_at=datetime.now(timezone.utc) + timedelta(hours=3),
            submission_state="CREATED",
        )
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_storage] = lambda: LocalFileStorage(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/assignments/assignment-1/user-files",
        files={"file": ("my work.py", b"print('mine')", "text/x-python")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "user_submission"
    assert body["filename"] == "my_work.py"
    assert repository.get_assignment("assignment-1").status is AssignmentStatus.READY_TO_SUBMIT
    assert len(repository.list_generated_files("assignment-1", GeneratedFileKind.USER_SUBMISSION)) == 1


def test_submit_requires_user_uploaded_files() -> None:
    repository = InMemoryRepository()
    repository.upsert_assignment(
        Assignment(
            id="assignment-1",
            course_id="course-1",
            title="Project",
            due_at=datetime.now(timezone.utc) + timedelta(hours=3),
            submission_state="CREATED",
        )
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    client = TestClient(app)

    response = client.post("/assignments/assignment-1/submit")

    assert response.status_code == 409
    assert response.json()["detail"] == "Upload user-authored files before submitting."
