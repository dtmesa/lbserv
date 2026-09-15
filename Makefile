.PHONY: help install openapi gen contract test test-backend test-frontend lint lint-backend lint-frontend \
	migrate dev-api dev-web db gitleaks check

TEST_DATABASE_URL ?= postgresql://postgres:postgres@localhost:5432/lbserv_test
GITLEAKS_IMAGE ?= ghcr.io/gitleaks/gitleaks:v8.30.1

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd backend && uv sync --frozen
	cd frontend && npm ci

db: ## Start local Postgres (docker compose)
	docker compose up -d db

migrate: ## Apply database migrations
	cd backend && uv run alembic upgrade head

dev-api: ## Run the API with reload on :8000
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-web: ## Run the Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev -- --host 0.0.0.0

openapi: ## Export the OpenAPI contract from the Pydantic backend
	cd backend && uv run python -m app.scripts.export_openapi ../openapi/openapi.json

gen: ## Regenerate frontend types, zod schemas, SDK and query hooks from the contract
	cd frontend && npm run gen:api

contract: openapi gen ## Fail if the contract or generated code is out of date
	git diff --exit-code -- openapi/openapi.json frontend/src/api/generated
	@test -z "$$(git ls-files --others --exclude-standard -- openapi frontend/src/api/generated)" \
		|| (echo "Untracked generated files; commit them." && exit 1)

test-backend: ## Run backend tests
	cd backend && DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest

test-frontend: ## Run frontend tests
	cd frontend && npm test

test: test-backend test-frontend ## Run all tests

lint-backend: ## Ruff + mypy
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app

lint-frontend: ## ESLint + TypeScript
	cd frontend && npm run lint && npm run typecheck

lint: lint-backend lint-frontend ## Run all linters

gitleaks: ## Scan the working tree for secrets
	@if command -v gitleaks >/dev/null; then gitleaks dir --config .gitleaks.toml --redact . ; \
	else docker run --rm -v "$$PWD:/repo" -w /repo $(GITLEAKS_IMAGE) dir --config .gitleaks.toml --redact . ; fi

check: lint test contract gitleaks ## Everything CI runs
