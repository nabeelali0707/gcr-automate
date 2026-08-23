from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(path: str | Path) -> str:
    """Extract plain text from a file.

    Supports: .txt, .md, .csv (direct read), .pdf (pdfplumber), .docx (python-docx).
    Falls back to raw byte decode for unknown types.
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".md", ".csv", ".rst"}:
        return file_path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        return _extract_pdf(file_path)

    if suffix == ".docx":
        return _extract_docx(file_path)

    if suffix in {".doc", ".odt"}:
        logger.warning("Legacy format %s — attempting plain-text fallback.", suffix)
        return file_path.read_text(encoding="utf-8", errors="replace")

    # Unknown binary — try to decode as UTF-8 and surface whatever text is there.
    logger.warning("Unknown file type %s — trying raw decode.", suffix)
    return file_path.read_bytes().decode("utf-8", errors="replace")


def _extract_pdf(path: Path) -> str:
    """Extract text from a PDF using pdfplumber."""
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is not installed. Run: pip install pdfplumber"
        ) from exc

    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
            else:
                # Page has no selectable text — try OCR if Tesseract is available.
                ocr_text = _ocr_page(page, page_num)
                if ocr_text:
                    pages.append(ocr_text)

    return "\n\n".join(pages)


def _ocr_page(page, page_num: int) -> str:
    """Run Tesseract OCR on a single PDF page image (optional dependency)."""
    try:
        import pytesseract  # type: ignore[import]
        from PIL import Image  # type: ignore[import]
    except ImportError:
        logger.debug("pytesseract/Pillow not installed — skipping OCR for page %d.", page_num)
        return ""

    try:
        img = page.to_image(resolution=200).original
        if not isinstance(img, Image.Image):
            img = Image.frombytes("RGB", img.size, img.tobytes())
        return pytesseract.image_to_string(img)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR failed on page %d: %s", page_num, exc)
        return ""


def _extract_docx(path: Path) -> str:
    """Extract text from a .docx file using python-docx."""
    try:
        import docx  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is not installed. Run: pip install python-docx"
        ) from exc

    doc = docx.Document(str(path))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)
