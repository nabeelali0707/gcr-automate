from __future__ import annotations

import argparse
from pathlib import Path

from app.services.demo import run_demo_digest, run_demo_poll, seed_demo_repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Classroom Deadline Assistant demo.")
    parser.add_argument(
        "--storage-dir",
        default="storage/demo",
        help="Directory for generated digest/scaffold files.",
    )
    args = parser.parse_args()

    repository = seed_demo_repository()
    poll_result = run_demo_poll(repository)

    print(f"Scanned {poll_result.scanned} demo assignment(s).")
    if not poll_result.urgent:
        print("No urgent demo assignments found.")
        return

    storage_dir = Path(args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    instructions = storage_dir / "demo-instructions.txt"
    instructions.write_text(
        "\n".join(
            [
                "Submit main.py before the deadline.",
                "You must implement your own functions.",
                "Include a short README.md explaining how to run your work.",
                "What should the program print for the sample input?",
            ]
        ),
        encoding="utf-8",
    )

    digest_result = run_demo_digest(repository, str(instructions), str(storage_dir))
    print(f"Digest written to: {digest_result.digest_file.storage_path}")
    for scaffold in digest_result.scaffold_files:
        print(f"Scaffold written to: {scaffold.storage_path}")


if __name__ == "__main__":
    main()
