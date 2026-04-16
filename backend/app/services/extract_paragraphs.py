"""Document extract stage: parse PDF into section-aware paragraph rows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SECTION_PATTERNS = (
    re.compile(r"^chapter\s+\d+", re.IGNORECASE),
    re.compile(r"^part\s+\d+", re.IGNORECASE),
    re.compile(r"^\d+\.\s+"),
)


class ExtractParagraphsError(RuntimeError):
    """Raised when document extraction cannot produce valid segments."""


def _normalize_text(text: str) -> str:
    """Normalize whitespace and line breaks from PDF text blocks."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    return normalized.strip()


def _is_noise(text: str) -> bool:
    """Filter low-value blocks such as bare numbers and page markers."""
    stripped = text.strip()
    if len(stripped) < 8:
        return True
    if re.fullmatch(r"\(?\d+\)?", stripped):
        return True
    if re.fullmatch(r"[\dIVXLCDMivxlcdm\s\-–—]+", stripped):
        return True
    return False


def _extract_from_pdf(pdf_path: Path, default_section: str) -> list[dict[str, Any]]:
    """Extract section/paragraph records from a local PDF."""
    try:
        import fitz
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("PyMuPDF (fitz) is not available for PDF extraction") from exc

    records: list[dict[str, Any]] = []
    section_title = default_section
    section_order: dict[str, int] = {section_title: 0}
    section_counts: dict[str, int] = {section_title: 0}

    try:
        with fitz.open(pdf_path) as document:
            for page in document:
                text = page.get_text("text") or ""
                blocks = [blk for blk in text.split("\n\n") if blk.strip()]
                for block in blocks:
                    cleaned = _normalize_text(block)
                    if not cleaned:
                        continue

                    first_line = cleaned.split(" ")[0:8]
                    heading_probe = " ".join(first_line)
                    if any(pattern.match(heading_probe) for pattern in SECTION_PATTERNS):
                        section_title = cleaned[:100]
                        if section_title not in section_order:
                            section_order[section_title] = len(section_order)
                            section_counts[section_title] = 0
                        continue

                    if _is_noise(cleaned):
                        continue

                    section_counts[section_title] = section_counts.get(section_title, 0) + 1
                    section_idx = section_order[section_title]
                    paragraph_idx = section_counts[section_title]
                    chunk_id = f"{section_idx + 1:03d}-{paragraph_idx:04d}"
                    order_index = len(records)
                    records.append(
                        {
                            "section_title": section_title,
                            "chunk_id": chunk_id,
                            "content": cleaned,
                            "order_index": order_index,
                        }
                    )
    except Exception as exc:
        raise ExtractParagraphsError(f"failed to parse PDF file: {pdf_path}") from exc

    return records


def run_extract_paragraphs(book_title: str, pdf_uri: str) -> list[dict[str, Any]]:
    """Run extract stage and return normalized section/paragraph rows."""
    _ = book_title
    pdf_path = Path(pdf_uri)

    if not pdf_path.exists():
        raise ExtractParagraphsError(f"pdf path does not exist: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ExtractParagraphsError(f"pdf path must end with .pdf: {pdf_path}")

    extracted = _extract_from_pdf(pdf_path=pdf_path, default_section="Section 1")
    if not extracted:
        raise ExtractParagraphsError(f"no extractable segments found in pdf: {pdf_path}")

    return extracted
