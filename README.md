<p align="center"><img src="frontend/public/favicon.svg" width="72" alt="AI Chatbot Framework logo"></p>

<h1 align="center">AI Chatbot Framework</h1>

<p align="center">
  A self-hosted AI agent for everyone on your team.<br>
  Each person gets an assistant with its own private computer, files, skills, app connections and scheduled tasks.
</p>

<p align="center">
  <a href="https://github.com/alfredfrancis/ai-chatbot-framework/actions/workflows/ci.yml"><img src="https://github.com/alfredfrancis/ai-chatbot-framework/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="License.txt"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#features">Features</a> ·
  <a href="#deploy">Deploy</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="#contributing">Contributing</a>
</p>

![AI Chatbot Framework home screen: chats, projects, files, skills, tasks, connections and personal apps in the sidebar, and the message box in the middle](docs/screenshots/home.webp)

> **Version 2.** AI Chatbot Framework used to be an intent/entity NLU chatbot builder. Version 2 rebuilds it
> as an agent. The old code is in the git history.

## Why

Most agent tools are built for developers. This one is built for people who just want work done: they type
what they need, and the agent reads their files, runs code, uses their apps and remembers how they like
things. You run it on your own server, with the model of your choice, and every user's work stays in
their own locked-down sandbox.

## Features

