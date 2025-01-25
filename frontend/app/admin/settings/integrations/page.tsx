"use client";

import React, { useEffect, useState } from 'react';
import { listIntegrations, type Integration, type FacebookSettings, type WebSettings, IntegrationDetails } from '@/app/services/integrations';
import { ArrowLeftIcon, ChatBubbleLeftRightIcon } from "@heroicons/react/24/outline";
import ChatWidget from './ChatWidget';
import FacebookMessenger from './FacebookMessenger';
import IntegrationTile from './IntegrationTile';

const IntegrationsPage: React.FC = () => {
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(null);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIntegrations = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await listIntegrations();
        setIntegrations(data);
      } catch (error) {
        console.error('Failed to fetch integrations:', error);
        setError('Failed to load integrations. Please try again later.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchIntegrations();
  }, []);

  const integrations_icons: Record<string, React.ReactNode> = {
    'chat_widget': <ChatBubbleLeftRightIcon className="w-8 h-8" />,
    'facebook': <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 2C6.477 2 2 6.145 2 11.243c0 2.936 1.444 5.564 3.741 7.288v3.769l3.424-1.883c.902.251 1.858.386 2.835.386 5.523 0 10-4.145 10-9.243S17.523 2 12 2zm1.193 12.333l-2.558-2.558-4.686 2.558 5.157-5.157 2.558 2.558 4.686-2.558-5.157 5.157z" />
    </svg>
  };

  const handleIntegrationUpdate = (updatedIntegration: Integration) => {
    setIntegrations(prevIntegrations => 
      prevIntegrations.map(integration => 
        integration.id === updatedIntegration.id ? updatedIntegration : integration
      )
    );
  };

  const renderIntegrationConfig = (integration: Integration) => {
    switch (integration.id) {
      case 'chat_widget':
        return <ChatWidget 
          integration={integration as IntegrationDetails<WebSettings>} 
          onUpdate={handleIntegrationUpdate} 
        />;
      case 'facebook':
        return <FacebookMessenger 
          integration={integration as IntegrationDetails<FacebookSettings>}
          onUpdate={handleIntegrationUpdate} 
        />;
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2].map((i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
          <strong className="font-bold">Error: </strong>
          <span className="block sm:inline">{error}</span>
        </div>
      </div>
    );
  }

  const selectedIntegrationData = integrations.find(i => i.id === selectedIntegration);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-800">Integrations</h1>
        <p className="text-gray-600 mt-1">Connect your chatbot with various platforms</p>
      </div>

      {!selectedIntegration ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {integrations.map((integration) => (
            <IntegrationTile
              key={integration.id}
              {...integration}
              icon={integrations_icons[integration.id]}
              onClick={() => setSelectedIntegration(integration.id)}
            />
          ))}
        </div>
      ) : selectedIntegrationData ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setSelectedIntegration(null)}
                className="text-gray-600 hover:text-gray-800"
              >
                <ArrowLeftIcon className="w-6 h-6" />
              </button>
              <h2 className="text-xl font-medium text-gray-800">
                {selectedIntegrationData.name}
              </h2>
            </div>
          </div>
          {renderIntegrationConfig(selectedIntegrationData)}
        </div>
      ) : null}
    </div>
  );
};

export default IntegrationsPage;