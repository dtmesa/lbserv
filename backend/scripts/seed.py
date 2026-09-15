"""Seed placeholder games and players through the public API.

Usage:
    SEED_API_KEY=... uv run python scripts/seed.py https://<app>.ondigitalocean.app

Deterministic (fixed random seed) and safe to re-run: existing games are reused, and resubmitting
the same scores never changes a best score. Going through the API (rather than SQL) exercises
validation, ranking, and real-time notifications exactly like real clients.
"""

import asyncio
import os
import random
import sys
from dataclasses import dataclass

import httpx

from app.schemas import Leaderboard, ScoreSubmissionResult


@dataclass(frozen=True)
class GameSeed:
    id: str
    name: str
    players: int
    max_score: int
    step: int  # arcade scores come in fixed increments, which also produces natural ties


GAMES = [
    GameSeed("pacman", "Pac-Man", players=50, max_score=3_333_360, step=10),
    GameSeed("galaga", "Galaga", players=150, max_score=1_000_000, step=10),
    GameSeed("donkey-kong", "Donkey Kong", players=250, max_score=1_260_000, step=100),
]

ADJECTIVES = [
    "atomic",
    "blazing",
    "cosmic",
    "crimson",
    "electric",
    "frosty",
    "golden",
    "hyper",
    "iron",
    "lucky",
    "midnight",
    "neon",
    "pixel",
    "quantum",
    "rapid",
    "retro",
    "shadow",
    "silent",
    "sonic",
    "turbo",
    "ultra",
    "velvet",
    "wild",
    "zesty",
]
NOUNS = [
    "arcade",
    "blaster",
    "comet",
    "dragon",
    "falcon",
    "ghost",
    "gorilla",
    "hunter",
    "joystick",
    "knight",
    "laser",
    "maze",
    "ninja",
    "otter",
    "phoenix",
    "pilot",
    "raccoon",
    "rocket",
    "runner",
    "samurai",
    "tiger",
    "voyager",
    "wizard",
    "yeti",
]


def player_ids(count: int, rng: random.Random) -> list[str]:
    ids: set[str] = set()
    while len(ids) < count:
        ids.add(f"{rng.choice(ADJECTIVES)}_{rng.choice(NOUNS)}_{rng.randint(1, 99):02d}")
    return sorted(ids)


def scores_for(game: GameSeed, rng: random.Random) -> list[tuple[str, int]]:
    """Each player submits 1-3 attempts; a skewed distribution puts few players near the top."""
    submissions = []
    for user_id in player_ids(game.players, rng):
        for _ in range(rng.randint(1, 3)):
            raw = game.max_score * rng.betavariate(1.6, 6.0)
            submissions.append((user_id, int(raw // game.step) * game.step))
    rng.shuffle(submissions)
    return submissions


async def seed(base_url: str, api_key: str) -> int:
    rng = random.Random(20260915)  # noqa: S311 - deterministic placeholder data, not security
    headers = {"X-API-Key": api_key}
    limiter = asyncio.Semaphore(8)

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=20) as http:
        for game in GAMES:
            created = await http.post("/api/v1/games", json={"id": game.id, "name": game.name})
            if created.status_code not in (201, 409):
                print(f"create {game.id}: {created.status_code} {created.text}", file=sys.stderr)
                return 1

            async def submit(user_id: str, score: int, game_id: str = game.id) -> None:
                async with limiter:
                    resp = await http.post(
                        f"/api/v1/games/{game_id}/scores", json={"user_id": user_id, "score": score}
                    )
                resp.raise_for_status()
                ScoreSubmissionResult.model_validate(resp.json())

            submissions = scores_for(game, rng)
            await asyncio.gather(*(submit(u, s) for u, s in submissions))

            board = Leaderboard.model_validate(
                (await http.get(f"/api/v1/games/{game.id}/leaderboard", params={"limit": 3})).json()
            )
            top = ", ".join(f"#{e.rank} {e.user_id} {e.score:,}" for e in board.entries)
            status = "created" if created.status_code == 201 else "existing"
            print(
                f"{game.id:<12} {status:<8} {len(submissions):>4} submissions -> "
                f"{board.total_players} players | {top}"
            )
            if board.total_players < game.players:
                print(f"{game.id}: expected >= {game.players} players", file=sys.stderr)
                return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or "SEED_API_KEY" not in os.environ:
        sys.exit(__doc__)
    sys.exit(asyncio.run(seed(sys.argv[1].rstrip("/"), os.environ["SEED_API_KEY"])))
