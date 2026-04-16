"""定义统一 API 包裹、请求体与响应体的 Pydantic 模型。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    """将 snake_case 字段名转换为 camelCase。"""
    parts = value.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """提供 camelCase 序列化策略的基础模型。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class ErrorPayload(CamelModel):
    """统一错误体模型。"""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiEnvelope(CamelModel):
    """统一 API 响应包裹模型。"""

    success: bool
    data: Any | None = None
    error: ErrorPayload | None = None
    request_id: str
    timestamp: datetime


def build_success_response(request_id: str, data: Any) -> dict[str, Any]:
    """构造成功响应包裹。"""
    payload = ApiEnvelope(
        success=True,
        data=data,
        error=None,
        request_id=request_id,
        timestamp=datetime.now(tz=UTC),
    )
    return payload.model_dump(by_alias=True, mode="json")


def build_error_response(
    request_id: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造失败响应包裹。"""
    payload = ApiEnvelope(
        success=False,
        data=None,
        error=ErrorPayload(code=code, message=message, details=details),
        request_id=request_id,
        timestamp=datetime.now(tz=UTC),
    )
    return payload.model_dump(by_alias=True, mode="json")


class AuthorCreateRequest(CamelModel):
    """创建作者请求体。"""

    author_name: str = Field(min_length=1, max_length=255)
    school: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=512)


class AuthorResponse(CamelModel):
    """作者返回体。"""

    author_id: str
    author_name: str
    school: str | None = None
    avatar_url: str | None = None
    manuscripts_count: int = 0


class AuthorDocumentUploadRequest(CamelModel):
    """上传文档请求体。"""

    book_title: str = Field(min_length=1, max_length=255)
    pdf_uri: str = Field(min_length=1, max_length=1024)


class AuthorDocumentResponse(CamelModel):
    """作者文档返回体。"""

    document_id: str
    author_id: str
    book_title: str
    pdf_uri: str
    status: str


class AuthorDocumentUploadResponse(CamelModel):
    """上传文档并触发重处理任务的返回体。"""

    document_id: str
    reload_job_id: str


class ReloadJobResponse(CamelModel):
    """文档重处理触发返回体。"""

    reload_job_id: str


class AuthorAnswerRequest(CamelModel):
    """作者问答请求体。"""

    query: str = Field(min_length=1)
