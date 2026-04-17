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
from app.infra import storage
from app.services.analyze_method_chunks import run_analyze_method_chunks
from app.services.answer_with_skills import run_answer_with_skills
from app.services.extract_paragraphs import run_extract_paragraphs
from app.services.main_skill import run_main_skill
from app.services.render import run_render
from app.services.select_skills import run_select_skills
from app.services.sub_skill import run_sub_skill
from sqlalchemy import select
from sqlalchemy.orm import Session


class PipelineCanceledError(RuntimeError):
    """表示任务在阶段边界被取消。"""


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


def _read_uri_content(uri: str) -> Any:
    """根据 URI 读取 JSON 或文本内容。"""
    path = storage.resolve_storage_uri(uri)
    if not path.exists():
        return None
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


def _ensure_not_canceled(session: Session, job: PipelineJob) -> None:
    """在阶段边界检查任务是否已取消。"""
    session.refresh(job, attribute_names=["status"])
    if job.status == JobStatus.CANCELED.value:
        raise PipelineCanceledError("job canceled")


def _persist_stage_progress(session: Session, job: PipelineJob, stage: Stage, progress: int) -> None:
    """Persist stage updates immediately so polling APIs can observe live progress."""
    job.status = JobStatus.RUNNING.value
    job.current_stage = stage.value
    job.progress = progress
    job.updated_at = _now_iso()
    session.flush()
    session.commit()


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


def _store_author_skill_artifacts(
    author_id: str,
    snapshot_id: str,
    method_analysis: dict[str, Any],
    main_skill_json: dict[str, Any],
    sub_skill_json: dict[str, Any],
    rendered: dict[str, Any],
) -> dict[str, str]:
    """落盘作者快照产物并返回 artifact_type -> uri。"""
    snapshot_dir = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)
    method_analysis_json_uri = storage.write_json(
        snapshot_dir / "method_analysis.json", method_analysis
    )
    main_skill_json_uri = storage.write_json(snapshot_dir / "main_skill.json", main_skill_json)
    sub_skill_json_uri = storage.write_json(snapshot_dir / "sub_skill.json", sub_skill_json)
    main_skill_md_uri = storage.write_text(
        snapshot_dir / "main_skill.md", rendered["main_skill_md"]
    )

    sub_skill_files = rendered.get("sub_skill_files", [])
    zip_files: list[tuple[str, str]] = []
    if isinstance(sub_skill_files, list):
        for item in sub_skill_files:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            content = item.get("content")
            if isinstance(name, str) and isinstance(content, str):
                zip_files.append((name, content))
    sub_skills_md_zip_uri = storage.write_zip_from_files(
        snapshot_dir / "sub_skills_md.zip", zip_files
    )

    return {
        OutputType.METHOD_ANALYSIS_JSON.value: method_analysis_json_uri,
        OutputType.MAIN_SKILL_JSON.value: main_skill_json_uri,
        OutputType.SUB_SKILL_JSON.value: sub_skill_json_uri,
        OutputType.MAIN_SKILL_MD.value: main_skill_md_uri,
        OutputType.SUB_SKILLS_MD_ZIP.value: sub_skills_md_zip_uri,
    }


def _store_answer_artifact(
    author_id: str, job_id: str, answer_json: dict[str, Any]
) -> dict[str, str]:
    """落盘作者问答产物并返回 artifact_type -> uri。"""
    answer_dir = storage.answer_root(author_id=author_id, job_id=job_id)
    answer_json_uri = storage.write_json(answer_dir / "answer.json", answer_json)
    return {OutputType.ANSWER_JSON.value: answer_json_uri}


