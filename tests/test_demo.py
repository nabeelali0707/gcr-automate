from app.db.models import GeneratedFileKind
from app.services.demo import run_demo_digest, run_demo_poll, seed_demo_repository


def test_demo_poll_and_digest_flow(tmp_path) -> None:
    repository = seed_demo_repository()
    poll_result = run_demo_poll(repository)
    instructions = tmp_path / "instructions.txt"
    instructions.write_text("Submit main.py. You must write your own code.", encoding="utf-8")

    digest_result = run_demo_digest(repository, str(instructions), str(tmp_path / "storage"))

    assert poll_result.scanned == 1
    assert poll_result.urgent[0].id == "demo-assignment"
    assert digest_result.digest_file.kind is GeneratedFileKind.DIGEST
    assert digest_result.scaffold_files[0].kind is GeneratedFileKind.SCAFFOLD
