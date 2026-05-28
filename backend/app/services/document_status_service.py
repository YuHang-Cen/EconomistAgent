"""Document status reconciliation helpers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.domain.enums import JobStatus, JobType
from app.domain.models import AuthorDocument, DocumentSegment, PipelineJob
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def reconcile_stale_processing_documents(
    session: Session,
    *,
    author_id: str,
    document_id: str | None = None,
) -> list[str]:
    """Recover processing documents that no longer have a live reload job."""
    conditions = [
        AuthorDocument.author_id == author_id,
        AuthorDocument.status == "processing",
    ]
    if document_id is not None:
        conditions.append(AuthorDocument.document_id == document_id)

    documents = list(session.execute(select(AuthorDocument).where(*conditions)).scalars())
    if not documents:
        return []

    document_ids = [item.document_id for item in documents]
    active_reload_doc_ids = {
        item
        for item in session.execute(
            select(PipelineJob.document_id).where(
                PipelineJob.author_id == author_id,
                PipelineJob.document_id.in_(document_ids),
                PipelineJob.job_type == JobType.DOCUMENT_RELOAD.value,
                PipelineJob.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
            )
        ).scalars()
        if isinstance(item, str) and item
    }

    latest_reload_by_document: dict[str, PipelineJob] = {}
    reload_jobs = session.execute(
        select(PipelineJob)
        .where(
            PipelineJob.author_id == author_id,
            PipelineJob.document_id.in_(document_ids),
            PipelineJob.job_type == JobType.DOCUMENT_RELOAD.value,
        )
        .order_by(PipelineJob.document_id.asc(), PipelineJob.created_at.desc())
    ).scalars()
    for job in reload_jobs:
        if not job.document_id or job.document_id in latest_reload_by_document:
            continue
        latest_reload_by_document[job.document_id] = job

    segment_counts = {
        str(document_key): int(count)
        for document_key, count in session.execute(
            select(DocumentSegment.document_id, func.count(DocumentSegment.segment_id))
            .where(
                DocumentSegment.document_id.in_(document_ids),
                DocumentSegment.is_deleted.is_(False),
            )
            .group_by(DocumentSegment.document_id)
        )
    }

    changed_document_ids: list[str] = []
    now = _now_iso()
    for document in documents:
        if document.document_id in active_reload_doc_ids:
            continue

        latest_job = latest_reload_by_document.get(document.document_id)
        target_status = "active" if segment_counts.get(document.document_id, 0) > 0 else "failed"
        if latest_job is not None and latest_job.status == JobStatus.FAILED.value:
            target_status = "failed"

        if document.status == target_status:
            continue

        logger.warning(
            "recovered stale processing document: author_id=%s document_id=%s old_status=%s new_status=%s latest_reload_job=%s",
            author_id,
            document.document_id,
            document.status,
            target_status,
            latest_job.job_id if latest_job is not None else None,
        )
        document.status = target_status
        document.updated_at = now
        changed_document_ids.append(document.document_id)

    if changed_document_ids:
        session.flush()
    return changed_document_ids
