import { useEffect, useRef, useState } from "react";
import { api } from "../api";

/** The OAuth redirect lands here; we hand the code to Harbor and report back to the opener. */
export default function OAuthCallback() {
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [message, setMessage] = useState("");
  const once = useRef(false);

  useEffect(() => {
    if (once.current) return;
    once.current = true;
    const q = new URLSearchParams(window.location.search);
    const finish = (ok: boolean, text: string) => {
      setState(ok ? "ok" : "error");
      setMessage(text);
      if (window.opener) {
        window.opener.postMessage({ type: "harbor-oauth", ok }, window.location.origin);
        if (ok) setTimeout(() => window.close(), 400);
      } else if (ok) {
        setTimeout(() => window.location.replace("/connections"), 800);
      }
    };
    if (q.get("error")) {
      finish(false, q.get("error_description") || q.get("error") || "Sign-in was cancelled.");
      return;
    }
    const code = q.get("code");
    const st = q.get("state");
    if (!code || !st) {
      finish(false, "This page is missing sign-in details.");
      return;
    }
    api.post<{ server: string }>("/oauth/callback", { code, state: st })
      .then((r) => finish(true, `Connected to ${r.server}.`))
      .catch((e) => finish(false, (e as Error).message));
  }, []);

  return (
    <div className="auth">
      <div className="auth-card" role="status">
        <h1>{state === "working" ? "Connecting…" : state === "ok" ? "You're connected" : "Sign-in failed"}</h1>
        <p>{message || "One moment."}</p>
        {state !== "working" && <a className="btn" href="/connections">Back to Connections</a>}
      </div>
    </div>
  );
}
