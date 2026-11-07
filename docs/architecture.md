# Architecture

```
Browser (React)  ──/api (JSON, SSE)──▶  FastAPI (acf)
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
| Steering | A message sent while the agent works is never an interruption. If the model is thinking, the call is restarted with the message added (only tokens are lost). If tools are running, it is injected when the batch ends — tools are never cut off. |
| Stop | Cancels the run; any tool call without a result gets "Stopped by the user", so the history stays valid. |
| Observable | Every step is an event (`message`, `tool_start`, `queued`, `notice`, `stopped`, `error`, `done`). A reloaded page attaches to the running agent and gets a replay. |

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
