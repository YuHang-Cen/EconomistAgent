"""Initialize SQLAlchemy engine, sessions, and transaction helpers."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from app.infra.settings import get_settings, resolve_sqlite_database_path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

settings = get_settings()
database_url = settings.normalized_database_url


def _ensure_sqlite_directory(url: str) -> None:
    """Ensure sqlite DB parent directory exists for file-based URLs."""
    db_file = resolve_sqlite_database_path(url)
    if db_file is None:
        return
    db_file.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(database_url)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


engine = create_engine(
    database_url,
    future=True,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """Yield request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide transactional session with commit/rollback semantics."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

