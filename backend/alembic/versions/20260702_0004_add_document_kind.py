"""Add author_documents.document_kind with book default."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260702_0004"
down_revision = "20260423_0003"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(item.get("name") == column_name for item in columns)


def upgrade() -> None:
    if not _has_column("author_documents", "document_kind"):
        op.add_column(
            "author_documents",
            sa.Column(
                "document_kind",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'book'"),
            ),
        )
    op.execute(
        "UPDATE author_documents SET document_kind = 'book' "
        "WHERE document_kind IS NULL OR document_kind = ''"
    )


def downgrade() -> None:
    if _has_column("author_documents", "document_kind"):
        op.drop_column("author_documents", "document_kind")
