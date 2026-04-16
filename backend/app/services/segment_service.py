"""提供章节与段落读取、软删除的应用服务骨架。"""

from __future__ import annotations


def list_chapters(author_id: str, document_id: str) -> list[dict[str, str]]:
    """读取章节列表骨架数据。"""
    _ = (author_id, document_id)
    return []


def list_segments(author_id: str, document_id: str, chapter_id: str) -> list[dict[str, str]]:
    """读取段落列表骨架数据。"""
    _ = (author_id, document_id, chapter_id)
    return []


def delete_chapter(author_id: str, document_id: str, chapter_id: str) -> dict[str, bool]:
    """执行章节软删除骨架逻辑。"""
    _ = (author_id, document_id, chapter_id)
    return {"deleted": True}


def delete_segment(author_id: str, document_id: str, segment_id: str) -> dict[str, bool]:
    """执行段落软删除骨架逻辑。"""
    _ = (author_id, document_id, segment_id)
    return {"deleted": True}
