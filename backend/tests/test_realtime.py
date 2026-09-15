import asyncio
import json
import socket

import uvicorn
from httpx import AsyncClient

from app.main import app
from app.realtime import LeaderboardBroker
from app.schemas import LeaderboardEvent
from tests.conftest import submit


async def test_notify_reaches_subscribers(client: AsyncClient, game: str) -> None:
    broker: LeaderboardBroker = app.state.broker
    await asyncio.wait_for(broker.connected.wait(), timeout=10)

    async with broker.subscribe(game) as queue, broker.subscribe("other-game") as other:
        await submit(client, game, "alice", 10)
        await submit(client, game, "alice", 5)  # not an improvement: no event
        event = await asyncio.wait_for(queue.get(), timeout=5)
        assert event == LeaderboardEvent(game_id=game, user_id="alice", best_score=10)
        await asyncio.sleep(0.2)
        assert queue.empty()
        assert other.empty()


async def test_sse_endpoint_streams_events(client: AsyncClient, game: str) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # Reuse the running app/broker; uvicorn's own lifespan would start a second broker.
    server = uvicorn.Server(uvicorn.Config(app, port=port, lifespan="off", log_level="warning"))
    serve = asyncio.create_task(server.serve())
    try:
        while not server.started:  # noqa: ASYNC110 - uvicorn exposes no startup event
            await asyncio.sleep(0.05)
        await asyncio.wait_for(app.state.broker.connected.wait(), timeout=10)

        async with AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as http:
            async with http.stream("GET", f"/api/v1/games/{game}/events") as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
                await submit(client, game, "bob", 42)
                lines = resp.aiter_lines()
                event_name = data = None
                while data is None:
                    line = await asyncio.wait_for(anext(lines), timeout=5)
                    if line.startswith("event:"):
                        event_name = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data = json.loads(line.split(":", 1)[1])
                assert event_name == "leaderboard_updated"
                assert data == {"game_id": game, "user_id": "bob", "best_score": 42}

        missing = await client.get("/api/v1/games/missing/events")
        assert missing.status_code == 404
    finally:
        server.should_exit = True
        await serve
