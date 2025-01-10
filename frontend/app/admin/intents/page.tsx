"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getIntents, deleteIntent } from '../../services/intents';
import { trainModels, IntentModel } from '../../services/training';
import { BoltIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';
import { useSnackbar } from '../../components/Snackbar/SnackbarContext';

const IntentsPage: React.FC = () => {
  const [intents, setIntents] = useState<IntentModel[]>([]);
  const router = useRouter();
  const { addSnackbar } = useSnackbar();

  useEffect(() => {
    fetchIntents();
  }, []);

  const fetchIntents = async () => {
    const data = await getIntents();
    setIntents(data);
  };

  const handleAdd = () => {
    router.push('/admin/intents/create');
  };

  const handleEdit = (intent: IntentModel) => {
    if(intent.id){
      router.push(`/admin/intents/${intent.id}`);
    } 
  };

  const handleTrain = (intent: IntentModel) => {
    if(intent.id){
    router.push(`/admin/intents/${intent.id}/train`);
    }
  };

  const handleDelete = async (intent: IntentModel) => {
    if (intent.id && window.confirm('Are you sure you want to delete this intent?')) {
      try {
        await deleteIntent(intent.id);
        addSnackbar('Intent deleted successfully', 'success');
        fetchIntents();
      } catch (error) {
        console.error('Error deleting intent:', error);
        addSnackbar('Failed to delete intent', 'error');
      }
    }
  };

  const handleTrainModels = async () => {
    try {
      await trainModels();
      addSnackbar('Training completed successfully', 'success');
    } catch (error) {
      console.error('Training failed:', error);
      addSnackbar('Training failed', 'error');
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Intents</h1>
          <p className="text-gray-600 mt-1">Manage your chatbot's intents and responses</p>
        </div>
        <div className="flex gap-3">
          <button
            className="px-4 py-2 text-sm font-medium rounded-lg text-white bg-blue-500 hover:bg-blue-600 transition-colors duration-200 flex items-center gap-2"
            onClick={handleTrainModels}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Train Models
          </button>
          <button
            className="px-4 py-2 text-sm font-medium rounded-lg text-white bg-green-500 hover:bg-green-600 transition-colors duration-200 flex items-center gap-2"
            onClick={handleAdd}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Add Intent
          </button>
        </div>
      </div>

      <div className="grid gap-4">
        {intents.map((intent) => (
          <div 
            key={intent?.id} 
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:border-green-200 transition-colors duration-200 group"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-800">{intent.name}</h3>
                <p className="text-gray-500 text-sm mt-1">ID: {intent.intentId}</p>
              </div>
              <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                <button
                  className="p-2 rounded-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50 transition-colors duration-200 group/btn relative"
                  onClick={() => handleTrain(intent)}
                >
                  <BoltIcon className="w-5 h-5" />
                  <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white px-2 py-1 rounded text-xs whitespace-nowrap opacity-0 group-hover/btn:opacity-100 transition-opacity duration-200">
                    Train Intent
                  </span>
                </button>
                <button
                  className="p-2 rounded-lg text-yellow-600 hover:text-yellow-700 hover:bg-yellow-50 transition-colors duration-200 group/btn relative"
                  onClick={() => handleEdit(intent)}
                >
                  <PencilSquareIcon className="w-5 h-5" />
                  <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white px-2 py-1 rounded text-xs whitespace-nowrap opacity-0 group-hover/btn:opacity-100 transition-opacity duration-200">
                    Edit Intent
                  </span>
                </button>
                {intent.userDefined && (
                  <button
                    className="p-2 rounded-lg text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors duration-200 group/btn relative"
                    onClick={() => handleDelete(intent)}
                  >
                    <TrashIcon className="w-5 h-5" />
                    <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white px-2 py-1 rounded text-xs whitespace-nowrap opacity-0 group-hover/btn:opacity-100 transition-opacity duration-200">
                      Delete Intent
                    </span>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default IntentsPage;