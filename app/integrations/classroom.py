from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from app.db.models import GeneratedFile, GeneratedFileKind


class ClassroomClient(Protocol):
    def list_courses(self) -> list[dict]: ...

    def list_coursework(self, course_id: str) -> list[dict]: ...

    def get_submission_status(self, course_id: str, coursework_id: str) -> str: ...

    def modify_attachments(
        self, course_id: str, coursework_id: str, submission_id: str, drive_file_ids: Sequence[str]
    ) -> None: ...

    def turn_in(self, course_id: str, coursework_id: str, submission_id: str) -> None: ...


class DriveClient(Protocol):
    def upload_file(self, storage_path: str, filename: str) -> str: ...


@dataclass(frozen=True)
class SubmissionRequest:
    assignment_id: str
    course_id: str | None = None
    coursework_id: str | None = None
    submission_id: str | None = None
    files: Sequence[GeneratedFile] = ()


@dataclass(frozen=True)
class SubmissionResult:
    assignment_id: str
    status: str
    submitted_at: datetime | None = None
    drive_file_ids: tuple[str, ...] = ()


class SubmissionBoundaryError(ValueError):
    """Raised when a submit flow tries to use non-user-authored files."""


class GoogleClassroomClient:
    def __init__(self, service) -> None:
        self.service = service

    def list_courses(self) -> list[dict]:
        response = self.service.courses().list().execute()
        return response.get("courses", [])

    def list_coursework(self, course_id: str) -> list[dict]:
        response = self.service.courses().courseWork().list(courseId=course_id).execute()
        return response.get("courseWork", [])

    def get_submission_status(self, course_id: str, coursework_id: str) -> str:
        response = (
            self.service.courses()
            .courseWork()
            .studentSubmissions()
            .list(courseId=course_id, courseWorkId=coursework_id)
            .execute()
        )
        submissions = response.get("studentSubmissions", [])
        if not submissions:
            return "NEW"
        return submissions[0].get("state", "NEW")

    def modify_attachments(
        self, course_id: str, coursework_id: str, submission_id: str, drive_file_ids: Sequence[str]
    ) -> None:
        body = {
            "addAttachments": [
                {"driveFile": {"id": drive_file_id}}
                for drive_file_id in drive_file_ids
            ]
        }
        (
            self.service.courses()
            .courseWork()
            .studentSubmissions()
            .modifyAttachments(
                courseId=course_id,
                courseWorkId=coursework_id,
                id=submission_id,
                body=body,
            )
            .execute()
        )

    def turn_in(self, course_id: str, coursework_id: str, submission_id: str) -> None:
        (
            self.service.courses()
            .courseWork()
            .studentSubmissions()
            .turnIn(courseId=course_id, courseWorkId=coursework_id, id=submission_id, body={})
            .execute()
        )


class SubmissionService:
    def __init__(self, classroom: ClassroomClient | None = None, drive: DriveClient | None = None):
        self.classroom = classroom
        self.drive = drive

    def assert_user_submission_files(self, files: Sequence[GeneratedFile]) -> None:
        if not files:
            raise SubmissionBoundaryError("Submit requires at least one user-authored file.")

        unsafe = [file for file in files if file.kind is not GeneratedFileKind.USER_SUBMISSION]
        if unsafe:
            kinds = ", ".join(sorted({file.kind.value for file in unsafe}))
            raise SubmissionBoundaryError(f"Only user_submission files can be submitted; got {kinds}.")

    def submit_user_files(self, request: SubmissionRequest) -> SubmissionResult:
        self.assert_user_submission_files(request.files)

        if not self.classroom or not self.drive:
            return SubmissionResult(assignment_id=request.assignment_id, status="validated")

        if not request.course_id or not request.coursework_id or not request.submission_id:
            raise ValueError("course_id, coursework_id, and submission_id are required for Classroom submission.")

        drive_file_ids = tuple(self.drive.upload_file(file.storage_path, file.filename) for file in request.files)
        self.classroom.modify_attachments(
            request.course_id,
            request.coursework_id,
            request.submission_id,
            drive_file_ids,
        )
        self.classroom.turn_in(request.course_id, request.coursework_id, request.submission_id)
        return SubmissionResult(
            assignment_id=request.assignment_id,
            status="submitted",
            submitted_at=datetime.utcnow(),
            drive_file_ids=drive_file_ids,
        )

    def submit_assignment(self, assignment_id: str, files: Sequence[str]) -> SubmissionResult:
        generated_files = [
            GeneratedFile(
                assignment_id=assignment_id,
                kind=GeneratedFileKind.USER_SUBMISSION,
                filename=file_id,
                storage_path=file_id,
            )
            for file_id in files
        ]
        return self.submit_user_files(SubmissionRequest(assignment_id=assignment_id, files=generated_files))
