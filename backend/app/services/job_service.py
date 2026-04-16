"""提供任务创建、轮询、取消与重试的应用服务骨架。"""

from __future__ import annotations

import uuid

from app.domain.enums import JobStatus, JobType, Stage


def create_author_skills_job(author_id: str) -> dict[str, str | int | bool]:
    """创建 author_skills 任务骨架结果。"""
    return {
        "jobId": str(uuid.uuid4()),
        "authorId": author_id,
        "jobType": JobType.AUTHOR_SKILLS.value,
        "status": JobStatus.QUEUED.value,
        "currentStage": Stage.ANALYZE.value,
        "progress": 0,
    }


def create_author_answer_job(author_id: str, query: str) -> dict[str, str | int]:
    """创建 author_answer 任务骨架结果。"""
    _ = query
    return {
        "jobId": str(uuid.uuid4()),
        "authorId": author_id,
        "jobType": JobType.AUTHOR_ANSWER.value,
        "status": JobStatus.QUEUED.value,
        "currentStage": Stage.SELECT_SKILLS.value,
        "progress": 0,
    }


def get_job(job_id: str) -> dict[str, str | int | bool | None]:
    """读取任务轮询骨架结果。"""
    return {
        "jobId": job_id,
        "status": JobStatus.RUNNING.value,
        "currentStage": Stage.ANALYZE.value,
        "progress": 10,
        "errorMessage": None,
        "retryable": True,
        "outputsReady": False,
    }


def list_outputs(job_id: str) -> list[dict[str, str]]:
    """读取任务产物清单骨架结果。"""
    _ = job_id
    return []


def get_output(job_id: str, output_type: str) -> dict[str, str]:
    """读取指定任务产物骨架结果。"""
    return {"jobId": job_id, "type": output_type, "uri": ""}


def retry_job(job_id: str) -> dict[str, str]:
    """执行任务重试骨架逻辑。"""
    return {"jobId": job_id, "status": JobStatus.QUEUED.value}


def cancel_job(job_id: str) -> dict[str, str]:
    """执行任务取消骨架逻辑。"""
    return {"jobId": job_id, "status": JobStatus.CANCELED.value}
