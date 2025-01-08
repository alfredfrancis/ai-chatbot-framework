const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/admin/';

interface AgentConfig {
  confidence_threshold: number
}

export const getConfig = async (): Promise<AgentConfig> => {
  const response = await fetch(`${API_BASE_URL}bots/default/config`);
  return response.json();
};

export const updateConfig = async (data: AgentConfig): Promise<AgentConfig> => {
  const response = await fetch(`${API_BASE_URL}bots/default/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
};

export const importIntents = async (fileToUpload: File) => {
  const formData = new FormData();
  formData.append('file', fileToUpload, fileToUpload.name);
  const response = await fetch(`${API_BASE_URL}bots/default/import`, {
    method: 'POST',
    body: formData,
  });
  return response.json();
};

export const exportIntents = async () => {
  window.location.href = `${API_BASE_URL}bots/default/export`;
};

export type { AgentConfig }; 