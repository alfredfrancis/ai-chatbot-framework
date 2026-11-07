import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { api, ApiError, type ChatSummary, type User } from "./api";
import { IconChat, IconClock, IconDoc, IconGear, IconMenu, IconPlug, IconPlus } from "./components/icons";
import AuthPage from "./pages/Auth";
import ChatPage from "./pages/Chat";
import ConnectionsPage from "./pages/Connections";
import MemoryPage from "./pages/Memory";
import OAuthCallback from "./pages/OAuthCallback";
import SettingsPage from "./pages/Settings";
import TasksPage from "./pages/Tasks";

type AppCtx = { user: User; chats: ChatSummary[]; refreshChats: () => void; signOut: () => void };
const Ctx = createContext<AppCtx | null>(null);
export const useApp = () => useContext(Ctx)!;

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

  return (
    <Ctx.Provider value={{ user, chats, refreshChats, signOut }}>
      <div className="shell">
        {open && <div className="scrim" onClick={() => setOpen(false)} />}
        <nav className={`sidebar${open ? " open" : ""}`} aria-label="Main">
          <div className="sidebar-head">
            <NavLink to="/" className="brand">Harbor</NavLink>
            <NavLink to="/" className="icon-btn" aria-label="New chat" title="New chat"><IconPlus /></NavLink>
          </div>
          <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><IconChat />Chats</NavLink>
          <NavLink to="/tasks" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><IconClock />Tasks</NavLink>
          <NavLink to="/connections" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><IconPlug />Connections</NavLink>
          <NavLink to="/memory" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><IconDoc />Memory</NavLink>
          {chats.length > 0 && <div className="section-label">Recent</div>}
          {chats.slice(0, 50).map((c) => (
            <NavLink key={c.id} to={`/c/${c.id}`} className={({ isActive }) => `nav-link chat${isActive ? " active" : ""}`}>
              {c.title}
            </NavLink>
          ))}
          <div className="sidebar-foot">
            <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><IconGear />Settings</NavLink>
            <div className="who">
              <span title={user.email}>{user.email}</span>
              <button className="btn ghost small" onClick={signOut}>Sign out</button>
            </div>
          </div>
        </nav>
        <div className="main">
          <div className="mobile-bar">
            <button className="icon-btn" aria-label="Open menu" onClick={() => setOpen(true)}><IconMenu /></button>
            <span className="brand">Harbor</span>
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
    api.get<{ user: User }>("/auth/me")
      .then((r) => setUser(r.user))
      .catch((e) => setUser(e instanceof ApiError && e.status === 401 ? null : null));
  }, []);

  if (user === undefined) return null;

  return (
    <BrowserRouter>
      <Routes>
        {user === null ? (
          <>
            <Route path="/oauth/callback" element={<AuthPage onAuthed={setUser} />} />
            <Route path="*" element={<AuthPage onAuthed={setUser} />} />
          </>
        ) : (
          <>
            <Route path="/oauth/callback" element={<OAuthCallback />} />
            <Route element={<Shell user={user} onSignOut={() => setUser(null)} />}>
              <Route path="/" element={<ChatPage />} />
              <Route path="/c/:id" element={<ChatPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/connections" element={<ConnectionsPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </>
        )}
      </Routes>
    </BrowserRouter>
  );
}
