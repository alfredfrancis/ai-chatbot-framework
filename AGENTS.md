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
  db.py              SQLAlchemy models + session helpers (PostgreSQL in Docker, SQLite by default); migrate()
  migrations/        Alembic migrations, run at startup; `make migration m="…"` writes one from model changes
  auth.py            email/password (scrypt), cookie sessions
  llm.py             LangChain init_chat_model, friendly errors, token estimate
  agent/loop.py      Run: steering, stop, parallel tools, compaction, events, history repair
  agent/tools.py     read / write / edit / bash + output truncation
  agent/subagents.py the `agent` tool: sub-agents with a fresh context and their own model, run in parallel
  agent/prompt.py    system prompt (built once per turn): instructions + context.md + skills + apps + project + memory.md
  agent/review.py    background review every N user messages: updates memory.md and skills
  agent/transcripts.py  past chats as .acf/chats/<id>.md for the agent to grep
  bus.py             run state shared by app processes: chat leases, inbox, run feeds, signals, locks (memory or Redis)
  scan.py            prompt-injection check for memory.md, skills and skill uploads
  acp.py             Agent Client Protocol over WebSocket (/api/acp): the chat interface for web + external apps
  acp_bridge.py      stdio <-> ACP WebSocket bridge for editor-style clients
  apps.py            personal apps: apps/<id>/app.json + app.oui (OpenUI Lang) + one action API
  artifacts.py       a chat's artifacts: files attached to it and files the agent made in it
  skills.py          skill discovery, upload (zip / SKILL.md), built-in skills (builtin_skills/), archiving
  workspace.py       per-user folder, path safety
  sandbox.py         Sandbox port + adapters: DockerSandbox (one container per user), LocalSandbox (dev only)
  docker_proxy.py    the only holder of the Docker socket in production; allows sandbox operations only
  secrets_box.py     encryption at rest for secret DB columns (db.EncryptedText, ACF_SECRET_KEY)
  mcp_client.py      config parsing, McpHub (one asyncio task per server connection), mcp_call + .acf/mcp/ files
  oauth.py           OAuth client for remote MCP servers
  projects.py        projects: instructions + an optional workspace folder; chats and tasks belong to one via project_id
  scheduler.py       tasks: repeating (cron) or one-off (run_at)
  system_mcp.py      built-in `system` MCP server: app features for the agent (tasks)
  api/routes.py      every HTTP endpoint
