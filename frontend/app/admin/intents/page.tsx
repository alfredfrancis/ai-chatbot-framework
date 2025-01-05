"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getIntents, deleteIntent } from '../../services/intents';
import { trainModels, IntentModel } from '../../services/training';

const IntentsPage: React.FC = () => {
  const [intents, setIntents] = useState<IntentModel[]>([]);
  const router = useRouter();

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
    if(intent._id){
      router.push(`/admin/intents/${intent._id.$oid}`);
    } 
  };

  const handleTrain = (intent: IntentModel) => {
    if(intent._id){
    router.push(`/admin/intents/${intent._id.$oid}/train`);
    }
  };

  const handleDelete = async (intent: IntentModel) => {
    if (intent._id &&  window.confirm('Are you sure you want to delete this intent?')) {
      await deleteIntent(intent._id.$oid);
      fetchIntents();
    }
  };

  const handleTrainModels = async () => {
    await trainModels();
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
            key={intent?._id?.$oid} 
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:border-green-200 transition-colors duration-200"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-800">{intent.name}</h3>
                <p className="text-gray-500 text-sm mt-1">ID: {intent.intentId}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="px-3 py-1.5 text-sm font-medium rounded-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50 transition-colors duration-200"
                  onClick={() => handleTrain(intent)}
                >
                  Train
                </button>
                <button
                  className="px-3 py-1.5 text-sm font-medium rounded-lg text-yellow-600 hover:text-yellow-700 hover:bg-yellow-50 transition-colors duration-200"
                  onClick={() => handleEdit(intent)}
                >
                  Edit
                </button>
                {intent.userDefined && (
                  <button
                    className="px-3 py-1.5 text-sm font-medium rounded-lg text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors duration-200"
                    onClick={() => handleDelete(intent)}
                  >
                    Delete
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