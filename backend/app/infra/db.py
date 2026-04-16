"""初始化 SQLAlchemy 引擎、会话工厂与基础模型。"""

from __future__ import annotations

from collections.abc import Generator

from app.infra.settings import get_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

settings = get_settings()


class Base(DeclarativeBase):
    """声明 SQLAlchemy 基础模型类。"""


engine = create_engine(
    settings.database_url,
    future=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """提供数据库会话依赖。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
