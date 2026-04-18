"""Add pipeline_jobs.model_config_json for per-job model override."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260418_0002"
down_revision = "20260416_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.drop_column("pipeline_jobs", "model_config_json")
