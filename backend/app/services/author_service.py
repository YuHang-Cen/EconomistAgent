"""Author and document management services."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    AuthorUpdateRequest,
    AuthorResponse,
)
from app.infra import storage
from app.infra.db import session_scope
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update

logger = logging.getLogger(__name__)

MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_AVATAR_SUFFIXES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _now_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat()


def _author_manifest(author: Author) -> dict[str, str | None]:
    return {
        "author_id": author.author_id,
        "author_name": author.author_name,
        "school": author.school,
        "avatar_url": author.avatar_url,
        "created_at": author.created_at,
        "updated_at": author.updated_at,
    }


def _write_author_manifest(author: Author) -> None:
    _write_author_manifest_payload(author_id=author.author_id, payload=_author_manifest(author))


def _write_author_manifest_payload(author_id: str, payload: dict[str, str | None]) -> None:
    try:
        storage.write_json(
            storage.author_root(author_id=author_id) / "author_meta.json",
            payload,
        )
    except OSError as exc:
        logger.warning(
            "failed to write author manifest: author_id=%s, error=%s",
            author_id,
            exc,
        )


def _author_avatar_candidates(author_id: str) -> list[Path]:
    root = storage.author_root(author_id=author_id)
    if not root.exists():
        return []
    return sorted(
        [
            item
            for item in root.glob("avatar.*")
            if item.is_file() and item.suffix.lower() in ALLOWED_AVATAR_SUFFIXES
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def _resolve_author_avatar_path(author_id: str) -> Path | None:
    files = _author_avatar_candidates(author_id=author_id)
    return files[0] if files else None


def _author_avatar_public_url(author_id: str) -> str:
    version = int(datetime.now(tz=UTC).timestamp() * 1000)
    return f"/api/public/authors/{author_id}/avatar?v={version}"


def _validate_avatar_upload(filename: str, content: bytes, content_type: str | None) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_AVATAR_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail="uploaded avatar must be one of .jpg/.jpeg/.png/.webp/.gif",
        )
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=422, detail="uploaded avatar must be <= 5MB")
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="uploaded avatar content type must be image/*")
    return suffix


def _persist_avatar_file(author_id: str, suffix: str, content: bytes) -> Path:
    root = storage.author_root(author_id=author_id)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"avatar{suffix}"
    target.write_bytes(content)

    for item in root.glob("avatar.*"):
        if item.is_file() and item != target:
            item.unlink(missing_ok=True)

    return target


def _create_document_with_reload_job(author_id: str, book_title: str, pdf_uri: str) -> dict[str, str]:
    """Create one document record and enqueue reload job."""
    now = _now_iso()
    document = AuthorDocument(
        document_id=str(uuid.uuid4()),
        author_id=author_id,
        book_title=book_title,
        pdf_uri=pdf_uri,
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
        author_manifest = _author_manifest(author)

    from app.services import job_service

    job = job_service.create_document_reload_job(
        author_id=author_id, document_id=document_id, auto_run=True
    )
    try:
        storage.write_json(
            storage.document_root(author_id=author_id, document_id=document_id) / "document_meta.json",
            {
                "document_id": document_id,
                "author_id": author_id,
                "book_title": document.book_title,
                "pdf_uri": document.pdf_uri,
                "status": document.status,
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            },
        )
        storage.write_json(
            storage.author_root(author_id=author_id) / "author_meta.json",
            author_manifest,
        )
    except OSError as exc:
        logger.warning(
            "failed to write document/author manifest: author_id=%s, document_id=%s, error=%s",
            author_id,
            document_id,
            exc,
        )
    return {"document_id": document_id, "reload_job_id": str(job["jobId"])}


def _count_manuscripts_by_author(session: Any, author_id: str) -> int:
    return int(
        session.execute(
            select(func.count(AuthorDocument.document_id)).where(
                AuthorDocument.author_id == author_id
            )
        ).scalar_one()
    )


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
    _write_author_manifest(author)
    return AuthorResponse(
        author_id=author.author_id,
        author_name=author.author_name,
        school=author.school,
        avatar_url=author.avatar_url,
        manuscripts_count=0,
    )


def update_author(author_id: str, payload: AuthorUpdateRequest) -> AuthorResponse:
    """Update author name and persist manifest."""
    author_name = payload.author_name.strip()
    if not author_name:
        raise HTTPException(status_code=422, detail="author name must not be empty")

    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")
        author.author_name = author_name
        author.updated_at = _now_iso()
        session.flush()
        manifest_data = _author_manifest(author)
        manuscripts_count = _count_manuscripts_by_author(session=session, author_id=author_id)

    _write_author_manifest_payload(author_id=author_id, payload=manifest_data)

    return AuthorResponse(
        author_id=str(manifest_data["author_id"]),
        author_name=str(manifest_data["author_name"]),
        school=str(manifest_data["school"]) if manifest_data["school"] is not None else None,
        avatar_url=str(manifest_data["avatar_url"]) if manifest_data["avatar_url"] else None,
        manuscripts_count=manuscripts_count,
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
    return _create_document_with_reload_job(
        author_id=author_id,
        book_title=payload.book_title,
        pdf_uri=payload.pdf_uri,
    )


def upload_document_file(author_id: str, book_title: str, filename: str, content: bytes) -> dict[str, str]:
    """Upload one PDF file from multipart payload, persist it, and enqueue reload job."""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="uploaded file must end with .pdf")

    # Ensure author exists before writing storage files.
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")

    document_id = str(uuid.uuid4())
    document_dir = storage.document_root(author_id=author_id, document_id=document_id)
    source_path = document_dir / "source.pdf"
    source_path.write_bytes(content)
    stored_pdf_uri = str(Path(source_path).resolve())

    now = _now_iso()
    document = AuthorDocument(
        document_id=document_id,
        author_id=author_id,
        book_title=book_title,
        pdf_uri=stored_pdf_uri,
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
        author_manifest = _author_manifest(author)

    from app.services import job_service

    job = job_service.create_document_reload_job(
        author_id=author_id, document_id=document_id, auto_run=True
    )
    try:
        storage.write_json(
            storage.document_root(author_id=author_id, document_id=document_id) / "document_meta.json",
            {
                "document_id": document_id,
                "author_id": author_id,
                "book_title": document.book_title,
                "pdf_uri": document.pdf_uri,
                "status": document.status,
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            },
        )
        storage.write_json(
            storage.author_root(author_id=author_id) / "author_meta.json",
            author_manifest,
        )
    except OSError as exc:
        logger.warning(
            "failed to write uploaded document manifest: author_id=%s, document_id=%s, error=%s",
            author_id,
            document_id,
            exc,
        )
    return {"document_id": document_id, "reload_job_id": str(job["jobId"])}


def upload_author_avatar(
    author_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
) -> AuthorResponse:
    suffix = _validate_avatar_upload(filename=filename, content=content, content_type=content_type)

    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")
        _persist_avatar_file(author_id=author_id, suffix=suffix, content=content)
        author.avatar_url = _author_avatar_public_url(author_id=author_id)
        author.updated_at = _now_iso()
        session.flush()
        manifest_data = _author_manifest(author)
        manuscripts_count = _count_manuscripts_by_author(session=session, author_id=author_id)

    _write_author_manifest_payload(author_id=author_id, payload=manifest_data)

    return AuthorResponse(
        author_id=str(manifest_data["author_id"]),
        author_name=str(manifest_data["author_name"]),
        school=str(manifest_data["school"]) if manifest_data["school"] is not None else None,
        avatar_url=str(manifest_data["avatar_url"]) if manifest_data["avatar_url"] else None,
        manuscripts_count=manuscripts_count,
    )


def get_public_avatar(author_id: str) -> tuple[Path, str]:
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")

    avatar_path = _resolve_author_avatar_path(author_id=author_id)
    if avatar_path is None or not avatar_path.exists():
        raise HTTPException(status_code=404, detail="avatar not found")

    media_type = ALLOWED_AVATAR_SUFFIXES.get(avatar_path.suffix.lower(), "application/octet-stream")
    return avatar_path, media_type


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
