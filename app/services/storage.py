from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredUpload:
    filename: str
    storage_path: str
    size_bytes: int


class LocalFileStorage:
    def __init__(self, root: str | Path = "storage/user_uploads") -> None:
        self.root = Path(root)

    async def save_upload(self, assignment_id: str, upload: UploadFile) -> StoredUpload:
        assignment_dir = self.root / sanitize_filename(assignment_id)
        assignment_dir.mkdir(parents=True, exist_ok=True)

        filename = sanitize_filename(upload.filename or "upload.bin")
        target = unique_path(assignment_dir / filename)
        size = 0

        with target.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                handle.write(chunk)

        return StoredUpload(filename=target.name, storage_path=str(target), size_bytes=size)


def sanitize_filename(filename: str) -> str:
    sanitized = SAFE_FILENAME.sub("_", filename.strip()).strip("._")
    return sanitized or "upload.bin"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
