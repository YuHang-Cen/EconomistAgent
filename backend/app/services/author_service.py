"""提供作者与文档管理服务，实现作者创建与文档上传最小闭环。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.models import Author, AuthorDocument
from app.domain.schemas import (
    AuthorCreateRequest,
    AuthorDocumentResponse,
    AuthorDocumentUploadRequest,
    AuthorResponse,
)
from app.infra.db import session_scope
from fastapi import HTTPException
from sqlalchemy import func, select


def _now_iso() -> str:
    """返回 UTC ISO 8601 时间字符串。"""
    return datetime.now(tz=UTC).isoformat()


def create_author(payload: AuthorCreateRequest) -> AuthorResponse:
    """创建作者并持久化到数据库。"""
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
    """读取作者列表并计算 manuscriptsCount 聚合值。"""
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
    """上传文档并自动创建 document_reload 任务。"""
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
    """读取指定作者文档列表。"""
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
    """为指定文档创建并执行 document_reload 任务。"""
    from app.services import job_service

    job = job_service.create_document_reload_job(
        author_id=author_id, document_id=document_id, auto_run=True
    )
    return {"reload_job_id": str(job["jobId"])}
