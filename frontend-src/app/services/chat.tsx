const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

export const converse = async (intent: any, botId: string = 'default') => {
  const response = await fetch(`${API_BASE_URL}api/v1`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(intent),
  });
  return response.json();
}; 