import asyncio

from httpx import AsyncClient

from tests.conftest import submit


async def test_best_score_is_kept(client: AsyncClient, game: str) -> None:
    first = await submit(client, game, "alice", 100)
    assert first == {
        "game_id": game,
        "user_id": "alice",
        "submitted_score": 100,
        "best_score": 100,
        "rank": 1,
        "improved": True,
    }
    lower = await submit(client, game, "alice", 40)
    assert lower["best_score"] == 100
    assert lower["improved"] is False
    higher = await submit(client, game, "alice", 150)
    assert higher["best_score"] == 150
    assert higher["improved"] is True


async def test_concurrent_submissions_keep_max(client: AsyncClient, game: str) -> None:
    scores = list(range(1, 41))
    await asyncio.gather(*(submit(client, game, "alice", s) for s in scores))
    resp = await client.get(f"/api/v1/games/{game}/leaderboard")
    assert resp.json()["entries"][0]["score"] == 40
    assert resp.json()["total_players"] == 1


async def test_top_orders_by_score_then_earliest(client: AsyncClient, game: str) -> None:
    for user, score in [("a", 10), ("b", 30), ("c", 20), ("d", 20), ("e", 5)]:
        await submit(client, game, user, score)

    resp = await client.get(f"/api/v1/games/{game}/leaderboard", params={"limit": 4})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_players"] == 5
    assert [(e["rank"], e["user_id"], e["score"]) for e in body["entries"]] == [
        (1, "b", 30),
        (2, "c", 20),  # tied with d but achieved first
        (3, "d", 20),
        (4, "a", 10),
    ]


async def test_top_empty_game(client: AsyncClient, game: str) -> None:
    resp = await client.get(f"/api/v1/games/{game}/leaderboard")
    assert resp.json() == {"game_id": game, "total_players": 0, "entries": []}


async def test_user_context_middle_and_edges(client: AsyncClient, game: str) -> None:
    for user, score in [("a", 50), ("b", 40), ("c", 30), ("d", 20), ("e", 10)]:
        await submit(client, game, user, score)
    url = f"/api/v1/games/{game}/users"

    mid = (await client.get(f"{url}/c/context", params={"neighbors": 2})).json()
    assert mid["user"]["rank"] == 3
    assert [(e["rank"], e["user_id"]) for e in mid["above"]] == [(1, "a"), (2, "b")]
    assert [(e["rank"], e["user_id"]) for e in mid["below"]] == [(4, "d"), (5, "e")]

    top = (await client.get(f"{url}/a/context")).json()
    assert top["user"]["rank"] == 1
    assert top["above"] == []
    assert [e["user_id"] for e in top["below"]] == ["b"]

    last = (await client.get(f"{url}/e/context")).json()
    assert last["user"]["rank"] == 5
    assert [e["user_id"] for e in last["above"]] == ["d"]
    assert last["below"] == []


async def test_user_context_rank_updates_after_improvement(client: AsyncClient, game: str) -> None:
    await submit(client, game, "a", 50)
    await submit(client, game, "b", 40)
    result = await submit(client, game, "b", 60)
    assert result["rank"] == 1
    ctx = (await client.get(f"/api/v1/games/{game}/users/a/context")).json()
    assert ctx["user"]["rank"] == 2
    assert [e["user_id"] for e in ctx["above"]] == ["b"]


async def test_list_games(client: AsyncClient, game: str) -> None:
    resp = await client.get("/api/v1/games")
    assert [g["id"] for g in resp.json()["games"]] == [game]
