#!/usr/bin/env bash
# Starts AI Chatbot Framework for end-to-end tests with a fresh data dir, pointing at the fake model server.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
DATA="${E2E_DATA_DIR:-$ROOT/frontend/test-results/acf-data}"
rm -rf "$DATA" && mkdir -p "$DATA"
export ACF_DATA_DIR="$DATA"
export ACF_FRONTEND_DIST="$ROOT/frontend/dist"
export ACF_SANDBOX="${E2E_SANDBOX:-local}"
export ACF_SANDBOX_IMAGE="${E2E_SANDBOX_IMAGE:-python:3.12-alpine}"
export ACF_LLM_PROVIDER=anthropic
export ACF_LLM_BASE_URL="http://127.0.0.1:${FAKE_LLM_PORT:-9100}"
export ACF_LLM_API_KEY=test-key
export ACF_SCHEDULER_INTERVAL=2
export ACF_SANDBOX_PREFIX=acf-e2e
if [ "$ACF_SANDBOX" = docker ]; then docker ps -aq --filter name=acf-e2e- | xargs -r docker rm -f >/dev/null; fi
cd "$ROOT/backend"
exec "$PY" -m uvicorn acf.main:app --host 127.0.0.1 --port "${ACF_PORT:-8765}" --log-level warning
