"""封装作者分区存储路径生成与目录创建工具。"""

from __future__ import annotations

from pathlib import Path

from app.infra.settings import get_settings

settings = get_settings()
storage_root = Path(settings.storage_root)


def ensure_storage_root() -> Path:
    """确保存储根目录存在。"""
    storage_root.mkdir(parents=True, exist_ok=True)
    return storage_root


def author_root(author_id: str) -> Path:
    """返回作者分区根目录。"""
    return ensure_storage_root() / "authors" / author_id
