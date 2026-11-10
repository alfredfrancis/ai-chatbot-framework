# Architecture

```
Browser (React) ──/api (JSON) + /api/acp (ACP over WebSocket)──▶  FastAPI (acf)
Other ACP clients ──/api/acp (Bearer token) or acf.acp_bridge (stdio)──▶
                                         ├── PostgreSQL (SQLite for quick local runs): users, chats, messages, tasks, OAuth tokens
                                         ├── Agent runs (one per chat) ── LangChain chat model
                                         ├── Run state shared between app processes (bus: memory or Redis)
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
| Files over special tools | Memory and context are `memory.md` and `context.md`; the agent edits them like any file. `memory.md` is capped at `ACF_MEMORY_LIMIT` characters: `write`/`edit` refuse to grow it past that (the error says to merge and prune), and the prompt shows how full it is. The prompt routes know-how to skills and only every-chat facts to memory, written as facts rather than orders. Past chats are files too: `.acf/chats/<id>.md` (user and assistant text, tool names), rewritten after each run and deleted with the chat, for the agent to grep. |
| Background review | Every `ACF_REVIEW_INTERVAL` user messages in a chat, after the run ends, `agent/review.py` calls the model with the turn's system prompt (so the cache is reused), the history and a review prompt, with `read`/`write`/`edit` limited to `memory.md`, `context.md` (read) and `skills/`. It runs in the background, one per user, and adds nothing to the history; a `note` row records it (`raw.review_at`) and, when files changed, names them, which clients get as `_acf/notice`. |
| Injection checks | `acf/scan.py` flags planted instructions ("ignore previous instructions", "don't tell the user", sending secrets with curl, bidi/tag characters). Writes of such text to `memory.md` or `skills/**/*.md` are refused, uploaded skills containing it are rejected, and a `memory.md` containing it is left out of the prompt. Narrow on purpose; the sandbox is the real boundary. |
| Progressive disclosure | Skills appear as one line each (`name: description (path)`); the agent reads `SKILL.md` when needed. MCP tools appear as names per connected app; each tool's definition (description and input schema) is written to `.acf/mcp/<server>/<tool>.json` when the run connects, and one `mcp_call` tool (`server`, `tool`, `arguments`) runs them. Binding every MCP schema instead costs tens of thousands of prompt tokens per step. |
| Parallel tools | All calls in one model answer run at the same time; results keep the call order. A call waits only for earlier calls on the same resource (a file path for `read`/`write`/`edit`, the app for `mcp_call`) when one of them writes. The prompt tells the model to batch only independent steps. |
| Sub-agents | The `agent` tool (`agent/subagents.py`; `description`, `prompt`, `model`) hands one part of a job to a helper, like the Task tool in Cursor and Claude Code. A sub-agent starts with a fresh context: the turn's system prompt plus a short role note, and the prompt the main agent wrote — nothing of the chat. It has the main agent's tools except `agent` (no nesting) and background commands. Calls in one answer run at the same time (at most `ACF_SUBAGENTS` per run; the rest wait), and each result is that sub-agent's last message, so the main agent fans out and then combines the reports. `model` is `inherit` (the default), `fast` (`ACF_SUBAGENT_FAST_MODEL`, or the provider's small model) or a model id; the provider, address and key stay the user's (`LLMConfig.with_model`). The chat stores the tool result with `raw.agent` = model, tokens, steps and `session`; the same record goes out as `agent` events while it works. `session` is the sub-agent's own session: a chat with `parent_id` set that holds its messages (prompt, answers, tool calls and results). It is left out of the chat lists and is read-only (ACP refuses `session/prompt` and `session/cancel` on it), but `session/load` opens it like any chat — also while the sub-agent works, since it holds that chat's lease and publishes its events to a feed — and the web app links to it from the sub-agent's step (“Open session”). Deleting a chat deletes its sub-agents' sessions. A provider error or the step limit is an error result, not a failed run; Stop cancels the sub-agents with the run. A built-in tool because it needs the loop itself: MCP calls to one app are serialised and can't reach the run. |
| Background commands | `bash` with `background: true` returns at once ("Started in the background as job bg-…") and runs as a job of the chat (up to 8 per chat, 1 hour max). Its output is saved as a user-role note (`raw.background` = job id, `tool_call_id` = the call that started it): a run that is still working reads it at its next step; otherwise it starts a new run. Stop ends jobs too (the note says so; it doesn't wake the agent). A job lost in a server restart gets a closing note. |
| Recoverable errors | Failed commands, bad arguments and unknown tools come back as error results, never crashes. |
| Small context | Tool output above 30k characters keeps head and tail; the full text is saved to `.acf/outputs/` for the agent to read. |
| Context usage | After every model call the run measures the context: `used` is the provider's input + output tokens (an estimate when it reports none), over the model's window (`ACF_CONTEXT_WINDOW` or LangChain's model profile). The breakdown (system prompt, tools, skills, messages) is estimated at ~4 characters a token. It is sent as an ACP `usage_update`, stored on the assistant message and replayed by `session/load`; the chat's top bar shows it as a meter. |
| Compaction | Before a new turn, if the history is over `ACF_COMPACT_TOKENS`, older messages are summarised into one record. The cut is at a user message so tool calls stay paired; thinking blocks from before the cut are dropped. |
| Append-only history | Assistant messages are stored as LangChain message dicts and replayed verbatim (Claude thinking blocks survive). |
| Prompt caching | The system prompt is a single cached block, built once per turn and reused for every step (and for compaction and the review), so edits during a turn don't break the cache; they show up next turn. It is ordered from most to least stable: instructions, `context.md`, skills, connected apps, `memory.md`, the date. |
| Streaming | The model is called with `astream`; text and thinking deltas are `delta` events as they arrive. When the stream ends the merged chunk becomes one stored message (`message_to_dict`), so history is unchanged. A stop mid-answer stores the text shown so far (no thinking, no tool calls). |
| Steering | A message sent while the agent works is never an interruption. If the model is still thinking (no text or tool call yet), the call is restarted with the message added (only tokens are lost). Once it is answering, the answer finishes and the message is read next — streamed text is never retracted. If tools are running, it is injected when the batch ends — tools are never cut off. |
| Stop | Cancels the run; any tool call without a result gets "Stopped by the user", so the history stays valid. |
| Observable | Every step is an event (`delta`, `message`, `tool_start`, `queued`, `notice`, `title`, `stopped`, `error`, `done`). Clients see them through ACP (below). |

## Several app processes (`backend/acf/bus.py`)

Any number of app processes can serve the same users: put them behind one address, with one PostgreSQL,
one data folder (workspaces) and one Docker (through `docker-proxy`), and set `ACF_REDIS_URL`. A user's
chats can be served by any process; their sandbox and workspace stay one per user. The database holds
everything that lasts; the bus holds what exists only while work is in flight. Without `ACF_REDIS_URL`
the bus is in memory (`LocalBus`), which is right for exactly one process.

| What | How |
|---|---|
| One run per chat | A run holds the chat's lease (`SET NX` with a TTL) while it works. |
| Messages to a run | `agent.start` pushes the message to the chat's inbox (a Redis list), then tries to claim the chat: it starts the run in its own process, or the run that holds the chat (anywhere) reads it at its next step and a `steer` signal restarts a model call that hasn't started answering. A finishing run releases the chat and then checks the inbox again, so a message is never left behind. Job notes go the same way. |
| Events | A run publishes every event to its feed: in-process listeners get it at once, and one publisher writes them in order to a Redis stream (batched, so streamed words don't cost a round trip each). Another process that follows the run tails the stream: replay, then live, ending at `done` (which carries the stop reason and error). `session/load` skips deltas of answers already in the history using the stream id stored with each assistant message, so a feed that trails by a few milliseconds never shows text twice. |
| Stop, chat events | Signals over Redis pub/sub to every process: `stop` cancels the run and the background commands of the chat wherever they run; `chat` delivers `_acf/turn_start` and job notes to clients connected to any process. |
| Scheduled tasks | Every process runs the scheduler. A due task is claimed with a compare-and-set update of `next_run_at`, so exactly one process starts it; a `task:<id>` lock stops "Run now" from overlapping it. |
| Locks | `review:<user>` (one background review per user), `sandbox:<user>` (one process creates or restarts a user's container at a time), and the background-command registry (the per-chat limit, and which jobs are still alive when the history is repaired). |
| Failure | Leases, locks and jobs expire `ACF_BUS_TTL` seconds after their process stops refreshing them. A process that dies frees its chats on its own: followers get a `done` with an error, and the next message runs elsewhere with the lost tool calls and jobs closed off in the history. A process cut off from Redis long enough to lose a lease stops that run rather than run the chat twice. |
| Scaling in | On shutdown a process stops taking work, lets its running agents finish for up to `ACF_SHUTDOWN_GRACE` seconds (clients reconnect to another process and keep following), then stops what is left and releases everything it holds. |

## Agent Client Protocol (`backend/acf/acp.py`)

The only way to talk to the agent, for the web chat and for third-party clients: JSON-RPC 2.0 over a
WebSocket at `/api/acp`. A session is a chat; `session/prompt` calls `agent.start`, so a prompt sent
while the agent works becomes steering. Run events become `session/update` notifications: a stored
assistant message → `agent_message_chunk` + one `tool_call` (pending) per call; `tool_start` →
`tool_call_update` (in_progress); a tool result → `tool_call_update` (completed/failed, with output and
`_meta.acf.durationMs`); a sub-agent's `agent` event → `tool_call_update` (in_progress) with `_meta.acf.agent` = `{model, tokens, steps: [{title, ok}]}`, and the update that completes the call carries the final one (`session` in it is the sub-agent's own read-only session; `session/load` on it answers with `_meta.acf.parent` = `{sessionId, title}`); a `delta` → `agent_message_chunk` / `agent_thought_chunk` with the stream's id
as `_meta.acf.messageId` (the stored message then sends only its tool calls, since its text was streamed). A background command's tool call stays `in_progress` (`_meta.acf.background`) until its note arrives as a `tool_call_update` (completed/failed, with output). Connections that loaded or prompted a session hear about runs a finished job starts there through `_acf/turn_start`, then follow them. `session/load` registers a listener on the running agent *before* reading the
history, replays the stored messages, then forwards only newer events — including the deltas of an answer
still being written — so a reloaded page neither misses nor duplicates anything. When a run ends, every connection following it gets `_acf/turn_end`; the
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

`Sandbox` is a port; each provider is an adapter, picked by `ACF_SANDBOX` (`docker`, `local`, a kind added
with `register_sandbox()`, or `package.module:Class`). Nothing outside `sandbox.py` knows which one runs.

| Method | What an adapter does |
|---|---|
| `ensure()` | Start the user's sandbox if needed; raise `SandboxError` with a sentence for the user if it can't. |
| `exec(command, timeout)` | Run a shell command in the workspace, return `ExecResult`. A timeout or a cancel kills it. |
| `spawn(argv, env)` | Start a long-lived process and return a `SandboxProcess`: `write`/`read` bytes on stdin/stdout, `close_stdin`, `returncode`, `kill`. Callers use `process()`, which runs `ensure()` and stops the process (close stdin, wait, kill). |
| `status()` / `reset()` | Report state for Settings; throw the sandbox away (the workspace stays). |

The contract, checked for every adapter by `tests/test_sandbox_contract.py`:

- **Workspace.** The user's workspace is storage the backend owns (`workspace.workspace_dir`) and the
  working directory of every command and process. The adapter mounts or syncs it, so `read`/`write`/`edit`,
  the system prompt, skills and artifacts (which use the backend's copy) see the same files as `bash`.
  A provider that can neither mount nor sync storage does not fit yet.
- **Stopping.** A timeout, a cancelled `exec` and `kill()` stop the command and everything it started
  *inside* the sandbox, not only the backend's handle on it.
- **Secrets stay in the backend.** Stdio MCP servers talk MCP over a `SandboxProcess`
  (`mcp_client._process_transport`); OAuth tokens and remote MCP connections never enter the sandbox.

Docker adapter: `acf-sbx-<user>` is created on first use with `--cap-drop ALL`, `no-new-privileges`,
memory/CPU/pids limits and the workspace bind-mounted at `/workspace`. It is labelled with the workspace's id
and replaced if the folder was recreated. Commands run as `docker exec` under a small `sh` wrapper that
records the session leader's pid; a stop kills that session inside the container (killing the `docker exec`
client alone would leave the command running). It needs only `sh` and `/proc` in the image.

## Skills (`backend/acf/skills.py`)

`skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`). A message calls a skill with
`/name` (the chat's message box offers them after `/`): `skills.reference`, applied in `agent.start`,
stores the message with a line `[Use skill: name](skills/name/SKILL.md)` for each one that exists, which
the prompt tells the agent to read first; clients get the message without those lines.
`council-of-llms` is a built-in skill over sub-agents: the same brief to several models at once, then the
main agent compares the reports and answers. Uploads accept a `.zip`/`.skill`
(the shallowest `SKILL.md` is the root; path traversal and `__MACOSX` are dropped; 20 MB limit) or a
single `SKILL.md`; every Markdown file in an upload goes through the injection check. Built-in skills
(`acf/builtin_skills/`) are copied in once each (`.acf/skills.json` remembers which, so a deleted one stays
deleted). Each `read` of a `SKILL.md` is recorded there too; at the start of a turn, skills unread for
`ACF_SKILL_ARCHIVE_DAYS` move to `skills/.archive/` (with a notice). `skill-creator` and skills with
`pinned: true` stay.

## OAuth for remote MCP servers (`backend/acf/oauth.py`)

401 → "Sign in" → discovery (RFC 9728/8414) → dynamic registration (RFC 7591) unless a `client_id` is
configured → PKCE authorize in a popup → `/oauth/callback` page posts code and state → token exchange →
automatic refresh.

## Personal apps (`backend/acf/apps.py`, `frontend/src/openui/`)

Diagrams: [personal-apps.md](personal-apps.md).

An app is `apps/<id>/app.json` (title, description, order, extra `files`; validated with pydantic, an
invalid one is listed with its error) plus `apps/<id>/app.oui`, a screen in OpenUI Lang. The menu shows at
most 5, by `order` then id.

Generative UI without generated HTML: the web app renders `app.oui` with `@openuidev/react-lang` and our own
component library (`frontend/src/openui/library.tsx`), whose components use the design system's classes and
tokens. The agent learns the language from a reference generated from that library
(`frontend/scripts/build-openui-prompt.mjs` → `builtin_skills/openui/reference.md`, rebuilt by
`npm run build`; CI checks it is current; the `openui` skill explains it and `personal-apps` points to it), so it can only use components that exist. Parse errors show on
the page with a button that sends them to the agent. We don't use OpenUI's own component package
(`@openuidev/react-ui`): it brings its own styling.

The same library renders views in chat replies: Markdown's ` ```openui ` code blocks become
`openui/ChatView.tsx` (in `pages/Chat.tsx`). A chat view has no tools — no `Query`, `Mutation` or Board, so
the agent puts the data in the program — and a button's `@ToAssistant` sends its text as the user's next
message in that chat. The view is part of the stored reply, so it comes back on reload and in transcripts.

