/**
 * Simulation Sessions API client.
 */

const API_BASE = '/api/v1/simulation-sessions';

export type SimulationModel = 'sonnet' | 'haiku' | 'opus';

export interface CreateSimulationRequest {
  system_prompt: string;
  design_session_id?: string;
  model?: SimulationModel;
}

export interface CreateSimulationResponse {
  session_id: string;
  system_prompt_preview: string;
  model: SimulationModel;
}

export interface SimulationState {
  session_id: string;
  system_prompt: string;
  model: SimulationModel;
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
}

/**
 * Create a new simulation session with a custom prompt.
 */
export async function createSimulationSession(
  request: CreateSimulationRequest
): Promise<CreateSimulationResponse> {
  const response = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to create simulation: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a simulation session from an existing design session's blueprint.
 */
export async function createSimulationFromDesignSession(
  designSessionId: string,
  model?: SimulationModel
): Promise<CreateSimulationResponse> {
  const url = model
    ? `${API_BASE}/from-design-session/${designSessionId}?model=${model}`
    : `${API_BASE}/from-design-session/${designSessionId}`;

  const response = await fetch(url, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to create simulation: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get the current state of a simulation session.
 */
export async function getSimulationSession(
  sessionId: string
): Promise<SimulationState> {
  const response = await fetch(`${API_BASE}/${sessionId}`);

  if (!response.ok) {
    throw new Error(`Failed to get simulation: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update the system prompt for a simulation session.
 */
export async function updateSimulationPrompt(
  sessionId: string,
  systemPrompt: string
): Promise<void> {
  const response = await fetch(`${API_BASE}/${sessionId}/prompt`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ system_prompt: systemPrompt }),
  });

  if (!response.ok) {
    throw new Error(`Failed to update prompt: ${response.statusText}`);
  }
}

/**
 * Reset the simulation conversation history.
 */
export async function resetSimulation(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${sessionId}/reset`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to reset simulation: ${response.statusText}`);
  }
}

/**
 * Delete a simulation session.
 */
export async function deleteSimulation(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${sessionId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete simulation: ${response.statusText}`);
  }
}

/**
 * Send a message and stream the response using fetch.
 */
export async function* sendSimulationMessage(
  sessionId: string,
  userMessage: string
): AsyncGenerator<{ type: string; delta?: string; message?: string }> {
  const response = await fetch(`${API_BASE}/${sessionId}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: userMessage }),
  });

  if (!response.ok) {
    throw new Error(`Failed to send message: ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          yield data;
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }
}
