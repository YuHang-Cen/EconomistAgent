"""定义作者、文档与文档重处理相关 API 路由骨架。"""

from __future__ import annotations

from typing import Annotated, Any

from app.api.deps import get_request_id, verify_api_key
from app.domain.schemas import (
    AuthorCreateRequest,
    AuthorDocumentUploadRequest,
    AuthorDocumentUploadResponse,
    ReloadJobResponse,
    build_success_response,
)
from app.services import author_service
from fastapi import APIRouter, Depends

router = APIRouter(tags=["authors"], dependencies=[Depends(verify_api_key)])


@router.post("/authors")
def create_author(
    payload: AuthorCreateRequest, request_id: Annotated[str, Depends(get_request_id)]
) -> dict[str, Any]:
    """创建作者接口。"""
    author = author_service.create_author(payload)
    return build_success_response(request_id=request_id, data=author.model_dump(by_alias=True))


@router.get("/authors")
def list_authors(request_id: Annotated[str, Depends(get_request_id)]) -> dict[str, Any]:
    """获取作者列表接口。"""
    authors = [item.model_dump(by_alias=True) for item in author_service.list_authors()]
    return build_success_response(request_id=request_id, data=authors)


@router.post("/authors/{author_id}/documents")
def upload_document(
    author_id: str,
    payload: AuthorDocumentUploadRequest,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """上传作者文档并自动触发 document_reload 任务接口。"""
    result = author_service.upload_document(author_id=author_id, payload=payload)
    response = AuthorDocumentUploadResponse.model_validate(result).model_dump(by_alias=True)
    return build_success_response(request_id=request_id, data=response)


@router.get("/authors/{author_id}/documents")
def list_documents(
    author_id: str, request_id: Annotated[str, Depends(get_request_id)]
) -> dict[str, Any]:
    """获取指定作者文档列表接口。"""
    documents = [
        item.model_dump(by_alias=True) for item in author_service.list_documents(author_id)
    ]
    return build_success_response(request_id=request_id, data=documents)


@router.post("/authors/{author_id}/documents/{document_id}/reload")
def reload_document(
    author_id: str,
    document_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """触发单文档重处理任务接口。"""
    result = author_service.reload_document(author_id=author_id, document_id=document_id)
    response = ReloadJobResponse.model_validate(result).model_dump(by_alias=True)
    return build_success_response(request_id=request_id, data=response)
