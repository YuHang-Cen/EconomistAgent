"""Document extract stage: parse PDF or EPUB into section-aware paragraph rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .extract_paragraphs_common import ExtractParagraphsError
from .extract_paragraphs_epub import _extract_from_epub
from .extract_paragraphs_md import _extract_from_md
from .extract_paragraphs_pdf import _extract_from_pdf


def run_extract_paragraphs(book_title: str, pdf_uri: str) -> list[dict[str, Any]]:
    """Run extract stage and return normalized section/paragraph rows."""
    source_path = Path(pdf_uri)

    if not source_path.exists():
        raise ExtractParagraphsError(f"pdf path does not exist: {source_path}")

    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        extracted = _extract_from_pdf(pdf_path=source_path, book_title=book_title)
    elif suffix == ".epub":
        extracted = _extract_from_epub(epub_path=source_path, book_title=book_title)
    elif suffix == ".md":
        extracted = _extract_from_md(md_path=source_path, book_title=book_title)
    else:
        raise ExtractParagraphsError(f"pdf path must end with .pdf, .epub, or .md: {source_path}")

    if not extracted:
        raise ExtractParagraphsError(f"no extractable segments found in document: {source_path}")

    return extracted
