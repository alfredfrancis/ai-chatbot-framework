const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

export const getIntents = async () => {
  const response = await fetch(`${API_BASE_URL}intents/`);
  return response.json();
};

export const getIntent = async (id: string) => {
  const response = await fetch(`${API_BASE_URL}intents/${id}`);
  return response.json();
};

export const saveIntent = async (intent: any) => {
  if (intent._id) {
    return updateIntent(intent);
  } else {
    delete intent._id;
    return createIntent(intent);
  }
};

export const createIntent = async (intent: any) => {
  const response = await fetch(`${API_BASE_URL}intents/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(intent),
  });
  return response.json();
};

export const updateIntent = async (intent: any) => {
  const response = await fetch(`${API_BASE_URL}intents/${intent._id.$oid}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(intent),
  });
  return response.json();
};

export const deleteIntent = async (id: string) => {
  const response = await fetch(`${API_BASE_URL}intents/${id}`, {
    method: 'DELETE',
  });
  return response.json();
};

export const importIntents = async (fileToUpload: File) => {
  const formData = new FormData();
  formData.append('file', fileToUpload, fileToUpload.name);
  const response = await fetch(`${API_BASE_URL}intents/import`, {
    method: 'POST',
    body: formData,
  });
  return response.json();
};