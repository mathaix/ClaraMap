# Thin Orchestrator Architecture

## Overview

This document describes the refactored orchestrator pattern for Clara's Design Assistant.
The key insight is that **the orchestrator should only route between phases** - all
conversation logic lives in the individual phase agents.

## Current vs. Proposed Architecture

### Current (Monolithic)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DesignAssistantSession                       │
│                        (~1000 lines)                            │
├─────────────────────────────────────────────────────────────────┤
│  - Session state management                                     │
│  - Subagent definitions (inline prompts)                        │
│  - Hook handling for UI events                                  │
│  - Router/structured output decision logic                      │
│  - Message processing & streaming                               │
│  - Phase transition detection                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Proposed (Thin Orchestrator + Phase Agents)

```
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                            │
│                         (~100 lines)                            │
├─────────────────────────────────────────────────────────────────┤
│  ONLY:                                                          │
│  1. Look up current phase from session state                    │
│  2. Route message to the correct phase agent                    │
│  3. Stream events from the phase agent                          │
│  4. Detect phase_transition events and update session           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Phase 1 Agent  │  │  Phase 2 Agent  │  │  Phase 3 Agent  │
│  Goal Discovery │  │  Agent Config   │  │  Blueprint      │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ - Own prompt    │  │ - Own prompt    │  │ - Own prompt    │
│ - Own tools     │  │ - Own tools     │  │ - Own tools     │
│ - Own hooks     │  │ - Own hooks     │  │ - Own hooks     │
│ - Transition    │  │ - Transition    │  │ - Transition    │
│   logic         │  │   logic         │  │   logic         │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Shared Context │
                    │  (Session State)│
                    ├─────────────────┤
                    │ - phase         │
                    │ - goal_summary  │
                    │ - agent_config  │
                    │ - blueprint     │
                    │ - entities      │
                    │ - agents        │
                    └─────────────────┘
```

## Benefits

1. **Single Responsibility**: Orchestrator only routes, agents only converse
2. **Testability**: Each phase agent can be tested in isolation
3. **Maintainability**: Changes to one phase don't affect others
4. **Readability**: Clear separation of concerns
5. **Flexibility**: Easy to add new phases or modify existing ones

## File Structure

```
clara/agents/
├── orchestrator.py          # Thin routing layer (~100 lines)
├── phase_agents/
│   ├── __init__.py
│   ├── base.py              # BasePhaseAgent class
│   ├── goal_understanding.py    # Phase 1
│   ├── agent_configuration.py   # Phase 2
│   └── blueprint_design.py      # Phase 3
├── tools.py                 # MCP tools (shared)
├── router.py                # UI routing logic (optional fallback)
├── structured_output.py     # Structured output parsing
└── prompts/                 # Prompt templates (unchanged)
```

## Implementation Details

### BasePhaseAgent

```python
class BasePhaseAgent(ABC):
    """Base class for phase agents."""

    phase: str  # Phase identifier
    tools: list[str]  # Tools available to this phase

    @abstractmethod
    def get_prompt(self, session_state: dict) -> str:
        """Get the hydrated prompt for this phase."""
        pass

    async def handle_message(
        self,
        message: str,
        session: DesignSessionState,
        client: ClaudeSDKClient,
    ) -> AsyncIterator[AGUIEvent]:
        """Process a message and yield AG-UI events."""
        pass

    def should_transition(self, event: AGUIEvent) -> str | None:
        """Check if we should transition to another phase.
        Returns the target phase name or None.
        """
        pass
```

### Orchestrator

```python
class DesignOrchestrator:
    """Thin orchestrator that routes to phase agents."""

    agents: dict[str, BasePhaseAgent] = {
        "goal_understanding": GoalUnderstandingAgent(),
        "agent_configuration": AgentConfigurationAgent(),
        "blueprint_design": BlueprintDesignAgent(),
    }

    async def handle_message(
        self,
        message: str,
        session: DesignSessionState,
    ) -> AsyncIterator[AGUIEvent]:
        """Route message to the appropriate phase agent."""

        # 1. Get current phase agent
        agent = self.agents[session.phase.value]

        # 2. Stream events from the agent
        async for event in agent.handle_message(message, session, self.client):
            # 3. Check for phase transition
            if target := agent.should_transition(event):
                session.phase = DesignPhase(target)
                yield AGUIEvent(type="STATE_SNAPSHOT", data={...})

            yield event
```

### Phase Transition Flow

Phase transitions happen via the `mcp__clara__phase` tool:

1. Phase agent calls `mcp__clara__phase({"phase": "next_phase"})`
2. Tool updates session state and returns success
3. Agent's turn ends naturally
4. Next message comes in
5. Orchestrator reads session.phase and routes to the new agent

The orchestrator does NOT need to detect transitions mid-stream because:
- Tools update session state synchronously
- The phase change is already persisted before the agent turn ends
- Next turn naturally goes to the new phase

### Hooks

Each phase agent can define its own hooks:

```python
class GoalUnderstandingAgent(BasePhaseAgent):
    def get_hooks(self) -> dict:
        """Get hooks for this phase."""
        return {
            'PreToolUse': [
                HookMatcher(
                    matcher="mcp__clara__ask",
                    hooks=[self._on_ask_tool]
                )
            ]
        }
```

The orchestrator merges hooks from the active phase agent when creating the client.

### Session State Flow

Session state is managed by `tools.py` and flows through MCP tools:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Message Flow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User message arrives                                        │
│                                                                 │
│  2. Orchestrator reads session.phase                            │
│                                                                 │
│  3. Routes to phase agent                                       │
│                                                                 │
│  4. Agent calls MCP tools:                                      │
│     - mcp__clara__ask          → emits CUSTOM event             │
│     - mcp__clara__save_goal    → updates session state          │
│     - mcp__clara__phase        → updates session.phase          │
│                                                                 │
│  5. Agent turn ends                                             │
│                                                                 │
│  6. Orchestrator emits STATE_SNAPSHOT                           │
│                                                                 │
│  7. Next message uses updated session.phase                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Migration Strategy

1. **Create BasePhaseAgent** - Define the interface
2. **Extract Phase 1** - Move goal understanding logic
3. **Extract Phase 2** - Move agent configuration logic
4. **Extract Phase 3** - Move blueprint design logic
5. **Create Orchestrator** - Wire everything together
6. **Update DesignAssistantSession** - Delegate to orchestrator
7. **Test each phase** - Verify behavior preserved
8. **Remove old code** - Clean up DesignAssistantSession

## Open Questions

1. **Should each phase agent own its SDK client instance?**
   - Option A: Share one client, reconfigure for each phase
   - Option B: Each phase agent creates its own client
   - Recommendation: Option A for simplicity

2. **How to handle restored sessions?**
   - Restoration context is already built in orchestrator
   - Phase agents don't need special handling

3. **Should router.py be per-phase?**
   - Currently router.py handles UI component inference
   - Could be moved into phase agents or kept shared
   - Recommendation: Keep shared for now, refactor later if needed
