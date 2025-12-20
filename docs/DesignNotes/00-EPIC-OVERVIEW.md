# Epic Overview: Design Assistant & Interview Blueprint

## Related Epics

This document covers the architectural and technical design considerations for two closely related epics:

### Epic 8: Design Assistant (Opus-Powered Agent Designer)
**Goal**: Help managers design Interview Blueprints through guided dialogue

| Story | Description | Priority |
|-------|-------------|----------|
| #9 | Design Assistant Conversation Interface | Must |
| #10 | Discovery Phase & Clarifying Questions | Must |
| #11 | MCP Context Gathering Integration | Should |
| #12 | Blueprint Drafting with Reasoning | Must |
| #13 | Blueprint Refinement & Iteration | Must |
| #14 | Quality Checks & Validation | Must |
| #15 | Test Scenario Generation | Should |
| #16 | Design Session State Management | Must |

### Epic 17: Interview Blueprint Schema & Storage
**Goal**: Define and persist the Interview Blueprint data model

| Story | Description | Priority |
|-------|-------------|----------|
| #18 | Blueprint Core Schema Definition | Must |
| #19 | Agent Blueprint Schema | Must |
| #20 | Extraction Schema Definition | Must |
| #21 | Synthesis Rules Schema | Must |
| #22 | Blueprint Storage & Versioning | Must |
| #23 | Blueprint Validation Service | Must |
| #24 | Agent Factory: Blueprint to Agent Instantiation | Must |

## Business Context

Managers are not AI prompt engineers. The Design Assistant solves this by:
1. Asking clarifying questions to understand the need
2. Pulling context from enterprise tools (Jira, Confluence via MCP)
3. Generating a comprehensive Interview Blueprint with transparent reasoning
4. Validating and iterating on the design before deployment

The **Interview Blueprint** becomes the single source of truth that drives:
- Interview agent configuration (personas, questions, goals)
- Entity extraction schemas
- Synthesis pipeline rules
- Report generation templates
- Quality metrics and success criteria

## Key Design Decisions

### 1. Blueprint as Master Specification

**Decision**: The Interview Blueprint is a comprehensive JSON/YAML document that drives ALL downstream systems.

**Rationale**:
- Single source of truth avoids configuration drift
- Enables version control and audit trails
- Allows non-technical review of agent configuration
- Supports template/duplication workflows

**Trade-offs**:
- Blueprint schema is complex (many nested components)
- Schema changes require migration strategy
- Larger payload size vs. normalized database storage

### 2. Opus for Design, Sonnet/Haiku for Execution

**Decision**: Use Claude Opus for the Design Assistant, but Sonnet/Haiku for actual interview agents.

**Rationale**:
- Opus has superior reasoning for complex design decisions
- Design is one-time cost (~$8 per agent design)
- Interviews are high-volume, cost-sensitive operations
- Separation allows model selection per agent

**Trade-offs**:
- Higher API costs during design phase
- Need to validate Opus output works well with Sonnet/Haiku

### 3. AG-UI for Real-Time Design Sessions

**Decision**: Use AG-UI Protocol (SSE) for Design Assistant conversation.

**Rationale**:
- Streaming responses for better UX
- State synchronization keeps UI in sync with design state
- Same protocol used for interviews (consistency)
- Built-in support in Pydantic AI

**Trade-offs**:
- SSE limitations (unidirectional server-to-client)
- Need WebSocket for bidirectional manager input
- State reconciliation complexity

### 4. MCP Integration is Optional but Valuable

**Decision**: MCP context gathering is "Should" priority, not "Must".

**Rationale**:
- Core Design Assistant works without external context
- MCP adds significant value when available
- Enterprise integrations vary widely
- Graceful degradation is essential

**Trade-offs**:
- Two code paths (with/without MCP)
- Design quality may vary based on available context

## Implementation Dependencies

