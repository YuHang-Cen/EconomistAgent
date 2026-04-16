"""配置后端日志格式与默认日志级别。"""

from __future__ import annotations

import logging


def configure_logging() -> None:
    """初始化基础日志配置。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
