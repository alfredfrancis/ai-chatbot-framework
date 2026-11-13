# Features

A closer look at what AI Chatbot Framework does. The [README](../README.md) has the short version.

- **Any model through LangChain** – Claude (default), OpenAI, any OpenAI-compatible server (Ollama,
  OpenRouter, vLLM, LiteLLM) or any other LangChain chat provider.
- **Model settings like Cursor** – a key per provider, a model list with on/off switches and models of your own,
  a token window per model, and a default model and effort; each chat picks its model and effort in the message
  box. Operators set the allowed models, their effort levels and windows (`ACF_MODELS_FILE`, `ACF_CUSTOM_MODELS`).
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
  Diagrams: [docs/personal-apps.md](personal-apps.md).
- **Views in chat** – the agent can answer with a chart, a plan, tabs or a small form inside its reply: an
  ` ```openui ` block written with the same components (bar, line and pie charts, progress, lists, steps,
  tabs, sliders, choices, buttons). A button sends its text back into the chat, so the user can pick
  instead of typing.
- **Projects** – ongoing work with its own instructions and, optionally, a folder in your files. A chat started
  in a project follows its instructions and keeps its files in that folder; a task made in a project runs as a
  chat there. Deleting a project keeps its chats, tasks and files.
- **Scheduled tasks** – repeating ("every weekday at 08:00 …") or once ("tomorrow at 17:00"); each run becomes a
  chat, and a one-off task turns itself off after its run. Each task can run on its own model, e.g. a small
  local one ([docs/local-model.md](local-model.md)) for hourly jobs. Set them up on the Tasks page or just ask the agent: the built-in `system` MCP server gives it `list_tasks`, `create_task`, `update_task`,
  `delete_task` and `run_task` (the server name `system` is reserved).
- **Agent Client Protocol (ACP)** – the chat speaks [ACP](https://agentclientprotocol.com) over a
  WebSocket, and so can your own apps and editors. Create an optional access token in
  **Settings → External apps** to let them in.
- A calm, keyboard-friendly interface (⌘K command menu, shortcuts), dark and light themes, phone layout,
  built from a documented design system whose tokens live in `design/tokens.json`.
- **Installable app (PWA)** – install it from the browser (Chrome/Edge: the install icon in the address
  bar; iPhone: Share → Add to Home Screen) and it opens in its own window with its own icon. A service
  worker (`frontend/public/sw.js`) keeps the app itself, never your data, so it opens without a network
  and says you're offline instead of asking you to sign in. Needs HTTPS (or `localhost`). The icons in
  `frontend/public/icons/` are drawn from the logo by `node frontend/scripts/build-icons.mjs`.

