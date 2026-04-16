"""协调 author_skills、document_reload、author_answer 三类流水线任务执行。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import JobStatus, Stage
from app.domain.models import AuthorDocument, DocumentChapter, DocumentSegment, PipelineJob
from app.services.extract_paragraphs import run_extract_paragraphs
from sqlalchemy import select
from sqlalchemy.orm import Session


def _now_iso() -> str:
    """返回 UTC ISO 8601 时间字符串。"""
    return datetime.now(tz=UTC).isoformat()


def run_author_skills(job_id: str) -> dict[str, str]:
    """执行作者技能流水线占位逻辑。"""
    return {"jobId": job_id, "pipeline": "author_skills"}


def run_author_answer(job_id: str) -> dict[str, str]:
    """执行作者问答流水线占位逻辑。"""
    return {"jobId": job_id, "pipeline": "author_answer"}


def _upsert_chapters_and_segments(
    session: Session, document_id: str, extracted_rows: list[dict[str, Any]]
) -> None:
    """执行 segment_sync：按章节与 chunk_id 写入段落并保留软删除约束。"""
    existing_chapters = session.execute(
        select(DocumentChapter).where(DocumentChapter.document_id == document_id)
    ).scalars()
    chapter_by_title = {chapter.chapter_title: chapter for chapter in existing_chapters}

    skip_chapter_titles: set[str] = set()
    chapter_id_by_title: dict[str, str] = {}

    section_titles: list[str] = []
    for row in extracted_rows:
        section_title = str(row["section_title"])
        if section_title not in section_titles:
            section_titles.append(section_title)

    for order_index, section_title in enumerate(section_titles):
        existing = chapter_by_title.get(section_title)
        now = _now_iso()
        if existing:
            if existing.is_deleted:
                skip_chapter_titles.add(section_title)
                continue
            existing.order_index = order_index
            existing.updated_at = now
            chapter_id_by_title[section_title] = existing.chapter_id
            continue

        chapter = DocumentChapter(
            chapter_id=str(uuid.uuid4()),
            document_id=document_id,
            chapter_title=section_title,
            order_index=order_index,
            is_deleted=False,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(chapter)
        chapter_id_by_title[section_title] = chapter.chapter_id

    existing_segments = session.execute(
        select(DocumentSegment).where(DocumentSegment.document_id == document_id)
    ).scalars()
    segment_by_chunk = {segment.chunk_id: segment for segment in existing_segments}

    for row in extracted_rows:
        section_title = str(row["section_title"])
        if section_title in skip_chapter_titles:
            continue
        chapter_id = chapter_id_by_title.get(section_title)
        if not chapter_id:
            continue

        chunk_id = str(row["chunk_id"])
        content = str(row["content"])
        order_index = int(row["order_index"])
        existing_segment = segment_by_chunk.get(chunk_id)
        now = _now_iso()

        if existing_segment:
            if existing_segment.is_deleted:
                continue
            existing_segment.chapter_id = chapter_id
            existing_segment.content = content
            existing_segment.order_index = order_index
            existing_segment.updated_at = now
            continue

        session.add(
            DocumentSegment(
                segment_id=str(uuid.uuid4()),
                document_id=document_id,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                content=content,
                order_index=order_index,
                is_deleted=False,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
        )


def run_document_reload(session: Session, job: PipelineJob) -> None:
    """执行最小 document_reload 链路：extract -> segment_sync。"""
    if not job.document_id:
        raise ValueError("document_reload requires document_id")

    document = session.get(AuthorDocument, job.document_id)
    if document is None:
        raise ValueError("document not found for document_reload")

    now = _now_iso()
    job.status = JobStatus.RUNNING.value
    job.current_stage = Stage.EXTRACT.value
    job.progress = 60
    job.updated_at = now
    document.status = "processing"
    document.updated_at = now
    session.flush()

    extracted_rows = run_extract_paragraphs(
        book_title=document.book_title, pdf_uri=document.pdf_uri
    )
    job.current_stage = Stage.SEGMENT_SYNC.value
    job.updated_at = _now_iso()
    _upsert_chapters_and_segments(
        session=session, document_id=document.document_id, extracted_rows=extracted_rows
    )

    job.status = JobStatus.SUCCESS.value
    job.progress = 100
    job.finished_at = _now_iso()
    job.updated_at = job.finished_at
    job.outputs_json = json.dumps({"segmentSyncRows": len(extracted_rows)})
    document.status = "active"
    document.updated_at = _now_iso()
