"""定义作者、文档、章节、段落、任务与快照的 SQLAlchemy 模型骨架。"""

from __future__ import annotations

from datetime import datetime

from app.infra.db import Base
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class Author(Base):
    """作者实体模型。"""

    __tablename__ = "authors"

    author_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class AuthorDocument(Base):
    """作者文档实体模型。"""

    __tablename__ = "author_documents"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    book_title: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class DocumentChapter(Base):
    """文档章节实体模型。"""

    __tablename__ = "document_chapters"

    chapter_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chapter_title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class DocumentSegment(Base):
    """文档段落实体模型。"""

    __tablename__ = "document_segments"

    segment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chapter_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class AuthorSkillSnapshot(Base):
    """作者技能快照实体模型。"""

    __tablename__ = "author_skill_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    outputs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class PipelineJob(Base):
    """流水线任务实体模型。"""

    __tablename__ = "pipeline_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outputs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: datetime.utcnow().isoformat()
    )
    finished_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
