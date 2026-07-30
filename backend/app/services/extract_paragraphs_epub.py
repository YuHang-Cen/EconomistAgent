"""EPUB-specific extraction helpers for section-aware paragraph parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .extract_paragraphs_common import (
    ExtractParagraphsError,
    _build_paragraphs,
    _clean_section_title,
    _normalize_text,
)

MAIN_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百千零〇两\d]+章")

EPUB_END_MATTER_RE = re.compile(
    r"^(目录|contents|致谢|后记|代后记|注释|参考文献|版权|封面|CIP|序|序言|前言|附录|索引)\b",
    re.IGNORECASE,
)

EPUB_PART_TITLE_RE = re.compile(r"^(上篇|中篇|下篇|第[一二三四五六七八九十百千零〇两\d]+篇|part\s+\d+)", re.IGNORECASE)

EPUB_NOTE_LINK_RE = re.compile(r"(#bz\d+|#note\d+|#fn\d+)$", re.IGNORECASE)

EPUB_INLINE_NOTE_ID_RE = re.compile(r"^(z\d+|fnref\d+)$", re.IGNORECASE)

EPUB_ALLOWED_BLOCK_TAGS = {"p", "li", "blockquote", "div"}

@dataclass(frozen=True)
class EpubTocEntry:
    title: str
    href: str
    level: int

@dataclass(frozen=True)
class EpubSectionRange:
    title: str
    start_href: str
    end_href: str | None

@dataclass(frozen=True)
class EpubSpineDocument:
    href: str
    content: str

def _normalize_epub_href(href: str) -> str:
    text = unquote(str(href or "").strip())
    text = text.split("?", 1)[0].split("#", 1)[0]
    text = text.replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text

def _split_epub_href(href: str) -> tuple[str, str | None]:
    raw = unquote(str(href or "").strip()).replace("\\", "/")
    raw = raw.split("?", 1)[0]
    if "#" in raw:
        path, fragment = raw.split("#", 1)
        return _normalize_epub_href(path), fragment.strip() or None
    return _normalize_epub_href(raw), None

def _is_main_epub_chapter_title(title: str) -> bool:
    normalized = _clean_section_title(title, "")
    return bool(normalized and MAIN_CHAPTER_RE.match(normalized))

def _is_excluded_epub_title(title: str) -> bool:
    normalized = _clean_section_title(title, "")
    if not normalized:
        return True
    return bool(EPUB_END_MATTER_RE.match(normalized))

def _extract_epub_ncx_entries(book: Any) -> list[EpubTocEntry]:
    try:
        from bs4 import BeautifulSoup
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("BeautifulSoup4 is not available for EPUB extraction") from exc

    ncx_item = None
    for item in book.get_items():
        media_type = str(getattr(item, "media_type", "") or "")
        file_name = _normalize_epub_href(str(getattr(item, "file_name", "") or ""))
        if media_type == "application/x-dtbncx+xml" or file_name.endswith(".ncx"):
            ncx_item = item
            break
    if ncx_item is None:
        return []

    content = ncx_item.get_content()
    soup = BeautifulSoup(content, "xml")
    nav_map = soup.find("navMap")
    if nav_map is None:
        return []

    entries: list[EpubTocEntry] = []

    def _walk(nav_points: list[Any], level: int) -> None:
        for nav_point in nav_points:
            label = nav_point.find("navLabel", recursive=False)
            content_tag = nav_point.find("content", recursive=False)
            title = ""
            if label is not None:
                text_tag = label.find("text")
                title = _clean_section_title(text_tag.get_text(" ", strip=True) if text_tag else "", "")
            href = _clean_section_title(content_tag.get("src") if content_tag else "", "")
            if title and href:
                entries.append(EpubTocEntry(title=title, href=href, level=level))
            children = nav_point.find_all("navPoint", recursive=False)
            if children:
                _walk(children, level + 1)

    _walk(nav_map.find_all("navPoint", recursive=False), 0)
    return entries

def _toc_entry_from_object(node: Any, level: int) -> EpubTocEntry | None:
    title = _clean_section_title(getattr(node, "title", ""), "")
    href = _clean_section_title(getattr(node, "href", ""), "")
    if not href:
        href = _clean_section_title(getattr(node, "file_name", ""), "")
    if not href:
        get_name = getattr(node, "get_name", None)
        if callable(get_name):
            href = _clean_section_title(get_name(), "")
    if title and href:
        return EpubTocEntry(title=title, href=href, level=level)
    return None

def _flatten_ebooklib_toc(nodes: Any, level: int = 0) -> list[EpubTocEntry]:
    entries: list[EpubTocEntry] = []
    if not isinstance(nodes, (list, tuple)):
        nodes = [nodes]

    for node in nodes:
        if isinstance(node, tuple) and len(node) == 2 and isinstance(node[1], (list, tuple)):
            entry = _toc_entry_from_object(node[0], level)
            if entry is not None:
                entries.append(entry)
            entries.extend(_flatten_ebooklib_toc(node[1], level + 1))
            continue
        if isinstance(node, list):
            entries.extend(_flatten_ebooklib_toc(node, level))
            continue
        entry = _toc_entry_from_object(node, level)
        if entry is not None:
            entries.append(entry)
    return entries

def _extract_epub_toc_entries(book: Any) -> list[EpubTocEntry]:
    entries = _extract_epub_ncx_entries(book)
    if entries:
        return entries
    return _flatten_ebooklib_toc(getattr(book, "toc", []))

def _get_epub_spine_documents(book: Any) -> list[EpubSpineDocument]:
    try:
        import ebooklib
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("ebooklib is not available for EPUB extraction") from exc

    documents: list[EpubSpineDocument] = []
    for entry in getattr(book, "spine", []):
        item_id = entry[0] if isinstance(entry, (list, tuple)) and entry else entry
        item = book.get_item_with_id(item_id)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        href = _normalize_epub_href(str(getattr(item, "file_name", "") or ""))
        if not href:
            continue
        content = item.get_content().decode("utf-8", errors="ignore")
        documents.append(EpubSpineDocument(href=href, content=content))
    return documents

def _fallback_epub_chapter_entries(spine_documents: list[EpubSpineDocument]) -> list[EpubTocEntry]:
    try:
        from bs4 import BeautifulSoup
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("BeautifulSoup4 is not available for EPUB extraction") from exc

    entries: list[EpubTocEntry] = []
    for document in spine_documents:
        soup = BeautifulSoup(document.content, "html.parser")
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            title = _normalize_text(heading.get_text(" ", strip=True))
            if _is_main_epub_chapter_title(title) and not _is_excluded_epub_title(title):
                entries.append(EpubTocEntry(title=title, href=document.href, level=0))
                break
    return entries

def _build_epub_section_ranges(toc_entries: list[EpubTocEntry]) -> list[EpubSectionRange]:
    sections: list[EpubSectionRange] = []
    for idx, entry in enumerate(toc_entries):
        title = _normalize_text(entry.title)
        if not _is_main_epub_chapter_title(title):
            continue
        if _is_excluded_epub_title(title):
            continue

        end_href: str | None = None
        for candidate in toc_entries[idx + 1 :]:
            if candidate.level <= entry.level:
                end_href = candidate.href
                break

        sections.append(EpubSectionRange(title=title, start_href=entry.href, end_href=end_href))
    return sections

def _find_spine_index(href: str, spine_lookup: dict[str, int]) -> int | None:
    normalized = _normalize_epub_href(href)
    if normalized in spine_lookup:
        return spine_lookup[normalized]
    basename = normalized.rsplit("/", 1)[-1]
    for key, value in spine_lookup.items():
        if key.rsplit("/", 1)[-1] == basename:
            return value
    return None

def _find_epub_anchor(soup: Any, fragment: str | None) -> Any | None:
    if not fragment:
        return None
    anchor = soup.find(id=fragment)
    if anchor is not None:
        return anchor
    return soup.find(attrs={"name": fragment})

def _should_collect_epub_tag(tag: Any) -> bool:
    if tag.name not in EPUB_ALLOWED_BLOCK_TAGS:
        return False
    if tag.name == "div":
        if tag.find(["p", "li", "blockquote", "div"], recursive=False):
            return False
        if tag.find(["img", "svg", "table", "figure"]):
            return False
    parent = tag.parent
    while parent is not None:
        if getattr(parent, "name", None) in EPUB_ALLOWED_BLOCK_TAGS:
            return False
        parent = parent.parent
    return True

def _clean_epub_block_text(tag: Any) -> str:
    try:
        from bs4 import BeautifulSoup
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("BeautifulSoup4 is not available for EPUB extraction") from exc

    fragment = BeautifulSoup(str(tag), "html.parser")
    for noisy in fragment.find_all(["img", "svg", "style", "script"]):
        noisy.decompose()
    for anchor in fragment.find_all("a"):
        href = str(anchor.get("href", "") or "")
        anchor_id = str(anchor.get("id", "") or "")
        text = anchor.get_text(" ", strip=True)
        if EPUB_NOTE_LINK_RE.search(href) or EPUB_INLINE_NOTE_ID_RE.match(anchor_id) or text.isdigit():
            anchor.decompose()
    text = _normalize_text(fragment.get_text(" ", strip=True))
    return text

def _extract_epub_blocks_between(content: str, start_anchor: str | None, end_anchor: str | None) -> list[str]:
    try:
        from bs4 import BeautifulSoup, Tag
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("BeautifulSoup4 is not available for EPUB extraction") from exc

    soup = BeautifulSoup(content, "html.parser")
    body = soup.body or soup
    start_tag = _find_epub_anchor(body, start_anchor)
    end_tag = _find_epub_anchor(body, end_anchor)

    started = start_tag is None
    blocks: list[str] = []
    for node in body.descendants:
        if node is end_tag:
            break
        if not started:
            if node is start_tag:
                started = True
            continue
        if not isinstance(node, Tag):
            continue
        if not _should_collect_epub_tag(node):
            continue
        text = _clean_epub_block_text(node)
        if text:
            blocks.append(text)
    return blocks

def _extract_from_epub(
    epub_path: Path,
    book_title: str,
    *,
    single_section: bool = False,
) -> list[dict[str, Any]]:
    try:
        from ebooklib import epub
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("ebooklib is not available for EPUB extraction") from exc

    try:
        book = epub.read_epub(str(epub_path))
    except Exception as exc:
        raise ExtractParagraphsError(f"failed to parse EPUB file: {epub_path}") from exc

    spine_documents = _get_epub_spine_documents(book)
    if not spine_documents:
        return []

    if single_section:
        blocks: list[str] = []
        for document in spine_documents:
            blocks.extend(
                _extract_epub_blocks_between(
                    content=document.content,
                    start_anchor=None,
                    end_anchor=None,
                )
            )

        paragraphs = _build_paragraphs(blocks, skip_numeric_prefix=False)
        records: list[dict[str, Any]] = []
        section_title = book_title.strip() or "Full Paper"
        for paragraph_idx, content in enumerate(paragraphs, start=1):
            records.append(
                {
                    "section_title": section_title,
                    "chunk_id": f"001-{paragraph_idx:04d}",
                    "content": content,
                    "order_index": paragraph_idx - 1,
                }
            )
        return records

    toc_entries = _extract_epub_toc_entries(book)
    section_ranges = _build_epub_section_ranges(toc_entries)
    if not section_ranges:
        fallback_entries = _fallback_epub_chapter_entries(spine_documents)
        section_ranges = _build_epub_section_ranges(fallback_entries)

    if not section_ranges:
        return []

    spine_lookup = {document.href: idx for idx, document in enumerate(spine_documents)}
    records: list[dict[str, Any]] = []
    order_index = 0

    for section_idx, section in enumerate(section_ranges, start=1):
        start_href, start_anchor = _split_epub_href(section.start_href)
        start_index = _find_spine_index(start_href, spine_lookup)
        if start_index is None:
            continue

        if section.end_href is None:
            boundary_index = len(spine_documents)
            boundary_anchor = None
        else:
            boundary_href, boundary_anchor = _split_epub_href(section.end_href)
            found_boundary = _find_spine_index(boundary_href, spine_lookup)
            if found_boundary is None:
                boundary_index = len(spine_documents)
                boundary_anchor = None
            else:
                boundary_index = found_boundary

        blocks: list[str] = []
        for doc_index in range(start_index, len(spine_documents)):
            if doc_index > boundary_index:
                break
            if doc_index == boundary_index and boundary_anchor is None:
                break

            document = spine_documents[doc_index]
            blocks.extend(
                _extract_epub_blocks_between(
                    content=document.content,
                    start_anchor=start_anchor if doc_index == start_index else None,
                    end_anchor=boundary_anchor if doc_index == boundary_index else None,
                )
            )

            if doc_index == boundary_index:
                break

        paragraphs = _build_paragraphs(blocks, skip_numeric_prefix=False)
        for paragraph_idx, content in enumerate(paragraphs, start=1):
            records.append(
                {
                    "section_title": section.title,
                    "chunk_id": f"{section_idx:03d}-{paragraph_idx:04d}",
                    "content": content,
                    "order_index": order_index,
                }
            )
            order_index += 1

    return records
