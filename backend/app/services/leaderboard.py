"""Leaderboard domain logic.

Ranking is a total order: best_score DESC, achieved_at ASC (earlier wins ties), user_id ASC.
A user's rank is 1 + the number of entries ahead of them in that order.
"""

from sqlalchemy import ColumnElement, and_, func, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.problems import GameAlreadyExists, GameNotFound, UserNotRanked
from app.realtime import CHANNEL

LE = models.LeaderboardEntry
RANK_ORDER = (LE.best_score.desc(), LE.achieved_at.asc(), LE.user_id.asc())
REVERSE_RANK_ORDER = (LE.best_score.asc(), LE.achieved_at.desc(), LE.user_id.desc())


# --- Games -----------------------------------------------------------------


async def list_games(session: AsyncSession) -> list[models.Game]:
    result = await session.scalars(select(models.Game).order_by(models.Game.name))
    return list(result)


async def create_game(session: AsyncSession, data: schemas.GameCreate) -> models.Game:
    game = models.Game(id=data.id, name=data.name)
    session.add(game)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise GameAlreadyExists(data.id) from exc
    await session.refresh(game)
    return game


async def ensure_game(session: AsyncSession, game_id: str) -> None:
    if await session.get(models.Game, game_id) is None:
        raise GameNotFound(game_id)


# --- Ranking helpers -------------------------------------------------------


def _ahead_of(entry: models.LeaderboardEntry) -> ColumnElement[bool]:
    return and_(
        LE.game_id == entry.game_id,
        or_(
            LE.best_score > entry.best_score,
            and_(
                LE.best_score == entry.best_score,
                tuple_(LE.achieved_at, LE.user_id)
                < tuple_(literal(entry.achieved_at), literal(entry.user_id)),
            ),
        ),
    )


def _behind(entry: models.LeaderboardEntry) -> ColumnElement[bool]:
    return and_(
        LE.game_id == entry.game_id,
        or_(
            LE.best_score < entry.best_score,
            and_(
                LE.best_score == entry.best_score,
                tuple_(LE.achieved_at, LE.user_id)
                > tuple_(literal(entry.achieved_at), literal(entry.user_id)),
            ),
        ),
    )


async def _rank_of(session: AsyncSession, entry: models.LeaderboardEntry) -> int:
    ahead = await session.scalar(select(func.count()).select_from(LE).where(_ahead_of(entry)))
    return (ahead or 0) + 1


async def _total_players(session: AsyncSession, game_id: str) -> int:
    total = await session.scalar(select(func.count()).select_from(LE).where(LE.game_id == game_id))
    return total or 0


def _to_entry(row: models.LeaderboardEntry, rank: int) -> schemas.LeaderboardEntry:
    return schemas.LeaderboardEntry(
        rank=rank, user_id=row.user_id, score=row.best_score, achieved_at=row.achieved_at
    )


# --- Scores ----------------------------------------------------------------


async def submit_score(
    session: AsyncSession, game_id: str, data: schemas.ScoreSubmission
) -> schemas.ScoreSubmissionResult:
    await ensure_game(session, game_id)
    session.add(models.ScoreSubmission(game_id=game_id, user_id=data.user_id, score=data.score))

    insert_stmt = insert(LE).values(
        game_id=game_id,
        user_id=data.user_id,
        best_score=data.score,
        achieved_at=func.clock_timestamp(),
    )
    # Atomic "keep the max": the conflicting row is locked, so concurrent submissions serialize.
    upsert = insert_stmt.on_conflict_do_update(
        index_elements=[LE.game_id, LE.user_id],
        set_={
            "best_score": insert_stmt.excluded.best_score,
            "achieved_at": insert_stmt.excluded.achieved_at,
            "updated_at": func.now(),
        },
        where=LE.best_score < insert_stmt.excluded.best_score,
    ).returning(LE.user_id)
    improved = (await session.execute(upsert)).first() is not None

    entry = await session.get(LE, (game_id, data.user_id), populate_existing=True)
    if entry is None:  # pragma: no cover - the upsert guarantees a row
        raise UserNotRanked(game_id, data.user_id)

    if improved:
        event = schemas.LeaderboardEvent(
            game_id=game_id, user_id=data.user_id, best_score=entry.best_score
        )
        # Delivered to listeners only when the transaction commits.
        await session.execute(select(func.pg_notify(CHANNEL, event.model_dump_json())))

    rank = await _rank_of(session, entry)
    await session.commit()
    return schemas.ScoreSubmissionResult(
        game_id=game_id,
        user_id=data.user_id,
        submitted_score=data.score,
        best_score=entry.best_score,
        rank=rank,
        improved=improved,
    )


# --- Leaderboard reads -----------------------------------------------------


async def top(session: AsyncSession, game_id: str, limit: int) -> schemas.Leaderboard:
    await ensure_game(session, game_id)
    rows = await session.scalars(
        select(LE).where(LE.game_id == game_id).order_by(*RANK_ORDER).limit(limit)
    )
    return schemas.Leaderboard(
        game_id=game_id,
        total_players=await _total_players(session, game_id),
        entries=[_to_entry(row, rank) for rank, row in enumerate(rows, start=1)],
    )


async def user_context(
    session: AsyncSession, game_id: str, user_id: str, neighbors: int
) -> schemas.UserContext:
    await ensure_game(session, game_id)
    entry = await session.get(LE, (game_id, user_id))
    if entry is None:
        raise UserNotRanked(game_id, user_id)

    rank = await _rank_of(session, entry)
    above_rows = list(
        await session.scalars(
            select(LE).where(_ahead_of(entry)).order_by(*REVERSE_RANK_ORDER).limit(neighbors)
        )
    )
    above_rows.reverse()
    below_rows = await session.scalars(
        select(LE).where(_behind(entry)).order_by(*RANK_ORDER).limit(neighbors)
    )

    return schemas.UserContext(
        game_id=game_id,
        total_players=await _total_players(session, game_id),
        user=_to_entry(entry, rank),
        above=[_to_entry(row, rank - len(above_rows) + i) for i, row in enumerate(above_rows)],
        below=[_to_entry(row, rank + 1 + i) for i, row in enumerate(below_rows)],
    )
