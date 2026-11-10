<p align="center"><img src="frontend/public/favicon.svg" width="72" alt="AI Chatbot Framework logo"></p>

<h1 align="center">AI Chatbot Framework</h1>

<p align="center">A lean, self-hosted AI agent that everyone can use. Each person gets an assistant with
its own private computer, their files, skills, app connections and scheduled jobs.</p>

![AI Chatbot Framework home: chats, files, skills, tasks, connections and your apps in the sidebar](docs/screenshots/home.webp)

> AI Chatbot Framework used to be an intent/entity NLU chatbot builder. Version 2 rebuilds it as an
> agent. The old code is in the git history.

## Features

- **Any model through LangChain** – Claude (default), OpenAI, any OpenAI-compatible server (Ollama,
  OpenRouter, vLLM, LiteLLM) or any other LangChain chat provider.
- **A lean, modern agent loop** – four tools (`read`, `write`, `edit`, `bash`) plus `mcp_call` for MCP tools; the calls
  of one answer run in parallel; long commands run in the background and report back when done; long outputs truncated and saved to a file; context compaction; **steering** (type
  while the agent works; it picks your message up without stopping — right away while it thinks, after
  the running command otherwise); **Stop** at any time.
- **Sub-agents** – for a job that splits into parts, the agent starts helpers that work side by side, each
  with its own goal, a fresh context and a model the agent picks (its own, a fast one, or any model id),
  then puts their reports together. The chat shows what each one is doing, and each one's own session opens
  read-only (also while it works) from its step in the chat.
- **One private sandbox per user** – a Docker container with a persistent `/workspace`, resource limits
  and no Linux capabilities. Commands and local MCP servers run there.
- **Files, not forms** – `context.md` (about you) and `memory.md` (what the agent remembers) are plain
  files the agent reads every turn and edits itself. The UI is a read-only file browser with preview,
  upload and download; to change anything, you ask the agent. `memory.md` has a size limit
  (`ACF_MEMORY_LIMIT`) so it stays a short list of facts that matter in every chat.
- **Learns as it goes** – every few messages (`ACF_REVIEW_INTERVAL`) a background pass looks back at the
  chat and updates `memory.md` and the skills (a corrected format, a method that worked); the chat shows a
  line saying what changed. Past chats are saved as Markdown in `.acf/chats/` so the agent can search them.
  Text that looks like planted instructions is kept out of memory and skills.
- **Attach files in chat** – the paperclip (or drag and drop) saves files to `uploads/` in the workspace
  (never overwriting: a second `report.csv` becomes `report (1).csv`) and sends them with the message.
  The agent reads them with its tools; the chat shows each attachment as a link to the file.
- **Artifacts panel** – each chat has a side panel (the panel button in its top bar) listing the files
  attached to it and the files the agent made in it, to open or download (`GET /api/chats/{id}/artifacts`).
  "Made" means written or edited by the agent, or changed in the workspace while one of the chat's commands
  was running. That last part goes by file modification time, so a file another chat changes at the same
  moment can show up too. `context.md`, `memory.md`, hidden files and deleted files are not listed.
