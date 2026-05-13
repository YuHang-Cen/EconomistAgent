"""Load backend settings and normalize runtime filesystem paths."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)

SQLITE_URL_PREFIX = "sqlite:///"


def _normalize_windows_drive_path(raw_path: str) -> str:
    """Normalize '/C:/...' to 'C:/...' for Windows sqlite URLs."""
    if (
        os.name == "nt"
        and len(raw_path) >= 4
        and raw_path[0] == "/"
        and raw_path[2] == ":"
    ):
        return raw_path[1:]
    return raw_path


def resolve_sqlite_database_path(
    database_url: str, *, project_root: Path = PROJECT_ROOT
) -> Path | None:
    """Resolve sqlite DB file path; relative paths are rooted at project root."""
    if not database_url.startswith(SQLITE_URL_PREFIX) or database_url.endswith(":memory:"):
        return None

    raw_path = database_url[len(SQLITE_URL_PREFIX) :]
    if not raw_path.strip():
        return None
    raw_path = _normalize_windows_drive_path(raw_path)

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def normalize_database_url(database_url: str, *, project_root: Path = PROJECT_ROOT) -> str:
    """Return absolute sqlite URL; leave non-sqlite URLs unchanged."""
    resolved = resolve_sqlite_database_path(database_url, project_root=project_root)
    if resolved is None:
        return database_url
    return f"{SQLITE_URL_PREFIX}{resolved.as_posix()}"


def normalize_storage_root(storage_root: str, *, project_root: Path = PROJECT_ROOT) -> Path:
    """Resolve storage root to absolute path based on project root."""
    value = storage_root.strip() if isinstance(storage_root, str) else str(storage_root)
    candidate = Path(value or "storage")
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


class Settings(BaseSettings):
    """Backend runtime settings."""

    app_name: str = "Economist Agent Backend"
    api_key: str = Field(default="")
    provider: str = Field(default="deepseek")
    model_name: str = Field(default="deepseek-chat")
    api_base: str = Field(default="https://api.deepseek.com")
    deepseek_api_key: str = Field(default="")
    database_url: str = Field(default="sqlite:///./storage/app.db")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0")
    storage_root: str = Field(default="storage")
    cors_allow_origins: str = Field(
        default=(
            "http://localhost:3000,"
            "http://127.0.0.1:3000,"
            "http://localhost:5173,"
            "http://127.0.0.1:5173"
        )
    )
    celery_task_always_eager: bool = Field(default=False)
    celery_task_eager_propagates: bool = Field(default=True)
    method_chunk_max_words: int = Field(default=1200)
    skills_batch_size: int = Field(default=2)
    skills_max_main_skills: int = Field(default=0)
    skills_select_recall_limit: int = Field(default=20)
    skills_select_count: int = Field(
        default=3,
        description="Maximum number of main skills selected for one answer.",
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def normalized_database_url(self) -> str:
        return normalize_database_url(self.database_url, project_root=PROJECT_ROOT)

    @property
    def resolved_storage_root(self) -> Path:
        return normalize_storage_root(self.storage_root, project_root=PROJECT_ROOT)

    def get_cors_allow_origins(self) -> list[str]:
        raw = self.cors_allow_origins
        if isinstance(raw, list):
            values = [str(item).strip() for item in raw]
        elif isinstance(raw, str):
            values = [item.strip() for item in raw.split(",")]
        else:
            values = [str(raw).strip()]
        return [item for item in values if item]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings object."""
    return Settings()
