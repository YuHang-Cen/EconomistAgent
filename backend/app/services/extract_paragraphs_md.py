"""Markdown-specific extraction helpers for single-section paragraph parsing."""

from __future__ import annotations

import re
from pathlib import Path

from .extract_paragraphs_common import _build_paragraphs

ATX_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})[ \t]+(.+?)\s*$")
CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
REFERENCE_LINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
STRONG_RE = re.compile(r"(\*\*|__)(.*?)\1")
EMPHASIS_RE = re.compile(r"(^|[^\w])(\*|_)([^*_]+?)\2(?=[^\w]|$)")
STRIKE_RE = re.compile(r"~~(.*?)~~")


def _strip_front_matter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return text


def _strip_markdown_inline(text: str) -> str:
    normalized = str(text or "")
    normalized = IMAGE_RE.sub(r"\1", normalized)
    normalized = LINK_RE.sub(r"\1", normalized)
    normalized = REFERENCE_LINK_RE.sub(r"\1", normalized)
    normalized = INLINE_CODE_RE.sub(r"\1", normalized)
    normalized = STRONG_RE.sub(r"\2", normalized)
    normalized = STRIKE_RE.sub(r"\1", normalized)

    while True:
        updated = EMPHASIS_RE.sub(r"\1\3", normalized)
        if updated == normalized:
            break
        normalized = updated

    normalized = re.sub(r"<(https?://[^>]+)>", r"\1", normalized)
    return normalized.strip()


def _normalize_markdown_line(line: str) -> str:
    normalized = str(line or "").rstrip()
    normalized = re.sub(r"^\s{0,3}>\s?", "", normalized)
    normalized = re.sub(r"^\s{0,3}(?:[-+*]|\d+[.)])\s+", "", normalized)
    normalized = re.sub(r"^\s{0,3}\[[ xX]\]\s+", "", normalized)

    if TABLE_SEPARATOR_RE.match(normalized):
        return ""

    if "|" in normalized:
        stripped = normalized.strip()
        if stripped.startswith("|") or stripped.endswith("|"):
            normalized = stripped.strip("|")
            normalized = re.sub(r"\s*\|\s*", " ", normalized)

    return _strip_markdown_inline(normalized)


def _flush_block(blocks: list[str], current_lines: list[str]) -> None:
    if not current_lines:
        return
    block = "\n".join(line for line in current_lines if line.strip()).strip()
    if block:
        blocks.append(block)
    current_lines.clear()


def _extract_markdown_blocks(
    text: str,
    book_title: str,
    *,
    single_section: bool = False,
) -> tuple[str, list[str]]:
    section_title = book_title.strip() or ("Full Paper" if single_section else "Full Document")
    stripped_text = _strip_front_matter(text)

    blocks: list[str] = []
    current_lines: list[str] = []
    pending_headings: list[str] = []
    in_code_fence = False
    seen_h1 = False

    for raw_line in stripped_text.splitlines():
        if CODE_FENCE_RE.match(raw_line):
            _flush_block(blocks, current_lines)
            in_code_fence = not in_code_fence
            continue

        if not in_code_fence:
            heading_match = ATX_HEADING_RE.match(raw_line)
            if heading_match:
                _flush_block(blocks, current_lines)
                heading_level = len(heading_match.group(1))
                heading_text = _strip_markdown_inline(heading_match.group(2).strip().rstrip("#").strip())
                if not heading_text:
                    continue
                if heading_level == 1 and not single_section and not seen_h1:
                    section_title = heading_text
                    seen_h1 = True
                else:
                    pending_headings.append(heading_text)
                continue

        if not raw_line.strip():
            _flush_block(blocks, current_lines)
            continue

        normalized_line = (
            raw_line.rstrip() if in_code_fence else _normalize_markdown_line(raw_line)
        )
        if not normalized_line.strip():
            continue

        if pending_headings and not current_lines:
            current_lines.extend(pending_headings)
            pending_headings.clear()
        current_lines.append(normalized_line)

    _flush_block(blocks, current_lines)
    return section_title, blocks


def _extract_from_md(
    md_path: Path,
    book_title: str,
    *,
    single_section: bool = False,
) -> list[dict[str, str | int]]:
    raw_text = md_path.read_text(encoding="utf-8-sig")
    section_title, blocks = _extract_markdown_blocks(
        raw_text,
        book_title=book_title,
        single_section=single_section,
    )
    paragraphs = _build_paragraphs(blocks, skip_numeric_prefix=False)

    records: list[dict[str, str | int]] = []
    for paragraph_index, content in enumerate(paragraphs, start=1):
        records.append(
            {
                "section_title": section_title,
                "chunk_id": f"001-{paragraph_index:04d}",
                "content": content,
                "order_index": paragraph_index - 1,
            }
        )
    return records
