from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCAFFOLD_BOUNDARY = (
    "Produce structure, starter placeholders, checklist items, and concept pointers only. "
    "Do not produce a complete answer, finished essay, solved worksheet, or working final implementation."
)


@dataclass(frozen=True)
class Scaffold:
    starter_files: dict[str, str]
    checklist: tuple[str, ...]
    concept_pointers: tuple[str, ...]


def generate_scaffold_from_digest(digest: dict[str, Any]) -> Scaffold:
    expected_files = digest.get("expected_output_files") or ["submission.txt"]
    starter_files = {
        filename: _starter_content(filename, digest.get("requirements") or [])
        for filename in expected_files
    }
    return Scaffold(
        starter_files=starter_files,
        checklist=tuple(digest.get("questions") or ["Restate the assignment in your own words."]),
        concept_pointers=tuple(digest.get("concepts") or ["Review the class notes relevant to this assignment."]),
    )


def _starter_content(filename: str, requirements: list[str]) -> str:
    lines = [
        f"# Starter scaffold for {filename}",
        "# Fill this in with your own work before submitting.",
        "",
        "## Requirements to address",
    ]
    lines.extend(f"- [ ] {requirement}" for requirement in requirements)
    lines.extend(
        [
            "",
            "## Your work",
            "<write your own solution here>",
            "",
            f"<!-- Boundary: {SCAFFOLD_BOUNDARY} -->",
        ]
    )
    return "\n".join(lines)
