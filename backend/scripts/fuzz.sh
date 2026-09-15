#!/usr/bin/env bash
# Property-based API testing with Schemathesis against a throwaway local server.
# Usage: scripts/fuzz.sh [extra `st run` args]   (env: DATABASE_URL, FUZZ_PORT, FUZZ_EXAMPLES)
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${FUZZ_PORT:-8001}"
export API_KEY="${FUZZ_API_KEY:-fuzz-key}"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/lbserv_test}"
export SENTRY_DSN=""

uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

# The SSE stream never completes, so it is excluded here and covered by tests/test_realtime.py.
uv run st run "http://127.0.0.1:${PORT}/api/openapi.json" \
  --wait-for-schema 30 \
  --header "X-API-Key: ${API_KEY}" \
  --checks all \
  --exclude-operation-id streamLeaderboardEvents \
  --max-examples "${FUZZ_EXAMPLES:-100}" \
  --workers 4 \
  --request-timeout 5 \
  --report junit \
  --report-dir reports/schemathesis \
  "$@"
