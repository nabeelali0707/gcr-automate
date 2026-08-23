"""Tests for the Docker sandbox runner (app.sandbox.runner)."""
from __future__ import annotations

from pathlib import Path

from app.sandbox.runner import SandboxResult, run_user_code_in_sandbox


def test_sandbox_missing_file(tmp_path):
    result = run_user_code_in_sandbox(tmp_path / "nonexistent.py")
    assert result.passed is False
    assert "not found" in result.output.lower()


def test_sandbox_non_python_file(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b,c")
    result = run_user_code_in_sandbox(f)
    assert result.passed is False
    # Either the file-type rejection message or the Docker-unavailable message
    assert ".py" in result.output or "Docker" in result.output


def test_sandbox_no_docker_graceful(tmp_path, monkeypatch):
    """When Docker is unavailable the runner must fail gracefully, not crash."""
    f = tmp_path / "hello.py"
    f.write_text("print('hello')")

    # Force _docker_available to return False
    import app.sandbox.runner as mod
    monkeypatch.setattr(mod, "_docker_available", lambda: False)

    result = run_user_code_in_sandbox(f)
    assert isinstance(result, SandboxResult)
    assert result.passed is False
    assert "Docker" in result.output
