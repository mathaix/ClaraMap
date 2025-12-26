/**
 * Design Session types for the Design Assistant UI.
 */

// AG-UI Event Types
export type AGUIEventType =
  | 'STATE_SNAPSHOT'
  | 'STATE_DELTA'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_END'
  | 'CUSTOM'
  | 'ERROR';

// Custom event names for Clara UI components
export type ClaraCustomEventName =
  | 'clara:ask'
  | 'clara:agent_configured'
  | 'clara:blueprint_preview'
  | 'clara:prompt_editor'
  | 'clara:data_table'
  | 'clara:process_map';

export interface AGUIEvent {
  type: AGUIEventType;
  [key: string]: unknown;
}

export interface StateSnapshotEvent extends AGUIEvent {
  type: 'STATE_SNAPSHOT';
  phase: DesignPhase;
  preview: BlueprintPreview;
  inferred_domain: string | null;
  debug: DebugInfo;
}

export interface TextMessageContentEvent extends AGUIEvent {
  type: 'TEXT_MESSAGE_CONTENT';
  delta: string;
}

export interface TextMessageEndEvent extends AGUIEvent {
  type: 'TEXT_MESSAGE_END';
}

export interface ToolCallStartEvent extends AGUIEvent {
  type: 'TOOL_CALL_START';
  tool: string;
  input: Record<string, unknown>;
}

export interface ToolCallEndEvent extends AGUIEvent {
  type: 'TOOL_CALL_END';
  tool?: string;
}

export interface ErrorEvent extends AGUIEvent {
  type: 'ERROR';
  message: string;
}

// CUSTOM event for Clara-specific UI components
export interface CustomEvent extends AGUIEvent {
  type: 'CUSTOM';
  name: ClaraCustomEventName;
  value: UIComponent;
}

// Design Session State
export type DesignPhase = 'goal_understanding' | 'agent_configuration' | 'blueprint_design' | 'complete';

export interface BlueprintPreview {
  project_name: string | null;
  project_type: string | null;
  entity_types: string[];
  agent_count: number;
  topics: string[];
}

export interface DebugInfo {
  thinking: string | null;
  approach: string | null;
  turn_count: number;
  message_count: number;
  domain_confidence: number;
  discussed_topics: string[];
}

// Debug event types for the debug panel
export type DebugEventType = 'tool_call' | 'phase_transition' | 'hydration' | 'state_update' | 'error';

export interface DebugEvent {
  id: string;
  timestamp: Date;
  type: DebugEventType;
  title: string;
  details: Record<string, unknown>;
}

export interface DesignSessionState {
  phase: DesignPhase;
  preview: BlueprintPreview;
  inferred_domain: string | null;
  debug: DebugInfo;
}

// API Types
export interface CreateSessionRequest {
  project_id: string;
  add_agent?: boolean;
}

export interface CreateSessionResponse {
  session_id: string;
  project_id: string;
  is_new: boolean;  // True if new session, False if resuming existing
}

export interface SessionInfo {
  session_id: string;
  project_id: string;
  phase: DesignPhase;
  turn_count: number;
  message_count: number;
}

// Full session state returned by GET /design-sessions/{id}
export interface SessionStateResponse {
  session_id: string;
  project_id: string;
  phase: DesignPhase;
  messages: Array<{ role: MessageRole; content: string }>;
  blueprint_state: {
    project?: {
      name?: string;
      type?: string;
      domain?: string;
      description?: string;
    } | null;
    entities: Array<{
      name: string;
      attributes: string[];
      description?: string;
    }>;
    agents: Array<{
      name: string;
      persona?: string;
      topics: string[];
      tone?: string;
      system_prompt?: string;
      context_files?: Array<{
        id: string;
        name: string;
        type: string;
        size: number;
        uploaded_at: string;
      }>;
    }>;
  };
  goal_summary: Record<string, unknown> | null;
  agent_capabilities: {
    role?: string;
    capabilities?: string[];
    expertise_areas?: string[];
    interaction_style?: string;
  } | null;
  turn_count: number;
  message_count: number;
  status: string;
}

