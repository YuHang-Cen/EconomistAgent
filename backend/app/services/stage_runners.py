"""定义 Celery 任务入口并分发到对应流水线执行函数。"""

from __future__ import annotations

from app.infra.queue import celery_app
from app.services import job_service


@celery_app.task(name="pipeline.author_skills")
def run_author_skills_pipeline(job_id: str) -> dict[str, str]:
    """执行 author_skills 任务。"""
    job_service.execute_author_skills_job(job_id=job_id)
    return {"jobId": job_id, "pipeline": "author_skills"}


@celery_app.task(name="pipeline.document_reload")
def run_document_reload_pipeline(job_id: str) -> dict[str, str]:
    """执行 document_reload 任务。"""
    job_service.execute_document_reload_job(job_id=job_id)
    return {"jobId": job_id, "pipeline": "document_reload"}


@celery_app.task(name="pipeline.author_answer")
def run_author_answer_pipeline(job_id: str) -> dict[str, str]:
    """执行 author_answer 任务。"""
    job_service.execute_author_answer_job(job_id=job_id)
    return {"jobId": job_id, "pipeline": "author_answer"}
