from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DriveAttachmentClient(Protocol):
    def download_attachment(self, file_id: str, destination_dir: str | Path) -> Path: ...


class NotConfiguredDriveClient:
    def download_attachment(self, file_id: str, destination_dir: str | Path) -> Path:
        raise NotImplementedError(f"Drive download is not configured for attachment {file_id}.")
