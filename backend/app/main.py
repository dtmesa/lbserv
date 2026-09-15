"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import get_settings
from app.db import get_engine
from app.observability import init_sentry
from app.problems import PROBLEM_MEDIA_TYPE, register_problem_handlers
from app.realtime import LeaderboardBroker
from app.routes import events, games, health, leaderboard
from app.schemas import ProblemDetails


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    broker = LeaderboardBroker(settings.asyncpg_dsn, settings.ssl)
    app.state.broker = broker
    await broker.start()
    try:
        yield
    finally:
        await broker.stop()
        await get_engine().dispose()


def _custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Make RFC 9457 problem details the only documented error shape."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    problem_schema = ProblemDetails.model_json_schema(ref_template="#/components/schemas/{model}")
    components.update(problem_schema.pop("$defs", {}))
    components["ProblemDetails"] = problem_schema
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)

    problem_ref = {"schema": {"$ref": "#/components/schemas/ProblemDetails"}}
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.get("responses", {})
            if operation.pop("x-event-stream", False):
                ok = responses["200"]["content"]
                ok["text/event-stream"] = ok.pop("application/json")
            if "422" in responses:
                responses["422"] = {
                    "description": "Validation failed",
                    "content": {PROBLEM_MEDIA_TYPE: problem_ref},
                }

    app.openapi_schema = schema
    return schema


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    init_sentry(settings)

    app = FastAPI(
        title="lbserv",
        version="1.0.0",
        description="Real-time gaming leaderboard API. Errors use RFC 9457 problem details.",
        lifespan=lifespan,
        separate_input_output_schemas=False,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    register_problem_handlers(app)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key"],
        )
    for router in (health.router, games.router, leaderboard.router, events.router):
        app.include_router(router)

    app.openapi = lambda: _custom_openapi(app)  # type: ignore[method-assign]
    return app


app = create_app()
