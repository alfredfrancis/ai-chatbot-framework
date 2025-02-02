import { API_BASE_URL } from "./base";

export interface ChatLog {
  thread_id: string;
  user_message: {
    text: string;
    context: Record<string, unknown>;
  };
  bot_message: Array<{ text: string }>;
  timestamp: string;
}

export interface ChatThreadInfo {
  thread_id: string;
  date: string;
}

export interface ChatLogsResponse {
  total: number;
  page: number;
  limit: number;
  conversations: ChatThreadInfo[];
}

export async function listChatLogs(page: number, limit: number): Promise<ChatLogsResponse> {
  const response = await fetch(`${API_BASE_URL}chatlogs/?page=${page}&limit=${limit}`);
  return response.json();
}

export async function getChatThread(threadId: string): Promise<ChatLog[]> {
  const response = await fetch(`${API_BASE_URL}chatlogs/${threadId}`);
  return response.json();
}

export function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}