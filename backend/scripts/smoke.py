"""Smoke tests for a deployed lbserv.

Usage:
    SMOKE_API_KEY=... uv run python scripts/smoke.py https://<app>.ondigitalocean.app

Creates a uniquely named `smoke-*` game and a few scores (there is no delete endpoint).
Every response body is validated against the Pydantic contract in app/schemas.py.
"""

import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel

from app.schemas import (
    Game,
    GameList,
    HealthStatus,
    Leaderboard,
    LeaderboardEvent,
    ProblemDetails,
    ScoreSubmissionResult,
    UserContext,
)

PROBLEM = "application/problem+json"


@dataclass
class Report:
    results: list[tuple[str, bool, str, float]] = field(default_factory=list)

    async def check(self, name: str, fn: Callable[[], Awaitable[str]]) -> None:
        start = time.perf_counter()
        try:
            detail = await fn()
            ok = True
        except Exception as exc:  # report and keep going
            detail, ok = f"{type(exc).__name__}: {exc}", False
        elapsed = (time.perf_counter() - start) * 1000
        self.results.append((name, ok, detail, elapsed))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name} ({elapsed:.0f} ms){' - ' + detail if detail else ''}", flush=True)


def parse[M: BaseModel](model: type[M], resp: httpx.Response, status: int = 200) -> M:
    assert resp.status_code == status, (
        f"expected {status}, got {resp.status_code}: {resp.text[:300]}"
    )
    return model.model_validate(resp.json())


def problem(resp: httpx.Response, status: int, code: str | None) -> ProblemDetails:
    assert resp.status_code == status, (
        f"expected {status}, got {resp.status_code}: {resp.text[:300]}"
    )
    assert resp.headers["content-type"] == PROBLEM, resp.headers["content-type"]
    body = ProblemDetails.model_validate(resp.json())
    assert body.code == code, f"code {body.code!r} != {code!r}"
    return body


