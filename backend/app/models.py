"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (CheckConstraint("id ~ '^[a-z0-9-]{1,64}$'", name="games_id_format"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoreSubmission(Base):
    """Append-only history of every score submitted."""

    __tablename__ = "score_submissions"
    __table_args__ = (
        CheckConstraint("score >= 0", name="score_submissions_score_non_negative"),
        Index("ix_score_submissions_game_user", "game_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(Text, ForeignKey("games.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(BigInteger)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LeaderboardEntry(Base):
    """A user's best score for a game. Ranking order: best_score DESC, achieved_at, user_id."""

    __tablename__ = "leaderboard_entries"
    __table_args__ = (
        CheckConstraint("best_score >= 0", name="leaderboard_entries_score_non_negative"),
    )

    game_id: Mapped[str] = mapped_column(
        Text, ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    best_score: Mapped[int] = mapped_column(BigInteger)
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Supports top-N and "rows ahead of me" scans in ranking order.
Index(
    "ix_leaderboard_entries_ranking",
    LeaderboardEntry.game_id,
    LeaderboardEntry.best_score.desc(),
    LeaderboardEntry.achieved_at,
    LeaderboardEntry.user_id,
)
