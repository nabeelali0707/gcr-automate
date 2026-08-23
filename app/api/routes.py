from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.dependencies import get_repository, get_storage
from app.db.models import AssignmentStatus, GeneratedFile, GeneratedFileKind
from app.db.repository import AssignmentRepository
from app.integrations.classroom import SubmissionService
from app.services.storage import LocalFileStorage

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/assignments/{assignment_id}/user-files")
async def upload_user_file(
    assignment_id: str,
    file: UploadFile,
    repository: AssignmentRepository = Depends(get_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> dict[str, str | int]:
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment is not tracked.")

    stored = await storage.save_upload(assignment_id, file)
    generated_file = repository.add_generated_file(
        GeneratedFile(
            assignment_id=assignment_id,
            kind=GeneratedFileKind.USER_SUBMISSION,
            filename=stored.filename,
            storage_path=stored.storage_path,
        )
    )
    repository.update_assignment_status(assignment_id, AssignmentStatus.READY_TO_SUBMIT)
    return {
        "assignment_id": assignment_id,
        "file_id": str(generated_file.id),
        "filename": generated_file.filename,
        "kind": generated_file.kind.value,
        "size_bytes": stored.size_bytes,
        "status": "accepted",
    }


@router.post("/assignments/{assignment_id}/submit")
def submit_assignment(
    assignment_id: str,
    repository: AssignmentRepository = Depends(get_repository),
) -> dict[str, str]:
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment is not tracked.")

    user_files = repository.list_generated_files(assignment_id, GeneratedFileKind.USER_SUBMISSION)
    if not user_files:
        raise HTTPException(status_code=409, detail="Upload user-authored files before submitting.")

    service = SubmissionService()
    result = service.submit_user_files(
        request=service_request_for_assignment(
            assignment_id=assignment_id,
            files=user_files,
        )
    )
    if result.status == "submitted":
        repository.update_assignment_status(assignment_id, AssignmentStatus.SUBMITTED)
    return {"assignment_id": assignment_id, "status": result.status}


def service_request_for_assignment(assignment_id: str, files: list[GeneratedFile]):
    from app.integrations.classroom import SubmissionRequest

    return SubmissionRequest(assignment_id=assignment_id, files=files)
