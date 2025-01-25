import React, { useState, useEffect } from 'react';
import { Accordion, ToggleSwitch } from "flowbite-react";
import { updateIntegration, getIntegration,  FacebookSettings, IntegrationDetails } from '@/app/services/integrations';



interface FacebookMessengerProps {
  integration: IntegrationDetails<FacebookSettings>;
  onUpdate?: (integration: IntegrationDetails<FacebookSettings>) => void;
}

const FacebookMessenger: React.FC<FacebookMessengerProps> = ({ integration, onUpdate }) => {
  const [isEnabled, setIsEnabled] = useState(integration.status);
  const [copied, setCopied] = useState(false);
  const [formData, setFormData] = useState({
    verify: integration.settings.verify || "ai-chatbot-framework",
    secret: integration.settings.secret || "",
    pageAccessToken: integration.settings.page_access_token || ""
  });

  // fetch the integration from the API
  useEffect(() => {
    const fetchIntegration = async () => {
      try {
        const fetchedIntegration = await getIntegration<FacebookSettings>(integration.id);
        setIsEnabled(fetchedIntegration.status);
        setFormData({
          verify: fetchedIntegration.settings.verify || "ai-chatbot-framework",
          secret: fetchedIntegration.settings.secret || "",
          pageAccessToken: fetchedIntegration.settings.page_access_token || ""
        });
      } catch (error) {
        console.error('Failed to fetch integration:', error);
      }
    };
    fetchIntegration();
  }, [integration.id]);

  const handleCopy = () => {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';
    navigator.clipboard.writeText(`${baseUrl}/bots/channels/facebook/webhook`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    try {
      const updatedIntegration = await updateIntegration<FacebookSettings>(integration.id, {
        ...integration,
        settings: {
          ...integration.settings,
          [name === 'pageAccessToken' ? 'page_access_token' : name]: value
        }
      });
      onUpdate?.(updatedIntegration);
    } catch (error) {
      console.error('Failed to update integration:', error);
    }
  };

  const handleToggle = async (checked: boolean) => {
    try {
      setIsEnabled(checked);
      const updatedIntegration = await updateIntegration(integration.id, {
        ...integration,
        status: checked,
        settings: {
          verify: formData.verify,
          secret: formData.secret,
          page_access_token: formData.pageAccessToken
        }
      });
      onUpdate?.(updatedIntegration);
    } catch (error) {
      console.error('Failed to update integration:', error);
      setIsEnabled(!checked); // Revert on error
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700">Facebook Page</h3>
          <ToggleSwitch
            checked={isEnabled}
            onChange={handleToggle}
            label={isEnabled ? 'Enabled' : 'Disabled'}
          />
        </div>
        <p className="text-sm text-gray-600">
          Connect your Facebook page to start receiving messages from Facebook Messenger.
        </p>
        <div className="bg-gray-50 p-4 rounded-lg">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Verify Token</label>
              <input
                type="text"
                name="verify"
                value={formData.verify}
                onChange={handleInputChange}
                placeholder="Enter your verify token"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">App Secret</label>
              <input
                type="password"
                name="secret"
                value={formData.secret}
                onChange={handleInputChange}
                placeholder="Enter your app secret"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Page Access Token</label>
              <input
                type="password"
                name="pageAccessToken"
                value={formData.pageAccessToken}
                onChange={handleInputChange}
                placeholder="Enter your page access token"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  type="text"
                  value={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}/bots/channels/facebook/webhook`}
                  readOnly
                  className="flex-1 block w-full px-3 py-2 rounded-l-md border border-r-0 border-gray-300 bg-gray-50"
                />
                <button 
                  onClick={handleCopy}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-r-md bg-gray-50 text-gray-500 hover:text-gray-700"
                >
                  {copied ? (
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                      </svg>
                      Copied
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                      </svg>
                      Copy
                    </span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Help Section */}
        <Accordion collapseAll>
          <Accordion.Panel>
            <Accordion.Title className="text-blue-800 bg-blue-50 hover:bg-blue-100">
              How to get Facebook credentials
            </Accordion.Title>
            <Accordion.Content className="text-blue-700 bg-blue-50">
              <div className="space-y-3">
                <div>
                  <p className="font-medium">Step 1: Create a Facebook App</p>
                  <ul className="list-disc pl-5 space-y-1">
                    <li>Go to Facebook for Developers</li>
                    <li>Click on "My Apps" → "Add New App"</li>
                  </ul>
                </div>

                <div>
                  <p className="font-medium">Step 2: Set up Messenger</p>
                  <ul className="list-disc pl-5 space-y-1">
                    <li>In the app dashboard, find "Products" section</li>
                    <li>Locate Messenger and click "Set Up"</li>
                    <li>Scroll to "Token Generation"</li>
                    <li>Create a new page or select existing one</li>
                    <li>Copy the generated Page Access Token</li>
                  </ul>
                </div>

                <div>
                  <p className="font-medium">Step 3: Get App Secret</p>
                  <ul className="list-disc pl-5 space-y-1">
                    <li>In app dashboard, go to "Settings" → "Basic"</li>
                    <li>Find and copy the App Secret</li>
                  </ul>
                </div>

                <div>
                  <p className="font-medium">Step 4: Configure Webhook</p>
                  <ul className="list-disc pl-5 space-y-1">
                    <li>Set up a Webhook in your Facebook app</li>
                    <li>Select "messaging" and "messaging_postback" subscriptions</li>
                    <li>Use the Webhook URL provided above</li>
                    <li>Use the Verify Token configured above when configuring the webhook</li>
                  </ul>
                </div>
              </div>
            </Accordion.Content>
          </Accordion.Panel>
        </Accordion>
      </div>
    </div>
  );
};

export default FacebookMessenger;