- **Skills** – the open Agent Skills format (`skills/<name>/SKILL.md`). Upload a `.zip` or a `SKILL.md`,
  or let the agent write its own. Only names and descriptions are in the prompt until a task needs one.
  Type `/` in a chat to pick one: a message with `/name` in it (also a task's prompt) makes the agent
  use that skill.
  Built in: `council-of-llms` (one question to several models as sub-agents; the agent compares their
  answers and gives the best one), `skill-creator`, `pdf`, `action-items`, `weekly-review`, `price-watch`, `cited-research`,
  `plain-writing`, `personal-assistant` (a proactive assistant over email, calendar and other apps, with
  a first-run interview that saves preferences to `assistant/profile.md`, and an optional Cockpit app),
  `openui` (views in chat answers, below) and `personal-apps` (how to build apps, below). Skills unused for
  `ACF_SKILL_ARCHIVE_DAYS` move to `skills/.archive/`.
- **MCP** – Claude-Desktop-style JSON config. Local servers run inside the sandbox; remote servers use
  Streamable HTTP with **OAuth sign-in** in a browser popup. Only tool names are in the prompt; each tool's
  definition is a file in `.acf/mcp/` that the agent reads before its first call, so a large server doesn't
  slow down every turn.
- **Personal apps** – the agent (or a skill) can add up to 5 small apps to the menu, right under New chat,
  e.g. the personal assistant's **Cockpit**: the day's brief and an Eisenhower matrix of to-dos you drag
  around. An app is just files: `apps/<id>/app.json` (menu entry) and `apps/<id>/app.oui`, a screen in
  [OpenUI Lang](https://openui.com) that the web app renders with its own design-system components
  (`frontend/src/openui/library.tsx`) — the agent never writes HTML. There is no app backend: the screen's
  `Query`/`Mutation` calls and buttons use one action API, `POST /api/apps/{id}/actions`: `read_file` and
  `update_file` (the app's folder and files it lists), `ask_agent` (a message to the agent in the app's own
  chat, answered in the background), `run` (an `apps/<id>/actions/<name>.sh` script in the sandbox) and
  `mcp` (read-only tools of connected apps; anything that changes things goes through the agent).
  Diagrams: [docs/personal-apps.md](docs/personal-apps.md).
- **Views in chat** – the agent can answer with a chart, a plan, tabs or a small form inside its reply: an
  ` ```openui ` block written with the same components (bar, line and pie charts, progress, lists, steps,
  tabs, sliders, choices, buttons). A button sends its text back into the chat, so the user can pick
  instead of typing.
- **Projects** – ongoing work with its own instructions and, optionally, a folder in your files. A chat started
  in a project follows its instructions and keeps its files in that folder; a task made in a project runs as a
  chat there. Deleting a project keeps its chats, tasks and files.
- **Scheduled tasks** – repeating ("every weekday at 08:00 …") or once ("tomorrow at 17:00"); each run becomes a
  chat, and a one-off task turns itself off after its run. Set them up on the Tasks page or just ask the agent: the built-in `system` MCP server gives it `list_tasks`, `create_task`, `update_task`,
  `delete_task` and `run_task` (the server name `system` is reserved).
- **Agent Client Protocol (ACP)** – the chat speaks [ACP](https://agentclientprotocol.com) over a
  WebSocket, and so can your own apps and editors. Create an optional access token in
  **Settings → External apps** to let them in.
- A calm, keyboard-friendly interface (⌘K command menu, shortcuts), dark and light themes, phone layout,
  built from a documented design system whose tokens live in `design/tokens.json`.

| Steering while it works | Skills | Connections (OAuth) |
|---|---|---|
| ![](docs/screenshots/e2e/04-steering-queued.png) | ![](docs/screenshots/e2e/07-skills.png) | ![](docs/screenshots/e2e/09-connections-connected.png) |
| **Files** | **Command menu (⌘K)** | **Phone, light** |
| ![](docs/screenshots/e2e/06-files.png) | ![](docs/screenshots/e2e/15-command-menu.png) | ![](docs/screenshots/e2e/14-phone-light-chat.png) |
| **Cockpit app** | **Cockpit, phone** | |
| ![](docs/screenshots/e2e/41-app-cockpit-moved.png) | ![](docs/screenshots/e2e/42-app-cockpit-phone-light.png) | |

All screenshots are taken by the end-to-end tests (`docs/screenshots/e2e/`).

## Run it in production (Docker)

On a server with Docker and a domain pointing at it:

```sh
git clone https://github.com/alfredfrancis/ai-chatbot-framework.git && cd ai-chatbot-framework
cp .env.example .env        # set ACF_DOMAIN, POSTGRES_PASSWORD, ACF_SECRET_KEY and a model key
# prepare the host first: gVisor, user-namespace remapping, sandbox firewall (deploy/README.md)
docker compose up -d        # or: make up
```

Set `ACF_ADMIN_EMAIL` and `ACF_ADMIN_PASSWORD` in `.env` to create your account at startup (sign-ups are
then closed unless `ACF_ALLOW_SIGNUP=true`). Without them, open `https://<ACF_DOMAIN>` and create the first
account, then set `ACF_ALLOW_SIGNUP=false`.
[Caddy](https://caddyserver.com) gets and renews the HTTPS certificate; ports 80 and 443 must be open.
Other host ports: `ACF_HTTP_PORT` / `ACF_HTTPS_PORT` (e.g. `127.0.0.1:8088` behind a tunnel or another proxy).
When that tunnel or proxy terminates HTTPS (e.g. Cloudflare Tunnel), also set `ACF_CADDY_ADDRESS=:80` so Caddy
serves plain HTTP.
The stack pulls the published images (`ACF_REGISTRY`/`ACF_VERSION` in `.env`); to build from source
instead (needed until the first release publishes images), run `docker compose up -d --build`. The
database is PostgreSQL in its own container (volume `postgres-data`); workspaces live in `./data`, or
`ACF_DATA_PATH`. Back up both. Logs are rotated and the app has a health check.

Each user gets one sandbox container. The app runs as a non-root user and never touches the Docker
socket: a small proxy (`docker-proxy`) holds it and allows only sandbox containers with fixed, locked-down
settings. Sandboxes run under gVisor, as a non-root user, on their own network, behind an egress firewall
on the host. **Set up the host as described in [deploy/README.md](deploy/README.md) before going public.**

### Scale out and in

The app is stateless between requests: run state is shared through Redis (in the stack), so you can run
as many app processes as you like and add or remove them at any time:

```sh
docker compose up -d --scale app=3
```

Caddy spreads requests and chat connections over them and picks up new ones within seconds. Any process
serves any chat; each user still has one sandbox and one workspace. A process that is stopped lets its
running agents finish first (`ACF_SHUTDOWN_GRACE`, default 20 s); its clients reconnect to another one and
keep following. One that crashes frees its chats after `ACF_BUS_TTL` (30 s). Across several machines,
every app process needs the same PostgreSQL, Redis and Docker proxy, and the data folder at the same path
(shared storage), because sandboxes mount workspaces from the Docker host. How it works:
[architecture](docs/architecture.md#several-app-processes-backendacfbuspy).

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
| `ACF_LLM_PROVIDERS` | providers that take an API key | Providers users may choose (comma-separated, `*` = any). The server's own is always allowed |
| `ACF_LLM_MODEL` | `claude-opus-5-5` / `gpt-4.1-mini` | Default model |
| `ACF_LLM_API_KEY` | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Server-wide key, used by every user without their own. Only sent to the server's provider and `ACF_LLM_BASE_URL` |
| `ACF_SECRET_KEY` | generated in `ACF_DATA_DIR/secret.key` | Encrypts API keys, MCP configs and OAuth tokens in the database. Required by the production stack |
| `ACF_LLM_BASE_URL` | provider default | e.g. `http://localhost:11434/v1` with `openai` for Ollama |
| `ACF_MAX_AGENT_STEPS` | `40` | Model calls per message (and per sub-agent) |
| `ACF_SUBAGENTS` | `8` | Sub-agents of one run working at the same time; more wait their turn (`0` = no sub-agents) |
| `ACF_SUBAGENT_FAST_MODEL` | provider's small model | The model a sub-agent gets when the agent asks for `fast` (Claude: `claude-haiku-5-5`, OpenAI: `gpt-4.1-mini`, others: the user's model) |
| `ACF_COMPACT_TOKENS` / `ACF_COMPACT_KEEP_TOKENS` | `120000` / `20000` | When to summarise old messages, and how much recent history to keep |
| `ACF_CONTEXT_WINDOW` | model's own | Context window size (tokens) for the chat's context meter; default comes from LangChain's model profile, `128000` if unknown |
| `ACF_MEMORY_LIMIT` | `4000` | Characters of `memory.md` (it goes into every prompt); the agent's writes past it are refused |
| `ACF_REVIEW_INTERVAL` | `10` | User messages per chat between background reviews that update memory and skills (`0` = off) |
| `ACF_SKILL_ARCHIVE_DAYS` | `30` | Skills not read for this many days move to `skills/.archive/` (`0` = never; `pinned: true` in a skill's frontmatter keeps it) |
| `ACF_DB_URL` | SQLite in `ACF_DATA_DIR` | Database. The Docker stacks use PostgreSQL (`postgresql://user:pass@host/db`) |
| `ACF_DATA_DIR` | `./data` | Workspaces (and the SQLite file when no `ACF_DB_URL` is set) |
| `ACF_ADMIN_EMAIL` / `ACF_ADMIN_PASSWORD` | – | Main account, created at startup; its password is reset to this value (and its sessions signed out) when it changes |
| `ACF_ADMIN_NAME` | email name | Display name for the main account |
| `ACF_ALLOW_SIGNUP` | `true`, `false` if `ACF_ADMIN_EMAIL` is set | Open sign-ups. When `false`, the first account can still be created on an empty server |
| `ACF_COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `ACF_SANDBOX` | `docker` | `docker`, `local` for development (**not isolated**), or your own adapter as `package.module:Class` (see [architecture](docs/architecture.md#sandboxes-backendacfsandboxpy)) |
| `ACF_SANDBOX_IMAGE` | `acf-sandbox:latest` | Sandbox image |
| `ACF_SANDBOX_NETWORK` | `acf-sandbox` | Created when missing, with traffic between sandboxes off. `none` cuts sandboxes off from the internet |
| `ACF_SANDBOX_BRIDGE` | `acf-sbx0` | Interface name of that network (the egress firewall matches it) |
| `ACF_SANDBOX_RUNTIME` | – (`runsc` in the production stack) | Container runtime, e.g. `runsc` for gVisor |
| `ACF_SANDBOX_MEMORY` / `_CPUS` | `1g` / `1` | Limits per sandbox |
| `ACF_SANDBOX_HOST_DATA_DIR` | – | Host path of the data dir when the app itself runs in Docker |
| `ACF_MCP_PRESETS_FILE` | – | JSON list of extra one-click apps for the Connections page (see below) |
| `ACF_REDIS_URL` | – (set in the production stack) | Redis for run state shared between app processes. Needed for more than one process; unset keeps it in memory |
| `ACF_REDIS_PREFIX` | `acf` | Key prefix, to share one Redis between deployments |
| `ACF_BUS_TTL` | `30` | Seconds before a dead process's chats, locks and background commands are freed |
| `ACF_SHUTDOWN_GRACE` | `20` | Seconds a stopping process gives its running agents to finish |

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

`oauth.authorize_params` adds parameters to the provider's sign-in URL. Google, for example, only issues a
refresh token with `{ "access_type": "offline", "prompt": "consent" }`; without one the connection ends when
the access token expires.

**Popular apps.** The Connections page lists remote MCP servers that support OAuth dynamic client
registration — Linear, Notion, Jira & Confluence, Sentry, monday.com, Canva, Intercom, Stripe, Vercel and
Hugging Face. **Connect** writes the entry into your configuration; **Sign in** does the rest, no API key needed.
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
every workspace starts with a `skill-creator` skill that teaches it how, plus a few general skills
(`backend/acf/builtin_skills/`). Each built-in skill is added once; one you delete stays deleted.

### External apps (ACP)

The agent is reachable over the [Agent Client Protocol](https://agentclientprotocol.com): JSON-RPC 2.0, one
message per WebSocket text frame, at `ws(s)://<host>/api/acp`. The web chat uses the same endpoint (with its
session cookie, same origin only). Other clients authenticate with `Authorization: Bearer <token>`, using
the access token from **Settings → External apps**. External access is off until a token is created; the
token is shown once, stored hashed, and can be replaced or revoked at any time.

Supported: `initialize`, `session/new`, `session/load` (replays the history, then follows a running agent),
`session/list`, `session/prompt` (text, resource links and embedded text resources) and `session/cancel`.
A resource link to `file:///workspace/<path>` is an attached workspace file: `session/load` replays it as a
`resource_link` chunk after the message's text (upload the file first with `POST /api/files`, `keep=true`).
Each session is a chat in the web app. Updates are `user_message_chunk`, `agent_message_chunk` and
`agent_thought_chunk` (streamed as the model writes; chunks of one message share `_meta.acf.messageId`),
`tool_call`, `tool_call_update` and `session_info_update`. A `session/prompt` sent while the agent works is
a steering message; its response arrives when the run ends. Extras live under `_acf/` (`_acf/notice`,
`_acf/turn_end`, `_acf/turn_start` when a finished background command wakes the agent) and `_meta.acf`, which other clients can ignore. The agent uses its own sandbox and
connections, so `cwd` and `mcpServers` from the client are ignored.

Clients that start agents as a subprocess over stdio (most editors) can use the bridge:

```sh
ACF_ACP_TOKEN=acp_… python -m acf.acp_bridge --url wss://agent.example.com/api/acp
```

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

- Sandboxes refuse to start when the workspace belongs to root: run the app as a normal user.
- No per-user quotas yet (model spend, disk, number of sandboxes), and no rate limiting on sign-in.

## License

MIT, see [License.txt](License.txt).
