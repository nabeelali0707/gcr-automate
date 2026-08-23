from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable, Protocol

from app.db.models import Assignment, AssignmentStatus, Course, GeneratedFile, GeneratedFileKind


class AssignmentRepository(Protocol):
    def upsert_course(self, course: Course) -> Course: ...

    def upsert_assignment(self, assignment: Assignment) -> Assignment: ...

    def get_assignment(self, assignment_id: str) -> Assignment | None: ...

    def list_open_assignments(self) -> list[Assignment]: ...

    def add_generated_file(self, file: GeneratedFile) -> GeneratedFile: ...

    def list_generated_files(
        self,
        assignment_id: str,
        kind: GeneratedFileKind | None = None,
    ) -> list[GeneratedFile]: ...

    def update_assignment_status(self, assignment_id: str, status: AssignmentStatus) -> Assignment: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self.courses: dict[str, Course] = {}
        self.assignments: dict[str, Assignment] = {}
        self.generated_files: dict[str, list[GeneratedFile]] = {}

    def upsert_course(self, course: Course) -> Course:
        self.courses[course.id] = course
        return course

    def upsert_assignment(self, assignment: Assignment) -> Assignment:
        existing = self.assignments.get(assignment.id)
        if existing:
            assignment = replace(
                existing,
                course_id=assignment.course_id,
                title=assignment.title,
                due_at=assignment.due_at,
                submission_state=assignment.submission_state,
                updated_at=datetime.now(timezone.utc),
            )
        self.assignments[assignment.id] = assignment
        return assignment

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        return self.assignments.get(assignment_id)

    def list_open_assignments(self) -> list[Assignment]:
        closed = {AssignmentStatus.SUBMITTED, AssignmentStatus.SKIPPED}
        return [assignment for assignment in self.assignments.values() if assignment.status not in closed]

    def add_generated_file(self, file: GeneratedFile) -> GeneratedFile:
        files = self.generated_files.setdefault(file.assignment_id, [])
        files.append(file)
        return file

    def add_generated_files(self, files: Iterable[GeneratedFile]) -> list[GeneratedFile]:
        return [self.add_generated_file(file) for file in files]

    def list_generated_files(
        self,
        assignment_id: str,
        kind: GeneratedFileKind | None = None,
    ) -> list[GeneratedFile]:
        files = list(self.generated_files.get(assignment_id, []))
        if kind is None:
            return files
        return [file for file in files if file.kind is kind]

    def update_assignment_status(self, assignment_id: str, status: AssignmentStatus) -> Assignment:
        assignment = self.assignments[assignment_id]
        updated = replace(assignment, status=status, updated_at=datetime.now(timezone.utc))
        self.assignments[assignment_id] = updated
        return updated
