"""协调 author_skills、document_reload、author_answer 三类流水线任务。"""

from __future__ import annotations


def run_author_skills(job_id: str) -> dict[str, str]:
    """执行作者技能流水线骨架逻辑。"""
    return {"jobId": job_id, "pipeline": "author_skills"}


def run_document_reload(job_id: str) -> dict[str, str]:
    """执行文档重处理流水线骨架逻辑。"""
    return {"jobId": job_id, "pipeline": "document_reload"}


def run_author_answer(job_id: str) -> dict[str, str]:
    """执行作者问答流水线骨架逻辑。"""
    return {"jobId": job_id, "pipeline": "author_answer"}
