"""Docker sandbox runner for testing user-authored code.

Runs a user's file inside a network-disabled, resource-limited Docker
container. Only Python files are supported for now; the container uses
the official python:3.11-slim image.

IMPORTANT: This sandbox is for *running the user's own code* to check it
works before submission — NOT for generating or verifying AI-produced answers.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Docker run constraints (matching ARCHITECTURE.md security requirements)
_CPU_QUOTA = "50000"   # 50 % of one CPU (100000 = 100 %)
_MEMORY = "128m"
_TIMEOUT_SECONDS = 15
_IMAGE = "python:3.11-slim"


@dataclass(frozen=True)
class SandboxResult:
    passed: bool
    output: str
    exit_code: int = 0


def run_user_code_in_sandbox(path: str | Path) -> SandboxResult:
    """Run a user-authored file in a Docker sandbox.

    Falls back gracefully if Docker is not available (returns passed=False
    with a clear message rather than crashing the whole pipeline).
    """
    file_path = Path(path)

    if not file_path.exists():
        return SandboxResult(passed=False, output=f"File not found: {file_path.name}", exit_code=-1)

    if not _docker_available():
        logger.info("Docker not available — sandbox skipped for %s.", file_path.name)
        return SandboxResult(
            passed=False,
            output=f"Docker is not installed or not running. Sandbox skipped for {file_path.name}.",
            exit_code=-1,
        )

    suffix = file_path.suffix.lower()
    if suffix != ".py":
        return SandboxResult(
            passed=False,
            output=f"Sandbox only supports .py files for now; got {suffix}.",
            exit_code=-1,
        )

    return _run_python_sandbox(file_path)


def _docker_available() -> bool:
    try:
        import docker  # type: ignore[import]
        client = docker.from_env()
        client.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


def _run_python_sandbox(file_path: Path) -> SandboxResult:
    """Copy the file into a temp dir and run it inside Docker."""
    try:
        import docker  # type: ignore[import]
        from docker.errors import ContainerError, ImageNotFound  # type: ignore[import]
    except ImportError:
        return SandboxResult(
            passed=False,
            output="docker Python SDK not installed. Run: pip install docker",
            exit_code=-1,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy user file into the temp dir (don't expose whole filesystem)
        sandbox_file = Path(tmpdir) / file_path.name
        shutil.copy2(file_path, sandbox_file)

        client = docker.from_env()

        try:
            container = client.containers.run(
                image=_IMAGE,
                command=f"python /sandbox/{file_path.name}",
                volumes={tmpdir: {"bind": "/sandbox", "mode": "ro"}},
                network_mode="none",        # No network access
                mem_limit=_MEMORY,
                cpu_quota=int(_CPU_QUOTA),
                cpu_period=100_000,
                read_only=True,
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
                timeout=_TIMEOUT_SECONDS,
            )
            output = container.decode("utf-8", errors="replace") if isinstance(container, bytes) else str(container)
            logger.info("Sandbox passed for %s.", file_path.name)
            return SandboxResult(passed=True, output=output.strip(), exit_code=0)

        except ContainerError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            logger.info("Sandbox: %s exited with error: %s", file_path.name, stderr[:200])
            return SandboxResult(passed=False, output=stderr.strip(), exit_code=exc.exit_status)

        except ImageNotFound:
            return SandboxResult(
                passed=False,
                output=f"Docker image {_IMAGE!r} not found. Run: docker pull {_IMAGE}",
                exit_code=-1,
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning("Sandbox error for %s: %s", file_path.name, exc)
            return SandboxResult(passed=False, output=str(exc), exit_code=-1)