- **Any model.** Claude by default; OpenAI, Ollama, OpenRouter, vLLM, LiteLLM or any other
  [LangChain](https://python.langchain.com) chat provider. Users can bring their own key.
- **A private computer per user.** One Docker sandbox with a persistent `/workspace`, resource limits and
  no Linux capabilities. Commands and local MCP servers run there.
- **A small, fast agent loop.** Four tools (`read`, `write`, `edit`, `bash`), parallel tool calls,
  background commands, context compaction, and **steering**: type while the agent works and it picks your
  message up without stopping.
- **Sub-agents.** The agent splits a big job into parts and runs helpers side by side, each with a fresh
  context and its own model. You can watch each one work.
- **Memory in plain files.** `context.md` (about you) and `memory.md` (what the agent remembers) are files
  the agent reads every turn and edits itself. Every few messages a background pass updates memory and
  skills from the chat.
- **Skills.** The open Agent Skills format (`skills/<name>/SKILL.md`). Upload one, let the agent write one,
  or type `/` in a chat to pick one. Eleven come built in, from `pdf` and `cited-research` to
  `council-of-llms` and `personal-assistant`.
- **App connections (MCP).** Local servers run in the sandbox; remote servers sign in with OAuth.
  One-click setup for Linear, Notion, Jira, Sentry, Stripe and more.
- **Personal apps.** The agent can build small apps for you, like a daily **Cockpit** or a grocery list,
  that show up in the sidebar. Chat replies can include charts, tabs and buttons too.
- **Projects and scheduled tasks.** Group chats under shared instructions and a folder. Run a prompt
  "every weekday at 08:00" or once "tomorrow at 17:00"; each run becomes a chat.
- **Files and artifacts.** Attach files to a message; each chat lists the files it used and made.
- **Open protocol.** The chat speaks the [Agent Client Protocol](https://agentclientprotocol.com) over
  WebSocket, so editors and your own apps can talk to the agent too.
- **Built to scale.** Stateless app processes behind Caddy, with PostgreSQL and Redis. Add or remove
  processes at any time.
- **A calm interface.** Keyboard-first (⌘K, shortcuts), dark and light themes, works on a phone.

Every feature in detail: [docs/features.md](docs/features.md).

## Screenshots

| Steering while it works | Skills | Connections (OAuth) |
|---|---|---|
| ![Steering: a message queued while the agent works](docs/screenshots/e2e/04-steering-queued.png) | ![Skills page](docs/screenshots/e2e/07-skills.png) | ![Connections page with a connected app](docs/screenshots/e2e/09-connections-connected.png) |
| **Files** | **Command menu (⌘K)** | **Phone, light theme** |
| ![Files page](docs/screenshots/e2e/06-files.png) | ![Command menu](docs/screenshots/e2e/15-command-menu.png) | ![Chat on a phone in light theme](docs/screenshots/e2e/14-phone-light-chat.png) |
| **Cockpit app** | **Sub-agents** | **Charts in a personal app** |
| ![Cockpit personal app](docs/screenshots/e2e/41-app-cockpit-moved.png) | ![Sub-agents working in parallel](docs/screenshots/e2e/09-sub-agents-working.png) | ![Personal app with charts](docs/screenshots/e2e/52-app-charts.png) |

The end-to-end tests take these screenshots on every run ([`docs/screenshots/e2e/`](docs/screenshots/e2e)).

## Quick start

Try it on your machine with Docker. A scripted fake model answers, so you don't need an API key:

```sh
git clone https://github.com/alfredfrancis/ai-chatbot-framework.git
cd ai-chatbot-framework
docker compose -f docker-compose.dev.yml up --build   # or: make up-dev
```

Open http://localhost:5173 and create an account. Try `run: ls` or `show system` in a chat.

To use a real model:

```sh
ACF_LLM_BASE_URL= ANTHROPIC_API_KEY=sk-ant-... make up-dev
```

<details>
<summary>Ports, database and running without Docker</summary>

The web app is on :5173 and the API on :8000 (API only; use 5173). Both reload when you save. PostgreSQL is
on host port 55432 (`postgresql://acf:acf@localhost:55432/acf`). If a port is taken, set
`ACF_DEV_WEB_PORT`, `ACF_DEV_API_PORT` or `ACF_DEV_DB_PORT`. Agents run in real sandboxes.

Without Docker, `make setup && make dev` runs the same thing on your machine (set `ACF_SANDBOX=local`;
it is **not isolated**, so use it for development only).

</details>

## Deploy

On a server with Docker and a domain pointing at it:

```sh
git clone https://github.com/alfredfrancis/ai-chatbot-framework.git && cd ai-chatbot-framework
cp .env.example .env        # set ACF_DOMAIN, POSTGRES_PASSWORD, ACF_SECRET_KEY and a model key
# prepare the host first: gVisor, user-namespace remapping, sandbox firewall (deploy/README.md)
docker compose up -d        # or: make up
```

> [!IMPORTANT]
> Set up the host as described in [deploy/README.md](deploy/README.md) before going public.

**Your account.** Set `ACF_ADMIN_EMAIL` and `ACF_ADMIN_PASSWORD` in `.env` to create your account at
startup; sign-ups are then closed unless `ACF_ALLOW_SIGNUP=true`. Without them, open
`https://<ACF_DOMAIN>`, create the first account, then set `ACF_ALLOW_SIGNUP=false`.

**HTTPS.** [Caddy](https://caddyserver.com) gets and renews the certificate; ports 80 and 443 must be open.
To use other host ports, set `ACF_HTTP_PORT` / `ACF_HTTPS_PORT` (e.g. `127.0.0.1:8088` behind a tunnel or
another proxy). When that tunnel or proxy terminates HTTPS (e.g. Cloudflare Tunnel), also set
`ACF_CADDY_ADDRESS=:80` so Caddy serves plain HTTP.

**Images.** The stack pulls published images (`ACF_REGISTRY` / `ACF_VERSION` in `.env`). To build from
source instead (needed until the first release publishes images), run `docker compose up -d --build`.

**Data.** PostgreSQL runs in its own container (volume `postgres-data`); workspaces live in `./data`, or
`ACF_DATA_PATH`. Back up both. Logs are rotated and the app has a health check.

**Security.** Each user gets one sandbox container. The app runs as a non-root user and never touches the
Docker socket: a small proxy (`docker-proxy`) holds it and allows only sandbox containers with fixed,
locked-down settings. Sandboxes run under gVisor, as a non-root user, on their own network, behind an
egress firewall on the host.

### Scaling

Run state is shared through Redis, so you can run as many app processes as you like and add or remove
them at any time:

```sh
docker compose up -d --scale app=3
```

Caddy spreads requests and chat connections over them and picks up new ones within seconds. Any process
serves any chat; each user still has one sandbox and one workspace. A stopping process lets its running
agents finish first (`ACF_SHUTDOWN_GRACE`, default 20 s), and its clients reconnect to another one. A
crashed process frees its chats after `ACF_BUS_TTL` (30 s).

Across several machines, every app process needs the same PostgreSQL, Redis and Docker proxy, and the data
folder at the same path (shared storage), because sandboxes mount workspaces from the Docker host. Details:
[architecture](docs/architecture.md#several-app-processes-backendacfbuspy).

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

### App connections (MCP)

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

### Editors and external apps (ACP)

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

## Contributing

Contributions are welcome. Read [AGENTS.md](AGENTS.md) first: it covers the layout, the rules (every
feature is tested end to end, including the UI) and the workflow. The design of the agent loop is in
[docs/architecture.md](docs/architecture.md).

```sh
make setup          # Python venv + npm install
make sandbox-image  # or set ACF_SANDBOX=local
make dev            # API :8000 + web :5173
make test           # backend tests (Docker tests run when a daemon is available)
make e2e            # Playwright end-to-end tests (writes docs/screenshots/e2e)
make e2e-docker     # the same with real Docker sandboxes (what CI runs)
make lint
```

Tests never call a real model: `backend/tests/fakes/` has a scripted model server (Anthropic and OpenAI
APIs), a dependency-free stdio MCP server and an OAuth-protected HTTP MCP server.

Design tokens live in `design/tokens.json` (mirroring the design system in Claude Design);
`cd frontend && npm run tokens` regenerates `src/tokens.css`.

## Known limitations

- Sandboxes refuse to start when the workspace belongs to root: run the app as a normal user.
- No per-user quotas yet (model spend, disk, number of sandboxes), and no rate limiting on sign-in.

## License

MIT. See [License.txt](License.txt).
