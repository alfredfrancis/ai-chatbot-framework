export type User = { id: number; email: string; name: string };
export type ToolCall = { id: string; name: string; arguments: Record<string, unknown> };
export type Message = {
  id: number;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_calls: ToolCall[];
  tool_call_id: string | null;
  name: string | null;
  is_error: boolean;
  duration_ms: number | null;
  created_at: string;
};
export type FileEntry = { name: string; path: string; type: "dir" | "file"; size?: number; items?: number };
export type Skill = { name: string; description: string; path: string; files: number };
export type ChatSummary = { id: number; title: string; task_id: number | null; updated_at: string };
export type Chat = ChatSummary & { messages: Message[]; running: boolean };
export type Task = {
  id: number;
  name: string;
  prompt: string;
  schedule: string;
  timezone: string;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: string;
  last_chat_id: number | null;
};
export type McpServer = {
  name: string;
  transport: "stdio" | "http";
  target: string;
  state: "connected" | "needs_auth" | "error" | "disabled" | "unknown";
  error: string | null;
  tools: { name: string; description: string }[];
  signed_in: boolean;
};
export type Settings = {
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  defaults: { provider: string; model: string; has_api_key: boolean };
};
export type AgentEvent =
  | { type: "message"; message: Message }
  | { type: "tool_start"; id: string; name: string; label: string }
  | { type: "notice"; text: string }
  | { type: "queued"; text: string }
  | { type: "stopped" }
  | { type: "error"; error: string }
  | { type: "done" };

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : (data.detail?.[0]?.msg ?? detail);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b: unknown = {}) => request<T>("POST", p, b),
  put: <T>(p: string, b: unknown) => request<T>("PUT", p, b),
  patch: <T>(p: string, b: unknown) => request<T>("PATCH", p, b),
  del: <T>(p: string) => request<T>("DELETE", p),
};

async function readSse(res: Response, onEvent: (e: AgentEvent) => void) {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
      }
    }
  }
}

/**
 * Send a chat message. If the agent is idle this starts a run and streams its events.
 * If it is already working, the message is queued (steering) and "queued" is returned.
 */
export async function sendMessage(chatId: number, content: string, onEvent: (e: AgentEvent) => void): Promise<"streamed" | "queued"> {
  const res = await fetch(`/api/chats/${chatId}/messages`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (res.status === 202) return "queued";
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    onEvent({ type: "error", error: detail });
    onEvent({ type: "done" });
    return "streamed";
  }
  await readSse(res, onEvent);
  return "streamed";
}

/** Follow a run that is already in progress. Resolves false if nothing is running. */
export async function attachStream(chatId: number, onEvent: (e: AgentEvent) => void): Promise<boolean> {
  const res = await fetch(`/api/chats/${chatId}/stream`, { credentials: "same-origin" });
  if (!res.ok || !res.headers.get("content-type")?.includes("text/event-stream")) return false;
  await readSse(res, onEvent);
  return true;
}

export async function uploadFile(path: string, file: File, field: Record<string, string> = {}) {
  const body = new FormData();
  body.append("file", file);
  for (const [k, v] of Object.entries(field)) body.append(k, v);
  const res = await fetch(`/api${path}`, { method: "POST", body, credentials: "same-origin" });
  if (!res.ok) throw new ApiError(res.status, (await res.json().catch(() => ({}))).detail ?? "Upload failed");
  return res.json();
}
