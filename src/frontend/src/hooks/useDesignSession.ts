/**
 * Custom hook for managing design session state and streaming.
 */

import { useState, useCallback, useRef } from 'react';
import { designSessionsApi } from '../api/design-sessions';
import type {
  ChatMessage,
  DesignSessionState,
  AGUIEvent,
  StateSnapshotEvent,
  TextMessageContentEvent,
  ErrorEvent,
  DesignPhase,
  BlueprintPreview,
  SessionStateResponse,
  DebugEvent,
  ToolCallStartEvent,
  CustomEvent,
  UIComponent,
} from '../types/design-session';

interface UseDesignSessionOptions {
  projectId: string;
}

interface UseDesignSessionReturn {
  // Session state
  sessionId: string | null;
  isConnected: boolean;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;

  // Chat state
  messages: ChatMessage[];
  sessionState: DesignSessionState | null;

  // UI component from CUSTOM events
  pendingUIComponent: UIComponent | null;

  // Debug state
  debugEvents: DebugEvent[];

  // Actions
  connect: () => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  disconnect: () => Promise<void>;
  clearDebugEvents: () => void;
  clearPendingUIComponent: () => void;
}

const initialSessionState: DesignSessionState = {
  phase: 'goal_understanding' as DesignPhase,
  preview: {
    project_name: null,
    project_type: null,
    entity_types: [],
    agent_count: 0,
    topics: [],
  },
  inferred_domain: null,
  debug: {
    thinking: null,
    approach: null,
    turn_count: 0,
    message_count: 0,
    domain_confidence: 0,
    discussed_topics: [],
  },
};

