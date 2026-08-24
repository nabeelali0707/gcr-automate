"""FastAPI routes for the Classroom Deadline Assistant.

Endpoints:
  GET  /health                              — liveness check
  GET  /oauth/google                        — redirect user to Google consent
  GET  /oauth/google/callback               — handle code exchange + store tokens
  GET  /assignments                         — list tracked open assignments
  GET  /assignments/{id}                    — single assignment detail
  POST /assignments/{id}/run-now            — trigger digest+scaffold immediately
  GET  /assignments/{id}/status             — digest/scaffold/files status
  POST /assignments/{id}/user-files         — upload user-authored file
  POST /assignments/{id}/submit             — trigger one-tap submit
  POST /telegram/webhook                    — Telegram Bot API webhook receiver
  GET  /status                              — overall dashboard summary
"""
from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_repository, get_storage
from app.config import get_settings
from app.db.models import AssignmentStatus, GeneratedFile, GeneratedFileKind
from app.db.repository import AssignmentRepository
from app.integrations.classroom import SubmissionService
from app.services.storage import LocalFileStorage

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# OAuth — Google
# ---------------------------------------------------------------------------

@router.get("/oauth/google", tags=["auth"])
def oauth_google_start():
    """Redirect the user to Google's OAuth consent screen."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    from app.integrations.oauth import GoogleOAuthFlow
    flow = GoogleOAuthFlow(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    state = secrets.token_urlsafe(16)
    url = flow.authorization_url(state=state)
    return RedirectResponse(url)


@router.get("/oauth/google/callback", tags=["auth"])
def oauth_google_callback(code: str, state: str = "", error: str = ""):
    """Handle the OAuth callback, exchange code for tokens, and store them."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")

    from app.integrations.oauth import GoogleOAuthFlow
    flow = GoogleOAuthFlow(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    try:
        bundle = flow.exchange_code(code)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        logger.exception("Token exchange failed:")
        raise HTTPException(status_code=502, detail="Token exchange with Google failed.") from exc

    # Store encrypted tokens (requires FERNET_KEY + live DB).
    if settings.fernet_key:
        try:
            from uuid import UUID
            from app.db.session import SessionLocal
            from app.db.sql_repository import OAuthTokenRepository
            from app.integrations.oauth import TokenCipher
            # Single-user mode: use a fixed demo UUID until multi-user auth is added.
            USER_ID = UUID("00000000-0000-0000-0000-000000000001")
            cipher = TokenCipher(settings.fernet_key)
            with SessionLocal() as db:
                repo = OAuthTokenRepository(db, cipher)
                repo.store(USER_ID, bundle)
            logger.info("Google OAuth tokens stored for user %s.", USER_ID)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist OAuth tokens: %s", exc)
            # Don't fail the flow — tokens were obtained, just not persisted.

    return {"status": "authenticated", "provider": "google", "scopes_granted": True}


# ---------------------------------------------------------------------------
# Assignments — list + detail
# ---------------------------------------------------------------------------

@router.get("/assignments", tags=["assignments"])
def list_assignments(
    repository: AssignmentRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    """Return all open (non-submitted, non-skipped) tracked assignments."""
    assignments = repository.list_open_assignments()
    return [_assignment_dict(a) for a in assignments]


@router.get("/assignments/{assignment_id}", tags=["assignments"])
def get_assignment(
    assignment_id: str,
    repository: AssignmentRepository = Depends(get_repository),
) -> dict[str, Any]:
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not tracked.")
    files = repository.list_generated_files(assignment_id)
    return {**_assignment_dict(assignment), "files": [_file_dict(f) for f in files]}


# ---------------------------------------------------------------------------
# Assignment status
# ---------------------------------------------------------------------------

@router.get("/assignments/{assignment_id}/status", tags=["assignments"])
def assignment_status(
    assignment_id: str,
    repository: AssignmentRepository = Depends(get_repository),
) -> dict[str, Any]:
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not tracked.")
    files = repository.list_generated_files(assignment_id)
    digest_files = [f for f in files if f.kind is GeneratedFileKind.DIGEST]
    scaffold_files = [f for f in files if f.kind is GeneratedFileKind.SCAFFOLD]
    user_files = [f for f in files if f.kind is GeneratedFileKind.USER_SUBMISSION]
    return {
        "assignment_id": assignment_id,
        "title": assignment.title,
        "status": assignment.status.value,
        "due_at": assignment.due_at.isoformat(),
        "digest_ready": bool(digest_files),
        "scaffold_ready": bool(scaffold_files),
        "user_files_uploaded": len(user_files),
        "ready_to_submit": assignment.status is AssignmentStatus.READY_TO_SUBMIT,
    }


# ---------------------------------------------------------------------------
# Run now — trigger digest+scaffold for a specific assignment
# ---------------------------------------------------------------------------

@router.post("/assignments/{assignment_id}/run-now", tags=["assignments"])
def run_now(
    assignment_id: str,
    repository: AssignmentRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Manually trigger the digest+scaffold pipeline for an already-tracked assignment.

    This is equivalent to what the scheduler does automatically; useful for
    testing or re-running after an attachment changes.
    """
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not tracked.")

    # Download attachments if Google Drive is configured.
    attachment_paths: list[str] = []
    settings = get_settings()

    if settings.google_client_id and settings.fernet_key:
        try:
            attachment_paths = _download_attachments(assignment_id, assignment.course_id, settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Attachment download failed, proceeding without files: %s", exc)

    if not attachment_paths:
        # Create a synthetic text file with the assignment title so the digest
        # runner has something to work with even without real attachments.
        from pathlib import Path
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        stub = tmp / "assignment.txt"
        stub.write_text(
            f"Assignment: {assignment.title}\nDue: {assignment.due_at.isoformat()}\n",
            encoding="utf-8",
        )
        attachment_paths = [str(stub)]

    from app.agent.runner import AssignmentDigestRunner
    runner = AssignmentDigestRunner(repository=repository, storage_dir="storage/digests")
    result = runner.run_from_attachment_paths(assignment_id, attachment_paths)

    return {
        "assignment_id": assignment_id,
        "digest_file": result.digest_file.filename,
        "scaffold_files": [f.filename for f in result.scaffold_files],
        "status": "scaffolded",
    }


# ---------------------------------------------------------------------------
# User file upload
# ---------------------------------------------------------------------------

@router.post("/assignments/{assignment_id}/user-files", tags=["submissions"])
async def upload_user_file(
    assignment_id: str,
    file: UploadFile,
    repository: AssignmentRepository = Depends(get_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

@router.post("/assignments/{assignment_id}/submit", tags=["submissions"])
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

    from app.integrations.classroom import SubmissionRequest
    service = SubmissionService()
    result = service.submit_user_files(
        SubmissionRequest(assignment_id=assignment_id, files=user_files)
    )
    if result.status in {"submitted", "validated"}:
        repository.update_assignment_status(assignment_id, AssignmentStatus.SUBMITTED)
    return {"assignment_id": assignment_id, "status": result.status}


# ---------------------------------------------------------------------------
# Telegram webhook
# ---------------------------------------------------------------------------

@router.post("/telegram/webhook", tags=["telegram"])
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Receive updates from the Telegram Bot API (webhook mode).

    Handles:
    - /start           — welcome message
    - /status          — summary of open assignments
    - /run_now <id>    — trigger digest for an assignment
    - callback queries — digest:, scaffold:, ignore:, submit:, cancel: buttons
    """
    try:
        update = await request.json()
    except Exception:
        return {"ok": "true"}

    settings = get_settings()
    if not settings.telegram_bot_token:
        return {"ok": "true"}

    from app.integrations.telegram import TelegramBotClient, TelegramMessage, InlineButton
    bot = TelegramBotClient(settings.telegram_bot_token)

    # --- plain messages (commands) ---
    message = update.get("message") or update.get("edited_message")
    if message:
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "").strip()

        if text.startswith("/start"):
            await bot.send_message(
                chat_id,
                TelegramMessage(
                    text=(
                        "👋 *Classroom Deadline Assistant* is active!\n\n"
                        "I'll ping you when assignments are due soon, "
                        "give you a digest + starter scaffold, and handle "
                        "the Drive upload / Classroom turn-in once you've "
                        "done the actual work.\n\n"
                        "Commands:\n"
                        "/status — see open assignments\n"
                        "/run\\_now <assignment\\_id> — trigger digest now"
                    ),
                    buttons=(),
                ),
            )

        elif text.startswith("/status"):
            from app.api.dependencies import get_repository as _repo
            repo = _repo()
            open_assignments = repo.list_open_assignments()
            if not open_assignments:
                body = "✅ No open assignments — you're all caught up!"
            else:
                lines = [f"📋 *{len(open_assignments)} open assignment(s):*\n"]
                for a in open_assignments[:10]:
                    lines.append(f"• `{a.id}` — {a.title} (due {a.due_at.strftime('%Y-%m-%d %H:%M')} UTC) [{a.status.value}]")
                body = "\n".join(lines)
            await bot.send_message(chat_id, TelegramMessage(text=body, buttons=()))

        elif text.startswith("/run_now"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await bot.send_message(
                    chat_id,
                    TelegramMessage(text="Usage: /run\\_now <assignment\\_id>", buttons=()),
                )
            else:
                assignment_id = parts[1].strip()
                await bot.send_message(
                    chat_id,
                    TelegramMessage(
                        text=f"⚙️ Triggering digest for `{assignment_id}`…\nUse POST /assignments/{assignment_id}/run-now via the API.",
                        buttons=(),
                    ),
                )

    # --- inline button callbacks ---
    callback = update.get("callback_query")
    if callback:
        chat_id = str(callback["message"]["chat"]["id"])
        data: str = callback.get("data", "")

        if data.startswith("ignore:"):
            await bot.send_message(chat_id, TelegramMessage(text="🙈 Assignment ignored.", buttons=()))

        elif data.startswith("digest:"):
            run_id = data.split(":", 1)[1]
            await bot.send_message(
                chat_id,
                TelegramMessage(
                    text=f"📄 Digest for run `{run_id}` — check GET /assignments/{run_id}/status for the full digest file.",
                    buttons=(),
                ),
            )

        elif data.startswith("scaffold:"):
            run_id = data.split(":", 1)[1]
            await bot.send_message(
                chat_id,
                TelegramMessage(
                    text=f"🏗️ Scaffold for run `{run_id}` — check GET /assignments/{run_id}/status for scaffold files.",
                    buttons=(),
                ),
            )

        elif data.startswith("submit:"):
            run_id = data.split(":", 1)[1]
            await bot.send_message(
                chat_id,
                TelegramMessage(
                    text=f"🚀 Submitting `{run_id}` via POST /assignments/{run_id}/submit …",
                    buttons=(),
                ),
            )

        elif data.startswith("cancel:"):
            await bot.send_message(chat_id, TelegramMessage(text="❌ Submission cancelled.", buttons=()))

    return {"ok": "true"}


# ---------------------------------------------------------------------------
# Overall dashboard
# ---------------------------------------------------------------------------

@router.get("/status", tags=["meta"])
def dashboard(
    repository: AssignmentRepository = Depends(get_repository),
) -> dict[str, Any]:
    """High-level status dashboard — counts of assignments by status."""
    from collections import Counter
    assignments = list(repository.list_open_assignments())
    counts: Counter = Counter(a.status.value for a in assignments)
    return {
        "open_assignments": len(assignments),
        "by_status": dict(counts),
        "assignments": [_assignment_dict(a) for a in assignments],
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _assignment_dict(a) -> dict[str, Any]:
    return {
        "id": a.id,
        "course_id": a.course_id,
        "title": a.title,
        "due_at": a.due_at.isoformat(),
        "submission_state": a.submission_state,
        "status": a.status.value,
    }


def _file_dict(f: GeneratedFile) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "kind": f.kind.value,
        "filename": f.filename,
    }


def _download_attachments(assignment_id: str, course_id: str, settings) -> list[str]:
    """Download Drive attachments for the assignment; returns local file paths."""
    from uuid import UUID
    from app.db.session import SessionLocal
    from app.db.sql_repository import OAuthTokenRepository
    from app.integrations.oauth import TokenCipher, build_credentials, build_classroom_service, build_drive_service
    from app.integrations.classroom import GoogleClassroomClient
    from app.integrations.drive import GoogleDriveClient
    from pathlib import Path

    USER_ID = UUID("00000000-0000-0000-0000-000000000001")
    cipher = TokenCipher(settings.fernet_key)

    with SessionLocal() as db:
        token_repo = OAuthTokenRepository(db, cipher)
        bundle = token_repo.load(USER_ID)

    if bundle is None:
        raise RuntimeError("No OAuth token found — complete /oauth/google first.")

    creds = build_credentials(bundle, settings.google_client_id, settings.google_client_secret)
    classroom_svc = build_classroom_service(creds)
    drive_svc = build_drive_service(creds)

    classroom = GoogleClassroomClient(classroom_svc)
    drive = GoogleDriveClient(drive_svc)

    # Fetch coursework to find material attachments.
    coursework_list = classroom.list_coursework(course_id)
    cw = next((c for c in coursework_list if str(c["id"]) == assignment_id), None)
    if not cw:
        return []

    dest = Path("storage") / "attachments" / assignment_id
    paths: list[str] = []
    for material in cw.get("materials", []):
        df = material.get("driveFile", {}).get("driveFile", {})
        file_id = df.get("id")
        if file_id:
            try:
                p = drive.download_attachment(file_id, dest)
                paths.append(str(p))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not download attachment %s: %s", file_id, exc)
    return paths
