"""Real-time fan-out: one Postgres LISTEN connection per process, per-game subscriber queues.

Score submissions call pg_notify() inside their transaction, so every API instance receives
each committed update and forwards it to its own SSE clients.
"""

import asyncio
import contextlib
import logging
import ssl
from collections import defaultdict
from collections.abc import AsyncIterator

import asyncpg
from pydantic import ValidationError

from app.schemas import LeaderboardEvent

logger = logging.getLogger(__name__)

CHANNEL = "leaderboard_updates"
QUEUE_SIZE = 100


class LeaderboardBroker:
    def __init__(self, dsn: str, ssl_arg: ssl.SSLContext | str | bool) -> None:
        self._dsn = dsn
        self._ssl = ssl_arg
        self._subscribers: defaultdict[str, set[asyncio.Queue[LeaderboardEvent]]] = defaultdict(set)
        self._task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()

    @property
    def connected(self) -> asyncio.Event:
        return self._connected

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="leaderboard-broker")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        """Keep a LISTEN connection alive, reconnecting with backoff."""
        backoff = 1.0
        while True:
            conn: asyncpg.Connection | None = None
            try:
                conn = await asyncpg.connect(self._dsn, ssl=self._ssl)
                lost = asyncio.Event()
                conn.add_termination_listener(lambda _c, lost=lost: lost.set())
                await conn.add_listener(CHANNEL, self._on_notify)
                self._connected.set()
                backoff = 1.0
                logger.info("Listening on channel %s", CHANNEL)
                await lost.wait()
                logger.warning("LISTEN connection lost; reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("LISTEN connection failed; retrying in %.0fs", backoff)
            finally:
                self._connected.clear()
                if conn is not None and not conn.is_closed():
                    with contextlib.suppress(Exception):
                        await asyncio.shield(conn.close(timeout=2))
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    def _on_notify(self, _conn: object, _pid: int, _channel: str, payload: str) -> None:
        try:
            event = LeaderboardEvent.model_validate_json(payload)
        except ValidationError:
            logger.warning("Ignoring malformed notification: %s", payload)
            return
        self.publish(event)

    def publish(self, event: LeaderboardEvent) -> None:
        for queue in self._subscribers.get(event.game_id, ()):
            with contextlib.suppress(asyncio.QueueFull):  # slow client: drop, it will refetch
                queue.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscribe(self, game_id: str) -> AsyncIterator[asyncio.Queue[LeaderboardEvent]]:
        queue: asyncio.Queue[LeaderboardEvent] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers[game_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[game_id].discard(queue)
            if not self._subscribers[game_id]:
                del self._subscribers[game_id]
