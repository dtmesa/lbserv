"""Application settings, loaded from environment variables."""

import ssl
from functools import lru_cache
from typing import Literal, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SslMode = Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DigitalOcean injects libpq-style URLs, e.g. postgresql://u:p@host:25060/db?sslmode=require
    database_url: str = "postgresql://postgres:postgres@localhost:5432/lbserv"
    database_ca_cert: str | None = None
    api_key: SecretStr = SecretStr("dev-api-key")
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    problem_type_base: str = "https://lbserv.dev/problems/"
    sse_ping_seconds: int = 15

    # Sentry is disabled unless a DSN is provided.
    sentry_dsn: SecretStr | None = None
    sentry_environment: str = "development"
    sentry_release: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def _parsed(self) -> tuple[str, SslMode | None]:
        """Return (dsn without sslmode, sslmode). Accepts postgres://, postgresql:// and +driver."""
        parts = urlsplit(self.database_url)
        query = dict(parse_qsl(parts.query))
        sslmode = cast(SslMode | None, query.pop("sslmode", None))
        dsn = urlunsplit(("postgresql", parts.netloc, parts.path, urlencode(query), parts.fragment))
        return dsn, sslmode

    @property
    def asyncpg_dsn(self) -> str:
        """DSN usable directly by asyncpg.connect()."""
        return self._parsed[0]

    @property
    def sqlalchemy_url(self) -> str:
        return self._parsed[0].replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def ssl(self) -> ssl.SSLContext | str | bool:
        """SSL argument for asyncpg, derived from sslmode and the optional CA certificate."""
        sslmode = self._parsed[1]
        if sslmode in (None, "disable"):
            return False
        if self.database_ca_cert:
            ctx = ssl.create_default_context(cadata=self.database_ca_cert)
            # DO managed DB certs are issued for the cluster hostname; verify-ca skips hostname.
            ctx.check_hostname = sslmode == "verify-full"
            return ctx
        return sslmode


@lru_cache
def get_settings() -> Settings:
    return Settings()
