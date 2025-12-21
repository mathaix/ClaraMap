# Clara Design Assistant: Claude Agent SDK + AG-UI Architecture

## Overview

This document outlines a radical refactoring of Clara's Design Assistant from Pydantic AI to Claude Agent SDK, with a rich, adaptive AG-UI frontend.

## Goals

1. **Replace Pydantic AI** with Claude Agent SDK for the agent loop
2. **Rich Adaptive UI** using AG-UI protocol with dynamic components
3. **Better Developer Experience** via SDK's built-in tooling
4. **Subagent Architecture** for specialized interview agent design
5. **Real-time Streaming** with native WebSocket support

---

## Architecture Comparison

### Current (Pydantic AI)

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (React)                                                │
│ ├── useStreamingChat hook                                       │
│ └── SSE event processing                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Backend                                                 │
│ ├── POST /design-sessions/{id}/stream                           │
│ └── StreamingResponse with SSE                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pydantic AI Agent                                               │
│ ├── Agent definition with @tool decorators                      │
│ ├── run_stream() for streaming                                  │
│ └── Manual SSE event emission                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Proposed (Claude Agent SDK)

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (React + AG-UI)                                        │
│ ├── @ag-ui/react components                                     │
│ ├── WebSocket connection                                        │
│ └── Dynamic UI component rendering                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Node.js Server (Express + WS)                                   │
│ ├── WebSocket endpoint (/ws)                                    │
│ ├── Session management                                          │
│ └── Claude Agent SDK integration                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Claude Agent SDK                                                │
│ ├── query() with async iteration                                │
│ ├── AgentDefinition for subagents                               │
│ ├── Built-in tools (Bash, Read, Write, etc.)                    │
│ ├── Custom tools for blueprint building                         │
│ └── Hooks for pre/post tool execution                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Subagents                                                       │
│ ├── Domain Expert (M&A, ERP, Customer Research)                 │
│ ├── Rubric Designer                                             │
│ ├── Question Crafter                                            │
│ └── Agent Configurator                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Claude Agent SDK Concepts

### 1. Query Function

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

// Long-lived conversation with async message queue
const outputIterator = query({
  prompt: messageQueue,  // AsyncIterable of user messages
  options: {
    maxTurns: 100,
    model: "sonnet",
    allowedTools: ["Read", "Write", "Bash", "WebSearch"],
    systemPrompt: SYSTEM_PROMPT,
  },
});

// Stream responses
for await (const message of outputIterator) {
  if (message.type === "assistant") {
    // Handle assistant message
  } else if (message.type === "result") {
    // Query complete
  }
}
```

### 2. Subagents with AgentDefinition

```typescript
import { AgentDefinition } from "claude-agent-sdk";

const agents = {
  "domain-expert": AgentDefinition({
    description: "Analyzes the project domain and proposes interview structure",
    tools: ["WebSearch", "Read"],
    prompt: domainExpertPrompt,
    model: "sonnet",
  }),

  "rubric-designer": AgentDefinition({
    description: "Designs the shared rubric schema for data extraction",
    tools: ["Write"],
    prompt: rubricDesignerPrompt,
    model: "haiku",
  }),

  "agent-configurator": AgentDefinition({
    description: "Configures specialized interview agents",
    tools: ["Write"],
    prompt: agentConfiguratorPrompt,
    model: "haiku",
  }),
};
```

### 3. Custom Tools

```typescript
import { tool } from "@anthropic-ai/claude-agent-sdk";

const updateBlueprintTool = tool({
  name: "update_blueprint",
  description: "Update a section of the interview blueprint",
  parameters: {
    section: { type: "string", enum: ["project", "rubric", "agents", "execution"] },
    data: { type: "object" },
  },
  execute: async ({ section, data }, context) => {
    // Update blueprint in session state
    context.session.blueprint[section] = data;

    // Emit AG-UI event for frontend update
    context.emit({
      type: "STATE_DELTA",
      delta: [{ op: "replace", path: `/blueprint/${section}`, value: data }],
    });

    return { success: true, section, updated: true };
  },
});
```

### 4. Hooks for Observability

```typescript
const hooks = {
  PreToolUse: [
    HookMatcher({
      matcher: null,  // Match all tools
      hooks: [async (toolName, input, context) => {
        // Log tool usage
        console.log(`[${toolName}]`, input);

        // Emit AG-UI activity event
        context.emit({
          type: "ACTIVITY_SNAPSHOT",
          activity: { tool: toolName, status: "running" },
        });
      }],
    }),
  ],
  PostToolUse: [
    HookMatcher({
      matcher: null,
      hooks: [async (toolName, result, context) => {
        context.emit({
          type: "ACTIVITY_SNAPSHOT",
          activity: { tool: toolName, status: "complete", result },
        });
      }],
    }),
  ],
};
```

---

## AG-UI Integration

### Dynamic UI Components

The Claude Agent SDK will emit AG-UI events that trigger dynamic UI components:

```typescript
// Agent emits tool call that triggers UI component
await context.emit({
  type: "TOOL_CALL_START",
  toolCallId: "tc_001",
  toolName: "show_domain_options",
});

