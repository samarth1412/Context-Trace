"""Add external RAG endpoints.

Revision ID: 0003_external_rag_endpoints
Revises: 0002_eval_sets
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_external_rag_endpoints"
down_revision: str | None = "0002_eval_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_rag_endpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("headers_json", sa.JSON(), nullable=False),
        sa.Column("body_template_json", sa.JSON(), nullable=False),
        sa.Column("response_mapping_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_external_rag_endpoints_project_name"),
    )


def downgrade() -> None:
    op.drop_table("external_rag_endpoints")
