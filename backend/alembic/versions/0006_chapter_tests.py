"""End-of-chapter listening tests."""

import sqlalchemy as sa

from alembic import op

revision = "0006_chapter_tests"
down_revision = "0005_visits"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "chapter_tests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chapter", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chapter_tests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapter_tests")),
    )
    op.create_index(
        "ix_chapter_tests_user_chapter_created",
        "chapter_tests",
        ["user_id", "chapter", "created_at"],
    )
    op.create_table(
        "chapter_test_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("part", sa.String(length=32), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("answer_index", sa.Integer(), nullable=False),
        sa.Column("choice", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name=op.f("fk_chapter_test_questions_item_id_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_id"],
            ["chapter_tests.id"],
            name=op.f("fk_chapter_test_questions_test_id_chapter_tests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapter_test_questions")),
        sa.UniqueConstraint(
            "test_id", "position", name=op.f("uq_chapter_test_questions_test_id_position")
        ),
    )
    op.create_index(
        op.f("ix_chapter_test_questions_item_id"), "chapter_test_questions", ["item_id"]
    )

def downgrade() -> None:
    op.drop_index(op.f("ix_chapter_test_questions_item_id"), table_name="chapter_test_questions")
    op.drop_table("chapter_test_questions")
    op.drop_index("ix_chapter_tests_user_chapter_created", table_name="chapter_tests")
    op.drop_table("chapter_tests")
