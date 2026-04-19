"""定义作者、文档与文档重处理相关 API 路由骨架。"""

from __future__ import annotations

from typing import Annotated, Any

from app.api.deps import get_request_id, verify_api_key
from app.domain.schemas import (
    AuthorCreateRequest,
    AuthorDocumentUploadRequest,
    AuthorDocumentUploadResponse,
    AuthorUpdateRequest,
    AuthorResponse,
    ReloadJobResponse,
    build_success_response,
)
from app.services import author_service
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(tags=["authors"], dependencies=[Depends(verify_api_key)])
public_router = APIRouter(tags=["authors-public"])


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


@router.delete("/authors/{author_id}")
def delete_author(
    author_id: str, request_id: Annotated[str, Depends(get_request_id)]
) -> dict[str, Any]:
    """Delete author and related data."""
    result = author_service.delete_author(author_id=author_id)
    return build_success_response(request_id=request_id, data=result)


@router.patch("/authors/{author_id}")
def update_author(
    author_id: str,
    payload: AuthorUpdateRequest,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """Update author display fields."""
    author = author_service.update_author(author_id=author_id, payload=payload)
    return build_success_response(request_id=request_id, data=author.model_dump(by_alias=True))


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


@router.post("/authors/{author_id}/documents/upload")
async def upload_document_file(
    author_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
    book_title: str = Form(..., alias="bookTitle"),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload PDF via multipart/form-data and trigger document_reload."""
    content = await file.read()
    result = author_service.upload_document_file(
        author_id=author_id,
        book_title=book_title,
        filename=file.filename or "",
        content=content,
    )
    response = AuthorDocumentUploadResponse.model_validate(result).model_dump(by_alias=True)
    return build_success_response(request_id=request_id, data=response)


@router.post("/authors/{author_id}/avatar/upload")
async def upload_author_avatar(
    author_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload author avatar image and persist to storage."""
    content = await file.read()
    author = author_service.upload_author_avatar(
        author_id=author_id,
        filename=file.filename or "",
        content=content,
        content_type=file.content_type,
    )
    response = AuthorResponse.model_validate(author).model_dump(by_alias=True)
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


@public_router.get("/public/authors/{author_id}/avatar")
def get_public_author_avatar(author_id: str) -> FileResponse:
    """Public avatar URL for img tags (no API key required)."""
    avatar_path, media_type = author_service.get_public_avatar(author_id=author_id)
    return FileResponse(path=avatar_path, media_type=media_type)
