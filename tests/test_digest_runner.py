from datetime import datetime, timedelta, timezone

from app.agent.runner import AssignmentDigestRunner
from app.db.models import Assignment, AssignmentStatus, GeneratedFileKind
from app.db.repository import InMemoryRepository


def test_digest_runner_stores_digest_and_scaffold_without_user_submission(tmp_path) -> None:
    repository = InMemoryRepository()
    repository.upsert_assignment(
        Assignment(
            id="assignment-1",
            course_id="course-1",
            title="Project",
            due_at=datetime.now(timezone.utc) + timedelta(hours=5),
            submission_state="CREATED",
        )
    )
    attachment = tmp_path / "instructions.txt"
    attachment.write_text(
        "Submit main.py. You must implement your own functions. What should the program print?",
        encoding="utf-8",
    )

    runner = AssignmentDigestRunner(repository=repository, storage_dir=tmp_path / "storage")
    result = runner.run_from_attachment_paths("assignment-1", [attachment])

    assert result.digest_file.kind is GeneratedFileKind.DIGEST
    assert result.scaffold_files[0].kind is GeneratedFileKind.SCAFFOLD
    assert repository.list_generated_files("assignment-1", GeneratedFileKind.USER_SUBMISSION) == []
    assert repository.get_assignment("assignment-1").status is AssignmentStatus.SCAFFOLDED
