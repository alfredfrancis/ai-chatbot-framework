"use client";

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { converse } from '../../services/chat';
import type { ChatState } from '../../services/training';
import './style.css';

interface Message {
  content: string;
  author: 'user' | 'chat';
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [chatCurrent, setChatCurrent] = useState<ChatState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isInitialMount = useRef(true);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const processResponse = useCallback((response: ChatState) => {
    response.owner = 'chat';
    response.date = new Date();
    setChatCurrent(response);

    if (Array.isArray(response.speechResponse)) {
      response.speechResponse.forEach((item, index) => {
        setTimeout(() => {
          setMessages(prev => [...prev, { content: item, author: 'chat' }]);
        }, 500 * index);
      });
    }
  }, []);

  const initChat = useCallback(async () => {
    const initialChat: ChatState = {
      currentNode: '',
      complete: null,
      context: {},
      parameters: [],
      extractedParameters: {},
      speechResponse: [],
      intent: {},
      input: '/init_conversation',
      missingParameters: []
    };

    try {
      const response = await converse(initialChat);
      processResponse(response);
    } catch (error) {
      console.error('Error initializing chat:', error);
    }
  }, [processResponse]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      initChat();
    }
  }, [initChat]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !chatCurrent) return;

    setIsLoading(true);
    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { content: userMessage, author: 'user' }]);

    const sendMessage: ChatState = {
      ...chatCurrent,
      input: userMessage,
      owner: 'user'
    };
    setChatCurrent(sendMessage);

    try {
      const response = await converse(sendMessage);
      setTimeout(() => {
        processResponse(response);
        setIsLoading(false);
      }, 1000);
    } catch (error) {
      console.error('Error sending message:', error);
      setIsLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-800">Chat Interface</h1>
        <p className="text-gray-600 mt-1">Test your chatbot&apos;s responses in real-time</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chat Window */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col h-[600px]">
          <div className="chat-container flex-1 p-4 space-y-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`chat-message flex ${message.author === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`chat-message-content ${message.author === 'user' ? 'user' : 'bot'}`}
                >
                  <div dangerouslySetInnerHTML={{ __html: message.content }} />
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="chat-message flex justify-start">
                <div className="typing-indicator">
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message here"
                className="flex-1 p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-colors duration-200"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors duration-200 disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </form>
        </div>

        {/* JSON Response */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-800 mb-4">POST /api/v1</h3>
          <pre className="bg-gray-50 p-4 rounded-lg overflow-auto h-[500px] text-sm">
            {JSON.stringify(chatCurrent, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;