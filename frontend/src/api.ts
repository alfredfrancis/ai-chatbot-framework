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
  created_at: string;
};
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

/** POST a chat message and call onEvent for each server-sent event. */
export async function streamMessage(chatId: number, content: string, onEvent: (e: AgentEvent) => void) {
  const res = await fetch(`/api/chats/${chatId}/messages`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    onEvent({ type: "error", error: detail });
    onEvent({ type: "done" });
    return;
  }
  const reader = res.body.getReader();
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
