"use client";

import React, { useState } from 'react';
import ChatWidget from './ChatWidget';
import FacebookMessenger from './FacebookMessenger';
import IntegrationTile from './IntegrationTile';

const IntegrationsPage: React.FC = () => {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(null);

  const integrations = [
    {
      id: 'chat-widget',
      name: 'Chat Widget',
      description: 'Add a chat widget to your website',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      ),
      status: 'Active'
    },
    {
      id: 'facebook',
      name: 'Facebook Messenger',
      description: 'Connect with Facebook Messenger',
      icon: (
        <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 2C6.477 2 2 6.145 2 11.243c0 2.936 1.444 5.564 3.741 7.288v3.769l3.424-1.883c.902.251 1.858.386 2.835.386 5.523 0 10-4.145 10-9.243S17.523 2 12 2zm1.193 12.333l-2.558-2.558-4.686 2.558 5.157-5.157 2.558 2.558 4.686-2.558-5.157 5.157z" />
        </svg>
      ),
      status: 'Inactive'
    }
  ];

  const renderIntegrationConfig = (integrationId: string) => {
    switch (integrationId) {
      case 'chat-widget':
        return <ChatWidget baseUrl={baseUrl} />;
      case 'facebook':
        return <FacebookMessenger baseUrl={baseUrl} />;
      default:
        return null;
    }
  };

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
              onClick={() => setSelectedIntegration(integration.id)}
            />
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setSelectedIntegration(null)}
                className="text-gray-600 hover:text-gray-800"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </button>
              <h2 className="text-xl font-medium text-gray-800">
                {integrations.find(i => i.id === selectedIntegration)?.name}
              </h2>
            </div>
          </div>
          {renderIntegrationConfig(selectedIntegration)}
        </div>
      )}
    </div>
  );
};

export default IntegrationsPage; 