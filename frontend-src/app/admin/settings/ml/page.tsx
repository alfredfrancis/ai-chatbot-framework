"use client";

import React, { useState, useEffect } from 'react';
import { getConfig, updateConfig, AgentConfig } from '../../../services/agents';

const MLSettingsPage: React.FC = () => {
  const [config, setConfig] = useState<AgentConfig>({
    confidence_threshold: 0.5
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const data = await getConfig();
      setConfig(data);
    } catch (error) {
      console.error('Error fetching config:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleThresholdChange = async (value: number) => {
    try {
      setConfig(prev => ({ ...prev, confidence_threshold: value }));
      await updateConfig(config);
    } catch (error) {
      console.error('Error updating config:', error);
    }
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
        <h1 className="text-2xl font-semibold text-gray-800">ML Settings</h1>
        <p className="text-gray-600 mt-1">Configure machine learning parameters for your chatbot</p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-medium text-gray-800 mb-4">Tune ML</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Intent Detection Threshold
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={config.confidence_threshold}
                    onChange={(e) => handleThresholdChange(parseFloat(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500"
                  />
                  <span className="text-sm font-medium text-gray-900 min-w-[4rem]">
                    {(config.confidence_threshold * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="mt-2 text-sm text-gray-500">
                  Adjust the confidence threshold for intent detection. Higher values mean more strict matching.
                </p>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-200 pt-6">
            <h3 className="text-sm font-medium text-gray-700 mb-2">About ML Settings</h3>
            <p className="text-sm text-gray-500">
              The confidence threshold determines how certain the model needs to be before matching an intent.
              A higher threshold means fewer false positives but might miss some valid intents.
              A lower threshold means more matches but might include some incorrect ones.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MLSettingsPage; 