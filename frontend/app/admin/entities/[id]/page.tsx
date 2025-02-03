"use client";

import React, { useState, useEffect, use, KeyboardEvent, useCallback } from 'react';
import { getEntity, saveEntity } from '../../../services/entities';
import type { EntityModel, EntityValue } from '../../../services/training';
import { useSnackbar } from '../../../components/Snackbar/SnackbarContext';
import { Popover } from 'flowbite-react';
import { QuestionMarkCircleIcon } from '@heroicons/react/24/outline';

const EntityPage = ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = use(params);
  const { addSnackbar } = useSnackbar();
  const [formData, setFormData] = useState<EntityModel>({
    name: '',
    entity_values: []
  });
  const [isLoading, setIsLoading] = useState(id !== 'new');
  const [synonymInputs, setSynonymInputs] = useState<{ [key: number]: string }>({});

  const fetchEntity = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await getEntity(id);
      // Ensure values is always an array
      setFormData({
        ...data,
        entity_values: Array.isArray(data.entity_values) ? data.entity_values : []
      });
    } catch (error) {
      console.error('Error fetching entity:', error);
      addSnackbar('Failed to load entity', 'error');
      // Initialize with empty values if there's an error
      setFormData({
        name: '',
        entity_values: []
      });
    } finally {
      setIsLoading(false);
    }
  }, [id, addSnackbar]);

  useEffect(() => {
    if (id !== 'new') {
      fetchEntity();
    }
  }, [id, fetchEntity]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await saveEntity(formData);
      addSnackbar('Entity saved successfully', 'success');
    } catch (error) {
      console.error('Error saving entity:', error);
      addSnackbar('Failed to save entity', 'error');
    }
  };

  const addValue = () => {
    setFormData(prev => ({
      ...prev,
      entity_values: [...prev.entity_values, { value: '', synonyms: [] }]
    }));
  };

  const updateValue = (index: number, field: keyof EntityValue, value: string | string[]) => {
    const newValues = [...formData.entity_values];
    newValues[index] = {
      ...newValues[index],
      [field]: value
    };
    setFormData(prev => ({
      ...prev,
      entity_values: newValues
    }));
  };

  const deleteValue = (index: number) => {
    setFormData(prev => ({
      ...prev,
      entity_values: prev.entity_values.filter((_, i) => i !== index)
    }));
    // Clean up synonym input state
    const newSynonymInputs = { ...synonymInputs };
    delete newSynonymInputs[index];
    setSynonymInputs(newSynonymInputs);
  };

  const handleSynonymInputChange = (index: number, value: string) => {
    setSynonymInputs(prev => ({
      ...prev,
      [index]: value
    }));
  };

  const handleSynonymInputKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && synonymInputs[index]?.trim()) {
      e.preventDefault();
      const newSynonym = synonymInputs[index].trim();
      if (!formData.entity_values[index].synonyms.includes(newSynonym)) {
        updateValue(index, 'synonyms', [...formData.entity_values[index].synonyms, newSynonym]);
      }
      setSynonymInputs(prev => ({
        ...prev,
        [index]: ''
      }));
    } else if (e.key === 'Backspace' && !synonymInputs[index] && formData.entity_values[index].synonyms.length > 0) {
      // Remove the last synonym when backspace is pressed on empty input
      const newSynonyms = [...formData.entity_values[index].synonyms];
      newSynonyms.pop();
      updateValue(index, 'synonyms', newSynonyms);
    }
  };

  const removeSynonym = (valueIndex: number, synonymIndex: number) => {
    const newSynonyms = [...formData.entity_values[valueIndex].synonyms];
    newSynonyms.splice(synonymIndex, 1);
    updateValue(valueIndex, 'synonyms', newSynonyms);
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-600">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-800">
          {id === 'new' ? 'Create Entity' : 'Edit Entity'}
        </h1>
        <p className="text-gray-600 mt-1">
          {id === 'new' ? 'Create a new entity for your chatbot' : 'Modify the existing entity'}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Entity Name</label>
          <input
            type="text"
            value={formData.name}
            onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
            className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-colors duration-200"
            required
          />
        </div>

        <div className="border-t border-gray-200 pt-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-medium text-gray-800">Values</h2>
              <Popover
                content={
                  <div className="max-w-sm space-y-2 p-3 bg-gray-50 rounded-lg">
                    <p>
                    Entity values and their synonyms help identify different ways users refer to the same entity.
                    </p>
                    <p className="mt-2">
                      Example:
                    </p>
                    <div className="bg-white p-3 rounded-lg border border-gray-200">
                      <p className="font-medium">Value: "credit_card"</p>
                      <p className="text-sm text-gray-600 mt-1">Synonyms:</p>
                      <ul className="list-disc pl-5 text-sm text-gray-600">
                        <li>card</li>
                        <li>credit</li>
                        <li>visa</li>
                        <li>mastercard</li>
                      </ul>
                      <p className="mt-2 text-sm text-gray-600">
                        When users mention any of these synonyms, the intent will receive "credit_card" as the entity value.
                      </p>
                    </div>
                  </div>
                }
              >
                <QuestionMarkCircleIcon className="h-5 w-5 text-gray-400 hover:text-gray-500 cursor-help" />
              </Popover>
            </div>
            <button
              type="button"
              onClick={addValue}
              className="px-4 py-2 text-sm font-medium rounded-lg text-white bg-green-500 hover:bg-green-600 transition-colors duration-200 flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              Add Value
            </button>
          </div>
          
          <div className="space-y-4">
            {formData.entity_values.map((value, index) => (
              <div key={index} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Value</label>
                    <input
                      type="text"
                      value={value.value}
                      onChange={e => updateValue(index, 'value', e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                        }
                      }}
                      className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-colors duration-200"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Synonyms</label>
                    <div className="space-y-2">
                      <div className="flex flex-wrap gap-2 min-h-[2.5rem] p-2 bg-white border border-gray-300 rounded-lg">
                        {value.synonyms.map((synonym, synonymIndex) => (
                          <span
                            key={synonymIndex}
                            className="inline-flex items-center px-2.5 py-1 rounded-full text-sm bg-green-100 text-green-800"
                          >
                            {synonym}
                            <button
                              type="button"
                              onClick={() => removeSynonym(index, synonymIndex)}
                              className="ml-1.5 text-green-600 hover:text-green-900"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </span>
                        ))}
                        <input
                          type="text"
                          value={synonymInputs[index] || ''}
                          onChange={e => handleSynonymInputChange(index, e.target.value)}
                          onKeyDown={e => handleSynonymInputKeyDown(index, e)}
                          className="flex-1 min-w-[120px] border-0 focus:ring-0 p-0 text-sm"
                          placeholder={value.synonyms.length ? "Add more synonyms..." : "Type and press Enter to add synonyms"}
                        />
                      </div>
                      <p className="text-xs text-gray-500">
                        Press Enter to add a synonym, Backspace to remove the last one
                      </p>
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    onClick={() => deleteValue(index)}
                    className="px-3 py-1.5 text-sm font-medium rounded-lg text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors duration-200"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
            {formData.entity_values.length === 0 && (
              <div className="py-8 text-center text-gray-500">
                No values added yet. Click "Add Value" to get started.
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end pt-6">
          <button
            type="submit"
            className="px-6 py-2.5 text-sm font-medium rounded-lg text-white bg-green-500 hover:bg-green-600 transition-colors duration-200"
          >
            Save Entity
          </button>
        </div>
      </form>
    </div>
  );
};

export default EntityPage;