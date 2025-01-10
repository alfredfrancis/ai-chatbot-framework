import type { EntityModel } from './training';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/admin/';

export const getEntities = async (): Promise<EntityModel[]> => {
  const response = await fetch(`${API_BASE_URL}entities/`);
  return response.json();
};

export const getEntity = async (id: string): Promise<EntityModel> => {
  const response = await fetch(`${API_BASE_URL}entities/${id}`);
  return response.json();
};

export const saveEntity = async (entity: EntityModel): Promise<EntityModel> => {
  if (entity.id) {
    return updateEntity(entity);
  } else {
    delete entity.id;
    return createEntity(entity);
  }
};

export const createEntity = async (entity: EntityModel): Promise<EntityModel> => {
  const response = await fetch(`${API_BASE_URL}entities/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entity),
  });
  return response.json();
};

export const updateEntity = async (entity: EntityModel): Promise<EntityModel> => {
  const response = await fetch(`${API_BASE_URL}entities/${entity.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entity),
  });
  return response.json();
};

export const deleteEntity = async (id: string): Promise<void> => {
  await fetch(`${API_BASE_URL}entities/${id}`, {
    method: 'DELETE',
  });
}; 