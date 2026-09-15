"""Pydantic API contract. The frontend's types are generated from these models via OpenAPI."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# Largest integer a JS number can represent exactly (Number.MAX_SAFE_INTEGER).
MAX_SAFE_INTEGER = 2**53 - 1

GameId = Annotated[
    str,
    Field(pattern=r"^[a-z0-9-]{1,64}$", examples=["space-invaders"], description="Game slug"),
]
UserId = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", examples=["player_42"], description="User identifier"),
]


def _integral_float_to_int(value: object) -> object:
    """JSON Schema counts 1500.0 as an integer, so accept it even in strict request bodies."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


# Constraints must precede the BeforeValidator or they are emitted as non-standard "ge"/"le".
Score = Annotated[
    int,
    Field(ge=0, le=MAX_SAFE_INTEGER, examples=[1500]),
    BeforeValidator(_integral_float_to_int),
]
Rank = Annotated[int, Field(ge=1, description="1-based position in the leaderboard")]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestBody(ApiModel):
    """Request bodies are strict: no type coercion (e.g. `false` is not accepted as `0`)."""

    model_config = ConfigDict(extra="forbid", strict=True)


# Printable text only: Postgres rejects NUL bytes, and control characters are never valid names.
PrintableText = Annotated[str, Field(pattern=r"^[^\x00-\x1f\x7f]+$")]


# --- Games -----------------------------------------------------------------


class GameCreate(RequestBody):
    id: GameId
    name: Annotated[PrintableText, Field(min_length=1, max_length=120, examples=["Space Invaders"])]


class Game(ApiModel):
    model_config = ConfigDict(from_attributes=True)

    id: GameId
    name: str
    created_at: datetime


class GameList(ApiModel):
    games: list[Game]


# --- Scores ----------------------------------------------------------------


class ScoreSubmission(RequestBody):
    user_id: UserId
    score: Score


class ScoreSubmissionResult(ApiModel):
    game_id: GameId
    user_id: UserId
    submitted_score: Score
    best_score: Score
    rank: Rank
    improved: bool = Field(description="True if this submission raised the user's best score")


# --- Leaderboard -----------------------------------------------------------


class LeaderboardQuery(ApiModel):
    limit: Annotated[int, Field(ge=1, le=100, description="Number of top users")] = 10


class UserContextQuery(ApiModel):
    neighbors: Annotated[
        int, Field(ge=0, le=10, description="Users to include above and below")
    ] = 1


class LeaderboardEntry(ApiModel):
    rank: Rank
    user_id: UserId
    score: Score
    achieved_at: datetime


class Leaderboard(ApiModel):
    game_id: GameId
    total_players: Annotated[int, Field(ge=0)]
    entries: list[LeaderboardEntry]


class UserContext(ApiModel):
    game_id: GameId
    total_players: Annotated[int, Field(ge=1)]
    user: LeaderboardEntry
    above: list[LeaderboardEntry] = Field(description="Users ranked directly above, best first")
    below: list[LeaderboardEntry] = Field(description="Users ranked directly below, best first")


class LeaderboardEvent(ApiModel):
    """Payload of each `leaderboard_updated` Server-Sent Event."""

    game_id: GameId
    user_id: UserId
    best_score: Score


# --- Health ----------------------------------------------------------------


class HealthStatus(ApiModel):
    status: str = "ok"


# --- RFC 9457 Problem Details ---------------------------------------------


class ProblemError(ApiModel):
    """A single validation problem. Exactly one of pointer/parameter/header locates it."""

    detail: str
    pointer: str | None = Field(
        default=None, description="JSON Pointer (RFC 6901) into the request body, e.g. #/score"
    )
    parameter: str | None = Field(default=None, description="Offending query or path parameter")
    header: str | None = Field(default=None, description="Offending request header")


class ProblemDetails(BaseModel):
    """RFC 9457 problem details (`application/problem+json`)."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(default="about:blank", description="URI identifying the problem type")
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: str | None = None
    instance: str | None = None
    code: str | None = Field(default=None, description="Stable machine-readable error code")
    errors: list[ProblemError] | None = None
