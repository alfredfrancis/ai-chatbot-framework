import type { ChatState } from './training';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

export const converse = async (intent: ChatState): Promise<ChatState> => {
  const response = await fetch(`${API_BASE_URL}bots/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(intent),
  });
  return response.json();
}; 