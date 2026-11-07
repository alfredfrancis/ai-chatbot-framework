<p align="center"><img src="frontend/public/favicon.svg" width="72" alt="AI Chatbot Framework logo"></p>

<h1 align="center">AI Chatbot Framework</h1>

<p align="center">A lean, self-hosted AI agent that everyone can use. Each person gets an assistant with
its own private computer, their files, skills, app connections and scheduled jobs.</p>

![Home](docs/screenshots/e2e/02-home.png)

> AI Chatbot Framework used to be an intent/entity NLU chatbot builder. Version 2 rebuilds it as an
> agent. The old code is in the git history.

## Features

- **Any model through LangChain** – Claude (default), OpenAI, any OpenAI-compatible server (Ollama,
  OpenRouter, vLLM, LiteLLM) or any other LangChain chat provider.
- **A lean, modern agent loop** – four tools (`read`, `write`, `edit`, `bash`) plus MCP tools; parallel
  read-only calls; long outputs truncated and saved to a file; context compaction; **steering** (type
  while the agent works and it picks your message up at the next step); **Stop** at any time.
- **One private sandbox per user** – a Docker container with a persistent `/workspace`, resource limits
  and no Linux capabilities. Commands and local MCP servers run there.
- **Files, not forms** – `context.md` (about you) and `memory.md` (what the agent remembers) are plain
  files the agent reads every turn and edits itself. The UI is a read-only file browser with preview,
  upload and download; to change anything, you ask the agent.
- **Skills** – the open Agent Skills format (`skills/<name>/SKILL.md`). Upload a `.zip` or a `SKILL.md`,
  or let the agent write its own. Only names and descriptions are in the prompt until a task needs one.
- **MCP** – Claude-Desktop-style JSON config. Local servers run inside the sandbox; remote servers use
  Streamable HTTP with **OAuth sign-in** in a browser popup.
- **Recurring tasks** – "every weekday at 08:00 …"; each run becomes a chat.
- A calm, keyboard-friendly interface (⌘K command menu, shortcuts), dark and light themes, phone layout,
  built from a documented design system whose tokens live in `design/tokens.json`.

| Steering while it works | Skills | Connections (OAuth) |
|---|---|---|
| ![](docs/screenshots/e2e/04-steering-queued.png) | ![](docs/screenshots/e2e/07-skills.png) | ![](docs/screenshots/e2e/09-connections-connected.png) |
| **Files** | **Command menu (⌘K)** | **Phone, light** |
| ![](docs/screenshots/e2e/06-files.png) | ![](docs/screenshots/e2e/15-command-menu.png) | ![](docs/screenshots/e2e/14-phone-light-chat.png) |

All screenshots are taken by the end-to-end tests (`docs/screenshots/e2e/`).

## Run it in production (Docker)

On a server with Docker and a domain pointing at it:

```sh
git clone https://github.com/alfredfrancis/ai-chatbot-framework.git && cd ai-chatbot-framework
cp .env.example .env        # set ACF_DOMAIN, POSTGRES_PASSWORD and ANTHROPIC_API_KEY (or another model)
docker compose up -d        # or: make up
```

