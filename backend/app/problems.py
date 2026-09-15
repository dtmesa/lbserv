"""RFC 9457 problem details: exception types, handlers, and OpenAPI wiring."""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, cast

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import compile_path

from app.config import get_settings
from app.schemas import ProblemDetails, ProblemError

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemException(Exception):
    """Base for domain errors rendered as problem details."""

    status: int = 500
    code: str = "internal-error"
    title: str = "Internal Server Error"

    def __init__(self, detail: str | None = None, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.headers = headers


class GameNotFound(ProblemException):
    status, code, title = 404, "game-not-found", "Game not found"

    def __init__(self, game_id: str) -> None:
        super().__init__(f"No game with id '{game_id}'.")


class UserNotRanked(ProblemException):
    status, code, title = 404, "user-not-ranked", "User not ranked"

    def __init__(self, game_id: str, user_id: str) -> None:
        super().__init__(f"User '{user_id}' has no score in game '{game_id}'.")


class GameAlreadyExists(ProblemException):
    status, code, title = 409, "game-already-exists", "Game already exists"

    def __init__(self, game_id: str) -> None:
        super().__init__(f"A game with id '{game_id}' already exists.")


class InvalidApiKey(ProblemException):
    status, code, title = 401, "invalid-api-key", "Invalid API key"

    def __init__(self) -> None:
        super().__init__(
            "A valid X-API-Key header is required.", headers={"WWW-Authenticate": "ApiKey"}
        )


def problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str | None = None,
    code: str | None = None,
    errors: list[ProblemError] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    problem = ProblemDetails(
        type=f"{get_settings().problem_type_base}{code}" if code else "about:blank",
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        code=code,
        errors=errors,
    )
    return JSONResponse(
        problem.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def _locate(loc: tuple[int | str, ...]) -> dict[str, str]:
    """Map a pydantic error location to an RFC 9457 pointer/parameter/header."""
    source, *path = loc or ("body",)
    if source == "body":
        escaped = [str(p).replace("~", "~0").replace("/", "~1") for p in path]
        return {"pointer": "#/" + "/".join(escaped)}
    name = str(path[0]) if path else ""
    return {"header": name} if source == "header" else {"parameter": name}


async def _handle_problem(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(ProblemException, exc)
    return problem_response(
        request,
        status=exc.status,
        title=exc.title,
        detail=exc.detail,
        code=exc.code,
        headers=exc.headers,
    )


async def _handle_validation(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    errors = [ProblemError(detail=err["msg"], **_locate(tuple(err["loc"]))) for err in exc.errors()]
    return problem_response(
        request,
        status=422,
        title="Validation failed",
        detail="The request contains invalid parameters.",
        code="validation-failed",
        errors=errors,
    )


_HTTP_METHODS = {"GET", "PUT", "POST", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"}


def _allowed_methods(request: Request) -> str:
    """Every method documented for this path; Starlette only reports the first matching route."""
    methods: set[str] = set()
    for template, item in request.app.openapi().get("paths", {}).items():
        regex, _, _ = compile_path(template)
        if regex.fullmatch(request.url.path):
            methods.update(m.upper() for m in item if m.upper() in _HTTP_METHODS)
    if "GET" in methods:
        methods.add("HEAD")
    return ", ".join(sorted(methods))


async def _handle_http(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    headers = dict(exc.headers or {})
    if exc.status_code == 405:
        headers["Allow"] = _allowed_methods(request)
    return problem_response(
        request,
        status=exc.status_code,
        title=HTTPStatus(exc.status_code).phrase,
        detail=exc.detail if isinstance(exc.detail, str) else None,
        headers=headers,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    sentry_sdk.capture_exception(exc)  # deduplicated if the integration already captured it
    return problem_response(
        request, status=500, title="Internal Server Error", code="internal-error"
    )


def register_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProblemException, _handle_problem)
    app.add_exception_handler(RequestValidationError, _handle_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_http)
    app.add_exception_handler(Exception, _handle_unexpected)


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries documenting problem+json bodies."""
    return {
        status: {
            "description": HTTPStatus(status).phrase,
            "content": {
                PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/ProblemDetails"}}
            },
        }
        for status in statuses
    }
