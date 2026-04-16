"""初始化 Celery 应用并提供任务队列基础配置。"""

from __future__ import annotations

from app.infra.settings import get_settings
from celery import Celery

settings = get_settings()

celery_app = Celery(
    "economist_agent_backend",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.services.stage_runners"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_eager_propagates,
)
