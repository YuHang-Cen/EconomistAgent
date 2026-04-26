"""Author language helpers shared by API, storage, and pipeline services."""

from __future__ import annotations

from typing import Any, Literal

AuthorLanguage = Literal["english", "chinese"]
DEFAULT_AUTHOR_LANGUAGE: AuthorLanguage = "english"


def normalize_author_language(value: Any, default: AuthorLanguage = DEFAULT_AUTHOR_LANGUAGE) -> AuthorLanguage:
    """Normalize arbitrary language input into one of the supported author languages."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"english", "en", "en-us", "en-gb"}:
            return "english"
        if normalized in {"chinese", "zh", "zh-cn", "zh-hans", "cn"}:
            return "chinese"
    return default
