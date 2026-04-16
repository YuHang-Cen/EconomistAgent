"""初始化 SQLAlchemy 引擎、会话工厂与基础模型。"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from app.infra.settings import get_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

settings = get_settings()


def _ensure_sqlite_directory(database_url: str) -> None:
    """当使用 sqlite 文件库时，确保数据库目录存在。"""
    if not database_url.startswith("sqlite:///") or database_url.endswith(":memory:"):
        return
    sqlite_path = database_url.replace("sqlite:///", "", 1)
    db_file = Path(sqlite_path)
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file
    db_file.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(settings.database_url)


class Base(DeclarativeBase):
    """声明 SQLAlchemy 基础模型类。"""


engine = create_engine(
    settings.database_url,
    future=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """提供数据库会话依赖。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """提供带自动提交与回滚语义的数据库会话。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