The page polls `GET /api/apps/{id}` for the source and the agent's state. Every call the screen makes —
`Query`/`Mutation` tools, `@ToAssistant` buttons, the Board — is `POST /api/apps/{id}/actions`:

- `read_file` / `update_file` inside `apps/<id>/` (not `app.json` or `app.oui`) or a file listed in
  `files`, through `workspace.resolve`.
- `ask_agent` starts or steers a run in the app's own chat (its id kept in `.acf/apps.json`); the message
  starts with `[App: <title>, apps/<id>/app.json] <event>` so the agent knows where it came from.
- `run` executes `apps/<id>/actions/<name>.sh` through `Sandbox.exec`, with the input JSON as `$1`.
- `mcp` opens an `McpHub` and calls a tool only if it is annotated read-only; writes must go through the
  agent, which asks the user first.

## Projects (`backend/acf/projects.py`)

A project is a row: a name, a description, instructions and an optional folder (a path inside the
workspace, checked with `workspace.resolve` and made if missing). Chats and tasks point at it with
`project_id`. Each turn, `Run._turn` loads the chat's project and `prompt.sections` adds a `<project>`
part (after the connected apps, before `memory.md`): the instructions, where the folder is, and the id to
pass to `create_task`. Because the prompt is built per turn, editing a project reaches its existing chats;
there is no new tool and no change to how paths or `bash` work — the folder is a place the agent is told to
use, not a second root. A task with a `project_id` creates its run's chat in that project. Over ACP,
`session/new` takes `_meta.acf.projectId`, `session/list` marks project sessions with it and `session/load`
answers with `_meta.acf.project` = `{id, name}`. Deleting a project clears `project_id` on its chats and
tasks; nothing else is removed.

## Scheduled tasks (`backend/acf/scheduler.py`)

Cron + time zone, or a single time (`run_at`) for a one-off task. `tick()` starts due tasks (next run is
computed first, so a slow run never double-fires; a one-off task is turned off instead); each run is an agent
run in a new chat.

The agent manages tasks through the built-in `system` MCP server (`backend/acf/system_mcp.py`): an
in-process `MCPServer` bound to the user, which `McpHub` connects next to the user's own servers on every
run. It goes through the same `.acf/mcp/` definitions and `mcp_call` as any app, so it adds no built-in
tool. Other app features the agent should reach belong there as tools.

## Database migrations (`backend/acf/migrations/`)

Alembic, run by `db.migrate()` on every start (`init_db`), on SQLite and PostgreSQL. `0001_baseline` is the
schema older versions made with `create_all`; a database that has those tables but no `alembic_version` is
stamped at the baseline and then upgraded, so existing installs keep their data. Write a migration with
`make migration m="…"` (autogenerate, `render_as_batch` for SQLite) and review it;
`tests/test_migrations.py` checks that the migrations build exactly the schema the models describe.
