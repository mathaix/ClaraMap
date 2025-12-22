/**
 * Interview Agents API client.
 *
 * Provides CRUD operations for InterviewAgent entities.
 */

import { apiRequest } from './client';

export interface InterviewAgentResponse {
  id: string;
  project_id: string;
  name: string;
  persona: string | null;
  topics: string[];
  tone: string | null;
  system_prompt: string | null;
  capabilities: {
    role?: string;
    capabilities?: string[];
    expertise_areas?: string[];
    interaction_style?: string;
  } | null;
  status: string;
  design_session_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewAgentListResponse {
  agents: InterviewAgentResponse[];
  total: number;
}

export interface CreateInterviewAgentRequest {
  project_id: string;
  name: string;
  persona?: string;
  topics?: string[];
  tone?: string;
  system_prompt?: string;
  capabilities?: Record<string, unknown>;
  design_session_id?: string;
}

export interface UpdateInterviewAgentRequest {
  name?: string;
  persona?: string;
  topics?: string[];
  tone?: string;
  system_prompt?: string;
  capabilities?: Record<string, unknown>;
  status?: string;
}

const BASE_URL = '/api/v1/interview-agents';

/**
 * List all interview agents for a project.
 */
export async function listProjectAgents(
  projectId: string
): Promise<InterviewAgentListResponse> {
  return apiRequest<InterviewAgentListResponse>(`${BASE_URL}/project/${projectId}`);
}

/**
 * Get a single interview agent.
 */
export async function getAgent(agentId: string): Promise<InterviewAgentResponse> {
  return apiRequest<InterviewAgentResponse>(`${BASE_URL}/${agentId}`);
}

/**
 * Create a new interview agent.
 */
export async function createAgent(
  data: CreateInterviewAgentRequest
): Promise<InterviewAgentResponse> {
  return apiRequest<InterviewAgentResponse>(BASE_URL, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an interview agent.
 */
export async function updateAgent(
  agentId: string,
  data: UpdateInterviewAgentRequest
): Promise<InterviewAgentResponse> {
  return apiRequest<InterviewAgentResponse>(`${BASE_URL}/${agentId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Delete an interview agent.
 */
export async function deleteAgent(agentId: string): Promise<void> {
  await apiRequest(`${BASE_URL}/${agentId}`, { method: 'DELETE' });
}

export const interviewAgentsApi = {
  listByProject: listProjectAgents,
  get: getAgent,
  create: createAgent,
  update: updateAgent,
  delete: deleteAgent,
};
