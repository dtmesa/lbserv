"""Sentry error monitoring."""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import Settings


def init_sentry(settings: Settings) -> bool:
    if settings.sentry_dsn is None:
        return False
    # Only 5xx are errors worth alerting on; 4xx problems are expected client mistakes.
    failed = {*range(500, 600)}
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.sentry_environment,
        release=settings.sentry_release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        integrations=[
            StarletteIntegration(failed_request_status_codes=failed),
            FastApiIntegration(failed_request_status_codes=failed),
        ],
    )
    return True