Open `https://<ACF_DOMAIN>` and create the first account, then set `ACF_ALLOW_SIGNUP=false`.
[Caddy](https://caddyserver.com) gets and renews the HTTPS certificate; ports 80 and 443 must be open.
The stack pulls the published images (`ACF_REGISTRY`/`ACF_VERSION` in `.env`); to build from source
instead (needed until the first release publishes images), run `docker compose up -d --build`. The
database is PostgreSQL in its own container (volume `postgres-data`); workspaces live in `./data`, or
`ACF_DATA_PATH`. Back up both. Logs are rotated and the app has a health check.

The app mounts the Docker socket to start one sandbox container per user. Whoever controls the Docker
socket controls the host, so run it on a machine dedicated to it.

## Develop in Docker

```sh
docker compose -f docker-compose.dev.yml up --build   # or: make up-dev
```

Web app on http://localhost:5173, API on :8000, both reloading when you save. PostgreSQL is on
host port 55432 (`postgresql://acf:acf@localhost:55432/acf`). If a port is taken, set
`ACF_DEV_WEB_PORT`, `ACF_DEV_API_PORT` or `ACF_DEV_DB_PORT`. Port 8000 is only the API; use 5173. Agents run in real
sandboxes, and a scripted fake model answers so no API key is needed (try `run: ls`, `show system`).
To use a real model: `ACF_LLM_BASE_URL= ANTHROPIC_API_KEY=sk-ant-... make up-dev`.
Without Docker, `make setup && make dev` runs the same thing on your machine.

## Configuration

Environment variables (users can override the model in **Settings**):

| Variable | Default | Meaning |
|---|---|---|
| `ACF_LLM_PROVIDER` | `anthropic` | Any LangChain provider id: `anthropic`, `openai`, `ollama`, `google_genai`, … |
| `ACF_LLM_MODEL` | `claude-opus-5-5` / `gpt-4.1-mini` | Default model |
| `ACF_LLM_API_KEY` | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Server-wide key |
| `ACF_LLM_BASE_URL` | provider default | e.g. `http://localhost:11434/v1` with `openai` for Ollama |
| `ACF_MAX_AGENT_STEPS` | `40` | Model calls per message |
| `ACF_COMPACT_TOKENS` / `ACF_COMPACT_KEEP_TOKENS` | `120000` / `20000` | When to summarise old messages, and how much recent history to keep |
| `ACF_DB_URL` | SQLite in `ACF_DATA_DIR` | Database. The Docker stacks use PostgreSQL (`postgresql://user:pass@host/db`) |
| `ACF_DATA_DIR` | `./data` | Workspaces (and the SQLite file when no `ACF_DB_URL` is set) |
| `ACF_ALLOW_SIGNUP` | `true` | Set `false` after creating accounts |
| `ACF_COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `ACF_SANDBOX` | `docker` | `docker`, or `local` for development (**not isolated**) |
| `ACF_SANDBOX_IMAGE` | `acf-sandbox:latest` | Sandbox image |
| `ACF_SANDBOX_NETWORK` | `bridge` | `none` cuts sandboxes off from the internet |
| `ACF_SANDBOX_MEMORY` / `_CPUS` | `1g` / `1` | Limits per sandbox |
| `ACF_SANDBOX_HOST_DATA_DIR` | – | Host path of the data dir when the app itself runs in Docker |
| `ACF_MCP_PRESETS_FILE` | – | JSON list of extra one-click apps for the Connections page (see below) |

Other LangChain providers need their package installed (`pip install langchain-ollama`, …).

### MCP configuration

Add, edit, turn off or delete connections from the form on the **Connections** page. Switch to **JSON** there
to edit the whole configuration directly (same format as Claude Desktop; needed for extra keys like `oauth`,
which the form keeps but doesn't edit). The API equivalents are `PUT`/`DELETE /api/mcp/servers/{name}` and
`PUT /api/mcp/config`.

```json
{
  "mcpServers": {
    "filesystem": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"] },
    "linear":     { "url": "https://mcp.linear.app/mcp" },
    "internal":   { "url": "https://mcp.example.com/mcp", "headers": { "X-Api-Key": "…" } },
    "github":     { "url": "https://api.example.com/mcp", "oauth": { "client_id": "…", "scopes": ["repo"] } }
  }
}
```

**Popular apps.** The Connections page lists remote MCP servers that support OAuth dynamic client
registration — Linear, Notion, Jira & Confluence, Sentry, monday.com, Canva, Intercom, Stripe, Vercel and
Hugging Face. **Add** writes the entry into your configuration; **Sign in** does the rest, no API key needed.
To add your own (or override a built-in one by `id`), point `ACF_MCP_PRESETS_FILE` at a JSON file:

```json
[{ "id": "acme", "name": "Acme", "description": "Tickets and docs", "url": "https://mcp.acme.com/mcp" }]
```

### Skills

A skill is a folder with a `SKILL.md`:

```markdown
---
name: weekly-report
description: Write the weekly sales report. Use when asked for the weekly report.
---
# Weekly report
1. Run `python skills/weekly-report/make.py data/sales.csv`
2. …
```

Upload it as a `.zip` (or just the `SKILL.md`) on the Skills page, or ask the agent to create one —
every workspace starts with a `skill-creator` skill that teaches it how.

## Development

```sh
make setup          # Python venv + npm install
make sandbox-image  # or set ACF_SANDBOX=local
make dev            # API :8000 + web :5173
make test           # backend tests (Docker tests run when a daemon is available)
make e2e            # Playwright end-to-end tests (writes docs/screenshots/e2e)
make e2e-docker     # the same with real Docker sandboxes (what CI runs)
make lint
```

Design tokens: edit `design/tokens.json` (mirrors the design system in Claude Design), then
`cd frontend && npm run tokens` regenerates `src/tokens.css`.

Tests never call a real model: `backend/tests/fakes/` has a scripted model server (Anthropic and
OpenAI APIs), a dependency-free stdio MCP server and an OAuth-protected HTTP MCP server.

Read [AGENTS.md](AGENTS.md) before contributing. Architecture: [docs/architecture.md](docs/architecture.md).

## Known limitations

- Replies arrive per step, not token by token.
- API keys and OAuth tokens are stored unencrypted in the database. Protect it and its backups.
- No schema migrations yet: tables are created at startup. A future schema change will need Alembic.
- Sandboxes run as root inside the container (no capabilities, `no-new-privileges`). For stronger
  isolation use gVisor (`--runtime=runsc`) on the Docker host.
- One app process: the scheduler and running agents live in it, so don't run several replicas.

## License

MIT, see [License.txt](License.txt).
