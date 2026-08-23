from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class GoogleDriveClient:
    """Thin wrapper around the Drive v3 API for downloading assignment attachments
    and uploading user-authored submission files.

    The service object is built externally (e.g. from stored OAuth credentials)
    and injected here to keep auth concerns separate.
    """

    def __init__(self, service) -> None:
        self.service = service

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_attachment(self, file_id: str, destination_dir: str | Path) -> Path:
        """Download a Drive file by ID into *destination_dir*.

        Returns the path of the saved file.
        """
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)

        # Fetch metadata to get the original filename.
        meta = self.service.files().get(fileId=file_id, fields="name,mimeType").execute()
        filename = meta.get("name", file_id)
        mime = meta.get("mimeType", "")

        # Google Workspace types must be exported to a portable format.
        export_map = {
            "application/vnd.google-apps.document": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
            "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
            "application/vnd.google-apps.presentation": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
        }

        out_path = dest / filename

        if mime in export_map:
            export_mime, ext = export_map[mime]
            if not out_path.suffix:
                out_path = out_path.with_suffix(ext)
            request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = self.service.files().get_media(fileId=file_id)

        buf = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import]

        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        out_path.write_bytes(buf.getvalue())
        logger.info("Downloaded Drive file %s → %s", file_id, out_path)
        return out_path

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_file(self, storage_path: str, filename: str) -> str:
        """Upload a local file to Drive and return its Drive file ID.

        The file is uploaded to the root of the user's Drive (scope: drive.file).
        """
        from googleapiclient.http import MediaFileUpload  # type: ignore[import]

        media = MediaFileUpload(storage_path, resumable=True)
        file_metadata = {"name": filename}
        result = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        drive_id = result["id"]
        logger.info("Uploaded %s → Drive file %s", filename, drive_id)
        return drive_id


class NotConfiguredDriveClient:
    """Fallback used when Drive credentials are not configured."""

    def download_attachment(self, file_id: str, destination_dir: str | Path) -> Path:
        raise NotImplementedError(
            f"Drive download is not configured for attachment {file_id}. "
            "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and complete the OAuth flow."
        )

    def upload_file(self, storage_path: str, filename: str) -> str:
        raise NotImplementedError(
            f"Drive upload is not configured for {filename}. "
            "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and complete the OAuth flow."
        )
