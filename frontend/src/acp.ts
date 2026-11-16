/**
 * Agent Client Protocol (https://agentclientprotocol.com) client: JSON-RPC 2.0 over a WebSocket to /api/acp.
 * The chat talks to the agent only through this. One shared connection, opened on first use; when it drops
 * (a restart, a deploy, a network blip) it comes back by itself.
 */

export type ContentBlock = { type: "text"; text: string } | { type: string; [k: string]: unknown };
export type ToolStatus = "pending" | "in_progress" | "completed" | "failed";
/** A sub-agent (the `agent` tool): its model, the tokens it used, its steps (`ok` is null while one runs) and
 *  its own session, which opens read-only. */
export type AgentInfo = { model: string; tokens: number; steps: { title: string; ok: boolean | null }[]; session?: string };
/** The session a sub-agent's session belongs to. */
export type ParentSession = { sessionId: string; title: string };
type Meta = { _meta?: { acf?: { messageId?: number | string; tool?: string; durationMs?: number | null; background?: string; agent?: AgentInfo } } };
export type SessionUpdate = Meta & (
  | { sessionUpdate: "user_message_chunk" | "agent_message_chunk" | "agent_thought_chunk"; content: ContentBlock }
  | { sessionUpdate: "tool_call"; toolCallId: string; title: string; kind?: string; status?: ToolStatus; rawInput?: Record<string, unknown> }
  | {
      sessionUpdate: "tool_call_update"; toolCallId: string; title?: string; status?: ToolStatus;
      content?: { type: string; content?: ContentBlock }[] | null;
    }
  | { sessionUpdate: "session_info_update"; title?: string | null }
  | { sessionUpdate: "usage_update"; used: number; size: number; _meta?: { acf?: UsageMeta } }
  | { sessionUpdate: string }
);
/** What fills the context window (estimates); see backend agent/usage.py. */
export type UsagePart = { name: string; tokens: number; items?: string[]; count?: number };
export type UsageMeta = { percent: number; measured: boolean; parts: UsagePart[] };
/** The context window after the latest model call. */
export type Usage = { used: number; size: number } & UsageMeta;
/** What a background review learned in a chat (a notice's `_meta.acf.learned`): the files it changed, and whether that can be undone. */
export type Learned = { id: number; changes: { name: string; added: boolean }[]; can_undo: boolean; undone: boolean };
export type AcpNotification =
  | { method: "session/update"; params: { sessionId: string; update: SessionUpdate } }
  | { method: "_acf/notice"; params: { sessionId: string; text: string; _meta?: { acf?: { learned?: Learned } } } }
  | { method: "_acf/turn_end"; params: { sessionId: string; stopReason: string; error?: string } }
  | { method: "_acf/turn_start"; params: { sessionId: string } }
  | { method: "_acf/disconnected"; params: Record<string, never> }
  | { method: "_acf/reconnected"; params: Record<string, never> }
  | { method: "_acf/signed_out"; params: Record<string, never> };
export type StopReason = "end_turn" | "cancelled" | "max_turn_requests" | "max_tokens" | "refusal";

export class AcpError extends Error {
  constructor(public code: number, message: string) {
    super(message);
  }
}

/** The code of an AcpError raised because there is no connection, not because the agent refused. */
export const NO_CONNECTION = -1;
export const lostConnection = (e: unknown) => e instanceof AcpError && e.code === NO_CONNECTION;

/**
 * idle: not wanted yet, or closed on sign-out. open: a socket is up. down: it was wanted and is not up; one
 * attempt at a time comes back after 0.5 s, doubling to 10 s, with jitter so a restarted server is not hit
 * by every client at once.
 */
export type Link = "idle" | "open" | "down";
const retryDelay = (attempt: number) => Math.min(10_000, 500 * 2 ** attempt) * (0.5 + Math.random() / 2);

type Listener = (n: AcpNotification) => void;

class AcpClient {
  private state: Link = "idle";
  private ws: WebSocket | null = null; // the socket being opened or open
  private dropped = new WeakSet<WebSocket>(); // closed on purpose: their close is not a lost connection
  private opening: Promise<WebSocket> | null = null;
  private attempt = 0;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private nextId = 1;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private listeners = new Set<Listener>();

  get link(): Link {
    return this.state;
  }

