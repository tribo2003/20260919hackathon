from __future__ import annotations

import io
import re
from pathlib import Path


def extract_resume_text(filename: str, raw: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(raw)
    if suffix in {".docx"}:
        return _from_docx(raw)
    return raw.decode("utf-8", errors="ignore")


def extract_candidate_name(resume_text: str) -> str:
    """Return a likely name from the first line of a resume, when safe to do so."""
    first_line = next((line.strip() for line in (resume_text or "").splitlines() if line.strip()), "")
    if not first_line:
        return ""

    explicit_name = re.match(r"^(?:name|\u59d3\u540d)\s*[:\uff1a]\s*(.+)$", first_line, flags=re.I)
    if explicit_name:
        first_line = explicit_name.group(1).strip()

    labeled = re.match(r"^(?:name|姓名)\s*[:：]\s*(.+)$", first_line, flags=re.I)
    candidate = labeled.group(1) if labeled else re.split(r"\s*[|｜]\s*", first_line, maxsplit=1)[0]
    candidate = re.sub(r"\s+", " ", candidate).strip(" -–—,，")
    lower_candidate = candidate.lower()
    rejected_terms = ("resume", "curriculum vitae", "experience", "education", "skills", "summary")
    if (
        not candidate
        or len(candidate) > 50
        or any(term in lower_candidate for term in rejected_terms)
        or "@" in candidate
        or "http" in lower_candidate
        or any(char.isdigit() for char in candidate)
    ):
        return ""

    role_terms = (
        "engineer", "scientist", "analyst", "developer", "designer", "manager",
        "consultant", "intern", "student",
    )
    if any(term in lower_candidate for term in role_terms):
        return ""

    # Supports common English names and Chinese names; do not guess from a
    # heading such as a job title when the first line is not name-like.
    english_name = re.fullmatch(r"[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,3}", candidate)
    chinese_name = re.fullmatch(r"[\u4e00-\u9fff]{2,5}", candidate.replace(" ", ""))
    return candidate if english_name or chinese_name else ""


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
