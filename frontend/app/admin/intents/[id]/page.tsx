"use client";

import React, { useState, useEffect, use, useCallback } from 'react';
import { getIntent, saveIntent } from '../../../services/intents';
import { getEntities } from '../../../services/entities';
import { Popover } from 'flowbite-react';
import { QuestionMarkCircleIcon, TrashIcon } from '@heroicons/react/24/outline';
import type { EntityModel, IntentModel } from '../../../services/training';
import { useSnackbar } from '../../../components/Snackbar/SnackbarContext';

const IntentPage = ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = use(params);
  const { addSnackbar } = useSnackbar();
  const defaultPrameterTypes = ['free_text'];

  const [formData, setFormData] = useState<IntentModel>({
    name: '',
    intentId: '',
    userDefined: true,
    speechResponse: '',
    apiTrigger: false,
    parameters: [],
  });
  const [entities, setEntities] = useState<EntityModel[]>([]);

  const fetchIntent = useCallback(async () => {
    const data = await getIntent(id);
    setFormData(data);
  }, [id]);

  const fetchEntities = useCallback(async () => {
    const data = await getEntities();
    setEntities(data);
  }, []);

  useEffect(() => {
    if (id !== 'new') {
      fetchIntent();
    }
    fetchEntities();
  }, [id, fetchIntent, fetchEntities]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await saveIntent(formData);
      addSnackbar('Intent saved successfully', 'success');
    } catch (error) {
      console.error('Error saving intent:', error);
      addSnackbar('Failed to save intent', 'error');
    }
  };

  const addParameter = () => {
    setFormData(prev => ({
      ...prev,
      parameters: [...prev.parameters, {
        name: '',
        type: 'free_text',
        required: false,
        prompt: ''
      }]
    }));
  };

  const updateParameter = (index: number, field: string, value: string | boolean) => {
    const newParameters = [...formData.parameters];
    newParameters[index] = {
      ...newParameters[index],
      [field]: value
    };
    setFormData(prev => ({
      ...prev,
      parameters: newParameters
    }));
  };

  const deleteParameter = (index: number) => {
    setFormData(prev => ({
      ...prev,
      parameters: prev.parameters.filter((_, i) => i !== index)
    }));
  };

  const addHeader = () => {
    if (!formData.apiDetails) {
      setFormData(prev => ({
        ...prev,
        apiDetails: {
          isJson: false,
          url: '',
          headers: [],
          requestType: 'GET',
          jsonData: ''
        }
      }));
    }
    setFormData(prev => ({
      ...prev,
      apiDetails: {
        ...prev.apiDetails!,
        headers: [...(prev.apiDetails?.headers || []), { headerKey: '', headerValue: '' }]
      }
    }));
  };

  const updateHeader = (index: number, field: 'headerKey' | 'headerValue', value: string) => {
    const newHeaders = [...(formData.apiDetails?.headers || [])];
    newHeaders[index] = {
      ...newHeaders[index],
      [field]: value
    };
    setFormData(prev => ({
      ...prev,
      apiDetails: {
        ...prev.apiDetails!,
        headers: newHeaders
      }
    }));
  };

  const deleteHeader = (index: number) => {
    setFormData(prev => ({
      ...prev,
      apiDetails: {
        ...prev.apiDetails!,
        headers: prev.apiDetails!.headers.filter((_, i) => i !== index)
      }
    }));
  };

  const handleApiTriggerChange = (checked: boolean) => {
    if (checked && !formData.apiDetails) {
      setFormData(prev => ({
        ...prev,
        apiTrigger: checked,
        apiDetails: {
          isJson: false,
          url: '',
          headers: [],
          requestType: 'GET',
          jsonData: ''
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        apiTrigger: checked
      }));
    }
  };

  return (
    <div className="p-6 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-800">
          {id === 'new' ? 'Create Intent' : 'Edit Intent'}
        </h1>
        <p className="text-gray-600 mt-1">
          {id === 'new' ? 'Create a new intent for your chatbot' : 'Modify the existing intent'}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Intent Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-colors duration-200"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Intent ID</label>
            <input
              type="text"
              value={formData.intentId}
              onChange={e => setFormData(prev => ({ ...prev, intentId: e.target.value }))}
              className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-colors duration-200"
              required
            />
          </div>
        </div>

        <div className="relative border-t border-gray-200 pt-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-medium text-gray-800">Parameters</h2>
              <Popover
                content={
                  <div className="max-w-sm p-3">
                    <p>Use ### to split your prompt into multiple lines. Each line will be asked separately in sequence.</p>
                    <p>Example:</p>
                    <pre className="bg-white p-2 rounded text-sm">{"What is your name?###Where do you live?###How old are you?"}</pre>
                  </div>
                }
              >
                <QuestionMarkCircleIcon className="h-5 w-5 text-gray-400 hover:text-gray-500 cursor-help" />
              </Popover>
            </div>
            <button
              type="button"
              onClick={addParameter}
              className="px-4 py-2.5 text-sm font-medium rounded-lg text-white bg-green-500 hover:bg-green-600 transition-colors duration-200"
            >
              Add Parameter
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[20%]">Name</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[20%]">Type</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[10%]">Required</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[45%]">Prompt</th>
                  <th scope="col" className="relative px-6 py-3 w-[5%]"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {formData.parameters.map((param, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="text"
                        value={param.name}
                        onChange={e => updateParameter(index, 'name', e.target.value)}
                        className="w-full p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                        required
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <select
                        value={param.type}
                        onChange={e => updateParameter(index, 'type', e.target.value)}
                        className="w-full p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                      >
                        <optgroup label="Default">
                          {defaultPrameterTypes.map(type => (
                            <option key={type} value={type}>{type}</option>
                          ))}
                        </optgroup>
                        <optgroup label="Entities">
                          {entities.map(entity => (
                            <option key={entity?.id} value={entity.name}>{entity.name}</option>
                          ))}
                        </optgroup>
                      </select>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={param.required}
                        onChange={e => updateParameter(index, 'required', e.target.checked)}
                        className="rounded border-gray-300 text-green-500 focus:ring-green-200"
                      />
                    </td>
                    <td className="px-6 py-4">
                      {param.required && (
                        <div className="flex flex-col">
                          <input
                            type="text"
                            value={param.prompt}
                            onChange={e => updateParameter(index, 'prompt', e.target.value)}
                            className="w-full p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                            required = {param.required}
                          />
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        type="button"
                        onClick={() => deleteParameter(index)}
                        className="text-red-600 hover:text-red-900 p-1 rounded-full hover:bg-red-50"
                      >
                        <TrashIcon className="w-5 h-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="relative border-t border-gray-200 pt-8 transition-all duration-200 hover:bg-gray-50 rounded-lg p-4 -mx-4">
          <label className="flex items-center mb-4">
            <input
              type="checkbox"
              checked={formData.apiTrigger}
              onChange={e => handleApiTriggerChange(e.target.checked)}
              className="rounded border-gray-300 text-green-500 focus:ring-green-200 mr-2"
            />
            <span className="text-sm font-medium text-gray-700">REST API Calling</span>
          </label>

          {formData.apiTrigger && (
            <div className="space-y-6 bg-white rounded-lg p-6 border border-gray-200">
              <div className="grid gap-4 md:grid-cols-6">
                <div className="md:col-span-5">
                  <label className="block text-sm font-medium text-gray-700 mb-2">API URL</label>
                  <input
                    type="text"
                    value={formData.apiDetails?.url}
                    onChange={e => setFormData(prev => ({
                      ...prev,
                      apiDetails: {
                        ...prev.apiDetails!,
                        url: e.target.value
                      }
                    }))}
                    className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                    required={formData.apiTrigger}
                  />
                </div>

                <div className="md:col-span-1">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Method</label>
                  <select
                    value={formData.apiDetails?.requestType}
                    onChange={e => setFormData(prev => ({
                      ...prev,
                      apiDetails: {
                        ...prev.apiDetails!,
                        requestType: e.target.value
                      }
                    }))}
                    className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                    required={formData.apiTrigger}
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-4">
                  <label className="text-sm font-medium text-gray-700">Headers</label>
                  <button
                    type="button"
                    onClick={addHeader}
                    className="text-blue-600 hover:text-blue-700"
                  >
                    Add Header
                  </button>
                </div>
                <div className="space-y-2">
                  {formData.apiDetails?.headers.map((header, index) => (
                    <div key={index} className="grid grid-cols-5 gap-2">
                      <div className="col-span-2">
                        <input
                          type="text"
                          value={header.headerKey}
                          onChange={e => updateHeader(index, 'headerKey', e.target.value)}
                          placeholder="Key"
                          className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                        />
                      </div>
                      <div className="col-span-2">
                        <input
                          type="text"
                          value={header.headerValue}
                          onChange={e => updateHeader(index, 'headerValue', e.target.value)}
                          placeholder="Value"
                          className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                        />
                      </div>
                      <div>
                        <button
                          type="button"
                          onClick={() => deleteHeader(index)}
                          className="text-red-600 hover:text-red-700 p-2"
                        >
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="flex items-center mb-4">
                  <input
                    type="checkbox"
                    checked={formData.apiDetails?.isJson}
                    onChange={e => setFormData(prev => ({
                      ...prev,
                      apiDetails: {
                        ...prev.apiDetails!,
                        isJson: e.target.checked
                      }
                    }))}
                    className="rounded border-gray-300 text-green-500 focus:ring-green-200 mr-2"
                  />
                  <span className="text-sm font-medium text-gray-700">JSON Payload</span>
                </label>
              </div>

              {formData.apiDetails?.isJson && (
                <div>
                  <div  className="flex items-center gap-2 mb-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">JSON Data</label>
                    <Popover
                      content={
                        <div className="max-w-sm p-3">
                          <div className="mb-4 text-sm text-gray-600">
                            Extracted parameters can be used to build your JSON. Example:
                            <pre className="bg-white p-3 mt-2 rounded-lg border border-gray-200">
                              {`{ "order_id": "{{parameters.order_id}}" }`}
                            </pre>
                          </div>
                        </div>
                      }
                    >
                      <QuestionMarkCircleIcon className="h-5 w-5 text-gray-400 hover:text-gray-500 cursor-help" />
                    </Popover>
                  </div>
                  <textarea
                    value={formData.apiDetails.jsonData}
                    onChange={e => setFormData(prev => ({
                      ...prev,
                      apiDetails: {
                        ...prev.apiDetails!,
                        jsonData: e.target.value
                      }
                    }))}
                    className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
                    rows={8}
                    required={formData.apiDetails.isJson}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        <div className="relative border-t border-gray-200 pt-8 transition-all duration-200 hover:bg-gray-50 rounded-lg p-4 -mx-4">
          <div className="flex items-center gap-2 mb-2">
            <label className="block text-sm font-medium text-gray-700">Speech Response</label>
            <Popover
              content={
                <div className="max-w-sm p-3">
                  <p>
                    You can use Jinja templating to create dynamic responses:
                  </p>
                  <ul className="list-disc pl-5 space-y-1">
                    <li>Use ### to split your response into multiple lines.</li>
                    <li>Access parameters with <code className="bg-gray-100 px-1 rounded">{"{{ parameters['param_name'] }}"}</code></li>
                    <li>Access API response with <code className="bg-gray-100 px-1 rounded">{"{{ result['field_name'] }}"}</code></li>
                  </ul>
                  <p>Example:</p>
                  <pre className="bg-white p-2 rounded text-sm">
                    {"Hello {{ parameters['name'] }}! ### The weather in {{ parameters['city'] }} is {{ result['temperature'] }}°C"}
                  </pre>
                </div>
              }
            >
              <QuestionMarkCircleIcon className="h-5 w-5 text-gray-400 hover:text-gray-500 cursor-help" />
            </Popover>
          </div>
          <textarea
            value={formData.speechResponse}
            onChange={e => setFormData(prev => ({ ...prev, speechResponse: e.target.value }))}
            className="w-full p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
            rows={5}
            required
          />
        </div>

        <div className="flex justify-end pt-6">
          <button
            type="submit"
            className="px-6 py-2.5 text-sm font-medium rounded-lg text-white bg-green-500 hover:bg-green-600 transition-colors duration-200"
          >
            Save Intent
          </button>
        </div>
      </form>
    </div>
  );
};

export default IntentPage;