await context.emit({
  type: "TOOL_CALL_ARGS",
  toolCallId: "tc_001",
  args: JSON.stringify({
    component: "select_cards",
    options: [
      { id: "ma", label: "M&A Due Diligence", icon: "briefcase" },
      { id: "erp", label: "ERP Migration", icon: "database" },
      { id: "customer", label: "Customer Research", icon: "users" },
    ],
    question: "What type of project are you working on?",
  }),
});
```

### Frontend Component Mapping

```tsx
// AG-UI component registry
const componentRegistry = {
  select_cards: SelectCardsComponent,
  rating_scale: RatingScaleComponent,
  entity_card: EntityCardComponent,
  progress_indicator: ProgressIndicatorComponent,
  rubric_preview: RubricPreviewComponent,
  agent_preview: AgentPreviewComponent,
};

// Dynamic rendering based on tool calls
function ToolCallRenderer({ toolCall }) {
  const Component = componentRegistry[toolCall.args.component];
  if (!Component) return null;

  return (
    <Component
      {...toolCall.args}
      onResponse={(value) => sendToolResponse(toolCall.id, value)}
    />
  );
}
```

---

## Session State Management

### Blueprint State Model

```typescript
interface DesignSession {
  id: string;
  projectId: string;
  createdAt: Date;

  // Conversation state
  messages: Message[];
  turnCount: number;

  // Blueprint being designed
  blueprint: {
    project?: ProjectContext;
    rubric?: RubricSpec;
    agents: AgentBlueprint[];
    executionPlan?: ExecutionPlan;
  };

  // UI state
  currentPhase: "discovery" | "rubric" | "agents" | "review" | "complete";
  activeComponents: UIComponent[];
  suggestedPrompts: SuggestedPrompt[];

  // Debug info
  debug: {
    inferredDomain?: string;
    domainConfidence: number;
    approachReasoning?: string;
    subagentActivity: SubagentActivity[];
  };
}
```

### State Sync via AG-UI

```typescript
// Full state snapshot (on connection or major change)
socket.send({
  type: "STATE_SNAPSHOT",
  snapshot: session.getFullState(),
});

