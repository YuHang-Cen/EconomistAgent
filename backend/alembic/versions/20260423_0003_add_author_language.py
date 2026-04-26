"""Add authors.language with english default for bilingual pipelines."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260423_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(item.get("name") == column_name for item in columns)


def upgrade() -> None:
    if not _has_column("authors", "language"):
        op.add_column(
            "authors",
            sa.Column(
                "language",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'english'"),
            ),
        )
    op.execute("UPDATE authors SET language = 'english' WHERE language IS NULL OR language = ''")


def downgrade() -> None:
    if _has_column("authors", "language"):
        op.drop_column("authors", "language")
