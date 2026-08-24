"""LangGraph state machine for the assignment pipeline.

Graph nodes (matching AGENT_WORKFLOW.md):
  CHECK_DEADLINE → DOWNLOAD → EXTRACT → DIGEST → SCAFFOLD
  → NOTIFY_DIGEST → AWAIT_USER_FILES → SANDBOX_CHECK
  → NOTIFY_READY → SUBMIT → [SKIP | FAIL]

The graph is compiled lazily on first use via get_graph().
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.agent.state import AssignmentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing helpers (kept for test compatibility)
# ---------------------------------------------------------------------------

def is_due_soon(state: AssignmentState, threshold_hours: int) -> bool:
    now = datetime.now(timezone.utc)
    seconds_until_due = (state["due_at"] - now).total_seconds()
    return 0 <= seconds_until_due <= threshold_hours * 60 * 60


def can_route_to_submit(state: AssignmentState) -> bool:
    return bool(state.get("user_files"))


def route_after_deadline_check(state: AssignmentState, threshold_hours: int = 24) -> str:
    return "DOWNLOAD" if is_due_soon(state, threshold_hours) else "SKIP"


def route_after_await_user_files(state: AssignmentState) -> str:
    return "SANDBOX_CHECK" if can_route_to_submit(state) else "AWAIT_USER_FILES"


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def node_check_deadline(state: AssignmentState) -> AssignmentState:
    """Route: is the assignment due soon?"""
    # Routing is handled by the conditional edge; node is a no-op pass-through.
    return state


def node_download(state: AssignmentState) -> AssignmentState:
    """Download Drive attachments listed in state['attachments'].

    In the live flow the monitor populates attachments with Drive file IDs.
    Without credentials we keep the list empty and let EXTRACT handle it.
    """
    downloaded: list[str] = []
    for file_id in state.get("attachments") or []:
        try:
            from app.config import get_settings
            from app.integrations.drive import GoogleDriveClient
            from app.integrations.oauth import build_credentials, build_drive_service, TokenCipher
            from app.db.session import SessionLocal
            from app.db.sql_repository import OAuthTokenRepository
            from uuid import UUID

            settings = get_settings()
            if not settings.fernet_key or not settings.google_client_id:
                break
            cipher = TokenCipher(settings.fernet_key)
            with SessionLocal() as db:
                bundle = OAuthTokenRepository(db, cipher).load(
                    UUID("00000000-0000-0000-0000-000000000001")
                )
            if not bundle:
                break
            creds = build_credentials(bundle, settings.google_client_id, settings.google_client_secret)
            drive = GoogleDriveClient(build_drive_service(creds))
            dest = Path("storage") / "attachments" / state["assignment_id"]
            p = drive.download_attachment(file_id, dest)
            downloaded.append(str(p))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Attachment download skipped for %s: %s", file_id, exc)

    return {**state, "attachments": downloaded or state.get("attachments", [])}


def node_extract(state: AssignmentState) -> AssignmentState:
    """Extract text from all downloaded attachment paths."""
    from app.extraction.text import extract_text

    paths = state.get("attachments") or []
    if not paths:
        # No attachments — synthesise text from the assignment title.
        text = f"Assignment: {state.get('assignment_id', 'unknown')}\n"
    else:
        parts: list[str] = []
        for p in paths:
            try:
                parts.append(extract_text(p))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Text extraction failed for %s: %s", p, exc)
        text = "\n\n".join(parts) or f"Assignment: {state.get('assignment_id', 'unknown')}\n"

    return {**state, "extracted_text": text}


def node_digest(state: AssignmentState) -> AssignmentState:
    """Run the requirement digest over the extracted text."""
    from app.services.llm import get_llm_digest

    text = state.get("extracted_text") or ""
    digest = get_llm_digest(text)
    return {**state, "digest": digest.as_dict()}


def node_scaffold(state: AssignmentState) -> AssignmentState:
    """Generate scaffold from the digest."""
    from app.scaffolding.generator import generate_scaffold_from_digest

    digest = state.get("digest") or {}
    scaffold_obj = generate_scaffold_from_digest(digest)
    return {
        **state,
        "scaffold": {
            "starter_files": scaffold_obj.starter_files,
            "checklist": list(scaffold_obj.checklist),
            "concept_pointers": list(scaffold_obj.concept_pointers),
        },
    }


def node_notify_digest(state: AssignmentState) -> AssignmentState:
    """Send Telegram notification that digest + scaffold are ready."""
    try:
        from app.config import get_settings
        from app.integrations.telegram import TelegramBotClient, digest_ready_message
        import asyncio

        settings = get_settings()
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return state

        bot = TelegramBotClient(settings.telegram_bot_token)
        msg = digest_ready_message(
            assignment_title=state.get("assignment_id", "assignment"),
            course_name=state.get("course_id", "course"),
            due_at=state["due_at"],
            agent_run_id=state["assignment_id"],
        )
        asyncio.run(bot.send_message(settings.telegram_chat_id, msg))
        logger.info("Telegram digest notification sent for %s.", state["assignment_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram notify_digest failed: %s", exc)
    return state


def node_await_user_files(state: AssignmentState) -> AssignmentState:
    """Pause point — the graph stays here until user_files is populated."""
    return state


def node_sandbox_check(state: AssignmentState) -> AssignmentState:
    """Run user code through the Docker sandbox (if configured)."""
    from app.sandbox.runner import run_user_code_in_sandbox

    results: dict[str, dict] = {}
    for path in state.get("user_files") or []:
        result = run_user_code_in_sandbox(path)
        results[path] = {"passed": result.passed, "output": result.output}
        if not result.passed:
            logger.info("Sandbox: %s did not pass — %s", path, result.output)

    return {**state, "sandbox_results": results}  # type: ignore[typeddict-unknown-key]


def node_notify_ready(state: AssignmentState) -> AssignmentState:
    """Send Telegram notification that user files are ready to submit."""
    try:
        from app.config import get_settings
        from app.integrations.telegram import TelegramBotClient, ready_to_submit_message
        import asyncio

        settings = get_settings()
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return state

        bot = TelegramBotClient(settings.telegram_bot_token)
        msg = ready_to_submit_message(
            assignment_title=state.get("assignment_id", "assignment"),
            agent_run_id=state["assignment_id"],
        )
        asyncio.run(bot.send_message(settings.telegram_chat_id, msg))
        logger.info("Telegram ready-to-submit notification sent for %s.", state["assignment_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram notify_ready failed: %s", exc)
    return state


def node_submit(state: AssignmentState) -> AssignmentState:
    """Submit user-authored files to Classroom via Drive."""
    from app.db.models import GeneratedFile, GeneratedFileKind
    from app.integrations.classroom import SubmissionRequest, SubmissionService

    user_files = [
        GeneratedFile(
            assignment_id=state["assignment_id"],
            kind=GeneratedFileKind.USER_SUBMISSION,
            filename=Path(p).name,
            storage_path=p,
        )
        for p in (state.get("user_files") or [])
    ]
    service = SubmissionService()
    result = service.submit_user_files(
        SubmissionRequest(assignment_id=state["assignment_id"], files=user_files)
    )
    logger.info("Submission result for %s: %s", state["assignment_id"], result.status)
    return {**state, "submit_status": result.status}  # type: ignore[typeddict-unknown-key]


def node_skip(state: AssignmentState) -> AssignmentState:
    logger.info("Assignment %s is not due soon — skipping.", state["assignment_id"])
    return state


def node_fail(state: AssignmentState) -> AssignmentState:
    logger.error("Assignment %s failed: %s", state["assignment_id"], state.get("error"))
    return state


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(threshold_hours: int = 24):
    """Build and compile the LangGraph assignment pipeline."""
    from langgraph.graph import END, StateGraph  # lazy import

    g = StateGraph(AssignmentState)

    # Register nodes
    g.add_node("CHECK_DEADLINE", node_check_deadline)
    g.add_node("DOWNLOAD", node_download)
    g.add_node("EXTRACT", node_extract)
    g.add_node("DIGEST", node_digest)
    g.add_node("SCAFFOLD", node_scaffold)
    g.add_node("NOTIFY_DIGEST", node_notify_digest)
    g.add_node("AWAIT_USER_FILES", node_await_user_files)
    g.add_node("SANDBOX_CHECK", node_sandbox_check)
    g.add_node("NOTIFY_READY", node_notify_ready)
    g.add_node("SUBMIT", node_submit)
    g.add_node("SKIP", node_skip)
    g.add_node("FAIL", node_fail)

    # Entry point
    g.set_entry_point("CHECK_DEADLINE")

    # Conditional: due soon → DOWNLOAD, else → SKIP
    g.add_conditional_edges(
        "CHECK_DEADLINE",
        lambda s: route_after_deadline_check(s, threshold_hours),
        {"DOWNLOAD": "DOWNLOAD", "SKIP": "SKIP"},
    )

    # Linear pipeline
    g.add_edge("DOWNLOAD", "EXTRACT")
    g.add_edge("EXTRACT", "DIGEST")
    g.add_edge("DIGEST", "SCAFFOLD")
    g.add_edge("SCAFFOLD", "NOTIFY_DIGEST")
    g.add_edge("NOTIFY_DIGEST", "AWAIT_USER_FILES")

    # Conditional: user files uploaded → SANDBOX_CHECK, else stay
    g.add_conditional_edges(
        "AWAIT_USER_FILES",
        route_after_await_user_files,
        {"SANDBOX_CHECK": "SANDBOX_CHECK", "AWAIT_USER_FILES": "AWAIT_USER_FILES"},
    )

    g.add_edge("SANDBOX_CHECK", "NOTIFY_READY")
    g.add_edge("NOTIFY_READY", "SUBMIT")

    # Terminal nodes
    g.add_edge("SUBMIT", END)
    g.add_edge("SKIP", END)
    g.add_edge("FAIL", END)

    return g


# Lazy singleton — call get_graph() to get the compiled graph
_graph = None


def get_graph(threshold_hours: int = 24):
    """Return the compiled LangGraph (built once, cached)."""
    global _graph
    if _graph is None:
        _graph = build_graph(threshold_hours)
    return _graph
