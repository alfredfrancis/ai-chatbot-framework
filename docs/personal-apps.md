# Personal apps

An app is a folder of files in the user's workspace. The agent writes a screen in
[OpenUI Lang](https://openui.com); the web app renders it with design-system components
(`frontend/src/openui/library.tsx`); every click goes through one action API
(`POST /api/apps/{id}/actions`) back to those files, the agent, the sandbox or a connected app.
Implementation notes: [architecture.md](architecture.md#personal-apps-backendacfappspy-frontendsrcopenui).

## Architecture

```mermaid
flowchart LR
  subgraph Browser["Browser (React)"]
    Sidebar["Sidebar: up to 5 apps<br/>under New chat"]
    AppView["AppView page<br/>pages/AppView.tsx"]
    Renderer["OpenUI Renderer<br/>@openuidev/react-lang"]
    Library["Component library<br/>openui/library.tsx<br/>Screen · Card · Tabs · Stat · List<br/>BarChart · LineChart · PieChart<br/>Button · TextField · Slider · Board …"]
    AppView --> Renderer --> Library
  end

  subgraph API["FastAPI (acf)"]
    Routes["/api/apps<br/>/api/apps/{id}<br/>POST /api/apps/{id}/actions"]
    Apps["apps.py<br/>path rules · 5-app limit"]
    Loop["Agent loop<br/>agent/loop.py"]
    Hub["McpHub<br/>read-only tools only"]
    Routes --> Apps
    Apps -->|ask_agent| Loop
    Apps -->|mcp| Hub
  end

  subgraph WS["User workspace (files)"]
    Meta["apps/<id>/app.json<br/>title · order · files"]
    Screen["apps/<id>/app.oui<br/>OpenUI Lang screen"]
    Data["brief.md · tasks.json<br/>+ files listed in app.json"]
    Scripts["apps/<id>/actions/*.sh"]
    Skill["skills/personal-apps/SKILL.md<br/>skills/openui/ SKILL.md + reference.md"]
  end

  Sandbox["Sandbox<br/>Docker container per user"]
  MCP["Connected apps<br/>(MCP servers)"]

  Sidebar -->|GET /api/apps| Routes
  AppView -->|GET source, poll| Routes
  Renderer -->|"Query / Mutation / @ToAssistant"| Routes
  Library -->|"Board: read_file / update_file"| Routes
  Apps -->|read_file · update_file| Data
  Apps -->|reads| Meta
  Apps -->|reads| Screen
  Apps -->|run| Sandbox
  Sandbox --> Scripts
  Hub --> MCP
  Loop -->|"read · write · edit · bash"| WS
  Loop -.->|"reads before writing a screen"| Skill
  Library -.->|"npm run build generates"| Skill
```

- **No app backend.** State is the files in `apps/<id>/`; the API only enforces where an app may read and write.
- **No generated HTML.** `app.oui` can only name components from `openui/library.tsx`, which use the design
  system's classes and tokens.
- **One vocabulary, two readers.** The same library renders screens and generates the agent's reference
  (`builtin_skills/openui/reference.md`), so the agent can't use a component that doesn't exist. CI checks
  the file is current.
- **Path rules.** An app reads and writes its own folder (never `app.json` or `app.oui`) plus files listed in
  `app.json`.
- **Writes to other services go through the agent.** The `mcp` action refuses tools not marked read-only;
  `ask_agent` lets the agent ask the user first.

## Sequence: the agent creates an app

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant C as Chat (ACP)
  participant A as Agent loop
  participant W as Workspace files
  participant S as Sidebar
  U->>C: "Set up my cockpit"
  C->>A: prompt (personal-assistant skill matches)
  A->>W: read skills/personal-apps + skills/openui (SKILL.md, reference.md)
  A->>W: write tasks.json, brief.md
  A->>W: write apps/cockpit/app.json
  A->>W: write apps/cockpit/app.oui (root = Screen([...]))
  A-->>C: "Your Cockpit is in the menu"
  C->>S: turn ended → refresh
  S->>W: GET /api/apps (validate app.json, app.oui present, first 5)
  S-->>U: Cockpit appears under New chat
```

## Sequence: the user works in the app

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant V as AppView + Renderer
  participant R as /api/apps/{id}/actions
  participant W as Workspace files
  participant A as Agent (app chat)
  participant X as Sandbox / MCP

  U->>V: open /apps/cockpit
  V->>R: GET /api/apps/cockpit
  R-->>V: app.oui source, running=false
  V->>V: parse OpenUI Lang, render library components
  V->>R: Query read_file {path: brief.md, tasks.json}
  R->>W: read (path rules)
  W-->>V: {text, data} → Stats, Card, Board

  Note over U,W: Drag a task between quadrants
  U->>V: drop "Book flights" on Schedule
  V->>V: optimistic update, writes queued in order
  V->>R: update_file {path: tasks.json, content}
  R->>W: write
  opt Board has agentNote
    V->>R: ask_agent {prompt, event: Moved "Book flights"…}
    R->>A: start or steer run in "Cockpit app" chat
    R-->>V: chat_id (returns at once)
  end

  Note over U,A: A button with @ToAssistant("Refresh the cockpit")
  U->>V: click Refresh
  V->>R: ask_agent {prompt}
  R->>A: "[App: Cockpit, apps/cockpit/app.json] …"
  V-->>U: "Agent working…" (poll every 1 s)
  A->>W: rewrite brief.md, update tasks.json
  A-->>R: run done
  V->>R: Query refresh interval re-reads files
  R-->>V: new brief and tasks → screen updates

  Note over U,X: Mutation("run") or Query("mcp")
  U->>V: click "Count tasks" (confirm first)
  V->>R: run {script: count}
  R->>X: sh apps/cockpit/actions/count.sh '{json}'
  X-->>V: {output} → shown via Badge
```

- **Polling, not push.** The page polls the app (4 s, or 1 s while the agent works); `Query(…, refreshSeconds)`
  keeps data current.
- **Broken screens are fixable from the page.** Parse errors show in a banner with "Ask the agent to fix it",
  which sends the errors to the app chat.
