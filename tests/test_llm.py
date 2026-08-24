"""Tests for the LLM digest service (app.services.llm)."""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from app.agent.digest import RequirementDigest
from app.config import Settings
from app.services.llm import get_llm_digest


def test_get_llm_digest_fallback_when_no_keys_configured(monkeypatch) -> None:
    # Force empty settings keys
    def mock_settings():
        return Settings(
            gemini_api_key=None,
            openai_api_key=None,
        )
    monkeypatch.setattr("app.services.llm.get_settings", mock_settings)

    text = "Submit project.py by tomorrow. What is the complexity?"
    digest = get_llm_digest(text)

    assert isinstance(digest, RequirementDigest)
    # The heuristic should find "project.py"
    assert "project.py" in digest.expected_output_files
    assert len(digest.questions) > 0


def test_get_llm_digest_gemini_success(monkeypatch) -> None:
    # Set gemini api key
    def mock_settings():
        return Settings(
            gemini_api_key="mock-gemini-key",
            openai_api_key=None,
        )
    monkeypatch.setattr("app.services.llm.get_settings", mock_settings)

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "questions": ["How do you run it?"],
                                "expected_output_files": ["run.sh"],
                                "requirements": ["Must use bash"],
                                "concepts": ["Shell scripting"],
                                "deadline_note": "Due Friday"
                            })
                        }
                    ]
                }
            }
        ]
    }

    # Mock httpx POST call
    def mock_post(*args, **kwargs):
        class MockResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return mock_gemini_response
        return MockResponse()

    with patch("httpx.Client.post", side_effect=mock_post):
        digest = get_llm_digest("Submit run.sh by Friday.")

    assert digest.expected_output_files == ("run.sh",)
    assert digest.questions == ("How do you run it?",)
    assert digest.requirements == ("Must use bash",)
    assert digest.concepts == ("Shell scripting",)
    assert digest.deadline_note == "Due Friday"


def test_get_llm_digest_openai_success(monkeypatch) -> None:
    # Set openai api key (no gemini key)
    def mock_settings():
        return Settings(
            gemini_api_key=None,
            openai_api_key="mock-openai-key",
        )
    monkeypatch.setattr("app.services.llm.get_settings", mock_settings)

    mock_openai_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "questions": ["Is it fast?"],
                        "expected_output_files": ["fast.py"],
                        "requirements": ["O(N) time complexity limit"],
                        "concepts": ["Algorithms"],
                        "deadline_note": None
                    })
                }
            }
        ]
    }

    # Mock httpx POST call
    def mock_post(*args, **kwargs):
        class MockResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return mock_openai_response
        return MockResponse()

    with patch("httpx.Client.post", side_effect=mock_post):
        digest = get_llm_digest("Submit fast.py.")

    assert digest.expected_output_files == ("fast.py",)
    assert digest.requirements == ("O(N) time complexity limit",)
    assert digest.concepts == ("Algorithms",)
    assert digest.deadline_note is None