```
                              ┌────────────────────┐
                              │ Epic 17: Blueprint │
                              │ Schema & Storage   │
                              └─────────┬──────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
              ┌─────────▼─────────┐           ┌────────▼────────┐
              │ #18 Core Schema   │           │ #22 Storage &   │
              │ Definition        │           │ Versioning      │
              └─────────┬─────────┘           └────────┬────────┘
                        │                              │
        ┌───────────────┼───────────────┐              │
        │               │               │              │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐      │
│ #19 Agent     │ │ #20 Extract│ │ #21 Synthesis │      │
│ Blueprint     │ │ Schema    │ │ Rules Schema  │      │
└───────┬───────┘ └─────┬─────┘ └───────┬───────┘      │
        │               │               │              │
        └───────────────┼───────────────┘              │
                        │                              │
              ┌─────────▼─────────┐           ┌────────▼────────┐
              │ #23 Blueprint     │           │ #24 Agent       │
              │ Validation        │◄──────────│ Factory         │
              └───────────────────┘           └─────────────────┘
                        │
                        │ Epic 8 depends on Epic 17
                        ▼
              ┌─────────────────────┐
              │ Epic 8: Design      │
              │ Assistant           │
              └─────────┬───────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐
│ #9 Conversa-  │ │ #16 State │ │ #11 MCP       │
│ tion Interface│ │ Management│ │ Integration   │
└───────┬───────┘ └─────┬─────┘ └───────────────┘
        │               │
┌───────▼───────┐ ┌─────▼─────┐
│ #10 Discovery │ │ #12 Draft │
│ Phase         │ │ w/Reasoning│
└───────┬───────┘ └─────┬─────┘
        │               │
┌───────▼───────┐ ┌─────▼─────┐
│ #13 Refine-   │ │ #14 Quality│
│ ment          │ │ Checks    │
└───────┬───────┘ └─────┬─────┘
        │               │
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │ #15 Test      │
        │ Scenarios     │
        └───────────────┘
```

## Recommended Implementation Order

### Phase 1: Foundation (Epic 17 - Blueprint Schema)
1. **#18 Blueprint Core Schema** - Define ProjectContext, SourceContext base models
2. **#19 Agent Blueprint Schema** - PersonaSpec, GoalSpec, QuestionSpec models
3. **#20 Extraction Schema** - EntitySpec, FieldSpec, RelationshipSpec
4. **#21 Synthesis Rules** - ResolutionRule, CorrelationRule, AnalysisFramework
5. **#22 Storage & Versioning** - Database models, CRUD operations
6. **#23 Validation Service** - Schema validation, quality scoring
7. **#24 Agent Factory** - Transform blueprint to runtime agent config

### Phase 2: Design Assistant Core (Epic 8)
8. **#16 State Management** - DesignSession model, persistence
9. **#9 Conversation Interface** - API endpoints, WebSocket handler
10. **#10 Discovery Phase** - Discovery agent, clarifying questions
11. **#12 Blueprint Drafting** - Opus design agent, reasoning capture

### Phase 3: Refinement & Quality (Epic 8)
12. **#13 Refinement** - Iteration loop, change tracking
13. **#14 Quality Checks** - Automated validation, scoring
14. **#15 Test Scenarios** - Persona generation, edge case coverage

### Phase 4: Enterprise Integration (Epic 8)
15. **#11 MCP Context** - Jira, Confluence, org structure integration

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Design completion time | < 30 min | Session timestamps |
| Clarifying questions asked | 3-5 | Conversation analysis |
| Quality score threshold | >= 70 | Blueprint validation |
| Blueprint-to-agent success | 100% | Agent factory tests |
| MCP context utilization | > 50% | Context usage tracking |

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Complex schema versioning | High | Semantic versioning, migrations |
| Opus reasoning quality | Medium | Human review checkpoints |
| MCP integration failures | Low | Graceful degradation |
| Blueprint validation gaps | Medium | Comprehensive test suite |
| State management complexity | Medium | Clear phase transitions |

## Related Documents

- `/Users/mantiz/Clara-Analysis/DESIGN-ASSISTANT-SDK-INTEGRATION.md`
- `/Users/mantiz/Clara-Analysis/AGENT-DESIGN-ASSISTANT.md`
- `/Users/mantiz/Clara-Analysis/PYDANTIC-ECOSYSTEM-ARCHITECTURE.md`
- `/Users/mantiz/Clara-Analysis/PRD.md` (Section 5.2)
