"""Coarse visit counts without IPs or user agents."""

import sqlalchemy as sa

from alembic import op

revision = "0005_visits"
down_revision = "0004_admin_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("anonymous_identities") as batch:
        batch.add_column(sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE anonymous_identities SET last_seen_at = created_at")
    with op.batch_alter_table("anonymous_identities") as batch:
        batch.alter_column("last_seen_at", existing_type=sa.DateTime(), nullable=False)
        batch.create_index("ix_anonymous_identities_last_seen_at", ["last_seen_at"])
    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "identity_id",
            sa.Integer(),
            sa.ForeignKey("anonymous_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("visited_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_visits_identity_id", "visits", ["identity_id"])
    op.create_index("ix_visits_visited_at", "visits", ["visited_at"])


def downgrade() -> None:
    op.drop_table("visits")
    with op.batch_alter_table("anonymous_identities") as batch:
        batch.drop_index("ix_anonymous_identities_last_seen_at")
        batch.drop_column("last_seen_at")
