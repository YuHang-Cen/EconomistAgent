"""提供章节与段落读取、软删除服务并遵守 is_deleted 过滤口径。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.models import AuthorDocument, DocumentChapter, DocumentSegment
from app.infra.db import session_scope
from fastapi import HTTPException
from sqlalchemy import select


def _now_iso() -> str:
    """返回 UTC ISO 8601 时间字符串。"""
    return datetime.now(tz=UTC).isoformat()


def _validate_author_document(author_id: str, document_id: str) -> None:
    """校验 author_id 与 document_id 归属关系。"""
    with session_scope() as session:
        document = session.get(AuthorDocument, document_id)
        if document is None or document.author_id != author_id:
            raise HTTPException(status_code=404, detail="document not found")


def list_chapters(author_id: str, document_id: str) -> list[dict[str, Any]]:
    """读取未软删除章节列表。"""
    _validate_author_document(author_id=author_id, document_id=document_id)
    with session_scope() as session:
        chapters = session.execute(
            select(DocumentChapter)
            .where(
                DocumentChapter.document_id == document_id,
                DocumentChapter.is_deleted.is_(False),
            )
            .order_by(DocumentChapter.order_index.asc())
        ).scalars()
        rows = list(chapters)

    return [
        {
            "chapterId": chapter.chapter_id,
            "documentId": chapter.document_id,
            "chapterTitle": chapter.chapter_title,
            "orderIndex": chapter.order_index,
        }
        for chapter in rows
    ]


def list_segments(author_id: str, document_id: str, chapter_id: str) -> list[dict[str, Any]]:
    """读取未软删除段落列表。"""
    _validate_author_document(author_id=author_id, document_id=document_id)
    with session_scope() as session:
        chapter = session.get(DocumentChapter, chapter_id)
        if chapter is None or chapter.document_id != document_id or chapter.is_deleted:
            raise HTTPException(status_code=404, detail="chapter not found")

        segments = session.execute(
            select(DocumentSegment)
            .where(
                DocumentSegment.document_id == document_id,
                DocumentSegment.chapter_id == chapter_id,
                DocumentSegment.is_deleted.is_(False),
            )
            .order_by(DocumentSegment.order_index.asc())
        ).scalars()
        rows = list(segments)

    return [
        {
            "segmentId": segment.segment_id,
            "documentId": segment.document_id,
            "chapterId": segment.chapter_id,
            "chunkId": segment.chunk_id,
            "content": segment.content,
            "orderIndex": segment.order_index,
        }
        for segment in rows
    ]


def delete_chapter(author_id: str, document_id: str, chapter_id: str) -> dict[str, bool]:
    """软删除章节并软删除其段落。"""
    _validate_author_document(author_id=author_id, document_id=document_id)
    with session_scope() as session:
        chapter = session.get(DocumentChapter, chapter_id)
        if chapter is None or chapter.document_id != document_id:
            raise HTTPException(status_code=404, detail="chapter not found")

        now = _now_iso()
        chapter.is_deleted = True
        chapter.deleted_at = now
        chapter.updated_at = now

        segments = session.execute(
            select(DocumentSegment).where(DocumentSegment.chapter_id == chapter_id)
        ).scalars()
        for segment in segments:
            segment.is_deleted = True
            segment.deleted_at = now
            segment.updated_at = now

    return {"deleted": True}


def delete_segment(author_id: str, document_id: str, segment_id: str) -> dict[str, bool]:
    """软删除单个段落。"""
    _validate_author_document(author_id=author_id, document_id=document_id)
    with session_scope() as session:
        segment = session.get(DocumentSegment, segment_id)
        if segment is None or segment.document_id != document_id:
            raise HTTPException(status_code=404, detail="segment not found")
        now = _now_iso()
        segment.is_deleted = True
        segment.deleted_at = now
        segment.updated_at = now
    return {"deleted": True}
