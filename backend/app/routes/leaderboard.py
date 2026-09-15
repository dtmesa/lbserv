from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.db import get_session
from app.problems import problem_responses
from app.routes.games import GamePath
from app.security import require_api_key
from app.services import leaderboard as service

router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["leaderboard"])

UserPath = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="User identifier")]


@router.post(
    "/scores",
    operation_id="submitScore",
    dependencies=[Depends(require_api_key)],
    responses=problem_responses(401, 404, 422, 500),
)
async def submit_score(
    game_id: GamePath,
    body: schemas.ScoreSubmission,
    session: AsyncSession = Depends(get_session),
) -> schemas.ScoreSubmissionResult:
    """Submit a score. The leaderboard keeps each user's best score per game."""
    return await service.submit_score(session, game_id, body)


@router.get(
    "/leaderboard", operation_id="getLeaderboard", responses=problem_responses(404, 422, 500)
)
async def get_leaderboard(
    game_id: GamePath,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of top users")] = 10,
    session: AsyncSession = Depends(get_session),
) -> schemas.Leaderboard:
    """Top users for a game, best first."""
    return await service.top(session, game_id, limit)


@router.get(
    "/users/{user_id}/context",
    operation_id="getUserContext",
    responses=problem_responses(404, 422, 500),
)
async def get_user_context(
    game_id: GamePath,
    user_id: UserPath,
    neighbors: Annotated[
        int, Query(ge=0, le=10, description="Users to include above and below")
    ] = 1,
    session: AsyncSession = Depends(get_session),
) -> schemas.UserContext:
    """A user's current rank with the users immediately above and below them."""
    return await service.user_context(session, game_id, user_id, neighbors)
