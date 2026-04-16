"""协调 author_skills、document_reload、author_answer 三类流水线任务执行。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import JobStatus, OutputType, Stage
from app.domain.models import (
    Author,
    AuthorDocument,
    AuthorSkillSnapshot,
    DocumentChapter,
    DocumentSegment,
    PipelineJob,
)
from app.services.analyze_method_chunks import run_analyze_method_chunks
from app.services.answer_with_skills import run_answer_with_skills
from app.services.extract_paragraphs import run_extract_paragraphs
from app.services.main_skill import run_main_skill
from app.services.render import run_render
from app.services.select_skills import run_select_skills
from app.services.sub_skill import run_sub_skill
from sqlalchemy import select
from sqlalchemy.orm import Session


def _now_iso() -> str:
    """返回 UTC ISO 8601 时间字符串。"""
    return datetime.now(tz=UTC).isoformat()


def _parse_outputs(outputs_json: str) -> dict[str, Any]:
    """解析 outputs_json，失败时返回空字典。"""
    try:
        parsed = json.loads(outputs_json or "{}")
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def _load_author_segments(session: Session, author_id: str) -> list[dict[str, Any]]:
    """读取作者 active 文档中未软删章节段落。"""
    documents = session.execute(
        select(AuthorDocument).where(
            AuthorDocument.author_id == author_id,
            AuthorDocument.status == "active",
        )
    ).scalars()
    document_rows = list(documents)
    if not document_rows:
        return []
    document_ids = [item.document_id for item in document_rows]

    chapters = session.execute(
        select(DocumentChapter).where(
            DocumentChapter.document_id.in_(document_ids),
            DocumentChapter.is_deleted.is_(False),
        )
    ).scalars()
    chapter_by_id = {chapter.chapter_id: chapter for chapter in chapters}

    segments = session.execute(
        select(DocumentSegment).where(
            DocumentSegment.document_id.in_(document_ids),
            DocumentSegment.is_deleted.is_(False),
        )
    ).scalars()
    segment_rows = sorted(
        list(segments),
        key=lambda item: (item.document_id, item.chapter_id, item.order_index),
    )

    result: list[dict[str, Any]] = []
    for segment in segment_rows:
        chapter = chapter_by_id.get(segment.chapter_id)
        if chapter is None:
            continue
        result.append(
            {
                "document_id": segment.document_id,
                "chapter_id": segment.chapter_id,
                "chapter_title": chapter.chapter_title,
                "chunk_id": segment.chunk_id,
                "content": segment.content,
                "order_index": segment.order_index,
            }
        )
    return result


def run_author_skills(session: Session, job: PipelineJob) -> None:
    """执行 author_skills 最小闭环并写入 author_skill_snapshots。"""
    author = session.get(Author, job.author_id)
    if author is None:
        raise ValueError("author not found for author_skills")

    job.status = JobStatus.RUNNING.value
    job.current_stage = Stage.ANALYZE.value
    job.progress = 35
    job.updated_at = _now_iso()
    session.flush()

    segments = _load_author_segments(session=session, author_id=job.author_id)
    if not segments:
        raise ValueError("no active segments found for author_skills")

    method_analysis = run_analyze_method_chunks(segments=segments)

    job.current_stage = Stage.MAIN_SKILL.value
    job.progress = 55
    job.updated_at = _now_iso()
    main_skill_json = run_main_skill(method_analysis=method_analysis)

    job.current_stage = Stage.SUB_SKILL.value
    job.progress = 70
    job.updated_at = _now_iso()
    sub_skill_json = run_sub_skill(main_skill_json=main_skill_json, method_analysis=method_analysis)

    job.current_stage = Stage.RENDER.value
    job.progress = 85
    job.updated_at = _now_iso()
    rendered = run_render(main_skill_json=main_skill_json, sub_skill_json=sub_skill_json)

    outputs = {
        OutputType.MAIN_SKILL_JSON.value: main_skill_json,
        OutputType.SUB_SKILL_JSON.value: sub_skill_json,
        OutputType.MAIN_SKILL_MD.value: rendered["main_skill_md"],
        OutputType.SUB_SKILLS_MD_ZIP.value: rendered["sub_skills_md_zip"],
    }
    snapshot_id = str(uuid.uuid4())
    now = _now_iso()

    latest_snapshots = session.execute(
        select(AuthorSkillSnapshot).where(
            AuthorSkillSnapshot.author_id == job.author_id,
            AuthorSkillSnapshot.is_latest.is_(True),
        )
    ).scalars()
    for snapshot in latest_snapshots:
        snapshot.is_latest = False

    session.add(
        AuthorSkillSnapshot(
            snapshot_id=snapshot_id,
            author_id=job.author_id,
            is_latest=True,
            outputs_json=json.dumps(outputs),
            created_at=now,
        )
    )

    job.snapshot_id = snapshot_id
    job.outputs_json = json.dumps(outputs)
    job.status = JobStatus.SUCCESS.value
    job.progress = 100
    job.updated_at = now
    job.finished_at = now


def run_author_answer(session: Session, job: PipelineJob) -> None:
    """执行 author_answer 最小闭环并产出 answer_json。"""
    if not job.query:
        raise ValueError("author_answer requires non-empty query")

    latest_snapshot = (
        session.execute(
            select(AuthorSkillSnapshot)
            .where(
                AuthorSkillSnapshot.author_id == job.author_id,
                AuthorSkillSnapshot.is_latest.is_(True),
            )
            .order_by(AuthorSkillSnapshot.created_at.desc())
        )
        .scalars()
        .first()
    )
    if latest_snapshot is None:
        raise ValueError("no latest snapshot found for author_answer")

    snapshot_outputs = _parse_outputs(latest_snapshot.outputs_json)

    job.status = JobStatus.RUNNING.value
    job.current_stage = Stage.SELECT_SKILLS.value
    job.progress = 40
    job.updated_at = _now_iso()
    selection = run_select_skills(snapshot_outputs=snapshot_outputs, query=job.query)

    job.current_stage = Stage.ANSWER.value
    job.updated_at = _now_iso()
    answer_json = run_answer_with_skills(
        query=job.query, selected=selection, snapshot_outputs=snapshot_outputs
    )

    outputs = {OutputType.ANSWER_JSON.value: answer_json}
    now = _now_iso()
    job.snapshot_id = latest_snapshot.snapshot_id
    job.outputs_json = json.dumps(outputs)
    job.status = JobStatus.SUCCESS.value
    job.progress = 100
    job.updated_at = now
    job.finished_at = now


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
