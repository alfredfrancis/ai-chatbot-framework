import { useEffect, useState, type FormEvent } from "react";
import { api, type User } from "../api";
import { Lockup } from "../components/icons";

export default function AuthPage({ onAuthed }: { onAuthed: (u: User) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [signupAllowed, setSignupAllowed] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<{ signup_allowed: boolean; has_users: boolean }>("/auth/config").then((c) => {
      setSignupAllowed(c.signup_allowed);
      if (!c.has_users) setMode("signup");
    });
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body = mode === "signup" ? { email, password, name } : { email, password };
      const r = await api.post<{ user: User }>(`/auth/${mode}`, body);
      onAuthed(r.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand-row"><Lockup size={32} /></div>
        <h1>{mode === "signup" ? "Create your account" : "Welcome back"}</h1>
        <p>{mode === "signup" ? "Your own agent, with a private computer, your files and your skills." : "Sign in to continue."}</p>
        {mode === "signup" && (
          <div className="field">
            <label htmlFor="name">Name</label>
            <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </div>
        )}
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" className="input" type="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" className="input" type="password" required minLength={8} value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "signup" ? "new-password" : "current-password"} />
          {mode === "signup" && <span className="hint">At least 8 characters.</span>}
        </div>
        {error && <div className="banner" role="alert">{error}</div>}
        <button className="btn primary lg" type="submit" disabled={busy}>
          {mode === "signup" ? "Create account" : "Sign in"}
        </button>
        {signupAllowed && (
          <button type="button" className="btn ghost" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}>
            {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
          </button>
        )}
      </form>
    </div>
  );
}
