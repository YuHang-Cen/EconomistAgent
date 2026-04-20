"""封装作者分区存储路径、产物落盘与 URI 解析能力。"""

from __future__ import annotations

import json
import shutil
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.infra.settings import get_settings

settings = get_settings()
storage_root = settings.resolved_storage_root


def ensure_storage_root() -> Path:
    """确保存储根目录存在。"""
    storage_root.mkdir(parents=True, exist_ok=True)
    return storage_root


def author_root(author_id: str) -> Path:
    """返回作者分区根目录。"""
    return ensure_storage_root() / "authors" / author_id


def document_root(author_id: str, document_id: str) -> Path:
    """返回作者文档目录。"""
    path = author_root(author_id) / "documents" / document_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def job_root(author_id: str, job_id: str) -> Path:
    """返回作者任务目录。"""
    path = author_root(author_id) / "jobs" / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot_root(author_id: str, snapshot_id: str) -> Path:
    """返回作者快照目录。"""
    path = author_root(author_id) / "snapshots" / snapshot_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def answer_root(author_id: str, job_id: str) -> Path:
    """返回作者回答产物目录。"""
    path = author_root(author_id) / "answers" / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def delete_answer_root(author_id: str, job_id: str) -> None:
    """Delete one answer artifact directory if it exists."""
    path = author_root(author_id) / "answers" / job_id
    if not path.exists():
        return
    shutil.rmtree(path)


def delete_author_root(author_id: str) -> None:
    """Delete the author storage directory if it exists."""
    path = author_root(author_id)
    if not path.exists():
        return
    shutil.rmtree(path)


def _to_storage_uri(path: Path) -> str:
    """将绝对路径转换为 storage 开头的相对 URI。"""
    root = ensure_storage_root().resolve()
    resolved = path.resolve()
    relative = resolved.relative_to(root.parent)
    return relative.as_posix()


def resolve_storage_uri(uri: str) -> Path:
    """将 storage URI 解析为绝对路径。"""
    raw = Path(uri)
    if raw.is_absolute():
        return raw
    if raw.parts and raw.parts[0] == ensure_storage_root().name:
        return (ensure_storage_root().parent / raw).resolve()
    return (ensure_storage_root() / raw).resolve()


def write_text(path: Path, content: str) -> str:
    """写入文本文件并返回 URI。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return _to_storage_uri(path)


def write_json(path: Path, payload: object) -> str:
    """写入 JSON 文件并返回 URI。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _to_storage_uri(path)


def write_zip_from_files(path: Path, files: list[tuple[str, str]]) -> str:
    """根据文本文件列表生成 ZIP 并返回 URI。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for filename, content in files:
            zip_file.writestr(filename, content)
    path.write_bytes(buffer.getvalue())
    return _to_storage_uri(path)
