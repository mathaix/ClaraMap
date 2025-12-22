/**
 * Automated Simulation Page - Run simulated interviews with AI personas.
 *
 * Users configure a persona (role, company, experience) and watch the
 * interview agent have a conversation with the simulated interviewee.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import clsx from 'clsx';
import {
  createAutoSimulation,
  createAutoSimulationFromDesignSession,
  runAutoSimulation,
  deleteSimulation,
  SimulationModel,
  CommunicationStyle,
  PersonaConfig,
} from '../api/simulation-sessions';

interface Message {
  id: string;
  role: 'interviewer' | 'interviewee';
  content: string;
  isStreaming?: boolean;
}

type SimulationStatus = 'configuring' | 'ready' | 'running' | 'completed' | 'error';

const DEFAULT_SYSTEM_PROMPT = `You are an expert discovery interviewer. Your goal is to understand the interviewee's role, responsibilities, challenges, and workflows.

Guidelines:
- Start by introducing yourself and explaining the purpose of the interview
- Ask open-ended questions to encourage detailed responses
- Follow up on interesting points to dig deeper
- Be empathetic and create a comfortable environment
- Cover key topics: current processes, pain points, tools used, and desired improvements
- Summarize key findings periodically`;

export function AutomatedSimulationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const designSessionId = searchParams.get('designSessionId');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SimulationStatus>('configuring');
  const [error, setError] = useState<string | null>(null);

  // Persona configuration
  const [persona, setPersona] = useState<PersonaConfig>({
    role: 'Product Manager',
    company_url: '',
    name: '',
    experience_years: 5,
    communication_style: 'professional',
  });

  // Simulation settings
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [selectedModel, setSelectedModel] = useState<SimulationModel>('sonnet');
  const [numTurns, setNumTurns] = useState(5);

  // Messages
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup session on unmount
  useEffect(() => {
    return () => {
      if (sessionId) {
        deleteSimulation(sessionId).catch(() => {});
      }
    };
  }, [sessionId]);

  // Load system prompt from design session if provided
  useEffect(() => {
    async function loadDesignSession() {
      if (!designSessionId) return;

      try {
        setIsLoading(true);
        // We'll create the session when starting, but could pre-fetch the prompt here
      } catch (err) {
        console.error('Failed to load design session:', err);
      } finally {
        setIsLoading(false);
      }
    }

    loadDesignSession();
  }, [designSessionId]);

  const handleStartSimulation = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      setMessages([]);

      // Create the auto-simulation session
      let result;
      if (designSessionId) {
        result = await createAutoSimulationFromDesignSession(
          designSessionId,
          persona,
          selectedModel
        );
      } else {
        result = await createAutoSimulation({
          system_prompt: systemPrompt,
          persona,
          model: selectedModel,
        });
      }

      setSessionId(result.session_id);
      setStatus('ready');

      // Now run the simulation
      setStatus('running');

      for await (const event of runAutoSimulation(result.session_id, numTurns)) {
        if (event.type === 'TEXT_MESSAGE_CONTENT') {
          // Interviewer (assistant) message content
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg?.role === 'interviewer' && lastMsg?.isStreaming) {
              return prev.map((msg, i) =>
                i === prev.length - 1
                  ? { ...msg, content: msg.content + (event.delta || '') }
                  : msg
              );
            }
            // New interviewer message
            return [
              ...prev,
              {
                id: `interviewer-${Date.now()}`,
                role: 'interviewer',
                content: event.delta || '',
                isStreaming: true,
              },
            ];
          });
        } else if (event.type === 'TEXT_MESSAGE_END') {
          // Interviewer message complete
          setMessages((prev) =>
            prev.map((msg) =>
              msg.role === 'interviewer' && msg.isStreaming
                ? { ...msg, isStreaming: false }
                : msg
            )
          );
        } else if (event.type === 'SIMULATED_USER_CONTENT') {
          // Interviewee (simulated user) message content
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg?.role === 'interviewee' && lastMsg?.isStreaming) {
              return prev.map((msg, i) =>
                i === prev.length - 1
                  ? { ...msg, content: msg.content + (event.delta || '') }
                  : msg
              );
            }
            // New interviewee message
            return [
              ...prev,
              {
                id: `interviewee-${Date.now()}`,
                role: 'interviewee',
                content: event.delta || '',
                isStreaming: true,
              },
            ];
          });
        } else if (event.type === 'SIMULATED_USER_END') {
          // Interviewee message complete
          setMessages((prev) =>
            prev.map((msg) =>
              msg.role === 'interviewee' && msg.isStreaming
                ? { ...msg, isStreaming: false }
                : msg
            )
          );
        } else if (event.type === 'SIMULATION_COMPLETE') {
          setStatus('completed');
        } else if (event.type === 'ERROR') {
          setError(event.message || 'An error occurred');
          setStatus('error');
        }
      }

      setStatus('completed');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start simulation';
      setError(errorMessage);
      setStatus('error');
    } finally {
      setIsLoading(false);
    }
  }, [designSessionId, persona, systemPrompt, selectedModel, numTurns]);

  const handleReset = useCallback(() => {
    if (sessionId) {
      deleteSimulation(sessionId).catch(() => {});
    }
    setSessionId(null);
    setStatus('configuring');
    setMessages([]);
    setError(null);
  }, [sessionId]);

  if (!projectId) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">No project selected</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Configuration Panel */}
      <div className="w-96 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center gap-3 mb-2">
            <Link
              to={`/projects/${projectId}`}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <h1 className="text-lg font-semibold text-gray-900">Automated Simulation</h1>
          </div>
          <p className="text-sm text-gray-500">
            Configure a persona to simulate an interview conversation
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Persona Configuration */}
          <section>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Persona</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Role *</label>
                <input
                  type="text"
                  value={persona.role}
                  onChange={(e) => setPersona((p) => ({ ...p, role: e.target.value }))}
                  placeholder="e.g., Product Manager, Senior Engineer"
                  disabled={status !== 'configuring'}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">Name (optional)</label>
                <input
                  type="text"
                  value={persona.name || ''}
                  onChange={(e) => setPersona((p) => ({ ...p, name: e.target.value || undefined }))}
                  placeholder="e.g., Sarah Chen"
                  disabled={status !== 'configuring'}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">Company Website (optional)</label>
                <input
                  type="url"
                  value={persona.company_url || ''}
                  onChange={(e) => setPersona((p) => ({ ...p, company_url: e.target.value || undefined }))}
                  placeholder="https://company.com"
                  disabled={status !== 'configuring'}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                />
                <p className="mt-1 text-xs text-gray-400">
                  We'll fetch context about the company to inform responses
                </p>
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">Years of Experience</label>
                <input
                  type="number"
                  value={persona.experience_years || ''}
                  onChange={(e) => setPersona((p) => ({ ...p, experience_years: parseInt(e.target.value) || undefined }))}
                  min={0}
                  max={50}
                  disabled={status !== 'configuring'}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">Communication Style</label>
                <select
                  value={persona.communication_style || 'professional'}
                  onChange={(e) => setPersona((p) => ({ ...p, communication_style: e.target.value as CommunicationStyle }))}
                  disabled={status !== 'configuring'}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                >
                  <option value="professional">Professional</option>
                  <option value="casual">Casual</option>
                  <option value="detailed">Detailed</option>
                  <option value="brief">Brief</option>
                </select>
              </div>
            </div>
          </section>

          {/* Simulation Settings */}
          <section>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Settings</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Model</label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value as SimulationModel)}
                  disabled={status !== 'configuring'}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                >
                  <option value="haiku">Haiku (Fast)</option>
                  <option value="sonnet">Sonnet (Balanced)</option>
                  <option value="opus">Opus (Most Capable)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Conversation Turns: {numTurns}
                </label>
                <input
                  type="range"
                  value={numTurns}
                  onChange={(e) => setNumTurns(parseInt(e.target.value))}
                  min={1}
                  max={20}
                  disabled={status !== 'configuring'}
                  className="w-full"
                />
                <p className="mt-1 text-xs text-gray-400">
                  Number of back-and-forth exchanges
                </p>
              </div>
            </div>
          </section>

          {/* System Prompt (only if no design session) */}
          {!designSessionId && (
            <section>
              <h3 className="text-sm font-medium text-gray-900 mb-3">Interview Prompt</h3>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                disabled={status !== 'configuring'}
                rows={8}
                className="w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              />
            </section>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-gray-200">
          {status === 'configuring' && (
            <button
              onClick={handleStartSimulation}
              disabled={!persona.role || isLoading}
              className="w-full px-4 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Starting...' : 'Start Simulation'}
            </button>
          )}

          {(status === 'running' || status === 'completed' || status === 'error') && (
            <button
              onClick={handleReset}
              className="w-full px-4 py-3 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
            >
              New Simulation
            </button>
          )}
        </div>
      </div>

      {/* Conversation View */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Interview Conversation</h2>
            <p className="text-sm text-gray-500">
              {status === 'configuring' && 'Configure a persona to start'}
              {status === 'ready' && 'Ready to begin'}
              {status === 'running' && 'Simulation in progress...'}
              {status === 'completed' && `Completed - ${messages.length} messages`}
              {status === 'error' && 'Simulation failed'}
            </p>
          </div>

          {status !== 'configuring' && (
            <div className="flex items-center gap-2">
              <span className={clsx(
                'px-3 py-1 text-xs font-medium rounded-full',
                status === 'running' && 'bg-yellow-100 text-yellow-700',
                status === 'completed' && 'bg-green-100 text-green-700',
                status === 'error' && 'bg-red-100 text-red-700',
                status === 'ready' && 'bg-blue-100 text-blue-700'
              )}>
                {status === 'running' && 'Running'}
                {status === 'completed' && 'Complete'}
                {status === 'error' && 'Error'}
                {status === 'ready' && 'Ready'}
              </span>
            </div>
          )}
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

        {/* Active Persona Card */}
        {status !== 'configuring' && (
          <div className="mx-6 mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-purple-900">
                    {persona.name || 'Simulated Interviewee'}
                  </h3>
                  <span className="px-2 py-0.5 text-xs font-medium bg-purple-200 text-purple-700 rounded-full">
                    {persona.communication_style || 'professional'}
                  </span>
                </div>
                <p className="text-sm text-purple-700">{persona.role}</p>
                <div className="flex items-center gap-4 mt-1 text-xs text-purple-600">
                  {persona.experience_years && (
                    <span>{persona.experience_years} years experience</span>
                  )}
                  {persona.company_url && (() => {
                    try {
                      const hostname = new URL(persona.company_url).hostname.replace('www.', '');
                      return (
                        <span className="flex items-center gap-1">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                          </svg>
                          {hostname}
                        </span>
                      );
                    } catch {
                      return null;
                    }
                  })()}
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-purple-500 uppercase tracking-wide">Model</div>
                <div className="text-sm font-medium text-purple-700 capitalize">{selectedModel}</div>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {status === 'configuring' && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md">
              <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Automated Interview Simulation</h3>
              <p className="text-gray-500 mb-4">
                Configure a persona on the left to simulate an interview. The AI will play the role
                of an interviewee with the specified characteristics.
              </p>
              <p className="text-sm text-gray-400">
                Example: "Product Manager at Facebook working on Instagram"
              </p>
            </div>
          </div>
        )}

        {/* Messages */}
        {status !== 'configuring' && (
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {messages.length === 0 && status === 'running' ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
                  <p className="mt-4 text-gray-500">Starting simulation...</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4 max-w-3xl mx-auto">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={clsx(
                      'flex',
                      message.role === 'interviewee' ? 'justify-end' : 'justify-start'
                    )}
                  >
                    <div className="flex items-start gap-3 max-w-[80%]">
                      {message.role === 'interviewer' && (
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                          <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                          </svg>
                        </div>
                      )}
                      <div
                        className={clsx(
                          'rounded-lg px-4 py-3',
                          message.role === 'interviewer'
                            ? 'bg-white text-gray-900 border border-gray-200'
                            : 'bg-purple-600 text-white',
                          message.isStreaming && 'animate-pulse'
                        )}
                      >
                        <div className="text-xs font-medium mb-1 opacity-70">
                          {message.role === 'interviewer' ? 'Interviewer' : persona.name || persona.role}
                        </div>
                        <div className="whitespace-pre-wrap text-sm leading-relaxed">
                          {message.content || (message.isStreaming && '...')}
                        </div>
                      </div>
                      {message.role === 'interviewee' && (
                        <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
                          <svg className="w-4 h-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                          </svg>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        )}

        {/* Completion Summary */}
        {status === 'completed' && messages.length > 0 && (
          <div className="px-6 py-4 bg-white border-t border-gray-200">
            <div className="max-w-3xl mx-auto flex items-center justify-between">
              <div className="text-sm text-gray-600">
                Simulation completed with {Math.ceil(messages.length / 2)} conversation turns
              </div>
              <button
                onClick={handleReset}
                className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                Run Another Simulation
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
