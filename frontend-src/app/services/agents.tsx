import type { AgentConfig } from './training';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

export const getConfig = async (): Promise<AgentConfig> => {
  const response = await fetch(`${API_BASE_URL}agents/default/config`);
  return response.json();
};

export const updateConfig = async (data: AgentConfig): Promise<AgentConfig> => {
  const response = await fetch(`${API_BASE_URL}agents/default/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
}; 