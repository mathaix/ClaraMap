/**
 * Simulation Page - Test interview agent prompts before deployment.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import clsx from 'clsx';
import {
  createSimulationSession,
  createSimulationFromDesignSession,
  sendSimulationMessage,
  resetSimulation,
  getSimulationSession,
  deleteSimulation,
  SimulationModel,
} from '../api/simulation-sessions';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
}

export function SimulationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const designSessionId = searchParams.get('designSessionId');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [selectedModel, setSelectedModel] = useState<SimulationModel>('sonnet');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  // Initialize session
  useEffect(() => {
    async function init() {
      try {
        setIsLoading(true);
        setError(null);

        let result;
        if (designSessionId) {
          // Create from design session blueprint with selected model
          result = await createSimulationFromDesignSession(designSessionId, selectedModel);
        } else {
          // Create with default prompt and selected model
          result = await createSimulationSession({
            system_prompt: 'You are a helpful AI assistant conducting a discovery interview. Ask thoughtful questions to understand the user\'s needs and gather relevant information.',
            model: selectedModel,
          });
        }

        setSessionId(result.session_id);

        // Get full session state including prompt
        const state = await getSimulationSession(result.session_id);
        setSystemPrompt(state.system_prompt);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initialize simulation');
      } finally {
        setIsLoading(false);
      }
    }

    init();
  }, [designSessionId, selectedModel]);

  // Cleanup session on unmount
  useEffect(() => {
    return () => {
      if (sessionId) {
        // Fire and forget - cleanup shouldn't block unmount
        deleteSimulation(sessionId).catch(() => {
          // Ignore errors on cleanup
        });
      }
    };
  }, [sessionId]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    if (!sessionId || !inputValue.trim() || isStreaming) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputValue.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsStreaming(true);

    // Add streaming placeholder
    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', isStreaming: true },
    ]);

    try {
      for await (const event of sendSimulationMessage(sessionId, userMessage.content)) {
        if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) {
          // Use functional update to avoid stale closure - append delta to current content
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + event.delta }
                : msg
            )
          );
        } else if (event.type === 'TEXT_MESSAGE_END') {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, isStreaming: false }
                : msg
            )
          );
        } else if (event.type === 'ERROR') {
          setError(event.message || 'An error occurred');
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      // If session not found, prompt user to refresh
      if (errorMessage.includes('Not Found')) {
        setError('Session expired. Please refresh the page to start a new simulation.');
        setSessionId(null);
      } else {
        setError(errorMessage);
      }
      // Remove streaming message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
    } finally {
      setIsStreaming(false);
    }
  }, [sessionId, inputValue, isStreaming]);

  const handleReset = useCallback(async () => {
    if (!sessionId) return;

    try {
      await resetSimulation(sessionId);
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset');
    }
  }, [sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!projectId) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">No project selected</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-4">
            <Link
              to={`/projects/${projectId}`}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Agent Simulation</h1>
              <p className="text-sm text-gray-500">Test your interview agent before deployment</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Model Selector - always visible */}
            <div className="flex items-center gap-2">
              <label htmlFor="model-select" className="text-sm text-gray-600">
                Model:
              </label>
              <select
                id="model-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value as SimulationModel)}
                disabled={isLoading || isStreaming}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                <option value="haiku">Haiku (Fast)</option>
                <option value="sonnet">Sonnet (Balanced)</option>
                <option value="opus">Opus (Most Capable)</option>
              </select>
            </div>

            <button
              onClick={() => setShowPrompt(!showPrompt)}
              className={clsx(
                'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                showPrompt
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              )}
            >
              {showPrompt ? 'Hide Prompt' : 'View Prompt'}
            </button>

            <button
              onClick={handleReset}
              disabled={isStreaming || messages.length === 0}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
            >
              Reset Chat
            </button>
          </div>
        </header>

        {/* Error Banner */}
        {error && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
            <p className="text-sm text-red-700">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="mt-4 text-gray-500">Setting up simulation...</p>
            </div>
          </div>
        )}

        {/* Messages */}
        {!isLoading && (
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center">
                <div className="text-center max-w-lg">
                  <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <h2 className="text-lg font-medium text-gray-900 mb-2">Simulation Ready</h2>
                  <p className="text-gray-500 mb-6">
                    Start a conversation to test how your interview agent will behave.
                    The agent will use your configured system prompt.
                  </p>
                  <p className="text-sm text-gray-400">
                    Try saying: "Hi, I'm here for the interview"
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4 max-w-3xl mx-auto">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={clsx(
                      'flex',
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    )}
                  >
                    <div
                      className={clsx(
                        'max-w-[80%] rounded-lg px-4 py-3',
                        message.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-white text-gray-900 border border-gray-200',
                        message.isStreaming && 'animate-pulse'
                      )}
                    >
                      <div className="whitespace-pre-wrap text-sm leading-relaxed">
                        {message.content || (message.isStreaming && '...')}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        )}

        {/* Input */}
        {!isLoading && sessionId && (
          <div className="px-6 py-4 bg-white border-t border-gray-200">
            <div className="max-w-3xl mx-auto flex items-end gap-3">
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isStreaming}
                placeholder="Type a message as an interviewee..."
                rows={1}
                className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50"
              />
              <button
                onClick={handleSend}
                disabled={!inputValue.trim() || isStreaming}
                className="px-6 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send
              </button>
            </div>
          </div>
        )}
      </div>

      {/* System Prompt Sidebar */}
      {showPrompt && (
        <div className="w-96 bg-white border-l border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">System Prompt</h3>
            <p className="text-sm text-gray-500 mt-1">
              This is the prompt powering your interview agent
            </p>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 p-4 rounded-lg">
              {systemPrompt}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
