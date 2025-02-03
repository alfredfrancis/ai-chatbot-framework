"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { getEntities, createEntity, deleteEntity } from '../../services/entities';
import { EntityModel } from '@/app/services/training';
import { useSnackbar } from '../../components/Snackbar/SnackbarContext';

const EntitiesPage: React.FC = () => {
  const [entities, setEntities] = useState<EntityModel[]>([]);
  const [newEntityName, setNewEntityName] = useState('');
  const router = useRouter();
  const { addSnackbar } = useSnackbar();

  const fetchEntities = useCallback(async () => {
    try {
      const data = await getEntities();
      setEntities(data);
    } catch (error) {
      console.error('Error fetching entities:', error);
      addSnackbar('Failed to load entities', 'error');
    }
  }, [addSnackbar]);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  const handleNewEntity = async () => {
    if (!newEntityName.trim()) return;

    if (entities.find(x => x.name === newEntityName)) {
      addSnackbar('Entity already exists', 'error');
      return;
    }

    try {
      const result = await createEntity({ name: newEntityName, entity_values: [] });
      console.log(result)
      setEntities([...entities, result]);
      setNewEntityName('');
      addSnackbar('Entity created successfully', 'success');
    } catch (error) {
      console.error('Error creating entity:', error);
      addSnackbar('Failed to create entity', 'error');
    }
  };

  const handleEdit = (entity: EntityModel) => {
    router.push(`/admin/entities/${entity?.id}`);
  };

  const handleDelete = async (id: string, index: number) => {
    if (window.confirm('Are you sure you want to delete this entity?')) {
      try {
        await deleteEntity(id);
        const newEntities = [...entities];
        newEntities.splice(index, 1);
        setEntities(newEntities);
        addSnackbar('Entity deleted successfully', 'success');
      } catch (error) {
        console.error('Error deleting entity:', error);
        addSnackbar('Failed to delete entity', 'error');
      }
    }
  };

  return (
    <div className="p-6 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-800">Entities</h1>
        <p className="text-gray-600 mt-1">Manage your chatbot's entities and their values</p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex gap-3 mb-6">
          <div className="flex-1">
            <input
              type="text"
              value={newEntityName}
              onChange={(e) => setNewEntityName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') {handleNewEntity();}}}
              placeholder="Enter entity name"
              className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-colors duration-200"
              required
            />
          </div>
          <button
            onClick={handleNewEntity}
            className="px-6 py-2.5 text-sm font-medium rounded-lg text-white bg-green-500 hover:bg-green-600 transition-colors duration-200 flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Add Entity
          </button>
        </div>

        <div className="divide-y divide-gray-200">
          {entities.map((entity, index) => (
            <div 
              key={entity?.id}
              className="py-4 flex items-center justify-between group"
            >
              <div className="flex-1">
                <h3 className="text-lg font-medium text-gray-800">{entity.name}</h3>
              </div>
              <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                <button
                  onClick={() => handleEdit(entity)}
                  className="px-3 py-1.5 text-sm font-medium rounded-lg text-yellow-600 hover:text-yellow-700 hover:bg-yellow-50 transition-colors duration-200"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(entity?.id || "", index)}
                  className="px-3 py-1.5 text-sm font-medium rounded-lg text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors duration-200"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
          {entities.length === 0 && (
            <div className="py-8 text-center text-gray-500">
              No entities found. Create one to get started.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EntitiesPage;