"""定义任务轮询、产物读取、重试与取消相关 API 路由骨架。"""

from __future__ import annotations

from typing import Annotated, Any

from app.api.deps import get_request_id, verify_api_key
from app.domain.schemas import AuthorAnswerRequest, AuthorSkillsRequest, build_success_response
from app.services import job_service
from fastapi import APIRouter, Body, Depends, Query

router = APIRouter(tags=["jobs"], dependencies=[Depends(verify_api_key)])


@router.post("/authors/{author_id}/jobs/skills")
def create_author_skills_job(
    author_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
    payload: AuthorSkillsRequest | None = Body(default=None),
) -> dict[str, Any]:
    """触发作者技能生成任务骨架接口。"""
    model_config = payload.model_cfg.model_dump(exclude_none=True) if payload and payload.model_cfg else None
    job = job_service.create_author_skills_job(author_id=author_id, model_config=model_config)
    return build_success_response(request_id=request_id, data=job)


@router.post("/authors/{author_id}/jobs/answer")
def create_author_answer_job(
    author_id: str,
    payload: AuthorAnswerRequest,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """触发作者问答任务骨架接口。"""
    job = job_service.create_author_answer_job(
        author_id=author_id,
        query=payload.query,
        model_config=payload.model_cfg.model_dump(exclude_none=True)
        if payload.model_cfg
        else None,
    )
    return build_success_response(request_id=request_id, data=job)


@router.get("/authors/{author_id}/jobs")
def list_author_jobs(
    author_id: str,
    request_id: Annotated[str, Depends(get_request_id)],
    job_type: str | None = Query(default=None, alias="jobType"),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    """List jobs for one author with filters and cursor pagination."""
    result = job_service.list_author_jobs(
        author_id=author_id,
        job_type=job_type,
        status=status,
        limit=limit,
        cursor=cursor,
    )
    return build_success_response(request_id=request_id, data=result)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request_id: Annotated[str, Depends(get_request_id)]) -> dict[str, Any]:
    """轮询任务状态骨架接口。"""
    job = job_service.get_job(job_id=job_id)
    return build_success_response(request_id=request_id, data=job)


@router.get("/jobs/{job_id}/outputs")
def list_outputs(
    job_id: str, request_id: Annotated[str, Depends(get_request_id)]
) -> dict[str, Any]:
    """读取任务产物清单骨架接口。"""
    outputs = job_service.list_outputs(job_id=job_id)
    return build_success_response(request_id=request_id, data=outputs)


@router.get("/jobs/{job_id}/outputs/{output_type}")
def get_output(
    job_id: str,
    output_type: str,
    request_id: Annotated[str, Depends(get_request_id)],
) -> dict[str, Any]:
    """读取任务产物详情骨架接口。"""
    output = job_service.get_output(job_id=job_id, output_type=output_type)
    return build_success_response(request_id=request_id, data=output)


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, request_id: Annotated[str, Depends(get_request_id)]) -> dict[str, Any]:
    """执行失败任务重试骨架接口。"""
    job = job_service.retry_job(job_id=job_id)
    return build_success_response(request_id=request_id, data=job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request_id: Annotated[str, Depends(get_request_id)]) -> dict[str, Any]:
    """执行任务取消骨架接口。"""
    job = job_service.cancel_job(job_id=job_id)
    return build_success_response(request_id=request_id, data=job)
