"""提供路由依赖项，包括 API Key 校验与请求上下文读取。"""

from __future__ import annotations

import uuid
from typing import Annotated

from app.infra.settings import Settings, get_settings
from fastapi import Depends, Header, HTTPException, Request


def get_request_id(request: Request) -> str:
    """从请求上下文获取 request_id。"""
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def get_app_settings() -> Settings:
    """获取全局配置对象。"""
    return get_settings()


def verify_api_key(
    settings: Annotated[Settings, Depends(get_app_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """校验请求头中的 API Key。"""
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid api key")
