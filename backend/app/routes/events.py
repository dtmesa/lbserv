from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.config import get_settings
from app.db import get_sessionmaker
from app.problems import problem_responses
from app.realtime import LeaderboardBroker
from app.routes.games import GamePath
from app.schemas import LeaderboardEvent
from app.services import leaderboard as service

router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["leaderboard"])

EVENT_NAME = "leaderboard_updated"


@router.get(
    "/events",
    operation_id="streamLeaderboardEvents",
    response_class=EventSourceResponse,
    openapi_extra={"x-event-stream": True},
    responses={
        200: {
            "model": LeaderboardEvent,
            "description": f"Server-Sent Events stream; each `{EVENT_NAME}` event's data is a "
            "LeaderboardEvent JSON document.",
        },
        **problem_responses(404, 422, 500),
    },
)
async def stream_leaderboard_events(game_id: GamePath, request: Request) -> EventSourceResponse:
    # Short-lived session: don't hold a pooled connection for the lifetime of the stream.
    async with get_sessionmaker()() as session:
        await service.ensure_game(session, game_id)

    broker: LeaderboardBroker = request.app.state.broker

    async def events() -> AsyncIterator[ServerSentEvent]:
        async with broker.subscribe(game_id) as queue:
            # Flush headers immediately and let clients know the stream is live.
            yield ServerSentEvent(comment="connected", retry=3000)
            while True:
                event = await queue.get()
                yield ServerSentEvent(data=event.model_dump_json(), event=EVENT_NAME)

    return EventSourceResponse(
        events(),
        ping=get_settings().sse_ping_seconds,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
