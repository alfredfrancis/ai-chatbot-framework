/**
 * Agent Client Protocol (https://agentclientprotocol.com) client: JSON-RPC 2.0 over a WebSocket to /api/acp.
 * The chat talks to the agent only through this. One shared connection, opened on first use and
 * re-opened after it drops.
 */

export type ContentBlock = { type: "text"; text: string } | { type: string; [k: string]: unknown };
export type ToolStatus = "pending" | "in_progress" | "completed" | "failed";
type Meta = { _meta?: { acf?: { messageId?: number; tool?: string; durationMs?: number | null } } };
export type SessionUpdate = Meta & (
  | { sessionUpdate: "user_message_chunk" | "agent_message_chunk" | "agent_thought_chunk"; content: ContentBlock }
  | { sessionUpdate: "tool_call"; toolCallId: string; title: string; kind?: string; status?: ToolStatus; rawInput?: Record<string, unknown> }
  | {
      sessionUpdate: "tool_call_update"; toolCallId: string; title?: string; status?: ToolStatus;
      content?: { type: string; content?: ContentBlock }[] | null;
    }
  | { sessionUpdate: "session_info_update"; title?: string | null }
  | { sessionUpdate: string }
);
export type AcpNotification =
  | { method: "session/update"; params: { sessionId: string; update: SessionUpdate } }
  | { method: "_acf/notice"; params: { sessionId: string; text: string } }
  | { method: "_acf/turn_end"; params: { sessionId: string; stopReason: string; error?: string } }
  | { method: "_acf/disconnected"; params: Record<string, never> };
export type StopReason = "end_turn" | "cancelled" | "max_turn_requests" | "max_tokens" | "refusal";

export class AcpError extends Error {
  constructor(public code: number, message: string) {
    super(message);
  }
}

type Listener = (n: AcpNotification) => void;

class AcpClient {
  private ws: WebSocket | null = null;
  private opening: Promise<WebSocket> | null = null;
  private nextId = 1;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private listeners = new Set<Listener>();

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
    this.opening = new Promise<WebSocket>((resolve, reject) => {
      const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/acp`);
      ws.onopen = () => {
        this.ws = ws;
        this.opening = null;
        resolve(ws);
        this.request("initialize", { protocolVersion: 1, clientCapabilities: {}, clientInfo: { name: "acf-web", version: "1" } }).catch(() => {});
      };
      ws.onerror = () => { if (this.opening) { this.opening = null; reject(new AcpError(-1, "Could not connect to the agent")); } };
      ws.onclose = () => {
        if (this.ws !== ws) return;
        this.ws = null;
        for (const p of this.pending.values()) p.reject(new AcpError(-1, "Connection lost"));
        this.pending.clear();
        this.emit({ method: "_acf/disconnected", params: {} });
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(String(ev.data));
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

  close() {
    const ws = this.ws;
    this.ws = null;
    ws?.close();
  }
}

export const acp = new AcpClient();

export const newSession = () => acp.request<{ sessionId: string }>("session/new", { cwd: "/workspace", mcpServers: [] });
export const loadSession = (sessionId: string) =>
  acp.request<{ _meta?: { acf?: { running?: boolean } } } | null>("session/load", { sessionId, cwd: "/workspace", mcpServers: [] });
export const prompt = (sessionId: string, text: string) =>
  acp.request<{ stopReason: StopReason }>("session/prompt", { sessionId, prompt: [{ type: "text", text }] });
export const cancel = (sessionId: string) => acp.notify("session/cancel", { sessionId });
