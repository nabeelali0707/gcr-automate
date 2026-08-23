from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxResult:
    passed: bool
    output: str


def run_user_code_in_sandbox(path: str | Path) -> SandboxResult:
    # Docker execution is intentionally deferred; this placeholder keeps the
    # public API explicit while preventing accidental execution on the host.
    return SandboxResult(passed=False, output=f"Sandbox adapter not configured for {Path(path).name}.")
