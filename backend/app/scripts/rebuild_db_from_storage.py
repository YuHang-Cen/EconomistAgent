"""Rebuild SQLite DB from `storage/authors/...` manifests and artifacts.

This is a manual recovery tool for when `storage/app.db` is lost but the storage
directory still exists.
"""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.enums import JobStatus, JobType, OutputType, Stage
from app.domain.models import (
    Author,
    AuthorDocument,
    AuthorSkillSnapshot,
    DocumentChapter,
    DocumentSegment,
    PipelineJob,
)
from app.infra import storage
from app.infra.db import session_scope
from sqlalchemy import delete, func, select


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _safe_load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _to_storage_uri(path: Path, storage_root: Path) -> str:
    """Mimic `app.infra.storage._to_storage_uri` without importing private API."""
    resolved = path.resolve()
    root = storage_root.resolve()
    relative = resolved.relative_to(root.parent)
    return relative.as_posix()


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _recovered_skills_job_id(author_id: str, snapshot_id: str) -> str:
    """Build a deterministic synthetic job id for recovered author_skills snapshots."""
    seed = f"rebuild-author-skills:{author_id}:{snapshot_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _pick_answer_generated_at(answer_json: dict[str, Any], fallback: str) -> str:
    generated_at = answer_json.get("generated_at")
    if isinstance(generated_at, str) and generated_at.strip():
        candidate = generated_at.strip()
        if _parse_iso(candidate) is not None:
            return candidate
    generated_at_camel = answer_json.get("generatedAt")
    if isinstance(generated_at_camel, str) and generated_at_camel.strip():
        candidate = generated_at_camel.strip()
        if _parse_iso(candidate) is not None:
            return candidate
    return fallback


@dataclass(frozen=True)
class RebuildSummary:
    authors: int
    documents: int
    chapters: int
    segments: int
    snapshots: int
    warnings: list[str]


