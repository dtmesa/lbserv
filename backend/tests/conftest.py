import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/lbserv_test")
os.environ["API_KEY"] = "test-key"
os.environ.pop("SENTRY_DSN", None)

from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import get_engine
from app.main import app

API_KEY = {"X-API-Key": "test-key"}


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def lifespan() -> AsyncIterator[None]:
    async with app.router.lifespan_context(app):
        yield


@pytest.fixture(autouse=True)
async def clean_tables(lifespan: None) -> None:
    async with get_engine().begin() as conn:
        await conn.execute(
            text("TRUNCATE leaderboard_entries, score_submissions, games RESTART IDENTITY CASCADE")
        )


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def game(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/games", json={"id": "tetris", "name": "Tetris"}, headers=API_KEY
    )
    assert resp.status_code == 201, resp.text
    return "tetris"


async def submit(client: AsyncClient, game_id: str, user_id: str, score: int) -> dict[str, object]:
    resp = await client.post(
        f"/api/v1/games/{game_id}/scores",
        json={"user_id": user_id, "score": score},
        headers=API_KEY,
    )
    assert resp.status_code == 200, resp.text
    data: dict[str, object] = resp.json()
    return data
