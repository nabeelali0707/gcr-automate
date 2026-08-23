from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RequirementDigest:
    questions: tuple[str, ...]
    expected_output_files: tuple[str, ...]
    requirements: tuple[str, ...]
    concepts: tuple[str, ...]
    deadline_note: str | None = None

    def as_dict(self) -> dict:
        return {
            "questions": list(self.questions),
            "expected_output_files": list(self.expected_output_files),
            "requirements": list(self.requirements),
            "concepts": list(self.concepts),
            "deadline_note": self.deadline_note,
        }


def digest_requirements(text: str) -> RequirementDigest:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    questions = tuple(line for line in lines if line.endswith("?"))[:10]
    expected_files = tuple(dict.fromkeys(re.findall(r"[\w.-]+\.(?:py|java|cpp|js|ts|pdf|docx|txt|md)", text)))
    requirements = tuple(_requirement_lines(lines))[:12]
    concepts = tuple(_concept_hints(text))
    return RequirementDigest(
        questions=questions or ("Identify the deliverables requested by the assignment.",),
        expected_output_files=expected_files or ("submission.txt",),
        requirements=requirements or ("Complete the assignment using your own work.",),
        concepts=concepts or ("Review the topic notes and examples from class.",),
        deadline_note=_find_deadline_note(lines),
    )


def _requirement_lines(lines: list[str]) -> list[str]:
    markers = ("must", "should", "submit", "include", "write", "create", "implement", "upload")
    return [line for line in lines if any(marker in line.lower() for marker in markers)]


def _concept_hints(text: str) -> list[str]:
    lowered = text.lower()
    concepts: list[str] = []
    keyword_map = {
        "function": "Function signatures and decomposition",
        "class": "Object-oriented design basics",
        "database": "Schema design and query constraints",
        "essay": "Outline, thesis, evidence, and revision",
        "citation": "Citation format required by the course",
        "algorithm": "Algorithm design and complexity",
    }
    for keyword, concept in keyword_map.items():
        if keyword in lowered:
            concepts.append(concept)
    return concepts


def _find_deadline_note(lines: list[str]) -> str | None:
    for line in lines:
        if "due" in line.lower() or "deadline" in line.lower():
            return line
    return None
