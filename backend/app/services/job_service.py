"""提供任务创建、轮询、取消、重试与产物读取服务。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from zipfile import ZipFile

from app.domain.enums import JobStatus, JobType, OutputType, Stage
from app.domain.models import Author, AuthorDocument, PipelineJob
from app.infra import storage
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


def _parse_outputs(outputs_json: str) -> dict[str, Any]:
    """解析 outputs_json 为字典。"""
    try:
        parsed = json.loads(outputs_json or "{}")
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def _allowed_output_values() -> set[str]:
    """返回对外允许的产物类型集合。"""
    return {item.value for item in OutputType}


def _extract_public_outputs(outputs_json: str) -> dict[str, Any]:
    """过滤出对外允许读取的产物。"""
    outputs = _parse_outputs(outputs_json)
    allowed = _allowed_output_values()
    return {key: value for key, value in outputs.items() if key in allowed}


def _serialize_job(job: PipelineJob) -> dict[str, Any]:
    """将任务模型序列化为轮询响应结构。"""
    public_outputs = _extract_public_outputs(job.outputs_json or "{}")
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
        "outputsReady": bool(public_outputs),
    }


def _dispatch_job(job_id: str, job_type: str) -> None:
    """按任务类型分发 Celery 异步任务。"""
    from app.services import stage_runners

    if job_type == JobType.DOCUMENT_RELOAD.value:
        stage_runners.run_document_reload_pipeline.delay(job_id)
    elif job_type == JobType.AUTHOR_SKILLS.value:
        stage_runners.run_author_skills_pipeline.delay(job_id)
    elif job_type == JobType.AUTHOR_ANSWER.value:
        stage_runners.run_author_answer_pipeline.delay(job_id)


def create_document_reload_job(
    author_id: str, document_id: str, auto_run: bool = True
) -> dict[str, Any]:
    """创建文档重处理任务，并自动入队。"""
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
        created_job_id = job.job_id
        serialized = _serialize_job(job)

    if auto_run:
        _dispatch_job(job_id=created_job_id, job_type=JobType.DOCUMENT_RELOAD.value)
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
        except pipeline_service.PipelineCanceledError:
            now = _now_iso()
            job.status = JobStatus.CANCELED.value
            job.updated_at = now
            job.finished_at = now
            if job.document_id:
                document = session.get(AuthorDocument, job.document_id)
                if document is not None:
                    document.status = "active"
                    document.updated_at = now
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


def create_author_skills_job(author_id: str, auto_run: bool = True) -> dict[str, Any]:
    """创建 author_skills 任务并自动入队。"""
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
        created_job_id = job.job_id
        serialized = _serialize_job(job)

    if auto_run:
        _dispatch_job(job_id=created_job_id, job_type=JobType.AUTHOR_SKILLS.value)
    return serialized


def execute_author_skills_job(job_id: str) -> None:
    """执行 author_skills 任务并写回任务状态。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.job_type != JobType.AUTHOR_SKILLS.value:
            raise HTTPException(
                status_code=409, detail="job type does not support author_skills run"
            )
        if job.status == JobStatus.CANCELED.value:
            return
        try:
            pipeline_service.run_author_skills(session=session, job=job)
        except pipeline_service.PipelineCanceledError:
            now = _now_iso()
            job.status = JobStatus.CANCELED.value
            job.updated_at = now
            job.finished_at = now
        except Exception as exc:
            now = _now_iso()
            job.status = JobStatus.FAILED.value
            job.error_message = str(exc)
            job.updated_at = now
            job.finished_at = now


def create_author_answer_job(author_id: str, query: str, auto_run: bool = True) -> dict[str, Any]:
    """创建 author_answer 任务并自动入队。"""
    if not query.strip():
        raise HTTPException(status_code=422, detail="query is required")
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
        created_job_id = job.job_id
        serialized = _serialize_job(job)

    if auto_run:
        _dispatch_job(job_id=created_job_id, job_type=JobType.AUTHOR_ANSWER.value)
    return serialized


def execute_author_answer_job(job_id: str) -> None:
    """执行 author_answer 任务并写回任务状态。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.job_type != JobType.AUTHOR_ANSWER.value:
            raise HTTPException(
                status_code=409, detail="job type does not support author_answer run"
            )
        if job.status == JobStatus.CANCELED.value:
            return
        try:
            pipeline_service.run_author_answer(session=session, job=job)
        except pipeline_service.PipelineCanceledError:
            now = _now_iso()
            job.status = JobStatus.CANCELED.value
            job.updated_at = now
            job.finished_at = now
        except Exception as exc:
            now = _now_iso()
            job.status = JobStatus.FAILED.value
            job.error_message = str(exc)
            job.updated_at = now
            job.finished_at = now


def get_job(job_id: str) -> dict[str, Any]:
    """读取单个任务轮询状态。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _serialize_job(job)


def _read_output_content(uri: str) -> Any:
    """根据 URI 读取产物内容。"""
    path = storage.resolve_storage_uri(uri)
    if not path.exists():
        raise HTTPException(status_code=404, detail="output not found")

    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix == ".md":
        return path.read_text(encoding="utf-8")
    if suffix == ".zip":
        with ZipFile(path, mode="r") as zip_file:
            return {"uri": uri, "files": sorted(zip_file.namelist())}

    return path.read_text(encoding="utf-8")


def list_outputs(job_id: str) -> list[dict[str, Any]]:
    """读取任务产物清单（仅返回 V3 允许类型）。"""
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        outputs = _extract_public_outputs(job.outputs_json or "{}")
        return [{"type": key} for key in sorted(outputs.keys())]


def get_output(job_id: str, output_type: str) -> dict[str, Any]:
    """读取指定任务产物（仅支持 V3 允许类型）。"""
    if output_type not in _allowed_output_values():
        raise HTTPException(status_code=422, detail="invalid output type")
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        outputs = _extract_public_outputs(job.outputs_json or "{}")
        output_uri = outputs.get(output_type)
        if not isinstance(output_uri, str) or not output_uri.strip():
            raise HTTPException(status_code=404, detail="output not found")
        content = _read_output_content(output_uri)
        return {"type": output_type, "content": content}


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
        resolved_job_id = job.job_id
        job_type = job.job_type

    _dispatch_job(job_id=resolved_job_id, job_type=job_type)
    return get_job(job_id=resolved_job_id)


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
