from httpx import AsyncClient

from tests.conftest import API_KEY

PROBLEM = "application/problem+json"


def assert_problem(resp, status: int, code: str | None) -> dict:  # type: ignore[no-untyped-def,type-arg]
    assert resp.status_code == status, resp.text
    assert resp.headers["content-type"] == PROBLEM
    body = resp.json()
    assert body["status"] == status
    assert body["title"]
    assert body["instance"] == resp.request.url.path
    if code:
        assert body["code"] == code
        assert body["type"].endswith(f"/problems/{code}")
    else:
        assert body["type"] == "about:blank"
    return body


async def test_missing_api_key(client: AsyncClient, game: str) -> None:
    resp = await client.post(f"/api/v1/games/{game}/scores", json={"user_id": "a", "score": 1})
    assert_problem(resp, 401, "invalid-api-key")
    assert resp.headers["www-authenticate"] == "ApiKey"


async def test_wrong_api_key(client: AsyncClient, game: str) -> None:
    resp = await client.post(
        f"/api/v1/games/{game}/scores",
        json={"user_id": "a", "score": 1},
        headers={"X-API-Key": "nope"},
    )
    assert_problem(resp, 401, "invalid-api-key")


async def test_body_validation_pointers(client: AsyncClient, game: str) -> None:
    resp = await client.post(
        f"/api/v1/games/{game}/scores",
        json={"user_id": "bad id", "score": 2**53, "extra": True},
        headers=API_KEY,
    )
    body = assert_problem(resp, 422, "validation-failed")
    assert {e["pointer"] for e in body["errors"]} == {"#/user_id", "#/score", "#/extra"}


async def test_query_validation_parameter(client: AsyncClient, game: str) -> None:
    resp = await client.get(f"/api/v1/games/{game}/leaderboard", params={"limit": 0})
    body = assert_problem(resp, 422, "validation-failed")
    assert body["errors"][0]["parameter"] == "limit"


async def test_unknown_game(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/games/missing/leaderboard")
    assert_problem(resp, 404, "game-not-found")
    resp = await client.post(
        "/api/v1/games/missing/scores", json={"user_id": "a", "score": 1}, headers=API_KEY
    )
    assert_problem(resp, 404, "game-not-found")


async def test_unranked_user(client: AsyncClient, game: str) -> None:
    resp = await client.get(f"/api/v1/games/{game}/users/ghost/context")
    assert_problem(resp, 404, "user-not-ranked")


async def test_duplicate_game(client: AsyncClient, game: str) -> None:
    resp = await client.post("/api/v1/games", json={"id": game, "name": "Again"}, headers=API_KEY)
    assert_problem(resp, 409, "game-already-exists")


async def test_unknown_route_is_problem(client: AsyncClient) -> None:
    resp = await client.get("/api/does-not-exist")
    assert_problem(resp, 404, None)
