import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { api, type ChatSummary, type User } from "./api";
import { IconClock, IconDrawer, IconGear, IconMenu, IconPlug, IconPlus, IconSpark, Lockup } from "./components/icons";
import AuthPage from "./pages/Auth";
import ChatPage from "./pages/Chat";
import ConnectionsPage from "./pages/Connections";
import FilesPage from "./pages/Files";
import OAuthCallback from "./pages/OAuthCallback";
import SettingsPage from "./pages/Settings";
import SkillsPage from "./pages/Skills";
import TasksPage from "./pages/Tasks";

type AppCtx = { user: User; chats: ChatSummary[]; refreshChats: () => void };
const Ctx = createContext<AppCtx | null>(null);
export const useApp = () => useContext(Ctx)!;

const NAV = [
  { to: "/files", label: "Files", icon: <IconDrawer /> },
  { to: "/skills", label: "Skills", icon: <IconSpark /> },
  { to: "/tasks", label: "Tasks", icon: <IconClock /> },
  { to: "/connections", label: "Connections", icon: <IconPlug /> },
];

function Shell({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const refreshChats = useCallback(() => {
    api.get<ChatSummary[]>("/chats").then(setChats).catch(() => {});
  }, []);
  useEffect(refreshChats, [refreshChats]);
  useEffect(() => setOpen(false), [location.pathname]);

  const signOut = async () => {
    await api.post("/auth/logout").catch(() => {});
    onSignOut();
  };
  const cls = ({ isActive }: { isActive: boolean }) => `nav-link${isActive ? " active" : ""}`;

  return (
    <Ctx.Provider value={{ user, chats, refreshChats }}>
      <div className="shell">
        {open && <div className="scrim" onClick={() => setOpen(false)} />}
        <nav className={`sidebar${open ? " open" : ""}`} aria-label="Main">
          <Link to="/" className="lockup" aria-label="AI Chatbot Framework home"><Lockup /></Link>
          <Link to="/" className="btn block"><IconPlus />New chat</Link>
          {NAV.map((n) => <NavLink key={n.to} to={n.to} className={cls}>{n.icon}{n.label}</NavLink>)}
          {chats.length > 0 && <div className="section-label">Recent</div>}
          {chats.slice(0, 50).map((c) => (
            <NavLink key={c.id} to={`/c/${c.id}`} className={({ isActive }) => `nav-link chat${isActive ? " active" : ""}`}>
              {c.title}
            </NavLink>
          ))}
          <div className="sidebar-foot">
            <NavLink to="/settings" className={cls}><IconGear />Settings</NavLink>
            <div className="who">
              <span title={user.email}>{user.email}</span>
              <button className="btn ghost small" onClick={signOut}>Sign out</button>
            </div>
          </div>
        </nav>
        <div className="main">
          <div className="mobile-bar">
            <button className="icon-btn" aria-label="Open menu" onClick={() => setOpen(true)}><IconMenu /></button>
            <Link to="/" className="lockup" aria-label="AI Chatbot Framework home"><Lockup /></Link>
          </div>
          <Outlet />
        </div>
      </div>
    </Ctx.Provider>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api.get<{ user: User }>("/auth/me").then((r) => setUser(r.user)).catch(() => setUser(null));
  }, []);

  if (user === undefined) return null;

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
