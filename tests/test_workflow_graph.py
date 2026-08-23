"""Tests for the LangGraph assignment pipeline (app.agent.workflow)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.agent.workflow import (
    build_graph,
    get_graph,
    is_due_soon,
    can_route_to_submit,
    route_after_deadline_check,
    route_after_await_user_files,
    node_extract,
    node_digest,
    node_scaffold,
)


def _state(due_in_hours: float = 3.0, user_files=None, attachments=None):
    return {
        "assignment_id": "test-1",
        "course_id": "course-1",
        "due_at": datetime.now(timezone.utc) + timedelta(hours=due_in_hours),
        "attachments": attachments or [],
        "extracted_text": None,
        "digest": None,
        "scaffold": None,
        "user_files": user_files,
        "attempt": 0,
        "error": None,
    }


# --- Routing helpers ---

def test_is_due_soon_within_threshold():
    assert is_due_soon(_state(due_in_hours=3), threshold_hours=24) is True


def test_is_due_soon_outside_threshold():
    assert is_due_soon(_state(due_in_hours=48), threshold_hours=24) is False


def test_route_after_deadline_check_due_soon():
    assert route_after_deadline_check(_state(due_in_hours=2)) == "DOWNLOAD"


def test_route_after_deadline_check_not_due():
    assert route_after_deadline_check(_state(due_in_hours=100)) == "SKIP"


def test_can_route_to_submit_with_files():
    assert can_route_to_submit(_state(user_files=["main.py"])) is True


def test_can_route_to_submit_without_files():
    assert can_route_to_submit(_state(user_files=None)) is False


def test_route_after_await_user_files_ready():
    assert route_after_await_user_files(_state(user_files=["f.py"])) == "SANDBOX_CHECK"


def test_route_after_await_user_files_waiting():
    assert route_after_await_user_files(_state(user_files=None)) == "AWAIT_USER_FILES"


# --- Node unit tests ---

def test_node_extract_no_attachments(tmp_path):
    state = _state()
    result = node_extract(state)
    assert result["extracted_text"] is not None
    assert "test-1" in result["extracted_text"]


def test_node_extract_with_txt_attachment(tmp_path):
    f = tmp_path / "brief.txt"
    f.write_text("You must implement the sort function.", encoding="utf-8")
    state = {**_state(), "attachments": [str(f)]}
    result = node_extract(state)
    assert "sort function" in result["extracted_text"]


def test_node_digest_produces_fields():
    state = {**_state(), "extracted_text": "You must submit main.py. What is the output?"}
    result = node_digest(state)
    d = result["digest"]
    assert "questions" in d
    assert "requirements" in d
    assert "expected_output_files" in d


def test_node_scaffold_produces_starter_files():
    digest = {
        "questions": ["What does the function return?"],
        "expected_output_files": ["solution.py"],
        "requirements": ["You must implement the sort."],
        "concepts": [],
    }
    state = {**_state(), "digest": digest}
    result = node_scaffold(state)
    sc = result["scaffold"]
    assert "solution.py" in sc["starter_files"]
    assert "checklist" in sc
    assert "concept_pointers" in sc


# --- Graph compile test ---

def test_graph_compiles():
    graph = get_graph()
    assert graph is not None
    # Verify the graph has expected nodes
    nodes = list(graph.nodes)
    assert "CHECK_DEADLINE" in nodes
    assert "SUBMIT" in nodes
    assert "SKIP" in nodes
