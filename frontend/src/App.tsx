import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { acp } from "./acp";
import { api, ApiError, type AppSummary, type ChatSummary, type Project, type User } from "./api";
import {
  IconApp, IconChat, IconClock, IconDrawer, IconGear, IconLogout, IconMenu, IconMore, IconPlug, IconPlus, IconProject, IconSearch, IconSpark, Keys, Lockup,
} from "./components/icons";
import AppPage from "./pages/AppView";
import AppsPage, { CREATE_APP_PROMPT } from "./pages/Apps";
import AuthPage from "./pages/Auth";
import ChatPage from "./pages/Chat";
import ConnectionsPage from "./pages/Connections";
import FilesPage from "./pages/Files";
import OAuthCallback from "./pages/OAuthCallback";
import ProjectPage from "./pages/Project";
import ProjectsPage from "./pages/Projects";
import SettingsPage from "./pages/Settings";
import SkillsPage from "./pages/Skills";
import TasksPage from "./pages/Tasks";

type Counts = { files: number; skills: number; tasks: number; connections: number };
type AppCtx = {
  user: User; chats: ChatSummary[]; apps: AppSummary[]; projects: Project[]; counts: Counts; refresh: () => void; openNav: () => void; openCommands: () => void;
  signOut: () => void;
};
const Ctx = createContext<AppCtx | null>(null);
export const useApp = () => useContext(Ctx)!;

const GO = [
  { key: "c", to: "/", label: "Chats", icon: <IconChat /> },
  { key: "p", to: "/projects", label: "Projects", icon: <IconProject /> },
  { key: "f", to: "/files", label: "Files", icon: <IconDrawer /> },
  { key: "s", to: "/skills", label: "Skills", icon: <IconSpark /> },
  { key: "t", to: "/tasks", label: "Tasks", icon: <IconClock /> },
  { key: "k", to: "/connections", label: "Connections", icon: <IconPlug /> },
  { key: ",", to: "/settings", label: "Settings", icon: <IconGear /> },
];

/** Top bar: breadcrumb on the left, actions on the right, menu button on phones.
 *  `phoneOnly` pages carry their title in a PageHeader instead, so the bar only shows on phones (for the menu button). */
export function Topbar({ crumb, crumbTo, title, children, phoneOnly = false }: {
  crumb?: string; crumbTo?: string; title: string; children?: ReactNode; phoneOnly?: boolean;
}) {
  const { openNav } = useApp();
  return (
    <header className={`topbar${phoneOnly ? " phone-only" : ""}`}>
      <button className="btn ghost icon menu-btn" aria-label="Open menu" onClick={openNav}><IconMenu /></button>
      {crumb && <>{crumbTo ? <Link className="crumb" to={crumbTo}>{crumb}</Link> : <span className="crumb">{crumb}</span>}<span className="crumb">/</span></>}
      <span className="here">{title}</span>
      {children && <span className="actions">{children}</span>}
    </header>
  );
}

/** A page's header: its title and one line on what it is for, with the page's one action on the right. */
export function PageHeader({ title, lead, children }: { title: string; lead: ReactNode; children?: ReactNode }) {
  return (
    <header className="page-head">
      <div className="text"><h1>{title}</h1><p className="lead">{lead}</p></div>
      {children && <div className="actions">{children}</div>}
    </header>
  );
}

const LIVE = ["ready", "running"];
const SANDBOX_LABEL: Record<string, string> = { ready: "Sandbox ready", running: "Sandbox ready", missing: "Sandbox starts on first use" };

type Command = { id: string; group: string; label: string; icon: ReactNode; keys?: string[]; run: () => void };

