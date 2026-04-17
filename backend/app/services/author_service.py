"""Author and document management services."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.domain.enums import JobStatus
from app.domain.models import (
    Author,
    AuthorDocument,
    AuthorSkillSnapshot,
    DocumentChapter,
    DocumentSegment,
    PipelineJob,
)
from app.domain.schemas import (
    AuthorCreateRequest,
    AuthorDocumentResponse,
    AuthorDocumentUploadRequest,
    AuthorResponse,
)
from app.infra import storage
from app.infra.db import session_scope
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat()


def create_author(payload: AuthorCreateRequest) -> AuthorResponse:
    """Create an author record."""
    now = _now_iso()
    author = Author(
        author_id=str(uuid.uuid4()),
        author_name=payload.author_name,
        school=payload.school,
        avatar_url=payload.avatar_url,
        created_at=now,
        updated_at=now,
    )
    with session_scope() as session:
        session.add(author)
    return AuthorResponse(
        author_id=author.author_id,
        author_name=author.author_name,
        school=author.school,
        avatar_url=author.avatar_url,
        manuscripts_count=0,
    )


def list_authors() -> list[AuthorResponse]:
    """List authors with manuscriptsCount aggregation."""
    with session_scope() as session:
        stmt = (
            select(
                Author.author_id,
                Author.author_name,
                Author.school,
                Author.avatar_url,
                func.count(AuthorDocument.document_id).label("manuscripts_count"),
            )
            .outerjoin(AuthorDocument, AuthorDocument.author_id == Author.author_id)
            .group_by(Author.author_id)
            .order_by(Author.created_at.desc())
        )
        rows = session.execute(stmt).all()

    return [
        AuthorResponse(
            author_id=row.author_id,
            author_name=row.author_name,
            school=row.school,
            avatar_url=row.avatar_url,
            manuscripts_count=int(row.manuscripts_count),
        )
        for row in rows
    ]


def upload_document(author_id: str, payload: AuthorDocumentUploadRequest) -> dict[str, str]:
    """Upload a document and enqueue a document_reload job."""
    now = _now_iso()
    document = AuthorDocument(
        document_id=str(uuid.uuid4()),
        author_id=author_id,
        book_title=payload.book_title,
        pdf_uri=payload.pdf_uri,
        status="processing",
        created_at=now,
        updated_at=now,
    )
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")
        session.add(document)
        session.flush()
        document_id = document.document_id

    from app.services import job_service

    job = job_service.create_document_reload_job(
        author_id=author_id, document_id=document_id, auto_run=True
    )
    return {"document_id": document_id, "reload_job_id": str(job["jobId"])}


def list_documents(author_id: str) -> list[AuthorDocumentResponse]:
    """List documents by author."""
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")
        rows = session.execute(
            select(AuthorDocument)
            .where(AuthorDocument.author_id == author_id)
            .order_by(AuthorDocument.created_at.desc())
        ).scalars()
        documents = list(rows)

    return [
        AuthorDocumentResponse(
            document_id=item.document_id,
            author_id=item.author_id,
            book_title=item.book_title,
            pdf_uri=item.pdf_uri,
            status=item.status,
        )
        for item in documents
    ]


def reload_document(author_id: str, document_id: str) -> dict[str, str]:
    """Create and execute a document_reload job for a document."""
    from app.services import job_service

    job = job_service.create_document_reload_job(
        author_id=author_id, document_id=document_id, auto_run=True
    )
    return {"reload_job_id": str(job["jobId"])}


def delete_author(author_id: str) -> dict[str, bool]:
    """Hard-delete an author and related data, while preserving canceled jobs."""
    now = _now_iso()
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")

        document_ids = list(
            session.execute(
                select(AuthorDocument.document_id).where(AuthorDocument.author_id == author_id)
            ).scalars()
        )

        session.execute(
            update(PipelineJob)
            .where(
                PipelineJob.author_id == author_id,
                PipelineJob.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
            )
            .values(
                status=JobStatus.CANCELED.value,
                updated_at=now,
                finished_at=now,
                error_message="author deleted",
            )
        )

        if document_ids:
            session.execute(
                delete(DocumentSegment).where(DocumentSegment.document_id.in_(document_ids))
            )
            session.execute(
                delete(DocumentChapter).where(DocumentChapter.document_id.in_(document_ids))
            )

        session.execute(delete(AuthorDocument).where(AuthorDocument.author_id == author_id))
        session.execute(delete(AuthorSkillSnapshot).where(AuthorSkillSnapshot.author_id == author_id))
        session.execute(delete(Author).where(Author.author_id == author_id))

    try:
        storage.delete_author_root(author_id=author_id)
    except OSError as exc:
        logger.warning(
            "failed to cleanup author storage directory: author_id=%s, error=%s",
            author_id,
            exc,
        )

    return {"deleted": True}
