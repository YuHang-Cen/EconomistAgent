"""组装 FastAPI 应用、路由与统一异常响应包裹。"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.routes import authors, jobs, segments
from app.domain.schemas import build_error_response, build_success_response
from app.infra.logging import configure_logging
from app.infra.settings import get_settings


def _error_code_from_status(status_code: int) -> str:
    """将 HTTP 状态码映射为统一错误码。"""
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "TASK_CONFLICT"
    if status_code == 422:
        return "INVALID_ARGUMENT"
    return "INTERNAL_ERROR"


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    configure_logging()
    application = FastAPI(title="Economist Agent Backend", version="0.1.0")
    settings = get_settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_allow_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def attach_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        payload = build_error_response(
            request_id=request_id,
            code=_error_code_from_status(exc.status_code),
            message=str(exc.detail),
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        payload = build_error_response(
            request_id=request_id,
            code="INVALID_ARGUMENT",
            message="request validation failed",
            details={"errors": exc.errors()},
        )
        return JSONResponse(status_code=422, content=payload)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        payload = build_error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="internal server error",
            details={"reason": str(exc)},
        )
        return JSONResponse(status_code=500, content=payload)

    @application.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return build_success_response(request_id=request_id, data={"status": "ok"})

    application.include_router(authors.router, prefix="/api")
    application.include_router(segments.router, prefix="/api")
    application.include_router(jobs.router, prefix="/api")
    return application


app = create_app()
