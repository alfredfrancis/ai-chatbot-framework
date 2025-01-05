"use client";

import React, { useState } from 'react';
import { importIntents } from '../../../services/intents';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

const DataSettingsPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setMessage(null);
    }
  };

  const handleImport = async () => {
    if (!file) return;

    setIsLoading(true);
    setMessage(null);

    try {
      await importIntents(file);
      setMessage({ type: 'success', text: 'Intents imported successfully' });
      setFile(null);
      // Reset file input
      const fileInput = document.getElementById('file-upload') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (error) {
      console.error('Error importing intents:', error);
      setMessage({ type: 'error', text: 'Failed to import intents. Please try again.' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = () => {
    window.open(`${API_BASE_URL}intents/export`, '_blank');
  };

  return (
    <div className="p-6 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-800">Data Management</h1>
        <p className="text-gray-600 mt-1">Import and export your chatbot's training data</p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="space-y-8">
          {/* Import Section */}
          <div>
            <h2 className="text-lg font-medium text-gray-800 mb-4">Import Intents</h2>
            <div className="space-y-4">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-center">
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <div className="flex flex-col items-center">
                        <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        <span className="mt-2 text-sm text-gray-600">
                          {file ? file.name : 'Click to select a file'}
                        </span>
                      </div>
                      <input
                        id="file-upload"
                        type="file"
                        className="hidden"
                        onChange={handleFileChange}
                        accept=".json"
                      />
                    </label>
                  </div>
                  <div className="text-center">
                    <button
                      onClick={handleImport}
                      disabled={!file || isLoading}
                      className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isLoading ? 'Importing...' : 'Import Intents'}
                    </button>
                  </div>
                </div>
              </div>

              {message && (
                <div
                  className={`p-4 rounded-lg ${
                    message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                  }`}
                >
                  {message.text}
                </div>
              )}
            </div>
          </div>

          {/* Export Section */}
          <div className="border-t border-gray-200 pt-6">
            <h2 className="text-lg font-medium text-gray-800 mb-4">Export Intents</h2>
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                Download all your intents in JSON format. This file can be used to backup your data or import it into another instance.
              </p>
              <button
                onClick={handleExport}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors duration-200"
              >
                Export Intents
              </button>
            </div>
          </div>

          {/* Help Section */}
          <div className="border-t border-gray-200 pt-6">
            <h3 className="text-sm font-medium text-gray-700 mb-2">About Data Management</h3>
            <div className="text-sm text-gray-500 space-y-2">
              <p>
                The import feature accepts JSON files containing intent definitions. Make sure your file follows the correct format.
              </p>
              <p>
                Exported data includes all your intents, their training phrases, and responses. This is useful for backup purposes or when migrating to a different instance.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataSettingsPage; 