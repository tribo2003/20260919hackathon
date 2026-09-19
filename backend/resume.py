from __future__ import annotations

import io
from pathlib import Path


def extract_resume_text(filename: str, raw: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(raw)
    if suffix in {".docx"}:
        return _from_docx(raw)
    return raw.decode("utf-8", errors="ignore")


def _from_pdf(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _from_docx(raw: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(raw))
    return "\n".join(p.text for p in doc.paragraphs)