def run_author_skills(session: Session, job: PipelineJob) -> None:
    """执行 author_skills 闭环并写入 author_skill_snapshots。"""
    author = session.get(Author, job.author_id)
    if author is None:
        raise ValueError("author not found for author_skills")

    _persist_stage_progress(session=session, job=job, stage=Stage.ANALYZE, progress=35)
    _ensure_not_canceled(session, job)

    segments = _load_author_segments(session=session, author_id=job.author_id)
    if not segments:
        raise ValueError("no active segments found for author_skills")
    method_analysis = run_analyze_method_chunks(segments=segments)

    _ensure_not_canceled(session, job)
    _persist_stage_progress(session=session, job=job, stage=Stage.MAIN_SKILL, progress=55)
    main_skill_json = run_main_skill(method_analysis=method_analysis)

    _ensure_not_canceled(session, job)
    _persist_stage_progress(session=session, job=job, stage=Stage.SUB_SKILL, progress=70)
    sub_skill_json = run_sub_skill(main_skill_json=main_skill_json, method_analysis=method_analysis)

    _ensure_not_canceled(session, job)
    _persist_stage_progress(session=session, job=job, stage=Stage.RENDER, progress=85)
    rendered = run_render(main_skill_json=main_skill_json, sub_skill_json=sub_skill_json)

    _ensure_not_canceled(session, job)
    snapshot_id = str(uuid.uuid4())
    outputs = _store_author_skill_artifacts(
        author_id=job.author_id,
        snapshot_id=snapshot_id,
        method_analysis=method_analysis,
        main_skill_json=main_skill_json,
        sub_skill_json=sub_skill_json,
        rendered=rendered,
    )
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
    session.flush()
    session.commit()


def run_author_answer(session: Session, job: PipelineJob) -> None:
    """执行 author_answer 闭环并产出 answer_json。"""
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

    snapshot_output_uris = _parse_outputs(latest_snapshot.outputs_json)
    main_skill_uri = snapshot_output_uris.get(OutputType.MAIN_SKILL_JSON.value)
    sub_skill_uri = snapshot_output_uris.get(OutputType.SUB_SKILL_JSON.value)
    if not isinstance(main_skill_uri, str) or not isinstance(sub_skill_uri, str):
        raise ValueError("snapshot outputs missing main/sub skill uri")

    main_skill_json = _read_uri_content(main_skill_uri)
    sub_skill_json = _read_uri_content(sub_skill_uri)
    if not isinstance(main_skill_json, dict) or not isinstance(sub_skill_json, dict):
        raise ValueError("snapshot artifacts unreadable")
    snapshot_outputs = {
        OutputType.MAIN_SKILL_JSON.value: main_skill_json,
        OutputType.SUB_SKILL_JSON.value: sub_skill_json,
    }

    job.status = JobStatus.RUNNING.value
    job.current_stage = Stage.SELECT_SKILLS.value
    job.progress = 40
    job.updated_at = _now_iso()
    session.flush()
    _ensure_not_canceled(session, job)

    selection = run_select_skills(snapshot_outputs=snapshot_outputs, query=job.query)
    if not selection.get("selected_main_skill_id"):
        raise ValueError("no available skill selected for author_answer")

    _ensure_not_canceled(session, job)
    job.current_stage = Stage.ANSWER.value
    job.updated_at = _now_iso()
    answer_json = run_answer_with_skills(
        query=job.query,
        selected=selection,
        snapshot_outputs=snapshot_outputs,
    )

    outputs = _store_answer_artifact(
        author_id=job.author_id, job_id=job.job_id, answer_json=answer_json
    )
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
    """执行 document_reload 链路：extract -> segment_sync。"""
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
    _ensure_not_canceled(session, job)

    extracted_rows = run_extract_paragraphs(
        book_title=document.book_title, pdf_uri=document.pdf_uri
    )

    _ensure_not_canceled(session, job)
    job.current_stage = Stage.SEGMENT_SYNC.value
    job.updated_at = _now_iso()
    _upsert_chapters_and_segments(
        session=session,
        document_id=document.document_id,
        extracted_rows=extracted_rows,
    )

    report_uri = storage.write_json(
        storage.job_root(author_id=job.author_id, job_id=job.job_id)
        / "document_reload_report.json",
        {"segmentSyncRows": len(extracted_rows)},
    )
    now = _now_iso()
    job.status = JobStatus.SUCCESS.value
    job.progress = 100
    job.finished_at = now
    job.updated_at = now
    job.outputs_json = json.dumps({"document_reload_report": report_uri})
    document.status = "active"
    document.updated_at = now
