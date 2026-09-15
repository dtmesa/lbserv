"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id ~ '^[a-z0-9-]{1,64}$'", name="games_id_format"),
    )
    op.create_table(
        "score_submissions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id", sa.Text(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("score", sa.BigInteger(), nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("score >= 0", name="score_submissions_score_non_negative"),
    )
    op.create_index("ix_score_submissions_game_user", "score_submissions", ["game_id", "user_id"])
    op.create_table(
        "leaderboard_entries",
        sa.Column(
            "game_id", sa.Text(), sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("best_score", sa.BigInteger(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("best_score >= 0", name="leaderboard_entries_score_non_negative"),
    )
    op.create_index(
        "ix_leaderboard_entries_ranking",
        "leaderboard_entries",
        ["game_id", sa.text("best_score DESC"), "achieved_at", "user_id"],
    )


def downgrade() -> None:
    op.drop_table("leaderboard_entries")
    op.drop_table("score_submissions")
    op.drop_table("games")
