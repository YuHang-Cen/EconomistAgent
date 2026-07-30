"""Document kind helpers for upload and extraction branching."""

from __future__ import annotations

from typing import Literal

DocumentKind = Literal["book", "paper"]

DEFAULT_DOCUMENT_KIND: DocumentKind = "book"


def normalize_document_kind(value: str | None) -> DocumentKind:
    normalized = str(value or "").strip().lower()
    if normalized == "paper":
        return "paper"
    return DEFAULT_DOCUMENT_KIND
