# Architecture

```
Browser (React)  ──/api (JSON, SSE)──▶  FastAPI (harbor)
                                         ├── SQLite: users, chats, messages, tasks, OAuth tokens
                                         ├── LLM: Anthropic SDK | OpenAI-compatible HTTP
                                         ├── Scheduler loop (in-process)
                                         ├── Remote MCP servers (Streamable HTTP + OAuth)
                                         └── Docker daemon ──▶ harbor-sbx-<user>  (/workspace mounted)
                                                                 ├── run_command
                                                                 └── stdio MCP servers (docker exec -i)
```

## A message, step by step

1. `POST /api/chats/{id}/messages` stores the user message and starts the agent in a background task
   (it finishes even if the browser disconnects). Events stream back as server-sent events.
2. `agent.run` builds the system prompt from `context.md` and `memory.md`, connects every enabled MCP
   server (`McpHub`), and offers the model the built-in tools plus `mcp__<server>__<tool>` tools.
3. The loop calls the model; each tool call is executed (sandbox, workspace, or MCP), and its result is
   stored and sent to the UI. It stops when the model answers without tool calls, or after
   `HARBOR_MAX_AGENT_STEPS`.
4. Assistant messages keep the provider's raw content blocks so they can be replayed verbatim; this keeps
   Claude's thinking blocks valid across tool-use turns.

## Built-in tools

| Tool | Where it runs |
|---|---|
| `run_command` | the user's sandbox (`docker exec … timeout -s KILL <n> sh -c`) |
| `read_file`, `write_file`, `list_files` | the workspace folder (path-checked) |
| `remember` | appends a line to `memory.md` |

## Sandboxes

`DockerSandbox.ensure()` creates `harbor-sbx-<id>` on first use with `--cap-drop ALL`,
`--security-opt no-new-privileges`, memory/CPU/pids limits and the workspace bind-mounted at `/workspace`.
Each container carries a `harbor.workspace` label; if it doesn't match the user's workspace id (the data
folder was recreated or an id was reused) the container is replaced.

## OAuth for remote MCP servers

1. Connecting without a token gets a 401 → the server is shown as "Sign in".
2. `POST /api/mcp/servers/{name}/oauth/start` discovers metadata, registers a client if needed, creates a
   PKCE verifier and state, and returns the authorize URL. The web app opens it in a popup.
3. The provider redirects to `/oauth/callback` in the web app, which posts `code` and `state` to
   `POST /api/oauth/callback`. Harbor exchanges the code and stores tokens; the popup tells the opener and
   closes.
4. Expired access tokens are refreshed before connecting.

## Scheduled tasks

Tasks store a 5-field cron expression and an IANA time zone. `scheduler.tick()` (every
`HARBOR_SCHEDULER_INTERVAL` seconds) starts due tasks, computes the next run first so a slow run never
double-fires, and runs each one as a new chat titled `<task> · <time>`.
