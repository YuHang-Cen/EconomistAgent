"""Document extract stage: parse PDF into section-aware paragraph rows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOC_MARKERS = ("contents", "table of contents", "目录")
TOC_LINE_PATTERNS = (
    re.compile(r"^(?P<title>.+?)\s+\.{2,}\s*(?P<page>\d+)\s*$"),
    re.compile(r"^(?P<title>.+?)\s+(?P<page>\d+)\s*$"),
)
RULE_SECTION_PATTERNS = (
    re.compile(r"^Chapter\s+\d+", re.IGNORECASE),
    re.compile(r"^Part\s+\d+", re.IGNORECASE),
    re.compile(r"^\d+\.\s+"),
    re.compile(r"^[IVX]+\.\s+", re.IGNORECASE),
)

SENTENCE_END_RE = re.compile(r'[.!?…]["\')\]]*$')
CONTINUATION_START_RE = re.compile(
    r"^(and|or|but|nor|for|yet|so|because|however|therefore|thus|then|while|when|which|that|who|whom|whose)\b",
    re.IGNORECASE,
)

HEADER_FOOTER_MAX_WORDS = 12


class ExtractParagraphsError(RuntimeError):
    """Raised when document extraction cannot produce valid segments."""


@dataclass
class TextLine:
    page_num: int
    y0: float
    y1: float
    x0: float
    x1: float
    text: str
    avg_size: float


@dataclass(frozen=True)
class SectionHint:
    title: str
    start_page: int  # 1-based


@dataclass(frozen=True)
class SectionRange:
    title: str
    start_page: int  # 1-based, inclusive
    end_page: int  # 1-based, inclusive


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clean_section_title(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return fallback


def _dedupe_and_sort_sections(sections: list[SectionHint]) -> list[SectionHint]:
    seen_pages: set[int] = set()
    deduped: list[SectionHint] = []
    for section in sorted(sections, key=lambda item: item.start_page):
        if section.start_page in seen_pages:
            continue
        seen_pages.add(section.start_page)
        deduped.append(section)
    return deduped


def _extract_outline_sections(doc: Any) -> list[SectionHint]:
    toc = doc.get_toc(simple=True)
    if not toc:
        return []

    sections: list[SectionHint] = []
    for item in toc:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        title = _clean_section_title(item[1], "")
        try:
            start_page = int(item[2])
        except (TypeError, ValueError):
            continue
        if start_page <= 0 or not title:
            continue
        sections.append(SectionHint(title=title, start_page=start_page))
    return sections


def _extract_toc_sections_from_text(doc: Any) -> list[SectionHint]:
    toc_pages: list[str] = []
    for page in doc:
        text = page.get_text("text") or ""
        if any(marker in text.lower() for marker in TOC_MARKERS):
            toc_pages.append(text)
    if not toc_pages:
        return []

    sections: list[SectionHint] = []
    for page_text in toc_pages:
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            for pattern in TOC_LINE_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue
                title = _clean_section_title(match.group("title").strip(" .\t"), "")
                page_raw = match.group("page")
                if not page_raw.isdigit():
                    continue
                start_page = int(page_raw)
                if start_page <= 0 or not title:
                    continue
                sections.append(SectionHint(title=title, start_page=start_page))
                break
    return sections


def _extract_rule_sections(doc: Any) -> list[SectionHint]:
    sections: list[SectionHint] = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:6]:
            if any(pattern.match(line) for pattern in RULE_SECTION_PATTERNS):
                sections.append(SectionHint(title=line, start_page=page_num))
                break
    return sections


def _detect_sections(doc: Any) -> list[SectionHint]:
    outline_sections = _dedupe_and_sort_sections(_extract_outline_sections(doc))
    if outline_sections:
        return outline_sections

    toc_sections = _dedupe_and_sort_sections(_extract_toc_sections_from_text(doc))
    if toc_sections:
        return toc_sections

    rule_sections = _dedupe_and_sort_sections(_extract_rule_sections(doc))
    if rule_sections:
        return rule_sections

    return [SectionHint(title="Full Book", start_page=1)]


def _build_section_ranges(section_hints: list[SectionHint], total_pages: int) -> list[SectionRange]:
    valid_hints = [
        SectionHint(
            title=_clean_section_title(hint.title, f"Section {hint.start_page}"),
            start_page=hint.start_page,
        )
        for hint in section_hints
        if 1 <= hint.start_page <= total_pages
    ]
    valid_hints = _dedupe_and_sort_sections(valid_hints)
    if not valid_hints:
        valid_hints = [SectionHint(title="Full Book", start_page=1)]

    if valid_hints[0].start_page > 1:
        valid_hints = [SectionHint(title="Front Matter", start_page=1), *valid_hints]

    ranges: list[SectionRange] = []
    for idx, hint in enumerate(valid_hints):
        if hint.start_page > total_pages:
            continue
        next_start = valid_hints[idx + 1].start_page if idx + 1 < len(valid_hints) else total_pages + 1
        end_page = min(total_pages, max(hint.start_page, next_start - 1))
        if end_page < hint.start_page:
            continue
        ranges.append(
            SectionRange(
                title=hint.title,
                start_page=hint.start_page,
                end_page=end_page,
            )
        )
    return ranges


def _char_is_superscript(
    ch_bbox: tuple[float, float, float, float],
    prev_bbox: tuple[float, float, float, float] | None,
    line_bbox: tuple[float, float, float, float],
    line_avg_size: float,
    ch_size: float,
) -> bool:
    if prev_bbox is None:
        return False

    ch_x0, ch_y0, ch_x1, ch_y1 = ch_bbox
    _, prev_y0, prev_x1, _ = prev_bbox
    line_y0, line_y1 = line_bbox[1], line_bbox[3]

    smaller = ch_size <= line_avg_size * 0.8
    raised = ch_y0 < prev_y0 - max(0.5, line_avg_size * 0.08)
    close_to_prev = (ch_x0 - prev_x1) <= max(2.5, line_avg_size * 0.25)
    upper_half = ch_y1 <= line_y0 + (line_y1 - line_y0) * 0.75

    return smaller and raised and close_to_prev and upper_half


def _clean_inline_footnotes(text: str) -> str:
    text = re.sub(r'([.!?…]["\')\]]*)\d+\b', r"\1", text)
    text = re.sub(r'([,;:]["\')\]]*)\d+\b', r"\1", text)
    return text


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\s+\n", "\n", normalized)
    normalized = re.sub(r"\n\s+", "\n", normalized)
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"([(\[\"'])\s+", r"\1", normalized)
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
    if re.fullmatch(r"[\dIVXLCDMivxlcdm\s\-–—]+", stripped) and len(stripped) <= 12:
        return True
    if re.fullmatch(r"\d+\s*[–—-]\s*[A-Za-z .~`'’]{1,80}", stripped):
        return True
    return False


def _starts_with_number(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0].isdigit()


def _looks_like_header_or_footer(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True

    words = stripped.split()
    if len(words) > HEADER_FOOTER_MAX_WORDS:
        return False
    if re.fullmatch(r"\(?\d+\)?", stripped):
        return True
    if re.fullmatch(r"[IVXLCDMivxlcdm]+", stripped):
        return True
    return False


def _should_merge(prev_para: str, curr_para: str) -> bool:
    prev = prev_para.rstrip()
    curr = curr_para.lstrip()
    if not prev or not curr:
        return False
    if prev.endswith("-"):
        return True
    if prev.endswith(("(", '"', "'", "“", "‘", ":", ";", ",")):
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


def _estimate_indent(line: TextLine, body_left_x: float) -> float:
    return line.x0 - body_left_x


def _extract_lines_from_page(page: Any, page_num: int) -> list[TextLine]:
    raw = page.get_text("rawdict", sort=True)
    lines: list[TextLine] = []

    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_bbox = tuple(line.get("bbox", (0, 0, 0, 0)))
            spans = line.get("spans", [])
            if not spans:
                continue

            span_sizes = [_safe_float(span.get("size", 0.0), 0.0) for span in spans if span.get("size")]
            line_avg_size = sum(span_sizes) / len(span_sizes) if span_sizes else 0.0

            chars: list[tuple[str, tuple[float, float, float, float], float]] = []
            for span in spans:
                span_size = _safe_float(span.get("size", line_avg_size), line_avg_size)
                span_text = span.get("text", "")
                span_chars = span.get("chars")
                if span_chars:
                    for ch in span_chars:
                        c = ch.get("c", "")
                        bbox = tuple(ch.get("bbox", (0, 0, 0, 0)))
                        chars.append((c, bbox, span_size))
                else:
                    span_bbox = tuple(span.get("bbox", (0, 0, 0, 0)))
                    for c in span_text:
                        chars.append((c, span_bbox, span_size))

            if not chars:
                continue

            chars.sort(key=lambda item: (item[1][0], item[1][1]))
            kept_chars: list[str] = []
            prev_bbox: tuple[float, float, float, float] | None = None
            prev_char: str | None = None

            for c, bbox, ch_size in chars:
                if not c:
                    continue
                if c.isdigit():
                    prev_is_attachable = prev_char is not None and prev_char not in {" ", "\t", "\n"}
                    if prev_is_attachable and _char_is_superscript(
                        ch_bbox=bbox,
                        prev_bbox=prev_bbox,
                        line_bbox=line_bbox,
                        line_avg_size=max(line_avg_size, ch_size),
                        ch_size=ch_size,
                    ):
                        continue

                kept_chars.append(c)
                prev_bbox = bbox
                prev_char = c

            text = _normalize_text("".join(kept_chars))
            if not text:
                continue

            lines.append(
                TextLine(
                    page_num=page_num,
                    y0=_safe_float(line_bbox[1]),
                    y1=_safe_float(line_bbox[3]),
                    x0=_safe_float(line_bbox[0]),
                    x1=_safe_float(line_bbox[2]),
                    text=text,
                    avg_size=max(line_avg_size, 0.1),
                )
            )

    return lines


def _group_lines_to_blocks(lines: list[TextLine]) -> list[str]:
    if not lines:
        return []

    filtered = [ln for ln in lines if not _looks_like_header_or_footer(ln.text)]
    if not filtered:
        filtered = lines
    filtered.sort(key=lambda ln: (ln.page_num, ln.y0, ln.x0))

    body_left_x = min(ln.x0 for ln in filtered)
    blocks: list[str] = []
    current_lines: list[TextLine] = [filtered[0]]

    for prev, curr in zip(filtered, filtered[1:]):
        new_block = False

        if curr.page_num != prev.page_num:
            new_block = True
        else:
            gap = curr.y0 - prev.y1
            line_height = prev.y1 - prev.y0
            page_right_x = max(ln.x1 for ln in filtered)

            prev_indent = _estimate_indent(prev, body_left_x)
            curr_indent = _estimate_indent(curr, body_left_x)
            indent_diff = abs(curr_indent - prev_indent)

            if gap > line_height:
                new_block = True
            elif indent_diff > max(prev.avg_size * 0.8, 8.0):
                new_block = True
            elif prev.x1 < page_right_x * 0.95 and (curr.text[:1].isupper() or curr.text[:1].isdigit()):
                new_block = True
            elif SENTENCE_END_RE.search(prev.text) and not curr.text[:1].islower():
                if curr_indent > max(6.0, prev.avg_size * 0.6):
                    new_block = True

        if new_block:
            block_text = _normalize_text(" ".join(ln.text for ln in current_lines))
            if block_text:
                blocks.append(block_text)
            current_lines = [curr]
        else:
            current_lines.append(curr)

    if current_lines:
        block_text = _normalize_text(" ".join(ln.text for ln in current_lines))
        if block_text:
            blocks.append(block_text)

    return blocks


def _extract_text_blocks_from_doc(doc: Any, start_page: int, end_page: int) -> list[str]:
    all_blocks: list[str] = []
    if start_page < 1 or end_page < start_page:
        return all_blocks

    for page_num in range(start_page, end_page + 1):
        page = doc.load_page(page_num - 1)
        lines = _extract_lines_from_page(page, page_num)
        all_blocks.extend(_group_lines_to_blocks(lines))

    return [blk for blk in all_blocks if blk.strip()]


def _build_paragraphs(blocks: list[str]) -> list[str]:
    paragraphs: list[str] = []
    for block in blocks:
        paragraph = _normalize_text(block)
        if _is_noise_paragraph(paragraph):
            continue
        if _starts_with_number(paragraph):
            continue
        if paragraphs and _should_merge(paragraphs[-1], paragraph):
            paragraphs[-1] = _merge_paragraph(paragraphs[-1], paragraph)
        else:
            paragraphs.append(paragraph)
    return paragraphs


def _extract_from_pdf(pdf_path: Path, book_title: str) -> list[dict[str, Any]]:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover
        raise ExtractParagraphsError("PyMuPDF (fitz) is not available for PDF extraction") from exc

    records: list[dict[str, Any]] = []

    try:
        doc = fitz.open(pdf_path)
        try:
            section_hints = _detect_sections(doc)
            section_ranges = _build_section_ranges(section_hints, doc.page_count)

            order_index = 0
            for section_idx, section in enumerate(section_ranges, start=1):
                blocks = _extract_text_blocks_from_doc(
                    doc=doc,
                    start_page=section.start_page,
                    end_page=section.end_page,
                )
                paragraphs = _build_paragraphs(blocks)

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
        finally:
            doc.close()
    except ExtractParagraphsError:
        raise
    except Exception as exc:
        raise ExtractParagraphsError(f"failed to parse PDF file: {pdf_path}") from exc

    return records


def run_extract_paragraphs(book_title: str, pdf_uri: str) -> list[dict[str, Any]]:
    """Run extract stage and return normalized section/paragraph rows."""
    pdf_path = Path(pdf_uri)

    if not pdf_path.exists():
        raise ExtractParagraphsError(f"pdf path does not exist: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ExtractParagraphsError(f"pdf path must end with .pdf: {pdf_path}")

    extracted = _extract_from_pdf(pdf_path=pdf_path, book_title=book_title)
    if not extracted:
        raise ExtractParagraphsError(f"no extractable segments found in pdf: {pdf_path}")

    return extracted