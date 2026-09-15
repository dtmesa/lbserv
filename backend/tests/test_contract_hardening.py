"""Regressions for issues found by Schemathesis (`make fuzz`)."""

from httpx import AsyncClient

from tests.conftest import API_KEY

PROBLEM = "application/problem+json"


async def test_nul_byte_in_name_is_422_not_500(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/games", json={"id": "nul", "name": "bad\u0000name"}, headers=API_KEY
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"] == PROBLEM
    assert resp.json()["errors"][0]["pointer"] == "#/name"


async def test_boolean_score_is_rejected(client: AsyncClient, game: str) -> None:
    resp = await client.post(
        f"/api/v1/games/{game}/scores", json={"user_id": "a", "score": False}, headers=API_KEY
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["pointer"] == "#/score"


async def test_string_score_is_rejected(client: AsyncClient, game: str) -> None:
    resp = await client.post(
        f"/api/v1/games/{game}/scores", json={"user_id": "a", "score": "5"}, headers=API_KEY
    )
    assert resp.status_code == 422


async def test_integral_float_score_is_accepted(client: AsyncClient, game: str) -> None:
    resp = await client.post(
        f"/api/v1/games/{game}/scores", json={"user_id": "a", "score": 1500.0}, headers=API_KEY
    )
    assert resp.status_code == 200
    assert resp.json()["best_score"] == 1500


async def test_fractional_score_is_rejected(client: AsyncClient, game: str) -> None:
    resp = await client.post(
        f"/api/v1/games/{game}/scores", json={"user_id": "a", "score": 1.5}, headers=API_KEY
    )
    assert resp.status_code == 422


async def test_unknown_query_parameter_is_rejected(client: AsyncClient, game: str) -> None:
    resp = await client.get(f"/api/v1/games/{game}/leaderboard", params={"limit": 5, "evil": 1})
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["parameter"] == "evil"


async def test_undecodable_body_is_documented_400_problem(client: AsyncClient, game: str) -> None:
    resp = await client.post(
        f"/api/v1/games/{game}/scores",
        content=b"\xff\xfe\x00garbage",
        headers={**API_KEY, "Content-Type": "application/json"},
    )
    assert resp.status_code in (400, 422)
    assert resp.headers["content-type"] == PROBLEM


async def test_405_allow_header_lists_every_method(client: AsyncClient) -> None:
    resp = await client.request("OPTIONS", "/api/v1/games")
    assert resp.status_code == 405
    assert resp.headers["content-type"] == PROBLEM
    assert resp.headers["allow"] == "GET, HEAD, POST"
