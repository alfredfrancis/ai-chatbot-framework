#!/usr/bin/env bash
# Starts AI Chatbot Framework for end-to-end tests with a fresh data dir, pointing at the fake model server.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
DATA="${E2E_DATA_DIR:-$ROOT/frontend/test-results/acf-data}"
rm -rf "$DATA" && mkdir -p "$DATA"
export ACF_DATA_DIR="$DATA"
# E2E_DB_URL (e.g. PostgreSQL in CI) is emptied first so every run starts clean; default is SQLite in $DATA.
if [ -n "${E2E_DB_URL:-}" ]; then
  export ACF_DB_URL="$E2E_DB_URL"
  (cd "$ROOT/backend" && "$PY" -c "from acf import db, config; db.init_db(); db.Base.metadata.drop_all(db._engine); db.Base.metadata.create_all(db._engine)")
fi
export ACF_FRONTEND_DIST="$ROOT/frontend/dist"
export ACF_SANDBOX="${E2E_SANDBOX:-local}"
export ACF_SANDBOX_IMAGE="${E2E_SANDBOX_IMAGE:-python:3.12-alpine}"
export ACF_LLM_PROVIDER=anthropic
export ACF_LLM_BASE_URL="http://127.0.0.1:${FAKE_LLM_PORT:-9100}"
export ACF_LLM_API_KEY=test-key
export ACF_SCHEDULER_INTERVAL=2
# A background review every 2 user messages (learning.spec); without a "learn:" message it saves nothing.
export ACF_REVIEW_INTERVAL=2
export ACF_SANDBOX_PREFIX=acf-e2e
# Main account from the environment; sign-ups stay open so every spec can make its own user.
export ACF_ADMIN_EMAIL=owner@example.com ACF_ADMIN_PASSWORD="owner password" ACF_ADMIN_NAME=Olivia
export ACF_ALLOW_SIGNUP=true
export ACF_MCP_PRESETS_FILE="$ROOT/frontend/e2e/presets.json"
export ACF_SECRET_KEY="${ACF_SECRET_KEY:-e2e-secret-key-that-is-long-enough-0000}"
cd "$ROOT/backend"
if [ "$ACF_SANDBOX" = docker ]; then
  docker ps -aq --filter name=acf-e2e- | xargs -r docker rm -f >/dev/null
  # As in production: the app reaches Docker only through the narrow proxy, on its own sandbox network.
  export ACF_SANDBOX_NETWORK="${E2E_SANDBOX_NETWORK:-acf-e2e-sandbox}" ACF_SANDBOX_BRIDGE="${E2E_SANDBOX_BRIDGE:-acf-e2e0}"
  PROXY_PORT="${E2E_DOCKER_PROXY_PORT:-2399}"
  "$PY" -m acf.docker_proxy --listen "127.0.0.1:$PROXY_PORT" --socket "${E2E_DOCKER_SOCKET:-/var/run/docker.sock}" &
  PROXY=$!
  trap 'kill $PROXY 2>/dev/null' EXIT INT TERM
  export DOCKER_HOST="tcp://127.0.0.1:$PROXY_PORT"
  "$PY" -m uvicorn acf.main:app --host 127.0.0.1 --port "${ACF_PORT:-8765}" --log-level warning
  exit
fi
exec "$PY" -m uvicorn acf.main:app --host 127.0.0.1 --port "${ACF_PORT:-8765}" --log-level warning
