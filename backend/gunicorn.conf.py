"""Gunicorn process manager with Uvicorn workers (production entrypoint).

Connection budget per API instance = WEB_CONCURRENCY x (1 LISTEN + DB_POOL_SIZE + DB_MAX_OVERFLOW).
Defaults: 2 x (1 + 2 + 2) = 10, so an old and a new instance overlapping during a deploy plus the
migrate job (21) stay within a 1 GiB managed PostgreSQL node's 22 backend connections.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
worker_class = "uvicorn_worker.UvicornWorker"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))

# For async workers this is a heartbeat timeout, not a request timeout: long-lived SSE is fine.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
# On deploys, give requests time to finish; open SSE streams are closed and clients reconnect.
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "20"))
# Keep idle keep-alive connections open longer than the platform load balancer's idle timeout.
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "75"))

# App Platform terminates TLS and forwards X-Forwarded-* headers.
forwarded_allow_ips = "*"

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
# Not preloaded: each worker opens its own DB pool and LISTEN connection in the app lifespan.
preload_app = False
