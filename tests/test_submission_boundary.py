from app.db.models import GeneratedFile, GeneratedFileKind
from app.integrations.classroom import SubmissionBoundaryError, SubmissionRequest, SubmissionService


def test_rejects_scaffold_files_for_submission() -> None:
    service = SubmissionService()
    scaffold = GeneratedFile(
        assignment_id="a1",
        kind=GeneratedFileKind.SCAFFOLD,
        filename="starter.py",
        storage_path="/tmp/starter.py",
    )

    try:
        service.submit_user_files(SubmissionRequest(assignment_id="a1", files=[scaffold]))
    except SubmissionBoundaryError as exc:
        assert "Only user_submission files" in str(exc)
    else:
        raise AssertionError("scaffold files must not be eligible for submission")


def test_accepts_user_submission_files_for_submission_validation() -> None:
    service = SubmissionService()
    user_file = GeneratedFile(
        assignment_id="a1",
        kind=GeneratedFileKind.USER_SUBMISSION,
        filename="my-work.py",
        storage_path="/tmp/my-work.py",
    )

    result = service.submit_user_files(SubmissionRequest(assignment_id="a1", files=[user_file]))

    assert result.status == "validated"
