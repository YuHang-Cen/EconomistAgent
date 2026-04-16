"""创建 V3 约定的六张核心业务表。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260416_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级数据库结构。"""
    op.create_table(
        "authors",
        sa.Column("author_id", sa.String(length=64), primary_key=True),
        sa.Column("author_name", sa.String(length=255), nullable=False),
        sa.Column("school", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )

    op.create_table(
        "author_documents",
        sa.Column("document_id", sa.String(length=64), primary_key=True),
        sa.Column("author_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("book_title", sa.String(length=255), nullable=False),
        sa.Column("pdf_uri", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )

    op.create_table(
        "document_chapters",
        sa.Column("chapter_id", sa.String(length=64), primary_key=True),
        sa.Column("document_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("chapter_title", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("document_id", "chapter_title", name="uq_chapter_title"),
    )

    op.create_table(
        "document_segments",
        sa.Column("segment_id", sa.String(length=64), primary_key=True),
        sa.Column("document_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("chapter_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_id", name="uq_segment_chunk"),
    )

    op.create_table(
        "author_skill_snapshots",
        sa.Column("snapshot_id", sa.String(length=64), primary_key=True),
        sa.Column("author_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("outputs_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )

    op.create_table(
        "pipeline_jobs",
        sa.Column("job_id", sa.String(length=64), primary_key=True),
        sa.Column("author_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("document_id", sa.String(length=64), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=32), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("outputs_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.Column("finished_at", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """回滚数据库结构。"""
    op.drop_table("pipeline_jobs")
    op.drop_table("author_skill_snapshots")
    op.drop_table("document_segments")
    op.drop_table("document_chapters")
    op.drop_table("author_documents")
    op.drop_table("authors")
