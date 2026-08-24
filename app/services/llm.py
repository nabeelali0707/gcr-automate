"""LLM service for requirement digest extraction.

Uses Gemini API (default) or OpenAI API (if configured) via HTTPX.
Guarantees JSON output schema matching the RequirementDigest structure.
If no API key is configured, falls back to the rule-based extractor.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.agent.digest import RequirementDigest, digest_requirements
from app.config import get_settings

logger = logging.getLogger(__name__)

# Structured prompt for extracting requirements without solving the assignment.
SYSTEM_PROMPT = """You are a student assistant that extracts requirements from coursework documents to create a helper digest and starter scaffolding.

Your task is to analyze the assignment text and return a JSON object with the following fields:
1. "questions": A list of key questions asked in the assignment (maximum 10).
2. "expected_output_files": A list of filenames (like "main.py", "report.pdf", "answers.txt") that the user is expected to submit. Look for filename patterns.
3. "requirements": A list of specific constraints or instructions the student must follow (maximum 12).
4. "concepts": A list of general educational concepts/topics covered by the assignment (maximum 5).
5. "deadline_note": Any specific mentions of due dates, grace periods, or penalty policies (string or null).

CRITICAL BOUNDARY AND SAFETY RULES:
- Do NOT solve the assignment.
- Do NOT write the code or answers.
- Do NOT generate completed essays, final answers, or solved worksheets.
- Focus ONLY on outlining what needs to be done, not doing it.
"""


def get_llm_digest(text: str) -> RequirementDigest:
    """Extract a requirement digest using LLM if configured, otherwise fall back to rule-based."""
    settings = get_settings()

    # Try Gemini first
    if settings.gemini_api_key:
        try:
            logger.info("Attempting LLM digest using Gemini API...")
            return _call_gemini(text, settings.gemini_api_key)
        except Exception as exc:
            logger.error("Gemini API call failed, falling back: %s", exc)

    # Try OpenAI second
    if settings.openai_api_key:
        try:
            logger.info("Attempting LLM digest using OpenAI API...")
            return _call_openai(text, settings.openai_api_key)
        except Exception as exc:
            logger.error("OpenAI API call failed, falling back: %s", exc)

    # Fallback to local heuristic
    logger.info("No LLM key configured (or calls failed). Using rule-based extractor.")
    return digest_requirements(text)


def _call_gemini(text: str, api_key: str) -> RequirementDigest:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"Extracted assignment text:\n\n{text}"}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": SYSTEM_PROMPT}
            ]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        }
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        res_json = response.json()

        # Parse text response which contains the JSON string
        raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(raw_text)
        return _parse_json_to_digest(parsed)


def _call_openai(text: str, api_key: str) -> RequirementDigest:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extracted assignment text:\n\n{text}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        res_json = response.json()

        raw_text = res_json["choices"][0]["message"]["content"]
        parsed = json.loads(raw_text)
        return _parse_json_to_digest(parsed)


def _parse_json_to_digest(parsed: dict[str, Any]) -> RequirementDigest:
    questions = tuple(str(q) for q in parsed.get("questions", []) if q)
    expected_files = tuple(str(f) for f in parsed.get("expected_output_files", []) if f)
    requirements = tuple(str(r) for r in parsed.get("requirements", []) if r)
    concepts = tuple(str(c) for c in parsed.get("concepts", []) if c)
    deadline_note = parsed.get("deadline_note")
    if deadline_note:
        deadline_note = str(deadline_note)

    return RequirementDigest(
        questions=questions or ("Identify the deliverables requested by the assignment.",),
        expected_output_files=expected_files or ("submission.txt",),
        requirements=requirements or ("Complete the assignment using your own work.",),
        concepts=concepts or ("Review the topic notes and examples from class.",),
        deadline_note=deadline_note,
    )
