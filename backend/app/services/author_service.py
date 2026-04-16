"""提供作者与文档管理的应用服务骨架。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.schemas import (
    AuthorCreateRequest,
    AuthorDocumentResponse,
    AuthorDocumentUploadRequest,
    AuthorResponse,
)


def create_author(payload: AuthorCreateRequest) -> AuthorResponse:
    """创建作者并返回骨架数据。"""
    return AuthorResponse(
        author_id=str(uuid.uuid4()),
        author_name=payload.author_name,
        school=payload.school,
        avatar_url=payload.avatar_url,
        manuscripts_count=0,
    )


def list_authors() -> list[AuthorResponse]:
    """返回作者列表骨架数据。"""
    return []


def upload_document(author_id: str, payload: AuthorDocumentUploadRequest) -> dict[str, str]:
    """上传文档并自动创建 document_reload 任务。"""
    _ = payload
    return {"document_id": str(uuid.uuid4()), "reload_job_id": str(uuid.uuid4())}


def list_documents(author_id: str) -> list[AuthorDocumentResponse]:
    """返回作者文档列表骨架数据。"""
    _ = author_id
    return []


def reload_document(author_id: str, document_id: str) -> dict[str, str]:
    """创建文档级重处理任务骨架结果。"""
    _ = (author_id, document_id, datetime.now(UTC))
    return {"reloadJobId": str(uuid.uuid4())}