def rebuild_from_storage(storage_root: Path) -> RebuildSummary:
    warnings: list[str] = []
    now = _now_iso()
    authors_dir = storage_root / "authors"
    if not authors_dir.exists() or not authors_dir.is_dir():
        return RebuildSummary(
            authors=0,
            documents=0,
            chapters=0,
            segments=0,
            snapshots=0,
            warnings=[f"authors dir not found or not directory: {authors_dir}"],
        )

    created_authors = 0
    created_documents = 0
    created_chapters = 0
    created_segments = 0
    created_snapshots = 0

    try:
        storage_author_dirs = sorted([p for p in authors_dir.iterdir() if p.is_dir()])
    except OSError as exc:
        return RebuildSummary(
            authors=0,
            documents=0,
            chapters=0,
            segments=0,
            snapshots=0,
            warnings=[f"failed to iterate authors dir: {authors_dir} ({exc})"],
        )
    storage_author_ids = {path.name for path in storage_author_dirs}

    with session_scope() as session:
        # Keep DB aligned with storage as source of truth.
        if storage_author_ids:
            stale_author_ids = list(
                session.execute(
                    select(Author.author_id).where(Author.author_id.not_in(storage_author_ids))
                ).scalars()
            )
            if stale_author_ids:
                stale_document_ids = list(
                    session.execute(
                        select(AuthorDocument.document_id).where(
                            AuthorDocument.author_id.in_(stale_author_ids)
                        )
                    ).scalars()
                )
                if stale_document_ids:
                    session.execute(
                        delete(DocumentSegment).where(
                            DocumentSegment.document_id.in_(stale_document_ids)
                        )
                    )
                    session.execute(
                        delete(DocumentChapter).where(
                            DocumentChapter.document_id.in_(stale_document_ids)
                        )
                    )
                session.execute(
                    delete(AuthorSkillSnapshot).where(
                        AuthorSkillSnapshot.author_id.in_(stale_author_ids)
                    )
                )
                session.execute(
                    delete(PipelineJob).where(PipelineJob.author_id.in_(stale_author_ids))
                )
                session.execute(
                    delete(AuthorDocument).where(AuthorDocument.author_id.in_(stale_author_ids))
                )
                session.execute(delete(Author).where(Author.author_id.in_(stale_author_ids)))

        for author_dir in storage_author_dirs:
            author_id = author_dir.name
            author_meta_path = author_dir / "author_meta.json"
            author_meta = _safe_load_json(author_meta_path) if author_meta_path.exists() else None

            if isinstance(author_meta, dict):
                author_name = str(author_meta.get("author_name") or author_id)
                school = author_meta.get("school")
                avatar_url = author_meta.get("avatar_url")
                created_at = str(author_meta.get("created_at") or now)
                updated_at = str(author_meta.get("updated_at") or created_at)
            else:
                warnings.append(f"missing/invalid author_meta.json for author_id={author_id}")
                author_name = author_id
                school = None
                avatar_url = None
                created_at = now
                updated_at = now

            existing_author = session.get(Author, author_id)
            if existing_author is None:
                session.add(
                    Author(
                        author_id=author_id,
                        author_name=author_name,
                        school=school,
                        avatar_url=avatar_url,
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                )
                created_authors += 1
            else:
                existing_author.author_name = author_name
                existing_author.school = school
                existing_author.avatar_url = avatar_url
                existing_author.updated_at = updated_at

            # Documents
            documents_dir = author_dir / "documents"
            if documents_dir.exists():
                for doc_dir in sorted([p for p in documents_dir.iterdir() if p.is_dir()]):
                    document_id = doc_dir.name
                    document_meta_path = doc_dir / "document_meta.json"
                    document_meta = (
                        _safe_load_json(document_meta_path) if document_meta_path.exists() else None
                    )
                    if isinstance(document_meta, dict):
                        book_title = str(document_meta.get("book_title") or document_id)
                        pdf_uri = str(document_meta.get("pdf_uri") or "")
                        status = str(document_meta.get("status") or "active")
                        doc_created_at = str(document_meta.get("created_at") or now)
                        doc_updated_at = str(document_meta.get("updated_at") or doc_created_at)
                    else:
                        warnings.append(
                            f"missing/invalid document_meta.json for author_id={author_id}, document_id={document_id}"
                        )
                        book_title = document_id
                        pdf_uri = ""
                        status = "active"
                        doc_created_at = now
                        doc_updated_at = now

                    existing_doc = session.get(AuthorDocument, document_id)
                    if existing_doc is None:
                        session.add(
                            AuthorDocument(
                                document_id=document_id,
                                author_id=author_id,
                                book_title=book_title,
                                pdf_uri=pdf_uri,
                                status=status,
                                created_at=doc_created_at,
                                updated_at=doc_updated_at,
                            )
                        )
                        created_documents += 1
                    else:
                        existing_doc.author_id = author_id
                        existing_doc.book_title = book_title
                        existing_doc.pdf_uri = pdf_uri
                        existing_doc.status = status
                        existing_doc.updated_at = doc_updated_at

                    # Chapters / Segments from extracted_segments.json
                    extracted_path = doc_dir / "extracted_segments.json"
                    extracted = _safe_load_json(extracted_path) if extracted_path.exists() else None
                    if not isinstance(extracted, list):
                        continue

                    # Replace existing extracted structure for this document.
                    session.execute(delete(DocumentSegment).where(DocumentSegment.document_id == document_id))
                    session.execute(delete(DocumentChapter).where(DocumentChapter.document_id == document_id))

                    chapter_id_by_title: dict[str, str] = {}
                    chapter_order: list[str] = []
                    for row in extracted:
                        if not isinstance(row, dict):
                            continue
                        section_title = str(row.get("section_title") or "").strip()
                        if not section_title:
                            continue
                        if section_title not in chapter_id_by_title:
                            chapter_id_by_title[section_title] = str(uuid.uuid4())
                            chapter_order.append(section_title)

                    for order_index, section_title in enumerate(chapter_order):
                        session.add(
                            DocumentChapter(
                                chapter_id=chapter_id_by_title[section_title],
                                document_id=document_id,
                                chapter_title=section_title,
                                order_index=order_index,
                                is_deleted=False,
                                deleted_at=None,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                        created_chapters += 1

                    for row in extracted:
                        if not isinstance(row, dict):
                            continue
                        section_title = str(row.get("section_title") or "").strip()
                        chunk_id = str(row.get("chunk_id") or "").strip()
                        content = str(row.get("content") or "")
                        try:
                            order_index = int(row.get("order_index") or 0)
                        except (TypeError, ValueError):
                            order_index = 0
                        chapter_id = chapter_id_by_title.get(section_title)
                        if not chapter_id or not chunk_id:
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
                        created_segments += 1

            # Snapshots
            snapshots_dir = author_dir / "snapshots"
            snapshot_records: list[tuple[str, str, dict[str, str]]] = []
            if snapshots_dir.exists():
                for snapshot_dir in sorted([p for p in snapshots_dir.iterdir() if p.is_dir()]):
                    snapshot_id = snapshot_dir.name
                    outputs: dict[str, str] = {}

                    file_map: list[tuple[str, OutputType]] = [
                        ("method_analysis.json", OutputType.METHOD_ANALYSIS_JSON),
                        ("main_skill.json", OutputType.MAIN_SKILL_JSON),
                        ("sub_skill.json", OutputType.SUB_SKILL_JSON),
                        ("main_skill.md", OutputType.MAIN_SKILL_MD),
                        ("main_skills_md.json", OutputType.MAIN_SKILLS_MD_JSON),
                        ("sub_skills_md.zip", OutputType.SUB_SKILLS_MD_ZIP),
                        ("sub_skills_md.json", OutputType.SUB_SKILLS_MD_JSON),
                    ]
                    for filename, output_type in file_map:
                        path = snapshot_dir / filename
                        if path.exists():
                            outputs[output_type.value] = _to_storage_uri(path, storage_root=storage_root)

                    meta_path = snapshot_dir / "snapshot_meta.json"
                    meta = _safe_load_json(meta_path) if meta_path.exists() else None
                    created_at = None
                    if isinstance(meta, dict):
                        created_at = meta.get("created_at")
                    created_at_text = str(created_at or datetime.fromtimestamp(snapshot_dir.stat().st_mtime, tz=UTC).isoformat())
                    snapshot_records.append((snapshot_id, created_at_text, outputs))

            # Replace snapshot rows for this author to ensure correct is_latest.
            session.execute(delete(AuthorSkillSnapshot).where(AuthorSkillSnapshot.author_id == author_id))
            session.execute(
                delete(PipelineJob).where(
                    PipelineJob.author_id == author_id,
                    PipelineJob.job_type == JobType.AUTHOR_SKILLS.value,
                )
            )
            session.execute(
                delete(PipelineJob).where(
                    PipelineJob.author_id == author_id,
                    PipelineJob.job_type == JobType.AUTHOR_ANSWER.value,
                )
            )

            if snapshot_records:
                snapshot_records.sort(
                    key=lambda item: _parse_iso(item[1]) or datetime.min.replace(tzinfo=UTC)
                )
                latest_id = snapshot_records[-1][0]
                for snapshot_id, created_at_text, outputs in snapshot_records:
                    session.add(
                        AuthorSkillSnapshot(
                            snapshot_id=snapshot_id,
                            author_id=author_id,
                            is_latest=(snapshot_id == latest_id),
                            outputs_json=json.dumps(outputs, ensure_ascii=False),
                            created_at=created_at_text,
                        )
                    )
                    session.add(
                        PipelineJob(
                            job_id=_recovered_skills_job_id(
                                author_id=author_id,
                                snapshot_id=snapshot_id,
                            ),
                            author_id=author_id,
                            document_id=None,
                            job_type=JobType.AUTHOR_SKILLS.value,
                            status=JobStatus.SUCCESS.value,
                            current_stage=Stage.RENDER.value,
                            progress=100,
                            query=None,
                            model_config_json="{}",
                            snapshot_id=snapshot_id,
                            outputs_json=json.dumps(outputs, ensure_ascii=False),
                            error_message=None,
                            created_at=created_at_text,
                            updated_at=created_at_text,
                            finished_at=created_at_text,
                        )
                    )
                    created_snapshots += 1

            # Rebuild author_answer jobs from answers/<job_id>/answer.json artifacts.
            answers_dir = author_dir / "answers"
            if answers_dir.exists():
                for answer_job_dir in sorted([p for p in answers_dir.iterdir() if p.is_dir()]):
                    answer_job_id = answer_job_dir.name
                    if not answer_job_id or len(answer_job_id) > 64:
                        warnings.append(
                            f"invalid answer job directory name for author_id={author_id}: {answer_job_id}"
                        )
                        continue

                    answer_json_path = answer_job_dir / "answer.json"
                    if not answer_json_path.exists():
                        warnings.append(
                            f"missing answer.json for author_id={author_id}, job_id={answer_job_id}"
                        )
                        continue

                    answer_json = _safe_load_json(answer_json_path)
                    if not isinstance(answer_json, dict):
                        warnings.append(
                            f"invalid answer.json for author_id={author_id}, job_id={answer_job_id}"
                        )
                        continue

                    created_at_text = _pick_answer_generated_at(
                        answer_json=answer_json,
                        fallback=datetime.fromtimestamp(
                            answer_json_path.stat().st_mtime, tz=UTC
                        ).isoformat(),
                    )
                    query = answer_json.get("query")
                    query_text = query.strip() if isinstance(query, str) else None
                    outputs = {
                        OutputType.ANSWER_JSON.value: _to_storage_uri(
                            answer_json_path,
                            storage_root=storage_root,
                        )
                    }
                    session.add(
                        PipelineJob(
                            job_id=answer_job_id,
                            author_id=author_id,
                            document_id=None,
                            job_type=JobType.AUTHOR_ANSWER.value,
                            status=JobStatus.SUCCESS.value,
                            current_stage=Stage.ANSWER.value,
                            progress=100,
                            query=query_text,
                            model_config_json="{}",
                            snapshot_id=None,
                            outputs_json=json.dumps(outputs, ensure_ascii=False),
                            error_message=None,
                            created_at=created_at_text,
                            updated_at=created_at_text,
                            finished_at=created_at_text,
                        )
                    )

        # Ensure FK-less consistency is good before commit.
        session.flush()

    # Aggregate counts from DB (safer than counting creates for idempotent runs).
    with session_scope() as session:
        authors_count = int(session.execute(select(func.count()).select_from(Author)).scalar_one())
        documents_count = int(
            session.execute(select(func.count()).select_from(AuthorDocument)).scalar_one()
        )
        chapters_count = int(
            session.execute(select(func.count()).select_from(DocumentChapter)).scalar_one()
        )
        segments_count = int(
            session.execute(select(func.count()).select_from(DocumentSegment)).scalar_one()
        )
        snapshots_count = int(
            session.execute(select(func.count()).select_from(AuthorSkillSnapshot)).scalar_one()
        )

    return RebuildSummary(
        authors=authors_count,
        documents=documents_count,
        chapters=chapters_count,
        segments=segments_count,
        snapshots=snapshots_count,
        warnings=warnings,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild DB from storage manifests/artifacts.")
    parser.add_argument(
        "--storage-root",
        default="",
        help="Storage root directory (defaults to settings.storage_root).",
    )
    args = parser.parse_args(argv)

    if args.storage_root:
        storage_root = Path(args.storage_root)
    else:
        storage_root = storage.ensure_storage_root()

    summary = rebuild_from_storage(storage_root=storage_root)
    print(
        json.dumps(
            {
                "authors": summary.authors,
                "documents": summary.documents,
                "chapters": summary.chapters,
                "segments": summary.segments,
                "snapshots": summary.snapshots,
                "warnings": summary.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
