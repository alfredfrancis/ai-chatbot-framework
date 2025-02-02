"use client";

import React, { useState, useEffect } from 'react';
import { getConfig, updateConfig,NLUConfig } from '../../../services/agents';

const MLSettingsPage: React.FC = () => {
  const [config, setConfig] = useState<NLUConfig | null>(null);
  const [localConfig, setLocalConfig] = useState<NLUConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const data = await getConfig();
      setConfig(data);
      setLocalConfig(data);
    } catch (error) {
      console.error('Error fetching config:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLocalConfigUpdate = (newConfig: NLUConfig) => {
    setLocalConfig(newConfig);
  };

  const handleSave = async () => {
    if (!localConfig) return;
    
    setIsSaving(true);
    try {
      await updateConfig(localConfig);
      setConfig(localConfig);
    } catch (error) {
      console.error('Error updating config:', error);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading || !config) {
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
        <h1 className="text-2xl font-semibold text-gray-800">ML Settings</h1>
        <p className="text-gray-600 mt-1">Configure machine learning parameters for your chatbot</p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 space-y-6">
        <div className="border-b border-gray-200 pb-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                NLU Pipeline Type
              </label>
              <p className="text-sm text-gray-500 mb-4">
                Choose how your chatbot processes and understands user messages. Select between a traditional machine learning approach or a modern large language model.
              </p>
              <select
                value={localConfig?.pipeline_type}
                onChange={(e) => handleLocalConfigUpdate({
                  ...localConfig!,
                  pipeline_type: e.target.value as 'traditional' | 'llm'
                })}
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm rounded-md"
              >
                <option value="traditional">Default NLU Pipeline (Manual Training Required)</option>
                <option value="llm">Large Language Model (Zero-shot Learning)</option>
              </select>
            </div>
          </div>
        </div>

        {localConfig?.pipeline_type === 'traditional' && (
          <div className="border-b border-gray-200 pb-6">
            <h2 className="text-lg font-medium text-gray-800 mb-4">Default NLU Pipeline Settings</h2>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Intent Detection Threshold
                </label>
                <p className="text-sm text-gray-500 mb-4">
                  Set the minimum confidence level required to match a user message to an intent. A higher threshold means more accurate but potentially fewer matches.
                </p>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={localConfig?.traditional_settings.intent_detection_threshold}
                    onChange={(e) => handleLocalConfigUpdate({
                      ...localConfig!,
                      traditional_settings: {
                        ...localConfig!.traditional_settings,
                        intent_detection_threshold: parseFloat(e.target.value)
                      }
                    })}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500"
                  />
                  <span className="text-sm font-medium text-gray-900 min-w-[4rem]">
                    {(localConfig?.traditional_settings.intent_detection_threshold * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {localConfig?.pipeline_type === 'llm' && (
          <div>
            <h2 className="text-lg font-medium text-gray-800 mb-4">LLM Settings</h2>
            <p className="text-sm text-gray-500 mb-4">
              Configure any OpenAI-compactible API endpoints including Deepseek, Gemini, GPT4ALL API, etc.
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Base URL
                </label>
                <input
                  type="text"
                  value={localConfig?.llm_settings.base_url}
                  onChange={(e) => handleLocalConfigUpdate({
                    ...localConfig!,
                    llm_settings: {
                      ...localConfig!.llm_settings,
                      base_url: e.target.value
                    }
                  })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-green-500 focus:border-green-500 sm:text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  API Token
                </label>
                <input
                  type="password"
                  value={localConfig?.llm_settings.api_key}
                  onChange={(e) => handleLocalConfigUpdate({
                    ...localConfig!,
                    llm_settings: {
                      ...localConfig!.llm_settings,
                      api_key: e.target.value
                    }
                  })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-green-500 focus:border-green-500 sm:text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Model Name
                </label>
                <input
                  type="text"
                  value={localConfig?.llm_settings.model_name}
                  onChange={(e) => handleLocalConfigUpdate({
                    ...localConfig!,
                    llm_settings: {
                      ...localConfig!.llm_settings,
                      model_name: e.target.value
                    }
                  })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-green-500 focus:border-green-500 sm:text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Tokens
                </label>
                <input
                  type="number"
                  value={localConfig?.llm_settings.max_tokens}
                  onChange={(e) => handleLocalConfigUpdate({
                    ...localConfig!,
                    llm_settings: {
                      ...localConfig!.llm_settings,
                      max_tokens: parseInt(e.target.value)
                    }
                  })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-green-500 focus:border-green-500 sm:text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Temperature
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={localConfig?.llm_settings.temperature}
                    onChange={(e) => handleLocalConfigUpdate({
                      ...localConfig!,
                      llm_settings: {
                        ...localConfig!.llm_settings,
                        temperature: parseFloat(e.target.value)
                      }
                    })}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500"
                  />
                  <span className="text-sm font-medium text-gray-900 min-w-[4rem]">
                    {localConfig?.llm_settings.temperature.toFixed(1)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Save Button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors duration-200 disabled:opacity-50"
          >
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MLSettingsPage;