import { API_BASE_URL } from "./base";
import type { IntentModel } from './training';


export const getIntents = async (): Promise<IntentModel[]> => {
  const response = await fetch(`${API_BASE_URL}intents/`);
  return response.json();
};

export const getIntent = async (id: string): Promise<IntentModel> => {
  const response = await fetch(`${API_BASE_URL}intents/${id}`);
  return response.json();
};

export const saveIntent = async (intent: IntentModel): Promise<IntentModel> => {
  if (intent.id) {
    return updateIntent(intent);
  } else {
    delete intent.id;
    return createIntent(intent);
  }
};

export const createIntent = async (intent: IntentModel): Promise<IntentModel> => {
  const response = await fetch(`${API_BASE_URL}intents/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(intent),
  });
  return response.json();
};

export const updateIntent = async (intent: IntentModel): Promise<IntentModel> => {
  const response = await fetch(`${API_BASE_URL}intents/${intent.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(intent),
  });
  return response.json();
};

export const deleteIntent = async (id: string): Promise<void> => {
  await fetch(`${API_BASE_URL}intents/${id}`, {
    method: 'DELETE',
  });
};