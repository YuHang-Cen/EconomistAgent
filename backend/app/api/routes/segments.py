"""定义章节与段落读取、软删除相关 API 路由骨架。"""

from __future__ import annotations

from typing import Annotated, Any

from app.api.deps import get_request_id, verify_api_key
from app.domain.schemas import build_success_response
from app.services import segment_service
from fastapi import APIRouter, Depends

router = APIRouter(tags=["segments"], dependencies=[Depends(verify_api_key)])


@router.get("/authors/{author_id}/documents/{document_id}/chapters")
def list_chapters(
    author_id: str, document_id: str, request_id: Annotated[str, Depends(get_request_id)]
) -> dict[str, Any]:
    """读取章节列表骨架接口。"""
    chapters = segment_service.list_chapters(author_id=author_id, document_id=document_id)
    return build_success_response(request_id=request_id, data=chapters)


@router.get("/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}/segments")
def list_segments(
    author_id: str,
    document_id: str,
    chapter_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """读取段落列表骨架接口。"""
    segments = segment_service.list_segments(
        author_id=author_id, document_id=document_id, chapter_id=chapter_id
    )
    return build_success_response(request_id=request_id, data=segments)


@router.delete("/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}")
def delete_chapter(
    author_id: str,
    document_id: str,
    chapter_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """软删除章节骨架接口。"""
    result = segment_service.delete_chapter(
        author_id=author_id, document_id=document_id, chapter_id=chapter_id
    )
    return build_success_response(request_id=request_id, data=result)


@router.delete("/authors/{author_id}/documents/{document_id}/segments/{segment_id}")
def delete_segment(
    author_id: str,
    document_id: str,
    segment_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """软删除段落骨架接口。"""
    result = segment_service.delete_segment(
        author_id=author_id, document_id=document_id, segment_id=segment_id
    )
    return build_success_response(request_id=request_id, data=result)
