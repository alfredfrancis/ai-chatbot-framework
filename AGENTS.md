# AGENTS.md

Guide for coding agents (and humans) working on Harbor. Read this before changing code.

## What Harbor is

A simple personal AI agent for non-technical people. Each user gets:

- a chat with an LLM that can call tools (Claude via the Anthropic SDK, or any OpenAI-compatible server)
- one private Docker sandbox (`harbor-sbx-<user id>`) with a persistent `/workspace`
- two Markdown files that steer the agent: `context.md` (user-written) and `memory.md` (agent-written)
- MCP servers from a Claude-Desktop-style JSON config: local servers run inside the sandbox, remote
  servers use Streamable HTTP with OAuth 2.1 (PKCE + dynamic client registration)
- recurring tasks (cron + prompt); each run creates a chat

## Layout

```
backend/harbor/
  main.py          FastAPI app; serves /api and the built web app
  config.py        HARBOR_* environment settings (always read via `config.settings`)
  db.py            SQLAlchemy models (SQLite by default) + session helpers
  auth.py          email/password, scrypt hashes, cookie sessions
  llm.py           provider-neutral messages; AnthropicLLM (SDK) and OpenAICompatLLM (httpx)
  agent.py         system prompt, built-in tools, the agent loop, SSE events
  sandbox.py       DockerSandbox (one container per user) and LocalSandbox (dev only, not isolated)
  workspace.py     per-user folder, path safety, context.md / memory.md
  mcp_client.py    config parsing, McpHub (one asyncio task per server connection)
  oauth.py         OAuth client for remote MCP servers
  scheduler.py     cron tasks; `tick()` starts due tasks, `loop()` runs in the app lifespan
  api/routes.py    every HTTP endpoint
backend/tests/     pytest; fakes/ has a scripted model server and two MCP servers
frontend/src/      React + Vite; pages/ per screen, styles.css holds all design tokens
frontend/e2e/      Playwright end-to-end tests (start real backend + fakes)
sandbox/Dockerfile the sandbox image (Python, Node/npx, uv/uvx)
```

## Commands

```
make setup        # venv + npm install
make dev          # API on :8000 + web on :5173 (set HARBOR_SANDBOX=local if no Docker)
make test         # backend tests (Docker tests auto-skip without a daemon)
make e2e          # build web app + Playwright tests with the local sandbox
make e2e-docker   # same, with real Docker sandboxes (what CI runs)
make lint         # ruff + tsc
```

## Rules

1. **Every feature is tested end to end, including the UI.** A change that users can see needs a
   Playwright test in `frontend/e2e/` that drives the real UI against the real backend. Backend logic
   also gets a pytest. Never mark work done with failing or skipped tests; never weaken a test to pass.
2. **No real model or network calls in tests.** Use `tests/fakes/fake_llm.py` (scripted: `run: …`,
   `remember: …`, `tool: <name> <json>`, `show system`, …). Extend its rules when you need new behaviour.
3. **Keep it simple.** This product is for non-technical people. Prefer fewer options, plain words in
   the UI ("Sign in", "Runs in your sandbox"), and errors that say what to do next.
4. **Isolation is a feature.** Anything the agent executes goes through `Sandbox` — never `subprocess`
   on the host outside `sandbox.py`. File paths from users or the model go through `workspace.resolve`.
   Every API query is scoped to `current_user`.
5. **Anthropic code uses the official SDK** (`anthropic`), default model `claude-opus-5-5`. Assistant
   turns are stored with their raw content blocks and replayed verbatim (thinking blocks must survive).
   Don't add OpenAI-specific features to the Anthropic path or vice versa.
6. **MCP connections live in their own task** (`_Connection._run`). Don't enter SDK contexts in one task
   and exit them in another.
7. **Design**: minimal, Apple-like. Use the tokens in `frontend/src/styles.css` (`--accent #0071e3`,
   `--surface #f5f5f7`, 8–16px radii, system font). No new colours, gradients, emoji or icon fonts;
   icons are inline stroke SVGs in `components/icons.tsx`. Light and dark mode both work. Layouts must
   work at 390px wide. Real `<button>`/`<label>`; tests select by role/label, so accessible names matter.
   Reference designs: the "Harbor Agent UI" canvas (Claude Design).
8. **Style**: Python 3.12, ruff (line length 110), type hints on public functions. TypeScript strict.
   Comments explain why, not what.

## Workflow for a change

1. Read the relevant module(s) and their tests.
2. Write or extend the failing test first (pytest and/or Playwright).
3. Implement. Keep diffs focused.
4. Run `make lint test e2e` (and `make e2e-docker` if you touched the sandbox or MCP stdio).
5. Update `README.md` / `docs/` when behaviour or configuration changes.

## Gotchas

- `config.settings` is replaced by `reload_settings()` in tests: import the module (`from harbor import
  config`), not the object.
- In Docker deployments Harbor talks to the host's Docker daemon, so bind mounts need the *host* path:
  `HARBOR_SANDBOX_HOST_DATA_DIR`.
- A sandbox container is labelled with its workspace id; if the data folder is recreated the old
  container is replaced automatically (see `DockerSandbox.ensure`).
- SQLite runs in WAL mode; keep DB sessions short and never hold one across an `await` on the model.