export interface SendMessageRequest {
  message: string;
}

// Project-level agent info (from aggregation endpoint)
export interface ProjectAgentInfo {
  id: string;  // Agent ID (InterviewAgent.id)
  session_id: string | null;  // May be null if agent was imported or session deleted
  agent_index: number;
  name: string;
  persona: string | null;
  topics: string[];
  tone: string | null;
  system_prompt: string | null;
  status: 'draft' | 'active' | 'archived';
  context_files: Array<{
    id: string;
    name: string;
    type: string;
    size: number;
    uploaded_at: string;
  }> | null;
}

export interface ProjectAgentsResponse {
  project_id: string;
  agents: ProjectAgentInfo[];
  agent_count: number;
}

// Chat Message Types
export type MessageRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

// Interactive UI Component Types (from ask tool)
export interface AskOption {
  id: string;
  label: string;
  description?: string;
  requires_input?: boolean;
}

export interface CardAction {
  id: string;
  label: string;
  style?: string;
}

export interface CardHelper {
  why_this?: string[];
  risks_if_skipped?: string[];
}

export type CardBody = Record<string, unknown> | string | Array<unknown>;

export interface CardEnvelope {
  card_id: string;
  type: string;
  title: string;
  subtitle?: string | null;
  body: CardBody;
  actions?: CardAction[];
  helper?: CardHelper;
}

export interface AskUIComponent {
  type: 'user_input_required';
  question: string;
  options: AskOption[];
  multi_select: boolean;
  cards?: CardEnvelope[];
}

export interface DataTableColumn {
  name: string;
  type: 'text' | 'number' | 'enum' | 'date' | 'url';
  required?: boolean;
  options?: string[];
}

export interface DataTableUIComponent {
  type: 'data_table';
  title: string;
  columns: DataTableColumn[];
  min_rows?: number;
  starter_rows?: number;
  input_modes?: Array<'paste' | 'inline' | 'import'>;
  summary_prompt?: string;
}

export interface ProcessMapUIComponent {
  type: 'process_map';
  title: string;
  required_fields: string[];
  edge_types?: string[];
  min_steps?: number;
  seed_nodes?: string[];
}

// Agent configured UI Component (from agent_summary tool)
export interface AgentConfiguredUIComponent {
  type: 'agent_configured';
  role: string;
  expertise_areas: string[];
  interaction_style: string;
  capabilities?: string[];
  focus_areas?: string[];
}

// Prompt editor UI Component (from prompt_editor tool)
export interface PromptEditorUIComponent {
  type: 'prompt_editor';
  title: string;
  prompt: string;
  description?: string;
}

// Union type for all UI components
export type UIComponent =
  | AskUIComponent
  | DataTableUIComponent
  | ProcessMapUIComponent
  | AgentConfiguredUIComponent
  | PromptEditorUIComponent;

export type DataTableRow = Record<string, string>;

export interface DataTableSubmission {
  title: string;
  columns: DataTableColumn[];
  rows: DataTableRow[];
}

export interface ProcessMapStep {
  step_name: string;
  owner: string;
  outcome: string;
  edge_type?: string;
}

export interface ProcessMapSubmission {
  title: string;
  steps: ProcessMapStep[];
}

// Parse UI component from message content
export function parseUIComponent(content: string): UIComponent | null {
  const match = content.match(/\[UI_COMPONENT\](.*?)\[\/UI_COMPONENT\]/s);
  if (!match) return null;

  try {
    return JSON.parse(match[1]) as UIComponent;
  } catch {
    return null;
  }
}

// Strip UI component markers from content
export function stripUIComponentMarkers(content: string): string {
  return content.replace(/\[UI_COMPONENT\].*?\[\/UI_COMPONENT\]/gs, '').trim();
}
