"""提供 Celery worker 启动脚本入口。"""

from __future__ import annotations

from app.infra.queue import celery_app


def main() -> None:
    """以标准参数启动 Celery worker。"""
    celery_app.worker_main(["worker", "--loglevel=info"])


if __name__ == "__main__":
    main()
