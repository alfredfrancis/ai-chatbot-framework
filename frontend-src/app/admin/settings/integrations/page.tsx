"use client";

import React, { useState } from 'react';

const IntegrationsPage: React.FC = () => {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';
  const [copied, setCopied] = useState(false);

  const widgetCode = `<script type="text/javascript">
!function(win,doc){"use strict";var script_loader=()=>{try
{var head=doc.head||doc.getElementsByTagName("head")[0],script=doc.createElement("script");script.setAttribute("type","text/javascript"),script.setAttribute("src",win.iky_base_url+"assets/widget/iky_widget.js"),head.appendChild(script)}
catch(e){}};win.chat_context={"username":"John"},win.iky_base_url="${baseUrl}",script_loader()}(window,document);
</script>`;

  const handleCopy = () => {
    navigator.clipboard.writeText(widgetCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-800">Integrations</h1>
        <p className="text-gray-600 mt-1">Add your chatbot to any website</p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="space-y-6">
          {/* Chat Widget Section */}
          <div>
            <h2 className="text-lg font-medium text-gray-800 mb-4">Chat Widget</h2>
            <p className="text-sm text-gray-600 mb-4">
              Copy and paste the below snippet into your HTML code to add the chat widget to your website.
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
                  <code className="px-2 py-1 bg-gray-100 rounded text-sm font-mono text-gray-800">win.iky_base_url</code>
                  <span className="text-sm text-gray-600">
                    Replace with your installation URL in the format "ip:port/"
                  </span>
                </div>
                <div className="flex gap-2">
                  <code className="px-2 py-1 bg-gray-100 rounded text-sm font-mono text-gray-800">win.chat_context</code>
                  <span className="text-sm text-gray-600">
                    Replace with any global context you want to pass to the chat
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Preview Section */}
          <div className="border-t border-gray-200 pt-6">
            <h2 className="text-lg font-medium text-gray-800 mb-4">Preview</h2>
            <div className="bg-gray-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600">
                After adding the widget to your website, it will appear as a chat button in the bottom-right corner.
                Users can click it to open the chat interface and start interacting with your chatbot.
              </p>
            </div>
          </div>

          {/* Help Section */}
          <div className="border-t border-gray-200 pt-6">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Need Help?</h3>
            <p className="text-sm text-gray-500">
              The chat widget is designed to work with any modern website. If you need help with integration or
              encounter any issues, please check the documentation or contact support.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IntegrationsPage; 