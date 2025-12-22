/**
 * Design Sessions API client with SSE streaming support.
 */

import { apiRequest } from './client';
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  SessionInfo,
  SessionStateResponse,
  AGUIEvent,
} from '../types/design-session';

const BASE_URL = '/api/v1/design-sessions';

/**
 * Create a new design session.
 */
export async function createSession(
  data: CreateSessionRequest
): Promise<CreateSessionResponse> {
  return apiRequest<CreateSessionResponse>(BASE_URL, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Get session info (basic).
 */
export async function getSession(sessionId: string): Promise<SessionInfo> {
  return apiRequest<SessionInfo>(`${BASE_URL}/${sessionId}`);
}

/**
 * Get full session state including messages and blueprint state.
 */
export async function getFullSession(sessionId: string): Promise<SessionStateResponse> {
  return apiRequest<SessionStateResponse>(`${BASE_URL}/${sessionId}`);
}

/**
 * Delete a session.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await apiRequest(`${BASE_URL}/${sessionId}`, { method: 'DELETE' });
}

/**
 * Get session by project ID (if exists).
 */
export async function getSessionByProject(projectId: string): Promise<SessionStateResponse | null> {
  try {
    return await apiRequest<SessionStateResponse>(`${BASE_URL}/project/${projectId}`);
  } catch {
    return null;
  }
}

/**
 * Parse SSE event from raw text.
 */
function parseSSEEvent(eventText: string): AGUIEvent | null {
  const lines = eventText.split('\n');
  let eventType = '';
  let data = '';

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      data = line.slice(5).trim();
    }
  }

  if (!data) return null;

  try {
    const parsed = JSON.parse(data);
    return { type: eventType || parsed.type, ...parsed } as AGUIEvent;
  } catch {
    console.error('Failed to parse SSE data:', data);
    return null;
  }
}

/**
 * Stream a message to the design assistant and receive events.
 */
export async function* streamMessage(
  sessionId: string,
  message: string
): AsyncGenerator<AGUIEvent, void, unknown> {
  const response = await fetch(`${BASE_URL}/${sessionId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error(`Stream request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error('No response body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split on double newline (SSE event separator)
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const eventText of events) {
        if (!eventText.trim()) continue;

        const event = parseSSEEvent(eventText);
        if (event) {
          yield event;
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      const event = parseSSEEvent(buffer);
      if (event) {
        yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export const designSessionsApi = {
  create: createSession,
  get: getSession,
  getFullSession,
  getByProject: getSessionByProject,
  delete: deleteSession,
  streamMessage,
};
