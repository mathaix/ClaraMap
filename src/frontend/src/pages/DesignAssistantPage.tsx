/**
 * Design Assistant page - full-screen chat interface with blueprint sidebar.
 */

import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { useDesignSession } from '../hooks/useDesignSession';
import { saveAgents } from '../api/design-sessions';
import {
  ChatMessage,
  ChatInput,
  BlueprintSidebar,
  DebugPanel,
} from '../components/design-assistant';

export function DesignAssistantPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const addAgent = searchParams.get('addAgent') === 'true';
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isDebugOpen, setIsDebugOpen] = useState(false);

  const {
    sessionId,
    isConnected,
    isLoading,
    isStreaming,
    error,
    messages,
    sessionState,
    pendingUIComponent,
    debugEvents,
    connect,
    sendMessage,
    disconnect,
    clearPendingUIComponent,
  } = useDesignSession({ projectId: projectId || 'default', addAgent });

  // Check if we have agents in the blueprint (meaning simulation is available)
  const hasBlueprint = (sessionState?.preview?.agent_count ?? 0) > 0;
  const [isSaving, setIsSaving] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);

  // Connect on mount
  useEffect(() => {
    connect().catch(console.error);

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (message: string) => {
    sendMessage(message);
  };

  const handleOptionSelect = (optionId: string) => {
    clearPendingUIComponent(); // Clear UI component when user interacts
    sendMessage(`I chose: ${optionId}`);
  };

  const handlePromptSave = (editedPrompt: string) => {
    clearPendingUIComponent(); // Clear the prompt editor
    // Send the edited prompt with a marker so the backend knows it's the finalized prompt
    sendMessage(`[PROMPT_SAVED]${editedPrompt}[/PROMPT_SAVED]`);
  };

  const handleClose = () => {
    disconnect();
    navigate(`/projects/${projectId}`);
  };

  const handleSaveAndClose = async () => {
    if (!sessionId) return;

    try {
      setIsSaving(true);
      await saveAgents(sessionId);
      disconnect();
      navigate(`/projects/${projectId}`);
    } catch (err) {
      console.error('Failed to save agents:', err);
      // Show error but don't close - user might want to retry
      alert(err instanceof Error ? err.message : 'Failed to save agents');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSimulate = async () => {
    if (!sessionId) return;

    try {
      setIsSimulating(true);
      // Save agents first, then navigate to simulation with the first agent
      const result = await saveAgents(sessionId);
      if (result.agent_ids.length > 0) {
        navigate(`/projects/${projectId}/simulate?agentId=${result.agent_ids[0]}`);
      } else {
        alert('No agents were saved. Please complete the design first.');
      }
    } catch (err) {
      console.error('Failed to save agents for simulation:', err);
      alert(err instanceof Error ? err.message : 'Failed to save agents');
    } finally {
      setIsSimulating(false);
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
    <div className="flex h-screen bg-white">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-4">
            <Link
              to={`/projects/${projectId}`}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
            </Link>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                Design Assistant
              </h1>
              <p className="text-sm text-gray-500">
                Create your Interview Blueprint
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Connection status */}
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-green-500' : 'bg-gray-300'
                }`}
              />
              <span className="text-sm text-gray-500">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>

            {hasBlueprint && sessionId && (
              <button
                onClick={handleSimulate}
                disabled={isSimulating || isStreaming}
                className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSimulating ? 'Saving...' : 'Simulate Agent'}
              </button>
            )}

            {hasBlueprint && sessionId && (
              <button
                onClick={handleSaveAndClose}
                disabled={isSaving || isStreaming}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? 'Saving...' : 'Save & Close'}
              </button>
            )}

            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Close
            </button>
          </div>
        </header>

        {/* Error Banner */}
        {error && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="mt-4 text-gray-500">Connecting to Design Assistant...</p>
            </div>
          </div>
        )}

        {/* Messages */}
        {!isLoading && (
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center">
                <div className="text-center max-w-2xl">
                  <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg
                      className="w-8 h-8 text-blue-600"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                      />
                    </svg>
                  </div>
                  <h2 className="text-lg font-medium text-gray-900 mb-2">
                    Welcome to the Design Assistant
                  </h2>
                  <p className="text-gray-500 mb-8">
                    I'll help you create an Interview Blueprint for your
                    project. Start by telling me what kind of discovery
                    interviews you want to conduct.
                  </p>

                  {/* Starter Prompts */}
                  <p className="text-sm text-gray-400 mb-3">Try an example to get started</p>
                  <div className="grid gap-3 max-w-xl mx-auto">
                    {[
                      {
                        icon: '🔄',
                        title: 'Post-M&A Product Consolidation',
                        prompt: 'I need to consolidate product lines after a merger. Help me interview stakeholders to understand system overlaps, integration challenges, and migration priorities.',
                      },
                      {
                        icon: '💬',
                        title: 'User Feedback & Pain Points',
                        prompt: 'I want to collect user feedback on my product to understand their pain points, frustrations, and unmet needs.',
                      },
                      {
                        icon: '⚡',
                        title: 'Process Optimization',
                        prompt: 'I need to optimize a business process. Help me interview stakeholders to identify costs, bottlenecks, and improvement opportunities.',
                      },
                    ].map((starter) => (
                      <button
                        key={starter.title}
                        onClick={() => handleSend(starter.prompt)}
                        disabled={!isConnected || isStreaming}
                        className="flex items-start gap-3 p-4 text-left bg-white border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="text-2xl">{starter.icon}</span>
                        <div>
                          <h3 className="font-medium text-gray-900">
                            {starter.title}
                          </h3>
                          <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                            {starter.prompt}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((message, index) => {
                  // Pass pendingUIComponent to the last assistant message
                  const isLastAssistantMessage =
                    message.role === 'assistant' &&
                    index === messages.length - 1;

                  return (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      onOptionSelect={handleOptionSelect}
                      onPromptSave={handlePromptSave}
                      externalUIComponent={isLastAssistantMessage ? pendingUIComponent : null}
                    />
                  );
                })}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        )}

        {/* Input */}
        {isConnected && (
          <ChatInput
            onSend={handleSend}
            disabled={isStreaming}
            placeholder={
              isStreaming
                ? 'Waiting for response...'
                : 'Describe your interview project...'
            }
          />
        )}
      </div>

      {/* Blueprint Sidebar */}
      <BlueprintSidebar state={sessionState} />

      {/* Debug Panel */}
      <DebugPanel
        events={debugEvents}
        isOpen={isDebugOpen}
        onToggle={() => setIsDebugOpen(!isDebugOpen)}
      />
    </div>
  );
}
