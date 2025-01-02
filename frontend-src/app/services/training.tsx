const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

export const saveTrainingData = async (intentId: string, data: any) => {
  const response = await fetch(`${API_BASE_URL}train/${intentId}/data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
};

export const getTrainingData = async (intentId: string) => {
  const response = await fetch(`${API_BASE_URL}train/${intentId}/data`);
  return response.json();
};

export const trainModels = async () => {
  const response = await fetch(`${API_BASE_URL}nlu/build_models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return response.json();
}; 