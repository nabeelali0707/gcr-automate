from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.agent.digest import digest_requirements
from app.db.models import AssignmentStatus, GeneratedFile, GeneratedFileKind
from app.db.repository import AssignmentRepository
from app.extraction.text import extract_text
from app.scaffolding.generator import generate_scaffold_from_digest


@dataclass(frozen=True)
class DigestRunResult:
    assignment_id: str
    digest_file: GeneratedFile
    scaffold_files: tuple[GeneratedFile, ...]


class AssignmentDigestRunner:
    def __init__(self, repository: AssignmentRepository, storage_dir: str | Path = "storage") -> None:
        self.repository = repository
        self.storage_dir = Path(storage_dir)

    def run_from_attachment_paths(self, assignment_id: str, attachment_paths: list[str | Path]) -> DigestRunResult:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        extracted = "\n\n".join(extract_text(path) for path in attachment_paths)
        digest = digest_requirements(extracted)
        scaffold = generate_scaffold_from_digest(digest.as_dict())

        digest_path = self.storage_dir / f"{assignment_id}-digest.json"
        digest_path.write_text(str(digest.as_dict()), encoding="utf-8")
        digest_file = self.repository.add_generated_file(
            GeneratedFile(
                assignment_id=assignment_id,
                kind=GeneratedFileKind.DIGEST,
                filename=digest_path.name,
                storage_path=str(digest_path),
            )
        )

        scaffold_files: list[GeneratedFile] = []
        for filename, content in scaffold.starter_files.items():
            safe_filename = filename.replace("/", "_").replace("\\", "_")
            path = self.storage_dir / f"{assignment_id}-{safe_filename}"
            path.write_text(content, encoding="utf-8")
            scaffold_files.append(
                self.repository.add_generated_file(
                    GeneratedFile(
                        assignment_id=assignment_id,
                        kind=GeneratedFileKind.SCAFFOLD,
                        filename=path.name,
                        storage_path=str(path),
                    )
                )
            )

        self.repository.update_assignment_status(assignment_id, AssignmentStatus.SCAFFOLDED)
        return DigestRunResult(
            assignment_id=assignment_id,
            digest_file=digest_file,
            scaffold_files=tuple(scaffold_files),
        )
