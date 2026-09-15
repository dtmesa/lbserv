from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.db import get_session
from app.problems import problem_responses
from app.security import require_api_key
from app.services import leaderboard as service

router = APIRouter(prefix="/api/v1", tags=["games"])

GamePath = Annotated[str, Path(pattern=r"^[a-z0-9-]{1,64}$", description="Game slug")]


@router.get("/games", operation_id="listGames", responses=problem_responses(500))
async def list_games(session: AsyncSession = Depends(get_session)) -> schemas.GameList:
    games = await service.list_games(session)
    return schemas.GameList(games=[schemas.Game.model_validate(g) for g in games])


@router.post(
    "/games",
    operation_id="createGame",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
    responses=problem_responses(401, 409, 422, 500),
)
async def create_game(
    body: schemas.GameCreate, session: AsyncSession = Depends(get_session)
) -> schemas.Game:
    return schemas.Game.model_validate(await service.create_game(session, body))