async def main(base_url: str, api_key: str) -> int:
    report = Report()
    game_id = f"smoke-{int(time.time())}"
    auth = {"X-API-Key": api_key}

    async with httpx.AsyncClient(base_url=base_url, timeout=15, follow_redirects=False) as http:

        async def tls_and_health() -> str:
            assert base_url.startswith("https://"), "deployment should be served over HTTPS"
            parse(HealthStatus, await http.get("/api/health"))
            parse(HealthStatus, await http.get("/api/ready"))
            return "health + DB readiness OK"

        async def web_app() -> str:
            index = await http.get("/")
            assert index.status_code == 200 and '<div id="root">' in index.text, index.text[:200]
            deep = await http.get("/some/client/route?game=x")
            assert deep.status_code == 200 and '<div id="root">' in deep.text, "SPA catch-all"
            return "index + SPA catch-all served"

        async def docs() -> str:
            schema = (await http.get("/api/openapi.json")).json()
            assert "ProblemDetails" in schema["components"]["schemas"]
            assert (await http.get("/api/docs")).status_code == 200
            return f"OpenAPI {schema['info']['version']}, {len(schema['paths'])} paths"

        async def writes_require_key() -> str:
            problem(
                await http.post("/api/v1/games", json={"id": game_id, "name": "x"}),
                401,
                "invalid-api-key",
            )
            problem(
                await http.post(
                    "/api/v1/games",
                    json={"id": game_id, "name": "x"},
                    headers={"X-API-Key": "wrong"},
                ),
                401,
                "invalid-api-key",
            )
            return "missing and wrong key -> 401 problem+json"

        async def create_game() -> str:
            game = parse(
                Game,
                await http.post(
                    "/api/v1/games", json={"id": game_id, "name": "Smoke Test"}, headers=auth
                ),
                201,
            )
            assert game.id == game_id
            problem(
                await http.post(
                    "/api/v1/games", json={"id": game_id, "name": "again"}, headers=auth
                ),
                409,
                "game-already-exists",
            )
            games = parse(GameList, await http.get("/api/v1/games"))
            assert any(g.id == game_id for g in games.games)
            return f"created {game_id}; duplicate -> 409"

        async def scores_and_ranking() -> str:
            for user, score in [("alice", 300), ("bob", 500), ("carol", 400), ("alice", 100)]:
                parse(
                    ScoreSubmissionResult,
                    await http.post(
                        f"/api/v1/games/{game_id}/scores",
                        json={"user_id": user, "score": score},
                        headers=auth,
                    ),
                )
            board = parse(
                Leaderboard,
                await http.get(f"/api/v1/games/{game_id}/leaderboard", params={"limit": 10}),
            )
            order = [(e.rank, e.user_id, e.score) for e in board.entries]
            assert order == [(1, "bob", 500), (2, "carol", 400), (3, "alice", 300)], order
            return f"best-score ranking OK: {order}"

        async def user_context() -> str:
            ctx = parse(
                UserContext,
                await http.get(
                    f"/api/v1/games/{game_id}/users/carol/context", params={"neighbors": 1}
                ),
            )
            assert ctx.user.rank == 2
            assert [e.user_id for e in ctx.above] == ["bob"]
            assert [e.user_id for e in ctx.below] == ["alice"]
            problem(
                await http.get(f"/api/v1/games/{game_id}/users/ghost/context"),
                404,
                "user-not-ranked",
            )
            return "carol #2 between bob and alice; unknown user -> 404"

        async def validation_problems() -> str:
            body = problem(
                await http.post(
                    f"/api/v1/games/{game_id}/scores",
                    json={"user_id": "bad id", "score": -1},
                    headers=auth,
                ),
                422,
                "validation-failed",
            )
            pointers = {e.pointer for e in body.errors or []}
            assert pointers == {"#/user_id", "#/score"}, pointers
            problem(await http.get("/api/v1/games/nope-nope/leaderboard"), 404, "game-not-found")
            problem(
                await http.get(f"/api/v1/games/{game_id}/leaderboard", params={"limit": 0}),
                422,
                "validation-failed",
            )
            return "422 pointers, 404 game-not-found"

        async def hardening_fixes() -> str:
            # Issues found by Schemathesis; these fail until the fixes are deployed.
            failures = []
            r = await http.post(
                f"/api/v1/games/{game_id}/scores",
                json={"user_id": "alice", "score": False},
                headers=auth,
            )
            if r.status_code != 422:
                failures.append(f"bool score -> {r.status_code}")
            r = await http.post(
                "/api/v1/games",
                json={"id": f"{game_id}-nul", "name": "a" + chr(0) + "b"},
                headers=auth,
            )
            if r.status_code != 422:
                failures.append(f"NUL in name -> {r.status_code}")
            r = await http.get(f"/api/v1/games/{game_id}/leaderboard", params={"bogus": 1})
            if r.status_code != 422:
                failures.append(f"unknown query param -> {r.status_code}")
            r = await http.request("OPTIONS", "/api/v1/games")
            if r.headers.get("allow") != "GET, HEAD, POST":
                failures.append(f"405 Allow={r.headers.get('allow')!r}")
            assert not failures, "; ".join(failures)
            return "strict bodies, NUL names, unknown params, Allow header"

        async def realtime_sse() -> str:
            received: asyncio.Queue[LeaderboardEvent] = asyncio.Queue()
            connected = asyncio.Event()

            async def listen() -> None:
                async with http.stream(
                    "GET", f"/api/v1/games/{game_id}/events", timeout=httpx.Timeout(20, read=20)
                ) as resp:
                    assert resp.status_code == 200
                    assert resp.headers["content-type"].startswith("text/event-stream")
                    async for line in resp.aiter_lines():
                        if line.startswith(":"):
                            connected.set()
                        elif line.startswith("data:"):
                            await received.put(LeaderboardEvent.model_validate_json(line[5:]))
                            return

            task = asyncio.create_task(listen())
            try:
                await asyncio.wait_for(connected.wait(), 10)
                sent = time.perf_counter()
                await http.post(
                    f"/api/v1/games/{game_id}/scores",
                    json={"user_id": "dave", "score": 900},
                    headers=auth,
                )
                event = await asyncio.wait_for(received.get(), 10)
                latency = (time.perf_counter() - sent) * 1000
            finally:
                task.cancel()
            assert event == LeaderboardEvent(game_id=game_id, user_id="dave", best_score=900)
            return f"event received {latency:.0f} ms after submit"

        async def latency() -> str:
            samples = []
            for _ in range(10):
                t = time.perf_counter()
                (await http.get(f"/api/v1/games/{game_id}/leaderboard")).raise_for_status()
                samples.append((time.perf_counter() - t) * 1000)
            samples.sort()
            p50, p90 = samples[len(samples) // 2], samples[int(len(samples) * 0.9) - 1]
            assert p90 < 1500, f"p90 {p90:.0f} ms"
            return f"leaderboard p50 {p50:.0f} ms, p90 {p90:.0f} ms"

        for name, fn in [
            ("TLS + health/readiness", tls_and_health),
            ("static web app", web_app),
            ("OpenAPI docs", docs),
            ("protected writes require API key", writes_require_key),
            ("create game", create_game),
            ("submit scores + top X", scores_and_ranking),
            ("user context", user_context),
            ("RFC 9457 validation problems", validation_problems),
            ("Schemathesis hardening fixes", hardening_fixes),
            ("real-time SSE", realtime_sse),
            ("read latency", latency),
        ]:
            await report.check(name, fn)

    failed = [r for r in report.results if not r[1]]
    print(
        json.dumps(
            {
                "base_url": base_url,
                "game_id": game_id,
                "passed": len(report.results) - len(failed),
                "failed": len(failed),
            }
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or "SMOKE_API_KEY" not in os.environ:
        sys.exit(__doc__)
    sys.exit(asyncio.run(main(sys.argv[1].rstrip("/"), os.environ["SMOKE_API_KEY"])))
