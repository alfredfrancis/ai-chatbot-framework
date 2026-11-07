# AGENTS.md

Guide for coding agents (and humans) working on AI Chatbot Framework. Read this before changing code.

## What it is

A lean, self-hosted agent for non-technical people. Each user gets a chat with an LLM (via LangChain),
one private Docker sandbox with a persistent `/workspace`, plain-file memory (`context.md`, `memory.md`),
skills (`skills/<name>/SKILL.md`), MCP connections (stdio in the sandbox, HTTP with OAuth) and
recurring tasks. Design of the agent loop: [docs/architecture.md](docs/architecture.md).

## Layout

```
backend/acf/
  main.py            FastAPI app; serves /api and the built web app
  config.py          ACF_* settings — always read as `config.settings` (tests reload it)
  db.py              SQLAlchemy models (SQLite) + session helpers
  auth.py            email/password (scrypt), cookie sessions
  llm.py             LangChain init_chat_model, friendly errors, token estimate
  agent/loop.py      Run: steering, stop, parallel tools, compaction, events, history repair
  agent/tools.py     read / write / edit / bash + output truncation
  agent/prompt.py    system prompt: instructions + context.md + memory.md + skills index
  skills.py          skill discovery, upload (zip / SKILL.md), built-in skill-creator
  workspace.py       per-user folder, path safety
  sandbox.py         DockerSandbox (one container per user), LocalSandbox (dev only, not isolated)
  mcp_client.py      config parsing, McpHub (one asyncio task per server connection)
  oauth.py           OAuth client for remote MCP servers
  scheduler.py       cron tasks
  api/routes.py      every HTTP endpoint
backend/tests/       pytest; fakes/ = scripted model server + stdio MCP + OAuth MCP servers
frontend/src/        React + Vite; pages/ per screen; styles.css holds all design tokens
frontend/e2e/        Playwright specs; they also write docs/screenshots/e2e/*.png
sandbox/Dockerfile   the sandbox image
```

## Commands

```
make setup        # venv + npm install
make dev          # API :8000 + web :5173 (ACF_SANDBOX=local if no Docker)
make test         # backend tests (Docker tests auto-skip without a daemon)
make e2e          # build web app + Playwright (local sandbox)
make e2e-docker   # same with real Docker sandboxes (CI)
make lint         # ruff + tsc
```

## Rules

1. **Every feature is tested end to end, including the UI.** User-visible changes need a Playwright spec
   in `frontend/e2e/` driving the real UI against the real backend, plus a `shot()` at the key moment.
   Backend logic also gets a pytest. Never weaken or skip a test to make it pass.
2. **No real model or network calls in tests.** Extend `backend/tests/fakes/fake_llm.py` (rules like
   `run: …`, `read: a b`, `edit: p | old | new`, `tool: <name> <json>`, `show system`, `show messages`).
3. **Keep the harness lean.** Prefer a file + the four tools over a new tool. A new built-in tool needs a
   strong reason; MCP and skills are the extension points. No custom UI editors for context files — the
   agent edits files; the UI browses them.
4. **Model access goes through LangChain** (`acf.llm.make_model`). Don't import provider SDKs elsewhere.
   History is append-only: store `message_to_dict(ai)` and replay it verbatim.
5. **Isolation is a feature.** Anything the agent executes goes through `Sandbox`. User/model paths go
   through `workspace.resolve`. Every query is scoped to `current_user`.
6. **MCP connections live in their own task** (`_Connection._run`); never enter SDK contexts in one task
   and exit them in another.
7. **Design** (canvas "AI Chatbot Framework — UI", round 3): ink `#111114` pill buttons, signal green
   `#4BE3B0` for the brand mark/glow/success only (text uses `#0B7A5A`), mist surfaces, glass sidebar,
   12–28px radii, system font. Use the tokens in `styles.css`; no new colours, no emoji, inline stroke
   SVG icons in `components/icons.tsx`. Light + dark + 390px wide must all work. Real buttons/labels:
   tests select by role and label.
8. **Style**: Python 3.12, ruff (line length 120), type hints on public functions; TypeScript strict.

## Workflow

1. Read the relevant modules and tests. 2. Write the failing test(s). 3. Implement. 4. `make lint test e2e`
(and `make e2e-docker` for sandbox/MCP changes). 5. Update README/docs when behaviour or config changes.

## Gotchas

- Docker deployments need `ACF_SANDBOX_HOST_DATA_DIR` (bind mounts use host paths).
- SQLite (WAL): keep DB sessions short; never hold one across an `await` on the model.
- Thinking blocks are bound to their prefix: only compaction may drop them, and only for messages
  before the cut.
- The E2E Playwright version is pinned to the preinstalled browser build (1.63.0).