function CommandMenu({ commands, onClose }: { commands: Command[]; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const shown = useMemo(() => commands.filter((c) => c.label.toLowerCase().includes(q.trim().toLowerCase())), [commands, q]);
  useEffect(() => { input.current?.focus(); }, []);
  useEffect(() => setSel(0), [q]);
  const run = (c?: Command) => { if (!c) return; onClose(); c.run(); };
  const groups = [...new Set(shown.map((c) => c.group))];
  return (
    <div className="cmd-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cmd" role="dialog" aria-label="Command menu">
        <div className="q">
          <IconSearch />
          <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search commands" placeholder="Search or run a command…"
            role="combobox" aria-expanded="true" aria-controls="cmd-results"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, shown.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
              else if (e.key === "Enter") { e.preventDefault(); run(shown[sel]); }
              else if (e.key === "Escape") { e.preventDefault(); onClose(); }
            }} />
          <span className="kbd">Esc</span>
        </div>
        <div className="results" id="cmd-results" role="listbox" aria-label="Commands">
          {shown.length === 0 && <div className="none">Nothing matches “{q}”.</div>}
          {groups.map((g) => (
            <div key={g}>
              <div className="group-label">{g}</div>
              {shown.filter((c) => c.group === g).map((c) => {
                const i = shown.indexOf(c);
                return (
                  <button key={c.id} className="item" role="option" aria-selected={i === sel} onMouseMove={() => setSel(i)} onClick={() => run(c)}>
                    {c.icon}<span className="label">{c.label}</span>{c.keys && <Keys keys={c.keys} />}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const typing = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));

function Shell({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [apps, setApps] = useState<AppSummary[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [counts, setCounts] = useState<Counts>({ files: 0, skills: 0, tasks: 0, connections: 0 });
  const [sandbox, setSandbox] = useState<string>("");
  const [navOpen, setNavOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const refresh = useCallback(() => {
    api.get<ChatSummary[]>("/chats").then(setChats).catch(() => {});
    api.get<AppSummary[]>("/apps").then(setApps).catch(() => {});
    api.get<Project[]>("/projects").then(setProjects).catch(() => {});
    api.get<{ state: string }>("/sandbox").then((r) => setSandbox(r.state)).catch(() => {});
    Promise.all([
      api.get<{ entries: unknown[] }>("/files").then((r) => r.entries.length).catch(() => 0),
      api.get<unknown[]>("/skills").then((r) => r.length).catch(() => 0),
      api.get<unknown[]>("/tasks").then((r) => r.length).catch(() => 0),
      api.get<{ config: string }>("/mcp/config").then((r) => {
        try { return Object.keys(JSON.parse(r.config).mcpServers ?? {}).length; } catch { return 0; }
      }).catch(() => 0),
    ]).then(([files, skills, tasks, connections]) => setCounts({ files, skills, tasks, connections }));
  }, []);
  useEffect(refresh, [refresh]);
  useEffect(() => { setNavOpen(false); }, [location.pathname]);

  // Keyboard: ⌘K / Ctrl+K command menu, C new chat, G then a letter to go somewhere.
  useEffect(() => {
    let pendingG = 0;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdOpen((o) => !o); return; }
      if (cmdOpen || typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (pendingG && Date.now() - pendingG < 1200) {
        pendingG = 0;
        const dest = GO.find((g) => g.key === k);
        if (dest) { e.preventDefault(); navigate(dest.to); }
        return;
      }
      if (k === "g") { pendingG = Date.now(); return; }
      if (k === "c") { e.preventDefault(); navigate("/"); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cmdOpen, navigate]);

  // Signing back in starts at home, wherever the person signed out from.
  const signOut = async () => { await api.post("/auth/logout").catch(() => {}); acp.close(); navigate("/", { replace: true }); onSignOut(); };

  const commands: Command[] = [
    { id: "new-chat", group: "Actions", label: "New chat", icon: <IconPlus />, keys: ["C"], run: () => navigate("/") },
    { id: "new-project", group: "Actions", label: "New project", icon: <IconProject />, run: () => navigate("/projects?new=1") },
    { id: "new-task", group: "Actions", label: "New task", icon: <IconClock />, run: () => navigate("/tasks?new=1") },
    { id: "upload-skill", group: "Actions", label: "Upload a skill", icon: <IconSpark />, run: () => navigate("/skills") },
    { id: "sign-out", group: "Actions", label: "Sign out", icon: <IconLogout />, run: signOut },
    ...GO.map((g) => ({ id: `go-${g.key}`, group: "Go to", label: g.label, icon: g.icon, keys: ["G", g.key.toUpperCase()], run: () => navigate(g.to) })),
    { id: "create-app", group: "Actions", label: "Create an app", icon: <IconApp />, run: () => navigate("/", { state: { draft: CREATE_APP_PROMPT } }) },
    { id: "all-apps", group: "Your apps", label: "See all apps", icon: <IconApp />, run: () => navigate("/apps") },
    ...apps.map((a) => ({ id: `app-${a.id}`, group: "Your apps", label: a.title, icon: <IconApp />, run: () => navigate(`/apps/${a.id}`) })),
    ...projects.map((p) => ({ id: `project-${p.id}`, group: "Projects", label: p.name, icon: <IconProject />, run: () => navigate(`/projects/${p.id}`) })),
    ...chats.slice(0, 8).map((c) => ({ id: `chat-${c.id}`, group: "Recent chats", label: c.title, icon: <IconChat />, run: () => navigate(`/c/${c.id}`) })),
  ];

  // Counts only when there is something to count: a row of zeros reads like errors.
  const nav = (to: string, label: string, icon: ReactNode, count: number) => (
    <NavLink to={to} className={({ isActive }) => `nav${isActive ? " active" : ""}`}>
      {icon}{label}{count > 0 && <span className="right">{count}</span>}
    </NavLink>
  );
  const onChat = location.pathname === "/" || location.pathname.startsWith("/c/");

  return (
    <Ctx.Provider value={{ user, chats, apps, projects, counts, refresh, openNav: () => setNavOpen(true), openCommands: () => setCmdOpen(true), signOut }}>
      <div className="shell">
        {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}
        <nav className={`sidebar${navOpen ? " open" : ""}`} aria-label="Main">
          <Link to="/" className="brand-row" aria-label="AI Chatbot Framework home"><Lockup /></Link>
          <button className="search-btn" aria-label="Search or run a command" onClick={() => setCmdOpen(true)}>
            <IconSearch /><span>Search</span><Keys keys={["⌘", "K"]} />
          </button>
          <Link to="/" className="btn new-chat"><IconPlus />New chat<span className="kbd">C</span></Link>
          <NavLink to="/" end className={() => `nav${onChat ? " active" : ""}`}><IconChat />Chats</NavLink>
          {nav("/projects", "Projects", <IconProject />, projects.length)}
          {nav("/files", "Files", <IconDrawer />, counts.files)}
          {nav("/skills", "Skills", <IconSpark />, counts.skills)}
          {nav("/tasks", "Tasks", <IconClock />, counts.tasks)}
          {nav("/connections", "Connections", <IconPlug />, counts.connections)}
          {apps.length > 0 && (
            <div className="apps-nav" role="group" aria-labelledby="apps-nav-label">
              <div className="section-label" id="apps-nav-label">Your apps</div>
              {apps.slice(0, 3).map((a) => (
                <NavLink key={a.id} to={`/apps/${a.id}`} title={a.description || a.title} className={({ isActive }) => `nav${isActive ? " active" : ""}`}>
                  <IconApp /><span className="nav-label">{a.title}</span>
                </NavLink>
              ))}
              <NavLink to="/apps" end className={({ isActive }) => `nav${isActive ? " active" : ""}`}>
                <IconMore /><span className="nav-label">See all apps</span><span className="right">{apps.length}</span>
              </NavLink>
            </div>
          )}
          <div className="recents">
            {chats.length > 0 && <div className="section-label">Recent</div>}
            {chats.slice(0, 40).map((c) => (
              <NavLink key={c.id} to={`/c/${c.id}`} title={c.title} className={({ isActive }) => `recent${isActive ? " active" : ""}`}>{c.title}</NavLink>
            ))}
          </div>
          <div className="me">
            <span className="avatar" aria-hidden="true">{(user.name || user.email)[0]}</span>
            <span className="who" title={user.email}>
              <span className="name">{user.name || user.email}</span>
              {sandbox && <span className="status" data-testid="sandbox-status">
                {LIVE.includes(sandbox) && <span className="live-dot" aria-hidden="true" />}{SANDBOX_LABEL[sandbox] ?? `Sandbox ${sandbox}`}
              </span>}
            </span>
            <NavLink to="/settings" className={({ isActive }) => `btn ghost icon${isActive ? " on" : ""}`} aria-label="Settings" title="Settings"><IconGear /></NavLink>
          </div>
        </nav>
        <div className="main"><Outlet /></div>
        {cmdOpen && <CommandMenu commands={commands} onClose={() => setCmdOpen(false)} />}
      </div>
    </Ctx.Provider>
  );
}

/** The installed app opened without a network (the service worker serves the page, the API can't answer). */
function Offline({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="auth">
      <div className="auth-card">
        <div className="brand-row"><Lockup size={32} /></div>
        <h1>You're offline</h1>
        <p>Reconnect to the internet, then try again.</p>
        <button className="btn primary lg" type="button" onClick={onRetry}>Try again</button>
      </div>
    </div>
  );
}

export default function App() {
  // undefined: loading; null: signed out; "offline": the server couldn't be reached at all.
  const [user, setUser] = useState<User | null | "offline" | undefined>(undefined);
  const load = useCallback(() => {
    api.get<{ user: User }>("/auth/me").then((r) => setUser(r.user))
      .catch((e) => setUser(e instanceof ApiError ? null : "offline"));
  }, []);
  useEffect(load, [load]);
  if (user === undefined) return null;
  if (user === "offline") return <Offline onRetry={() => { setUser(undefined); load(); }} />;
  return (
    <BrowserRouter>
      <Routes>
        {user === null ? (
          <Route path="*" element={<AuthPage onAuthed={setUser} />} />
        ) : (
          <>
            <Route path="/oauth/callback" element={<OAuthCallback />} />
            <Route element={<Shell user={user} onSignOut={() => setUser(null)} />}>
              <Route path="/" element={<ChatPage />} />
              <Route path="/c/:id" element={<ChatPage />} />
              <Route path="/apps" element={<AppsPage />} />
              <Route path="/apps/:id" element={<AppPage />} />
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/projects/:id" element={<ProjectPage />} />
              <Route path="/files" element={<FilesPage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/connections" element={<ConnectionsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </>
        )}
      </Routes>
    </BrowserRouter>
  );
}
