"""提供 uv run 命令入口，统一启动开发服务与工程检查。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


def _run(command: Sequence[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def dev() -> None:
    """启动 FastAPI 开发服务器。"""
    raise SystemExit(_run(["uvicorn", "app.main:app", "--reload"]))


def worker() -> None:
    """启动 Celery worker。"""
    raise SystemExit(
        _run(["celery", "-A", "app.infra.queue:celery_app", "worker", "--loglevel=info"])
    )


def lint() -> None:
    """执行 Ruff 静态检查。"""
    raise SystemExit(_run(["ruff", "check", "app", "scripts", "tests", "alembic"]))


def format_code() -> None:
    """执行 Ruff 代码格式化。"""
    raise SystemExit(_run(["ruff", "format", "app", "scripts", "tests", "alembic"]))


def typecheck() -> None:
    """执行 Mypy 类型检查。"""
    raise SystemExit(_run(["mypy", "app"]))


def test() -> None:
    """执行 Pytest 测试。"""
    raise SystemExit(_run(["python", "-m", "pytest", "-q"]))


if __name__ == "__main__":
    sys.exit(_run(["uvicorn", "app.main:app", "--reload"]))
