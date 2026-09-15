"""API key protection for write endpoints."""

import secrets

from fastapi import Security
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.problems import InvalidApiKey

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="ApiKeyAuth")


async def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    expected = get_settings().api_key.get_secret_value()
    if not api_key or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise InvalidApiKey()