// Incremental updates (JSON Patch)
socket.send({
  type: "STATE_DELTA",
  delta: [
    { op: "replace", path: "/currentPhase", value: "rubric" },
    { op: "add", path: "/blueprint/rubric", value: rubricData },
  ],
});
```

---

## Implementation Plan

### Phase 1: Server Infrastructure

1. **Create Node.js server** with Express + WebSocket
2. **Integrate Claude Agent SDK** with basic query loop
3. **Implement session management** with in-memory store
4. **Set up WebSocket message protocol** matching AG-UI

### Phase 2: Custom Tools

1. **Blueprint tools**: `update_project`, `update_rubric`, `add_agent`, etc.
2. **UI trigger tools**: `show_options`, `request_rating`, `show_preview`
3. **Validation tools**: `validate_blueprint`, `check_completeness`

### Phase 3: Subagent Architecture

1. **Domain Expert subagent** for initial analysis
2. **Rubric Designer subagent** for schema creation
3. **Agent Configurator subagent** for interview agent setup
4. **Orchestrator** (lead agent) to coordinate

### Phase 4: Frontend Integration

1. **WebSocket hook** replacing SSE-based streaming
2. **Component registry** for dynamic UI
3. **State management** with AG-UI events
4. **Rich interactive components**:
   - Domain selection cards
   - Rubric field builder
   - Agent persona configurator
   - Question flow designer
   - Blueprint preview/export

### Phase 5: Polish & Production

1. **Persistence** (Redis/PostgreSQL for sessions)
2. **Error handling** and recovery
3. **Observability** (Logfire integration)
4. **Testing** (unit, integration, e2e)

---

## File Structure

```
ClaraMap/
├── src/
│   ├── server/                          # NEW: Node.js server
│   │   ├── index.ts                     # Express + WS entry point
│   │   ├── session.ts                   # Session management
│   │   ├── agent/
│   │   │   ├── architect.ts             # Lead architect agent
│   │   │   ├── subagents/
│   │   │   │   ├── domain-expert.ts
│   │   │   │   ├── rubric-designer.ts
│   │   │   │   └── agent-configurator.ts
│   │   │   ├── tools/
│   │   │   │   ├── blueprint-tools.ts   # Blueprint manipulation
│   │   │   │   ├── ui-tools.ts          # UI component triggers
│   │   │   │   └── validation-tools.ts
│   │   │   └── prompts/
│   │   │       ├── architect.txt
│   │   │       ├── domain-expert.txt
│   │   │       └── ...
│   │   ├── protocol/
│   │   │   ├── ag-ui-events.ts          # AG-UI event types
│   │   │   └── ws-handler.ts            # WebSocket message handling
│   │   └── types/
│   │       ├── session.ts
│   │       └── blueprint.ts
│   │
│   ├── frontend/                        # Updated React frontend
│   │   ├── src/
│   │   │   ├── hooks/
│   │   │   │   └── useAgentWebSocket.ts # NEW: WebSocket hook
│   │   │   ├── components/
│   │   │   │   ├── design-assistant/
│   │   │   │   │   ├── DesignAssistantChat.tsx
│   │   │   │   │   ├── DynamicComponent.tsx    # NEW
│   │   │   │   │   ├── components/             # NEW: Dynamic UI
│   │   │   │   │   │   ├── SelectCards.tsx
│   │   │   │   │   │   ├── RatingScale.tsx
│   │   │   │   │   │   ├── RubricBuilder.tsx
│   │   │   │   │   │   ├── AgentConfigurator.tsx
│   │   │   │   │   │   └── BlueprintPreview.tsx
│   │   │   │   │   └── ...
│   │   │   └── types/
│   │   │       └── ag-ui.ts
│   │
│   └── backend/                         # Keep FastAPI for other APIs
│       ├── clara/
│       │   ├── api/                     # REST APIs (projects, blueprints)
│       │   ├── models/                  # Pydantic models
│       │   └── services/                # Business logic
│       └── ...
```

---

## Key Differences from Current Approach

| Aspect | Pydantic AI (Current) | Claude Agent SDK (Proposed) |
|--------|----------------------|----------------------------|
| **Language** | Python | TypeScript/Node.js |
| **Agent Loop** | Manual with run_stream() | Built-in query() with async iteration |
| **Tools** | @tool decorators | tool() function + custom tools |
| **Subagents** | Manual orchestration | AgentDefinition + Task tool |
| **Streaming** | SSE via FastAPI | Native WebSocket |
| **UI Events** | Manual SSE emission | AG-UI protocol |
| **State Mgmt** | Python dataclass | TypeScript interfaces |
| **Hooks** | None | Pre/PostToolUse hooks |

---

## Open Questions

1. **Python vs TypeScript**: SDK is primarily TypeScript. Do we:
   - Move entire Design Assistant to Node.js?
   - Use Python SDK (claude-agent-sdk on PyPI)?
   - Keep hybrid (Node.js for agent, Python for storage)?

2. **FastAPI Integration**: How to connect:
   - Keep FastAPI for REST APIs (projects, blueprints, interviews)?
   - Node.js server proxies to FastAPI for data persistence?
   - Or move everything to Node.js?

3. **Session Persistence**: In-memory vs Redis vs PostgreSQL?

4. **AG-UI Components**: Build custom or use existing library?

---

## Next Steps

1. [ ] Decide on language (TypeScript vs Python SDK)
2. [ ] Set up basic Node.js server with Claude Agent SDK
3. [ ] Implement minimal WebSocket → AG-UI bridge
4. [ ] Build first custom tool (e.g., `update_blueprint`)
5. [ ] Create first dynamic UI component (e.g., domain selection)
6. [ ] Iterate on subagent architecture

---

## References

- [Claude Agent SDK Documentation](https://platform.claude.com/docs/en/agent-sdk)
- [Claude Agent SDK Migration Guide](https://platform.claude.com/docs/en/agent-sdk/migration-guide)
- [AG-UI Protocol Specification](https://docs.ag-ui.com)
- [Sample Demos](/Users/mantiz/Clara-Analysis/claude-agent-sdk-demos)
- [Clara UI Interaction Flow](/Users/mantiz/Clara-Analysis/CLARA-UI-INTERACTION-FLOW.md)
