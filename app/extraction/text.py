from pathlib import Path


def extract_text(path: str | Path) -> str:
    file_path = Path(path)
    if file_path.suffix.lower() in {".txt", ".md", ".csv"}:
        return file_path.read_text(encoding="utf-8")
    raise NotImplementedError("PDF/DOCX/OCR extraction adapters are planned for the next implementation phase.")
