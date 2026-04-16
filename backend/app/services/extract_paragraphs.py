"""封装文档切分阶段，负责输出章节与段落结构化数据。"""

from __future__ import annotations

from pathlib import Path


def run_extract_paragraphs(input_pdf: Path, output_json: Path) -> dict[str, str]:
    """执行 extract_paragraphs 阶段骨架逻辑。"""
    _ = (input_pdf, output_json)
    return {"stage": "extract", "status": "stub"}