  on(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  private emit(n: AcpNotification) {
    for (const l of [...this.listeners]) l(n);
  }

  private connect(): Promise<WebSocket> {
    if (this.ws?.readyState === WebSocket.OPEN) return Promise.resolve(this.ws);
    if (this.opening) return this.opening;
    // Down, or the socket is closing (its close event marks the link down): the next attempt is scheduled or
    // about to be, so callers fail fast instead of opening a second socket.
    if (this.state !== "idle") return Promise.reject(new AcpError(NO_CONNECTION, "Not connected"));
    return this.open();
  }

  private open(): Promise<WebSocket> {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/acp`);
    this.ws = ws;
    this.opening = new Promise<WebSocket>((resolve, reject) => {
      ws.onopen = () => {
        if (this.dropped.has(ws)) return;
        this.opening = null;
        this.attempt = 0;
        const back = this.state === "down";
        this.state = "open";
        resolve(ws);
        this.request("initialize", { protocolVersion: 1, clientCapabilities: {}, clientInfo: { name: "acf-web", version: "1" } }).catch(() => {});
        if (back) this.emit({ method: "_acf/reconnected", params: {} });
      };
      ws.onclose = () => {
        reject(new AcpError(NO_CONNECTION, "Could not connect to the agent"));
        if (this.dropped.has(ws)) return;
        this.ws = null;
        this.opening = null;
        for (const p of this.pending.values()) p.reject(new AcpError(NO_CONNECTION, "Connection lost"));
        this.pending.clear();
        if (this.state !== "down") {
          this.state = "down";
          this.emit({ method: "_acf/disconnected", params: {} });
        }
        this.later();
      };
      ws.onmessage = (ev) => {
        let msg;
        try {
          msg = JSON.parse(String(ev.data));
        } catch {
          return; // one bad frame is dropped, the connection stays
        }
        if (msg.id != null && !msg.method) {
          const p = this.pending.get(msg.id);
          if (!p) return;
          this.pending.delete(msg.id);
          if (msg.error) p.reject(new AcpError(msg.error.code, msg.error.message));
          else p.resolve(msg.result);
        } else if (msg.method && msg.id == null) {
          this.emit(msg as AcpNotification);
        }
      };
    });
    return this.opening;
  }

  private later() {
    this.retry = setTimeout(() => this.reconnect(), retryDelay(this.attempt++));
  }

  /** One attempt to come back: ask the server first, and open a socket only once it answers. A server that
   *  answers but no longer knows the user ends the attempts. */
  private async reconnect() {
    this.retry = undefined;
    const server = await fetch("/api/auth/me", { credentials: "same-origin" })
      .then((r) => (r.status === 401 ? "signed out" : r.ok ? "up" : "down"), () => "down");
    if (this.state !== "down") return; // closed meanwhile
    if (server === "signed out") {
      this.close();
      this.emit({ method: "_acf/signed_out", params: {} });
    } else if (server === "down") this.later();
    else this.open().catch(() => {});
  }

  async request<T>(method: string, params: Record<string, unknown>): Promise<T> {
    const ws = await this.connect();
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      ws.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
    });
  }

  async notify(method: string, params: Record<string, unknown>) {
    (await this.connect()).send(JSON.stringify({ jsonrpc: "2.0", method, params }));
  }

  /** Signing out: close the connection and stop coming back. */
  close() {
    clearTimeout(this.retry);
    this.retry = undefined;
    this.state = "idle";
    this.attempt = 0;
    const ws = this.ws;
    if (ws) this.dropped.add(ws);
    this.ws = null;
    this.opening = null;
    for (const p of this.pending.values()) p.reject(new AcpError(NO_CONNECTION, "Connection closed"));
    this.pending.clear();
    ws?.close();
  }
}

export const acp = new AcpClient();

/** A session setting the user can choose, such as the model or its effort (ACP session config options). */
export type ConfigOption = {
  id: string; name: string; category?: string; type: "select"; currentValue: string;
  options: { value: string; name: string; description?: string }[];
};
/** A new chat; with `projectId`, a chat in that project. */
export const newSession = (projectId?: number) =>
  acp.request<{ sessionId: string; configOptions?: ConfigOption[] }>("session/new", {
    cwd: "/workspace", mcpServers: [], ...(projectId ? { _meta: { acf: { projectId } } } : {}),
  });
export const loadSession = (sessionId: string) =>
  acp.request<{ configOptions?: ConfigOption[]; _meta?: { acf?: { running?: boolean; title?: string; parent?: ParentSession } } } | null>("session/load", { sessionId, cwd: "/workspace", mcpServers: [] });
/** A file in the workspace, sent as an ACP resource_link (file:///workspace/<path>). */
export type Attachment = { name: string; uri: string };
export const WORKSPACE_URI = "file:///workspace/";
export const prompt = (sessionId: string, text: string, files: Attachment[] = []) =>
  acp.request<{ stopReason: StopReason }>("session/prompt", {
    sessionId,
    prompt: [...(text ? [{ type: "text", text }] : []), ...files.map((f) => ({ type: "resource_link", ...f }))],
  });
/** Choose a chat's model or effort; returns the options as they are now. */
export const setConfigOption = (sessionId: string, configId: string, value: string) =>
  acp.request<{ configOptions: ConfigOption[] }>("session/set_config_option", { sessionId, configId, value });
export const cancel = (sessionId: string) => acp.notify("session/cancel", { sessionId });
