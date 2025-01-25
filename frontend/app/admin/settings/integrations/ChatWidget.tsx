import React, { useState } from 'react';
import { updateIntegration,  WebSettings, IntegrationDetails } from '@/app/services/integrations';

import { ToggleSwitch } from "flowbite-react";

interface ChatWidgetProps {
  integration: IntegrationDetails<WebSettings>;
  onUpdate?: (integration: IntegrationDetails<WebSettings>) => void;
}

const ChatWidget: React.FC<ChatWidgetProps> = ({ integration, onUpdate }) => {
  const [isEnabled, setIsEnabled] = useState(integration.status);
  const [copied, setCopied] = useState(false);

  const widgetCode = `<script type="text/javascript">
!function(win,doc){"use strict";var script_loader=()=>{try
{var head=doc.head||doc.getElementsByTagName("head")[0],script=doc.createElement("script");script.setAttribute("type","text/javascript"),script.setAttribute("src","https://alfredfrancis.in/ai-chatbot-framework/app/static/widget/script.js"),head.appendChild(script)}
catch(e){}};win.chat_context={"username":"John"},win.iky_base_url="${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}",script_loader()}(window,document);
</script>`;

  const handleCopy = () => {
    navigator.clipboard.writeText(widgetCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleToggle = async (checked: boolean) => {
    try {
      setIsEnabled(checked);
      const updatedIntegration = await updateIntegration(integration.id, {
        ...integration,
        status: checked
      });
      onUpdate?.(updatedIntegration);
    } catch (error) {
      console.error('Failed to update integration:', error);
      setIsEnabled(!checked); // Revert on error
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <div></div>
        <ToggleSwitch
          checked={isEnabled}
          onChange={handleToggle}
          label={isEnabled ? 'Enabled' : 'Disabled'}
        />
      </div>
      <p className="text-sm text-gray-600 mb-4">
        Copy and paste the below snippet into your HTML code (below body tag) to add the chat widget to your website.
      </p>

      <div className="relative">
        <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto text-sm font-mono text-gray-800 whitespace-pre-wrap break-all">
          {widgetCode}
        </pre>
        <button 
          onClick={handleCopy}
          className="absolute top-2 right-2 px-3 py-1.5 text-sm font-medium rounded-lg text-gray-600 hover:text-gray-700 hover:bg-gray-100 transition-colors duration-200"
        >
          {copied ? (
            <span className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
              Copied!
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

      <div className="mt-6 space-y-4">
        <h3 className="text-sm font-medium text-gray-700">Configuration</h3>
        <div className="space-y-2">
          <div className="flex gap-2">
            <code className="px-2 py-1 bg-gray-100 rounded text-sm font-mono text-gray-800">iky_base_url</code>
            <span className="text-sm text-gray-600">
              Replace with ai chatbot frame work hostname
            </span>
          </div>
          <div className="flex gap-2">
            <code className="px-2 py-1 bg-gray-100 rounded text-sm font-mono text-gray-800">chat_context</code>
            <span className="text-sm text-gray-600">
              Add any context you want to pass to the chat such as username, email, etc.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatWidget; 