'use client';

import { useState, useEffect } from 'react';
import { ChatLog, ChatThreadInfo, listChatLogs, getChatThread, formatTimestamp } from '@/app/services/chatlogs';

const ChatLogsPage = () => {
  const [threads, setThreads] = useState<ChatThreadInfo[]>([]);
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatLog[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [threadLoading, setThreadLoading] = useState(false);
  const limit = 10;

  const fetchThreads = async () => {
    try {
      const data = await listChatLogs(page, limit);
      setThreads(data.conversations);
      setTotal(data.total);
    } catch (error) {
      console.error('Error fetching chat logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchThreadMessages = async (threadId: string) => {
    setThreadLoading(true);
    try {
      const messages = await getChatThread(threadId);
      setMessages(messages);
      setSelectedThread(threadId);
    } catch (error) {
      console.error('Error fetching thread messages:', error);
    } finally {
      setThreadLoading(false);
    }
  };

  useEffect(() => {
    fetchThreads();
  }, []);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="p-6 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-800">Chat Logs</h1>
        <p className="text-gray-600 mt-1">View and analyze conversation history</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 min-h-[calc(100vh-12rem)]">
        {/* Thread List */}
        <div className="lg:col-span-1 bg-white rounded-lg shadow-md overflow-hidden min-w-[320px]">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-800">Conversations</h2>
          </div>
          <div className="overflow-y-auto h-[calc(100vh-20rem)]">
            {loading ? (
              <div className="flex justify-center items-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {threads.map((thread) => (
                  <div
                    key={thread.thread_id}
                    onClick={() => fetchThreadMessages(thread.thread_id)}
                    className={`p-4 cursor-pointer transition-all ${selectedThread === thread.thread_id ? 'bg-blue-50 border-l-4 border-blue-500' : 'hover:bg-gray-50'}`}
                  >
                    <div className="flex flex-col space-y-1">
                      <div className="text-sm font-medium text-gray-900 truncate">
                        {thread.thread_id}
                      </div>
                      <div className="text-xs text-gray-500">{formatTimestamp(thread.date)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-700">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          )}
        </div>

        {/* Message Thread */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-md overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-800">
              {selectedThread ? 'Conversation Details' : 'Select a Conversation'}
            </h2>
          </div>
          <div className="overflow-y-auto h-[calc(100vh-20rem)]">
            {!selectedThread ? (
              <div className="flex flex-col justify-center items-center h-full p-8 text-center">
                <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                <p className="text-gray-600">Select a conversation from the list to view messages</p>
              </div>
            ) : threadLoading ? (
              <div className="flex justify-center items-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <div className="p-6 space-y-6">
                {messages.map((message, index) => (
                  <div key={index} className="space-y-4">
                    {/* User Message */}
                    <div className="chat-message flex justify-end">
                      <div className="flex-1">
                        <div className="bg-green-50 rounded-lg p-4 ml-12">
                          <p className="text-sm text-gray-800">{message.user_message.text}</p>
                        </div>
                      </div>
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-100 flex items-center justify-center ml-2">
                        <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                      </div>
                    </div>

                    {/* Bot Message */}
                    <div className="chat-message flex justify-start">
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center mr-2">
                        <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="bg-blue-50 rounded-lg p-4 mr-12">
                          {message.bot_message.map((msg, i) => (
                            <p key={i} className="text-sm text-gray-800 mb-2 last:mb-0">{msg.text}</p>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatLogsPage;