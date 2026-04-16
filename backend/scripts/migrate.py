"""提供数据库迁移脚本入口，统一调用 Alembic 升级命令。"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """执行 alembic upgrade head。"""
    result = subprocess.run(["alembic", "-c", "alembic.ini", "upgrade", "head"], check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    sys.exit(main())
