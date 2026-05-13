"""Shared helpers for section-aware paragraph extraction."""

from __future__ import annotations

import re
from typing import Any

SENTENCE_END_RE = re.compile(r"""[.!?。！？”'")\]]*$""")

CONTINUATION_START_RE = re.compile(
    r"^(and|or|but|nor|for|yet|so|because|however|therefore|thus|then|while|when|which|that|who|whom|whose)\b",
    re.IGNORECASE,
)


class ExtractParagraphsError(RuntimeError):
    """Raised when document extraction cannot produce valid segments."""


def _clean_section_title(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return fallback


def _clean_inline_footnotes(text: str) -> str:
    """Remove inline footnote markers while preserving real numerals."""
    cleaned = re.sub(r"""(?<!\d)([.!?。！？'"")\]])\d+(?=\s|$)""", r"\1", text)
    cleaned = re.sub(r"""(?<!\d)([,;:，；：'"")\]])\d+(?=\s|$)""", r"\1", cleaned)
    cleaned = re.sub(r"\[(\d+)\]", "", cleaned)
    return cleaned


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\s+\n", "\n", normalized)
    normalized = re.sub(r"\n\s+", "\n", normalized)
    normalized = re.sub(r"\s+([,.;:!?，。；：！？%])", r"\1", normalized)
    normalized = re.sub(r"""([(\["'])\s+""", r"\1", normalized)
    normalized = _clean_inline_footnotes(normalized)
    return normalized.strip()


def _is_noise_paragraph(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) <= 2:
        return True
    if re.fullmatch(r"\(?\d+\)?", stripped):
        return True
    if re.fullmatch(r"[\dIVXLCDMivxlcdm\s\-路]+", stripped) and len(stripped) <= 12:
        return True
    if re.fullmatch(r"\[\d+\]", stripped):
        return True
    return False


def _starts_with_number(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0].isdigit()


def _should_merge(prev_para: str, curr_para: str) -> bool:
    prev = prev_para.rstrip()
    curr = curr_para.lstrip()
    if not prev or not curr:
        return False
    if prev.endswith("-"):
        return True
    if prev.endswith(("(", '"', "'", ":", ";", ",")):
        return True
    if curr and curr[0].islower():
        return True
    if CONTINUATION_START_RE.match(curr) and SENTENCE_END_RE.search(prev) is None:
        return True
    return False


def _merge_paragraph(prev_para: str, curr_para: str) -> str:
    if prev_para.endswith("-"):
        return (prev_para[:-1] + curr_para.lstrip()).strip()
    return f"{prev_para.rstrip()} {curr_para.lstrip()}".strip()


def _build_paragraphs(blocks: list[str], *, skip_numeric_prefix: bool = True) -> list[str]:
    paragraphs: list[str] = []
    for block in blocks:
        paragraph = _normalize_text(block)
        if _is_noise_paragraph(paragraph):
            continue
        if skip_numeric_prefix and _starts_with_number(paragraph):
            continue
        if paragraphs and _should_merge(paragraphs[-1], paragraph):
            paragraphs[-1] = _merge_paragraph(paragraphs[-1], paragraph)
        else:
            paragraphs.append(paragraph)
    return paragraphs
