#!/usr/bin/env bash
# Starts Harbor for end-to-end tests with a fresh data dir, pointing at the fake model server.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
DATA="${E2E_DATA_DIR:-$ROOT/frontend/test-results/harbor-data}"
rm -rf "$DATA" && mkdir -p "$DATA"
export HARBOR_DATA_DIR="$DATA"
export HARBOR_FRONTEND_DIST="$ROOT/frontend/dist"
export HARBOR_SANDBOX="${E2E_SANDBOX:-local}"
export HARBOR_SANDBOX_IMAGE="${E2E_SANDBOX_IMAGE:-python:3.12-alpine}"
export HARBOR_LLM_PROVIDER=anthropic
export HARBOR_LLM_BASE_URL="http://127.0.0.1:${FAKE_LLM_PORT:-9100}"
export HARBOR_LLM_API_KEY=test-key
export HARBOR_SCHEDULER_INTERVAL=2
export HARBOR_SANDBOX_PREFIX=harbor-e2e
if [ "$HARBOR_SANDBOX" = docker ]; then docker ps -aq --filter name=harbor-e2e- | xargs -r docker rm -f >/dev/null; fi
cd "$ROOT/backend"
exec "$PY" -m uvicorn harbor.main:app --host 127.0.0.1 --port "${HARBOR_PORT:-8765}" --log-level warning
