"""提供任务创建、轮询、取消与重试服务，落地 PipelineJob 状态机。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import JobStatus, JobType, Stage
from app.domain.models import Author, AuthorDocument, PipelineJob
from app.infra.db import session_scope
from app.services import pipeline_service
from fastapi import HTTPException


def _now_iso() -> str:
    """返回 UTC ISO 8601 时间字符串。"""
    return datetime.now(tz=UTC).isoformat()


def _job_start_stage(job_type: str) -> Stage:
    """根据任务类型返回默认起始阶段。"""
    if job_type == JobType.AUTHOR_SKILLS.value:
        return Stage.ANALYZE
    if job_type == JobType.DOCUMENT_RELOAD.value:
        return Stage.EXTRACT
    return Stage.SELECT_SKILLS


def _serialize_job(job: PipelineJob) -> dict[str, Any]:
    """将任务模型序列化为轮询响应结构。"""
    outputs_ready = False
    try:
        outputs_ready = bool(json.loads(job.outputs_json or "{}"))
    except json.JSONDecodeError:
        outputs_ready = False

    return {
        "jobId": job.job_id,
        "authorId": job.author_id,
        "documentId": job.document_id,
        "jobType": job.job_type,
        "status": job.status,
        "currentStage": job.current_stage,
        "progress": job.progress,
        "errorMessage": job.error_message,
        "retryable": job.status in {JobStatus.FAILED.value, JobStatus.CANCELED.value},
        "outputsReady": outputs_ready,
    }


def create_document_reload_job(
    author_id: str, document_id: str, auto_run: bool = False
) -> dict[str, Any]:
    """创建文档重处理任务，并可选择立即执行。"""
    now = _now_iso()
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")
        document = session.get(AuthorDocument, document_id)
        if document is None or document.author_id != author_id:
            raise HTTPException(status_code=404, detail="document not found")

        document.status = "processing"
        document.updated_at = now

        job = PipelineJob(
            job_id=str(uuid.uuid4()),
            author_id=author_id,
            document_id=document_id,
            job_type=JobType.DOCUMENT_RELOAD.value,
            status=JobStatus.QUEUED.value,
            current_stage=Stage.EXTRACT.value,
            progress=0,
            query=None,
            snapshot_id=None,
            outputs_json="{}",
            error_message=None,
            created_at=now,
            updated_at=now,
            finished_at=None,
        )
        session.add(job)
        session.flush()
        serialized = _serialize_job(job)
        job_id = job.job_id

    if auto_run:
        execute_document_reload_job(job_id=job_id)
        return get_job(job_id=job_id)
    return serialized


def execute_document_reload_job(job_id: str) -> None:
    """执行 document_reload 任务并写回任务状态。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.job_type != JobType.DOCUMENT_RELOAD.value:
            raise HTTPException(
                status_code=409, detail="job type does not support document_reload run"
            )
        if job.status == JobStatus.CANCELED.value:
            return
        try:
            pipeline_service.run_document_reload(session=session, job=job)
        except Exception as exc:
            now = _now_iso()
            job.status = JobStatus.FAILED.value
            job.error_message = str(exc)
            job.updated_at = now
            job.finished_at = now
            if job.document_id:
                document = session.get(AuthorDocument, job.document_id)
                if document is not None:
                    document.status = "failed"
                    document.updated_at = now


def create_author_skills_job(author_id: str) -> dict[str, Any]:
    """创建 author_skills 任务。"""
    now = _now_iso()
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")
        job = PipelineJob(
            job_id=str(uuid.uuid4()),
            author_id=author_id,
            document_id=None,
            job_type=JobType.AUTHOR_SKILLS.value,
            status=JobStatus.QUEUED.value,
            current_stage=Stage.ANALYZE.value,
            progress=0,
            query=None,
            snapshot_id=None,
            outputs_json="{}",
            error_message=None,
            created_at=now,
            updated_at=now,
            finished_at=None,
        )
        session.add(job)
        session.flush()
        return _serialize_job(job)


def create_author_answer_job(author_id: str, query: str) -> dict[str, Any]:
    """创建 author_answer 任务。"""
    now = _now_iso()
    with session_scope() as session:
        author = session.get(Author, author_id)
        if author is None:
            raise HTTPException(status_code=404, detail="author not found")
        job = PipelineJob(
            job_id=str(uuid.uuid4()),
            author_id=author_id,
            document_id=None,
            job_type=JobType.AUTHOR_ANSWER.value,
            status=JobStatus.QUEUED.value,
            current_stage=Stage.SELECT_SKILLS.value,
            progress=0,
            query=query,
            snapshot_id=None,
            outputs_json="{}",
            error_message=None,
            created_at=now,
            updated_at=now,
            finished_at=None,
        )
        session.add(job)
        session.flush()
        return _serialize_job(job)


def get_job(job_id: str) -> dict[str, Any]:
    """读取单个任务轮询状态。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _serialize_job(job)


def list_outputs(job_id: str) -> list[dict[str, Any]]:
    """读取任务产物清单。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        try:
            outputs = json.loads(job.outputs_json or "{}")
        except json.JSONDecodeError:
            outputs = {}
        return [{"type": key, "uri": value} for key, value in outputs.items()]


def get_output(job_id: str, output_type: str) -> dict[str, str]:
    """读取指定任务产物。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        try:
            outputs = json.loads(job.outputs_json or "{}")
        except json.JSONDecodeError:
            outputs = {}
        if output_type not in outputs:
            raise HTTPException(status_code=404, detail="output not found")
        return {"type": output_type, "uri": str(outputs[output_type])}


def retry_job(job_id: str) -> dict[str, Any]:
    """重试失败或取消任务。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.status not in {JobStatus.FAILED.value, JobStatus.CANCELED.value}:
            raise HTTPException(status_code=409, detail="job is not retryable")
        now = _now_iso()
        job.status = JobStatus.QUEUED.value
        job.current_stage = _job_start_stage(job.job_type).value
        job.progress = 0
        job.error_message = None
        job.finished_at = None
        job.updated_at = now
        job.outputs_json = "{}"
        serialized = _serialize_job(job)
        job_type = job.job_type
        resolved_job_id = job.job_id

    if job_type == JobType.DOCUMENT_RELOAD.value:
        execute_document_reload_job(job_id=resolved_job_id)
        return get_job(job_id=resolved_job_id)
    return serialized


def cancel_job(job_id: str) -> dict[str, Any]:
    """取消 queued/running 任务。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.status in {
            JobStatus.SUCCESS.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELED.value,
        }:
            raise HTTPException(status_code=409, detail="job is not cancelable")
        now = _now_iso()
        job.status = JobStatus.CANCELED.value
        job.updated_at = now
        job.finished_at = now
        return _serialize_job(job)