export function useDesignSession({
  projectId,
}: UseDesignSessionOptions): UseDesignSessionReturn {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionState, setSessionState] = useState<DesignSessionState | null>(
    null
  );
  const [pendingUIComponent, setPendingUIComponent] = useState<UIComponent | null>(null);
  const [debugEvents, setDebugEvents] = useState<DebugEvent[]>([]);

  const messageIdCounter = useRef(0);
  const debugEventIdCounter = useRef(0);

  const addDebugEvent = useCallback(
    (type: DebugEvent['type'], title: string, details: Record<string, unknown> = {}) => {
      debugEventIdCounter.current += 1;
      const event: DebugEvent = {
        id: `debug-${Date.now()}-${debugEventIdCounter.current}`,
        timestamp: new Date(),
        type,
        title,
        details,
      };
      setDebugEvents((prev) => [...prev, event]);
    },
    []
  );

  const clearDebugEvents = useCallback(() => {
    setDebugEvents([]);
    debugEventIdCounter.current = 0;
  }, []);

  const clearPendingUIComponent = useCallback(() => {
    setPendingUIComponent(null);
  }, []);

  const generateMessageId = useCallback(() => {
    messageIdCounter.current += 1;
    return `msg-${Date.now()}-${messageIdCounter.current}`;
  }, []);

  // Convert API message to ChatMessage
  const apiMessageToChatMessage = useCallback(
    (msg: { role: 'user' | 'assistant'; content: string }, index: number): ChatMessage => ({
      id: `restored-${index}`,
      role: msg.role,
      content: msg.content,
      timestamp: new Date(), // We don't have timestamps from the API
    }),
    []
  );

  // Restore session state from API response
  const restoreSessionState = useCallback(
    (sessionState: SessionStateResponse) => {
      // Restore messages
      const restoredMessages = sessionState.messages.map(apiMessageToChatMessage);
      setMessages(restoredMessages);
      messageIdCounter.current = restoredMessages.length;

      // Restore session state
      const blueprintState = sessionState.blueprint_state || {};
      const project = blueprintState.project;

      setSessionState({
        phase: sessionState.phase,
        preview: {
          project_name: project?.name || null,
          project_type: project?.type || null,
          entity_types: blueprintState.entities?.map((e) => e.name) || [],
          agent_count: blueprintState.agents?.length || 0,
          topics: [],
        },
        inferred_domain: project?.domain || null,
        debug: {
          thinking: null,
          approach: null,
          turn_count: sessionState.turn_count,
          message_count: sessionState.message_count,
          domain_confidence: 0,
          discussed_topics: [],
        },
      });
    },
    [apiMessageToChatMessage]
  );

  const connect = useCallback(async () => {
    if (isConnected) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await designSessionsApi.create({ project_id: projectId });
      setSessionId(response.session_id);
      setIsConnected(true);

      if (response.is_new) {
        // New session - start fresh
        setSessionState(initialSessionState);
        setMessages([]);
      } else {
        // Existing session - load previous state
        const fullState = await designSessionsApi.getFullSession(response.session_id);
        restoreSessionState(fullState);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [projectId, isConnected, restoreSessionState]);

  const disconnect = useCallback(async () => {
    if (!sessionId) return;

    // Just clear local state - don't delete the session from DB
    // Session persists in DB so user can resume later
    setSessionId(null);
    setIsConnected(false);
    setMessages([]);
    setSessionState(null);
  }, [sessionId]);

  const handleEvent = useCallback(
    (event: AGUIEvent, currentAssistantMessage: ChatMessage | null, prevPhase: DesignPhase | null) => {
      switch (event.type) {
        case 'STATE_SNAPSHOT': {
          const snapshot = event as StateSnapshotEvent;

          // Track phase transitions
          if (prevPhase && snapshot.phase !== prevPhase) {
            addDebugEvent('phase_transition', `${prevPhase} → ${snapshot.phase}`, {
              from: prevPhase,
              to: snapshot.phase,
            });
          }

          // Track state updates
          addDebugEvent('state_update', `State snapshot received`, {
            phase: snapshot.phase,
            turn_count: snapshot.debug?.turn_count,
            message_count: snapshot.debug?.message_count,
          });

          setSessionState({
            phase: snapshot.phase,
            preview: snapshot.preview as BlueprintPreview,
            inferred_domain: snapshot.inferred_domain,
            debug: snapshot.debug,
          });
          break;
        }

        case 'TEXT_MESSAGE_CONTENT': {
          const textEvent = event as TextMessageContentEvent;
          if (currentAssistantMessage) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === currentAssistantMessage.id
                  ? { ...msg, content: msg.content + textEvent.delta }
                  : msg
              )
            );
          }
          break;
        }

        case 'TEXT_MESSAGE_END': {
          if (currentAssistantMessage) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === currentAssistantMessage.id
                  ? { ...msg, isStreaming: false }
                  : msg
              )
            );
          }
          break;
        }

        case 'TOOL_CALL_START': {
          const toolEvent = event as ToolCallStartEvent;
          const toolName = toolEvent.tool || 'unknown';

          // Determine event type based on tool name
          let eventType: DebugEvent['type'] = 'tool_call';
          let title = toolName;

          if (toolName.includes('hydrate')) {
            eventType = 'hydration';
            title = toolName.replace('mcp__clara__', '');
          } else if (toolName.includes('phase')) {
            eventType = 'phase_transition';
            title = `Phase tool: ${JSON.stringify(toolEvent.input)}`;
          } else {
            title = toolName.replace('mcp__clara__', '');
          }

          addDebugEvent(eventType, title, toolEvent.input || {});
          break;
        }

        case 'TOOL_CALL_END': {
          // Tool completion is tracked implicitly
          break;
        }

        case 'CUSTOM': {
          // Handle CUSTOM AG-UI events for Clara UI components
          const customEvent = event as CustomEvent;
          const eventName = customEvent.name;
          const value = customEvent.value;

          // Log as debug event
          addDebugEvent('tool_call', `UI: ${eventName}`, { component: value });

          // Set the pending UI component for rendering
          setPendingUIComponent(value);
          break;
        }

        case 'ERROR': {
          const errorEvent = event as ErrorEvent;
          addDebugEvent('error', errorEvent.message, { error: errorEvent.message });
          setError(errorEvent.message);
          break;
        }
      }
    },
    [addDebugEvent]
  );

  const sendMessage = useCallback(
    async (message: string) => {
      if (!sessionId || isStreaming) return;

      setIsStreaming(true);
      setError(null);

      // Add user message
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        role: 'user',
        content: message,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // Create placeholder for assistant message
      const assistantMessage: ChatMessage = {
        id: generateMessageId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      try {
        const stream = designSessionsApi.streamMessage(sessionId, message);
        const prevPhase = sessionState?.phase || null;

        for await (const event of stream) {
          handleEvent(event, assistantMessage, prevPhase);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message');
        // Remove the empty assistant message on error
        setMessages((prev) =>
          prev.filter((msg) => msg.id !== assistantMessage.id)
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [sessionId, isStreaming, generateMessageId, handleEvent]
  );

  return {
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
    clearDebugEvents,
    clearPendingUIComponent,
  };
}
