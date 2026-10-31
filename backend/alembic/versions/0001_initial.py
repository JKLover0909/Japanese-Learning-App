"""Initial schema.

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# UTCDateTime uses SQLAlchemy's DATETIME representation. SQLite stores naive UTC.
def _utc_datetime() -> sa.DateTime:
    return sa.DateTime()


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lessons")),
        sa.UniqueConstraint("slug", name=op.f("uq_lessons_slug")),
    )
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("meaning", sa.String(length=160), nullable=True),
        sa.Column("readings", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name=op.f("fk_items_lesson_id_lessons"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items")),
        sa.UniqueConstraint("lesson_id", "key", name=op.f("uq_items_lesson_id_key")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("expires_at", _utc_datetime(), nullable=False),
        sa.Column("last_used_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"])
    op.create_table(
        "item_progress",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("wrong_count", sa.Integer(), nullable=False),
        sa.Column("weakness", sa.Integer(), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", _utc_datetime(), nullable=True),
        sa.Column("last_wrong_at", _utc_datetime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name=op.f("fk_item_progress_item_id_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_item_progress_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "item_id", name=op.f("pk_item_progress")),
    )
    op.create_index(op.f("ix_item_progress_item_id"), "item_progress", ["item_id"])
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("focus_count", sa.Integer(), nullable=False),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("completed_at", _utc_datetime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name=op.f("fk_practice_sessions_lesson_id_lessons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_practice_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_sessions")),
    )
    op.create_index(
        "ix_practice_sessions_user_lesson_status",
        "practice_sessions",
        ["user_id", "lesson_id", "status"],
    )
    op.create_index(
        "ix_practice_sessions_user_created", "practice_sessions", ["user_id", "created_at"]
    )
    op.create_table(
        "session_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("is_focus", sa.Boolean(), nullable=False),
        sa.Column("answer", sa.String(length=200), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("answered_at", _utc_datetime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name=op.f("fk_session_questions_item_id_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.id"],
            name=op.f("fk_session_questions_session_id_practice_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_questions")),
        sa.UniqueConstraint(
            "session_id", "position", name=op.f("uq_session_questions_session_id_position")
        ),
    )
    op.create_index(op.f("ix_session_questions_item_id"), "session_questions", ["item_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_session_questions_item_id"), table_name="session_questions")
    op.drop_table("session_questions")
    op.drop_index("ix_practice_sessions_user_created", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_user_lesson_status", table_name="practice_sessions")
    op.drop_table("practice_sessions")
    op.drop_index(op.f("ix_item_progress_item_id"), table_name="item_progress")
    op.drop_table("item_progress")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("items")
    op.drop_table("lessons")
    op.drop_table("users")
