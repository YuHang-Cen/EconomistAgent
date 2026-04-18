"""Add pipeline_jobs.model_config_json for per-job model override."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260418_0002"
down_revision = "20260416_0001"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(item.get("name") == column_name for item in columns)


def upgrade() -> None:
    if not _has_column("pipeline_jobs", "model_config_json"):
        op.add_column(
            "pipeline_jobs",
            sa.Column(
                "model_config_json",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )


def downgrade() -> None:
    if _has_column("pipeline_jobs", "model_config_json"):
        op.drop_column("pipeline_jobs", "model_config_json")
