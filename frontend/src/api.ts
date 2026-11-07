export type User = { id: number; email: string; name: string };
export type FileEntry = { name: string; path: string; type: "dir" | "file"; size?: number; items?: number };
export type Artifact = { path: string; name: string; kind: "uploaded" | "produced"; size: number; modified_at: string };
export type Skill = { name: string; description: string; path: string; files: number };
export type ChatSummary = { id: number; title: string; task_id: number | null; updated_at: string };
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
export type McpPreset = {
  id: string;
  name: string;
  description: string;
  url: string;
  added: boolean;
};
export type Settings = {
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  defaults: { provider: string; model: string; has_api_key: boolean };
};
/** A file size people can read: 812 B, 4.2 KB, 1.3 MB. */
export const formatSize = (n?: number) =>
  n == null ? "" : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
/** URL of a workspace file: opened in the browser, or downloaded. */
export const rawUrl = (path: string, download = false) => `/api/files/raw?path=${encodeURIComponent(path)}${download ? "&download=true" : ""}`;

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

export async function uploadFile(path: string, file: File, field: Record<string, string> = {}) {
  const body = new FormData();
  body.append("file", file);
  for (const [k, v] of Object.entries(field)) body.append(k, v);
  const res = await fetch(`/api${path}`, { method: "POST", body, credentials: "same-origin" });
  if (!res.ok) throw new ApiError(res.status, (await res.json().catch(() => ({}))).detail ?? "Upload failed");
  return res.json();
}
