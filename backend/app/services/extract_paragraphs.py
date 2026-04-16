"""执行 document_reload 的 extract 阶段并输出章节段落结构。"""

from __future__ import annotations

from pathlib import Path


def _extract_from_pdf(pdf_path: Path) -> list[str]:
    """从本地 PDF 提取段落文本，失败时返回空列表。"""
    try:
        import fitz
    except Exception:
        return []

    paragraphs: list[str] = []
    try:
        with fitz.open(pdf_path) as document:
            for page in document:
                text = page.get_text("text").strip()
                if not text:
                    continue
                for block in text.split("\n\n"):
                    cleaned = " ".join(block.split()).strip()
                    if cleaned:
                        paragraphs.append(cleaned)
    except Exception:
        return []
    return paragraphs


def run_extract_paragraphs(book_title: str, pdf_uri: str) -> list[dict[str, str | int]]:
    """执行最小 extract 逻辑并返回标准段落结构。"""
    local_pdf = Path(pdf_uri)
    extracted_paragraphs: list[str] = []
    if local_pdf.exists() and local_pdf.suffix.lower() == ".pdf":
        extracted_paragraphs = _extract_from_pdf(local_pdf)

    if not extracted_paragraphs:
        extracted_paragraphs = [f"Auto extracted summary paragraph for {book_title}."]

    return [
        {
            "section_title": "Section 1",
            "chunk_id": index + 1,
            "content": paragraph,
            "order_index": index,
        }
        for index, paragraph in enumerate(extracted_paragraphs)
    ]
