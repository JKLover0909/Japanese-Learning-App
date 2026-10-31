"""Add browser-scoped anonymous learner identities.

Revision ID: 0002_anonymous_identity
Revises: 0001_initial
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_anonymous_identity"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anonymous_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_anonymous_identities_user_id", "anonymous_identities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_anonymous_identities_user_id", table_name="anonymous_identities")
    op.drop_table("anonymous_identities")
