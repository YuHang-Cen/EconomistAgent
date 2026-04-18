"""统一加载后端配置并从 backend/.env 读取环境变量。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    """后端运行配置。"""

    app_name: str = "Economist Agent Backend"
    api_key: str = Field(default="")
    provider: str = Field(default="deepseek")
    model_name: str = Field(default="deepseek-chat")
    api_base: str = Field(default="https://api.deepseek.com")
    deepseek_api_key: str = Field(default="")
    database_url: str = Field(default="sqlite:///./storage/app.db")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0")
    storage_root: str = Field(default="storage")
    celery_task_always_eager: bool = Field(default=False)
    celery_task_eager_propagates: bool = Field(default=True)
    method_chunk_max_words: int = Field(default=1200)
    skills_batch_size: int = Field(default=2)
    skills_max_main_skills: int = Field(default=6)

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取缓存后的配置对象。"""
    return Settings()