backend/tests/       pytest; fakes/ = scripted model server + stdio MCP + OAuth MCP servers
frontend/src/        React + Vite; pages/ per screen; openui/ = the component library personal apps and chat views are written in; styles.css (components) + tokens.css (generated)
design/              tokens.json (source of truth), README.md (brand book), components.css
PRODUCT.md           who it's for, purpose, principles, accessibility bar (read before UI or copy work)
DESIGN.md            generated: tokens.json as DESIGN.md frontmatter + design/README.md (for design tools)
frontend/e2e/        Playwright specs; they also write docs/screenshots/e2e/*.png
sandbox/Dockerfile   the sandbox image
deploy/              Caddyfile, host hardening guide (gVisor, userns-remap), sandbox egress firewall
```

## Commands

```
make setup        # venv + npm install
make dev          # API :8000 + web :5173 (ACF_SANDBOX=local if no Docker)
make test         # backend tests (Docker tests auto-skip without a daemon)
make e2e          # build web app + Playwright (local sandbox)
make e2e-docker   # same with real Docker sandboxes (CI)
make e2e-replicas # same with two app processes behind a round-robin proxy (CI runs Docker + two)
make lint         # ruff + tsc
```

## Rules

1. **Every feature is tested end to end, including the UI.** User-visible changes need a Playwright spec
   in `frontend/e2e/` driving the real UI against the real backend, plus a `shot()` at the key moment.
   Backend logic also gets a pytest. Never weaken or skip a test to make it pass.
2. **No real model or network calls in tests.** Extend `backend/tests/fakes/fake_llm.py` (rules like
   `run: …`, `read: a b`, `edit: p | old | new`, `tool: <name> <json>`, `show system`, `show messages`).
3. **Keep the harness lean.** Prefer a file + the four tools (and `agent` for sub-agents) over a new tool. A new built-in tool needs a
   strong reason; MCP and skills are the extension points. No custom UI editors for context files — the
   agent edits files; the UI browses them.
4. **Model access goes through LangChain** (`acf.llm.make_model`). Don't import provider SDKs elsewhere.
   History is append-only: store `message_to_dict(ai)` and replay it verbatim.
5. **Isolation is a feature.** Anything the agent executes goes through `Sandbox` (`exec`, or `process()` for
   long-lived processes); never branch on the adapter's kind, and every adapter passes
   `tests/test_sandbox_contract.py`. User/model paths go through `workspace.resolve`. Every query is scoped to `current_user`.
6. **MCP connections live in their own task** (`_Connection._run`); never enter SDK contexts in one task
   and exit them in another.
7. **Design** follows the "AI Chatbot Framework" design system (Claude Design). Its tokens are committed as
   `design/tokens.json` — the single source; `npm run tokens` (also run by `build`/`dev`) generates
   `frontend/src/tokens.css` and the root `DESIGN.md`, which must never be edited by hand (CI checks both).
   `design/README.md` is the brand book (in DESIGN.md's section order) and `design/components.css` the
   reference component styles. `PRODUCT.md` says who it is for and the accessibility bar (WCAG 2.2 AA).
   Dark first, light via the OS; the logo green (`brand-signal`) is for the mark only, `accent` for the one
   primary action, focus and live state. Text ≥ 16px (caption 13px floor), controls 40px. No new colours or one-off values in
   components; inline 1.75px stroke SVG icons in `components/icons.tsx`. Light + dark + 390px wide must
   all work; real buttons/labels (tests select by role and label). Keyboard: ⌘K menu, `C`, `G`+letter.
8. **Style**: Python 3.12, ruff (line length 120), type hints on public functions; TypeScript strict.

## Workflow

1. Read the relevant modules and tests. 2. Write the failing test(s). 3. Implement. 4. `make lint test e2e`
(and `make e2e-docker` for sandbox/MCP changes). 5. Update README/docs when behaviour or config changes.

## Gotchas

- Docker deployments need `ACF_SANDBOX_HOST_DATA_DIR` (bind mounts use host paths).
- Sandboxes never run as root: Docker tests must run as a non-root user. A change to how DockerSandbox
  calls Docker must also pass `docker_proxy.Policy` (tests/test_docker_proxy.py); never widen the
  proxy to get a feature working without a test that the unsafe variant is still refused.
- The server's model key only goes to the server's own provider and address (`LLMConfig.for_user`).
- Columns holding secrets use `EncryptedText`; never put secrets in other columns.
- A model change needs a migration (`make migration m="…"`, then read and fix what it wrote);
  `tests/test_migrations.py` fails when models and migrations disagree. Never edit a released migration.
- Keep DB sessions short; never hold one across an `await` on the model. PostgreSQL enforces column
  lengths (SQLite doesn't): bound user input in the API models and run tests on both
  (`ACF_TEST_DB_URL=postgresql://… make test`; CI runs both).
- Build the system prompt once per turn (`Run._turn`); never rebuild it per step — that breaks the cache.
- Thinking blocks are bound to their prefix: only compaction may drop them, and only for messages
  before the cut.
- The app scales out: any process serves any request. State that outlives a request lives in the database
  or goes through `acf.bus` (leases, inbox, feeds, signals, locks) — never in a module-level dict or a
  process-local lock. Bus/multi-process changes need `tests/test_bus.py` / `tests/test_cluster.py` (real
  processes + Redis; they skip without `redis-server` or `ACF_TEST_REDIS_URL`).
- All chat traffic is ACP (`acp.py`, `frontend/src/acp.ts`); there are no chat REST/SSE endpoints. Backend
  tests drive it in-process with `tests/acp_client.py` (`send()` / `prompt()` in conftest).
- Personal apps and ` ```openui ` blocks in chat replies are OpenUI Lang rendered by `frontend/src/openui/library.tsx`
  (+ `charts.tsx`). Changing it regenerates `backend/acf/builtin_skills/openui/reference.md` (`npm run build`); commit both.
  Install with `OPENUI_TELEMETRY_DISABLED=1` (`@openuidev/lang-core` pings PostHog on install otherwise).
- The E2E Playwright version is pinned to the preinstalled browser build (1.63.0).
