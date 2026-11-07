# Common tasks. Run `make help` for the list.
PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: help setup dev api web test test-fast e2e e2e-docker lint format build sandbox-image up up-dev down down-dev

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup: ## Install backend (venv) and frontend dependencies
	python3 -m venv .venv
	$(PIP) install -e "backend[dev]"
	cd frontend && npm install

api: ## Run the API on :8000 with reload (sandbox=docker unless ACF_SANDBOX=local)
	cd backend && ../$(PY) -m uvicorn acf.main:app --reload --port 8000

web: ## Run the web app on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

dev: ## Run API and web app together
	$(MAKE) -j2 api web

test: ## Backend tests (Docker tests run when a daemon is available)
	cd backend && ../$(PY) -m pytest -q

test-fast: ## Backend tests without Docker
	cd backend && ../$(PY) -m pytest -q -m "not docker"

e2e: ## Build the web app and run Playwright end-to-end tests (local sandbox)
	cd frontend && npm run build && npm run e2e

e2e-docker: ## End-to-end tests against real Docker sandboxes
	cd frontend && npm run build && E2E_SANDBOX=docker npm run e2e

lint: ## Lint and typecheck everything
	cd backend && ../.venv/bin/ruff check . && ../.venv/bin/ruff format --check .
	cd frontend && npm run typecheck

format: ## Auto-format Python
	cd backend && ../.venv/bin/ruff format . && ../.venv/bin/ruff check --fix .

sandbox-image: ## Build the per-user sandbox image
	docker build -t acf-sandbox:latest sandbox

build: sandbox-image ## Build the app image
	docker build -t ai-chatbot-framework:latest .

up: ## Production: Caddy + HTTPS on ACF_DOMAIN (see .env.example); pulls published images
	docker compose up -d

down: ## Stop the production stack
	docker compose down

up-dev: ## Development in Docker: hot reload, real sandboxes, fake model (web on :5173)
	docker compose -f docker-compose.dev.yml up --build

down-dev: ## Stop the development stack
	docker compose -f docker-compose.dev.yml down
