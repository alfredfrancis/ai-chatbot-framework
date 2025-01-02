const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

export const getEntities = async () => {
  const response = await fetch(`${API_BASE_URL}entities/`);
  return response.json();
};

export const getEntity = async (id: string) => {
  const response = await fetch(`${API_BASE_URL}entities/${id}`);
  return response.json();
};

export const saveEntity = async (entity: any) => {
  if (entity._id) {
    return updateEntity(entity);
  } else {
    delete entity._id;
    return createEntity(entity);
  }
};

export const createEntity = async (entity: any) => {
  const response = await fetch(`${API_BASE_URL}entities/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entity),
  });
  return response.json();
};

export const updateEntity = async (entity: any) => {
  const response = await fetch(`${API_BASE_URL}entities/${entity._id.$oid}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entity),
  });
  return response.json();
};

export const deleteEntity = async (id: string) => {
  const response = await fetch(`${API_BASE_URL}entities/${id}`, {
    method: 'DELETE',
  });
  return response.json();
}; 