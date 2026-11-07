# Architecture

```
Browser (React) ──/api (JSON) + /api/acp (ACP over WebSocket)──▶  FastAPI (acf)
Other ACP clients ──/api/acp (Bearer token) or acf.acp_bridge (stdio)──▶
                                         ├── PostgreSQL (SQLite for quick local runs): users, chats, messages, tasks, OAuth tokens
                                         ├── Agent runs (one per chat) ── LangChain chat model
                                         ├── Scheduler loop
                                         ├── Remote MCP servers (Streamable HTTP + OAuth)
                                         └── Docker ──▶ acf-sbx-<user>  (/workspace mounted)
                                                          ├── bash tool
                                                          └── stdio MCP servers (docker exec -i)
```

## The agent loop (`backend/acf/agent/loop.py`)

Lean on purpose; the ideas come from pi, Hermes and Claude Code.

| Practice | How |
|---|---|
| Few, sharp tools | `read` (numbered lines, offset/limit), `write`, `edit` (exact, unique replacement), `bash` (sandbox). Everything else is bash. |
| Files over special tools | Memory and context are `memory.md` and `context.md`; the agent edits them like any file. |
| Progressive disclosure | Skills appear as one line each (`name: description (path)`); the agent reads `SKILL.md` when needed. |
| Parallel tools | If every call in a batch is read-only (`read`, MCP tools with `readOnlyHint`), they run concurrently; otherwise in order. |
| Recoverable errors | Failed commands, bad arguments and unknown tools come back as error results, never crashes. |
| Small context | Tool output above 30k characters keeps head and tail; the full text is saved to `.acf/outputs/` for the agent to read. |
| Compaction | Before a new turn, if the history is over `ACF_COMPACT_TOKENS`, older messages are summarised into one record. The cut is at a user message so tool calls stay paired; thinking blocks from before the cut are dropped. |
| Append-only history | Assistant messages are stored as LangChain message dicts and replayed verbatim (Claude thinking blocks survive). |
| Prompt caching | The system prompt is a single cached block; it changes only when context files, skills or the date change. |
| Steering | A message sent while the agent works is queued and injected after the current tool batch (or right after the final answer, which starts another turn). |
| Stop | Cancels the run; any tool call without a result gets "Stopped by the user", so the history stays valid. |
| Observable | Every step is an event (`message`, `tool_start`, `queued`, `notice`, `title`, `stopped`, `error`, `done`). Clients see them through ACP (below). |

## Agent Client Protocol (`backend/acf/acp.py`)

The only way to talk to the agent, for the web chat and for third-party clients: JSON-RPC 2.0 over a
WebSocket at `/api/acp`. A session is a chat; `session/prompt` calls `agent.start`, so a prompt sent
while the agent works becomes steering. Run events become `session/update` notifications: a stored
assistant message → `agent_message_chunk` + one `tool_call` (pending) per call; `tool_start` →
`tool_call_update` (in_progress); a tool result → `tool_call_update` (completed/failed, with output and
`_meta.acf.durationMs`). `session/load` registers a listener on the running agent *before* reading the
history, replays the stored messages, then forwards only newer events, so a reloaded page neither misses
nor duplicates anything. When a run ends, every connection following it gets `_acf/turn_end`; the
prompt's response carries the ACP stop reason (`end_turn`, `cancelled`, `max_turn_requests`) or a
JSON-RPC error for a failed run. A disconnecting client doesn't stop the agent.

Auth: the session cookie (only when the `Origin` matches the host, against cross-site WebSocket hijacking)
or the user's ACP token as a bearer token. ACP tokens (`acp_tokens`) are random, stored as SHA-256 and
only accepted on this endpoint. `acf.acp_bridge` relays newline-delimited JSON-RPC on stdio to the
WebSocket for clients that spawn agents as subprocesses.

## Model layer (`backend/acf/llm.py`)

`langchain.chat_models.init_chat_model(model, model_provider=…)`. For Claude it sets `max_tokens` and
`output_config.effort: medium` on current models. Provider errors become one friendly sentence.

## Sandboxes (`backend/acf/sandbox.py`)

`acf-sbx-<user>` is created on first use with `--cap-drop ALL`, `no-new-privileges`, memory/CPU/pids
limits and the workspace bind-mounted at `/workspace`. It is labelled with the workspace's id and replaced
if the folder was recreated.

## Skills (`backend/acf/skills.py`)

`skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`). Uploads accept a `.zip`/`.skill`
(the shallowest `SKILL.md` is the root; path traversal and `__MACOSX` are dropped; 20 MB limit) or a
single `SKILL.md`. New workspaces get `skill-creator`.

## OAuth for remote MCP servers (`backend/acf/oauth.py`)

401 → "Sign in" → discovery (RFC 9728/8414) → dynamic registration (RFC 7591) unless a `client_id` is
configured → PKCE authorize in a popup → `/oauth/callback` page posts code and state → token exchange →
automatic refresh.

## Scheduled tasks (`backend/acf/scheduler.py`)

Cron + time zone. `tick()` starts due tasks (next run is computed first, so a slow run never
double-fires); each run is an agent run in a new chat.
