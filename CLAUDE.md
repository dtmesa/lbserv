# lbserv — project rules

Real-time gaming leaderboard: FastAPI + PostgreSQL backend (`backend/`), React + Vite frontend
(`frontend/`), deployed to DigitalOcean App Platform (`.do/app.yaml`).

## Commands

| Task | Command |
|---|---|
| Backend tests | `make test-backend` (needs Postgres; `DATABASE_URL` → `lbserv_test`) |
| Backend lint/types | `make lint-backend` (ruff + mypy strict) |
| Export OpenAPI contract | `make openapi` → `openapi/openapi.json` |
| Regenerate frontend API code | `make gen` → `frontend/src/api/generated/` |
| Contract drift check | `make contract` |
| Frontend checks | `make lint-frontend test-frontend` |
| Secret scan | `make gitleaks` |
| Migrations | `cd backend && uv run alembic revision -m "..."` then `uv run alembic upgrade head` |

## Rule: no manual typing on the frontend (API types are generated)

The Pydantic models in `backend/app/schemas.py` are the single source of truth for the API.

- **Never hand-write** TypeScript interfaces, type aliases, zod schemas, fetch calls, or
  EventSource clients for API shapes in `frontend/`. Import from `frontend/src/api/generated/`
  (`types.gen`, `zod.gen`, `sdk.gen`, `@tanstack/react-query.gen`).
- **Never edit** `frontend/src/api/generated/**` or `openapi/openapi.json` by hand. A PreToolUse
  hook blocks it.
- **Never cast** API data with `as`; use generated types and zod validators.
- To change the contract: edit `backend/app/schemas.py` (and routes) → `make openapi gen` → use
  the regenerated types → `make contract` must be clean.
- Form validation uses generated zod schemas via `zodResolver` (compose with `.pick()`/`.extend()`
  on generated schemas if needed, never `z.object` from scratch).
- ESLint enforces this (`frontend/eslint.config.js`); CI fails on drift.

## Rule: errors are RFC 9457 problem details

- Every non-2xx response is `application/problem+json` shaped like `ProblemDetails`.
- Raise a `ProblemException` subclass from `backend/app/problems.py` for domain errors; add a new
  subclass (with a stable `code`) rather than raising bare `HTTPException`.
- Document error statuses on routes with `responses=problem_responses(...)`.
- Validation errors carry `errors[]` with `pointer` (JSON Pointer into the body) or `parameter`.
- Frontend: every failure is normalized to `ProblemDetails` in `frontend/src/api/client.ts`;
  map `errors[].pointer` onto form fields with `problemFieldErrors()`.

## Other conventions

- Leaderboard keeps each user's **best** score per game; ranking order is
  `best_score DESC, achieved_at ASC, user_id ASC` (see `backend/app/services/leaderboard.py`).
- Scores are capped at `2**53 - 1` so they stay exact in JavaScript.
- Real-time updates: `pg_notify` inside the score transaction → `LeaderboardBroker` → SSE.
- Secrets never go in the repo. Gitleaks runs in pre-commit and CI; use `.env` (gitignored) locally
  and App Platform secrets in production.
- Sentry is enabled only when `SENTRY_DSN` (backend) / `VITE_SENTRY_DSN` (frontend) is set. Only 5xx
  and unexpected client failures are reported; 4xx problems are expected.
