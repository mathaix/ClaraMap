# Technical Decisions and Trade-offs

## Overview

This document captures key technical decisions for the Design Assistant and Interview Blueprint implementation, including alternatives considered and trade-offs made.

---

## Decision 1: Blueprint Storage Format

### Decision
Store blueprints as JSONB in PostgreSQL with selective field extraction for indexing.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **JSONB (chosen)** | Simple, flexible, full-text search | Larger storage, complex querying |
| Normalized tables | Better querying, referential integrity | Complex migrations, many joins |
| Document DB (MongoDB) | Native JSON, flexible schema | Additional infrastructure |
| File storage (S3) | Simple, versioning built-in | No querying, separate index needed |

### Rationale
- Blueprints are read-mostly, updated rarely
- Full blueprint needed for agent creation (no benefit to normalization)
- PostgreSQL JSONB operators sufficient for needed queries
- Version history is separate table for audit

### Implementation Notes
```python
# Extract indexed fields on save
blueprint.project_type = content["project"]["type"]
blueprint.agent_count = len(content["agents"])
```

---

## Decision 2: Design Session State Management

### Decision
Use Redis for active sessions, PostgreSQL for completed session records.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Redis + PG (chosen)** | Fast for active, durable for history | Two stores to manage |
| PostgreSQL only | Single store, ACID | Slower for frequent updates |
| Redis only | Fast, simple | Data loss risk, no history |
| Local memory + PG | No Redis dependency | No horizontal scaling |

### Rationale
- Active sessions need sub-millisecond reads (conversation context)
- Session state changes frequently during design
- Completed sessions rarely accessed but need durability
- Redis TTL handles abandoned session cleanup

### Implementation Notes
```python
# Active session: Redis with 24h TTL
await redis.set(f"design_session:{id}", state.json(), ex=86400)

# On completion: Move to PostgreSQL
await db.execute(insert(DesignSessionRecord).values(...))
await redis.delete(f"design_session:{id}")
```

---

## Decision 3: Model Selection Strategy

### Decision
Use Opus for design reasoning, Sonnet/Haiku for interview execution.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Opus design / Sonnet exec (chosen)** | Best reasoning where needed | Higher design cost |
| Sonnet for everything | Lower cost, simpler | May miss design nuances |
| Opus for everything | Maximum quality | Prohibitively expensive at scale |
| User-selected | Maximum flexibility | Complex UX, potential misuse |

### Rationale
- Design is one-time, high-stakes (~$8/agent)
- Interviews are high-volume, cost-sensitive (~$0.15/interview)
- Opus reasoning materially improves blueprint quality
- Per-agent model selection allows cost optimization

### Cost Breakdown
| Activity | Model | Tokens | Cost |
|----------|-------|--------|------|
| Design session | Opus | ~95K | ~$8 |
| Interview (30 min) | Sonnet | ~20K | ~$0.15 |
| Interview (30 min) | Haiku | ~20K | ~$0.02 |

---

## Decision 4: MCP Integration Approach

### Decision
Make MCP context gathering optional with graceful degradation.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Optional MCP (chosen)** | Works without integrations | Two code paths |
| Required MCP | Rich context always | Blocks users without integrations |
| Deferred MCP | Simpler initial implementation | Context less useful later |
| Manual context only | No integration work | Limited value proposition |

### Rationale
- Many users won't have Jira/Confluence
- Core value proposition works without MCP
- MCP adds significant value when available
- Can progressively add integrations

### Implementation Notes
```python
# Graceful degradation
if mcp_servers:
    context = await gather_mcp_context(mcp_servers)
else:
    context = SourceContext()  # Empty but valid

# Design assistant works with or without context
blueprint = await drafting_agent.run(
    prompt,
    deps={"context": context}  # May be empty
)
```

---

## Decision 5: AG-UI vs WebSocket vs REST

### Decision
Use AG-UI Protocol (SSE) for streaming, WebSocket for bidirectional, REST for CRUD.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **AG-UI + WS + REST (chosen)** | Best fit for each use case | Multiple protocols |
| WebSocket only | Single protocol, bidirectional | Complex state management |
| REST + polling | Simple, well-understood | Poor UX for streaming |
| AG-UI only | Pydantic AI native | Limited bidirectional support |

### Rationale
- AG-UI provides native Pydantic AI streaming integration
- WebSocket needed for real-time bidirectional (manager intervention)
- REST appropriate for CRUD operations (sessions, blueprints)
- Protocols complement each other

### Protocol Usage
| Use Case | Protocol |
|----------|----------|
| Agent text streaming | AG-UI (SSE) |
| State synchronization | AG-UI (SSE) |
| Manager intervention | WebSocket |
| Session CRUD | REST |
| Blueprint CRUD | REST |

---

## Decision 6: Blueprint Versioning Strategy

### Decision
Semantic versioning (MAJOR.MINOR.PATCH) with immutable version records.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Semantic (chosen)** | Clear meaning, familiar | Requires judgment |
| Auto-increment | Simple, deterministic | No semantic meaning |
| Hash-based | Content-addressable | Hard to compare |
| Timestamp-based | Automatic, sortable | No structure indication |

### Rationale
- Version numbers convey change significance
- MAJOR: Breaking changes to extraction schema
- MINOR: New questions, topics, agents
- PATCH: Wording changes, fixes
- Supports rollback to specific versions

### Implementation Notes
```python
def calculate_next_version(current: str, changes: ChangeSet) -> str:
    major, minor, patch = map(int, current.split("."))

    if changes.has_schema_changes:
        return f"{major + 1}.0.0"
    elif changes.has_structural_changes:
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"
```

---

## Decision 7: Entity Resolution Algorithm

### Decision
Use blocking strategy with configurable similarity thresholds per entity type.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Blocking + threshold (chosen)** | Efficient, tunable | Requires configuration |
| Pairwise comparison | Complete, accurate | O(n²) doesn't scale |
| ML-based matching | Adaptive, learning | Training data needed |
| Exact match only | Simple, fast | Misses variations |

### Rationale
- Blocking reduces comparison space (same name prefix, department, etc.)
- Threshold is configurable per entity type (systems stricter than people)
- Preserves relationship types during merges
- Manual review queue for low-confidence matches

### Implementation Notes
```python
# Blocking strategy
def get_blocks(entities: list[Entity]) -> dict[str, list[Entity]]:
    blocks = defaultdict(list)
    for entity in entities:
        # Block by normalized first word of name
        key = normalize(entity.name.split()[0])
        blocks[key].append(entity)
    return blocks

# Only compare within blocks
for block in blocks.values():
    for a, b in combinations(block, 2):
        if similarity(a, b) > threshold:
            merge(a, b)
```

---

## Decision 8: Quality Scoring Algorithm

### Decision
Weighted scoring with separate dimensions, 70+ threshold for deployment.

### Dimensions and Weights

| Dimension | Weight | Checks |
|-----------|--------|--------|
| Completeness | 25% | All required fields, agents, questions |
| Coherence | 20% | Cross-references valid, no orphans |
| Question Quality | 20% | Rapport questions, proper ordering |
| Extraction Coverage | 20% | Entities match goals, fields complete |
| Persona Quality | 15% | Expertise depth, handling guidance |

### Scoring Logic
```python
def calculate_score(issues: list[Issue]) -> float:
    # Start at 100
    score = 100.0

    # Deduct based on severity
    for issue in issues:
        if issue.severity == "error":
            score -= 20  # Errors are blocking
        elif issue.severity == "warning":
            score -= 5   # Warnings are concerning
        elif issue.severity == "info":
            score -= 1   # Info is minor

    return max(0, min(100, score))
```

### Thresholds
- **70+**: Ready for deployment
- **50-69**: Needs refinement
- **< 50**: Significant issues, requires rework

---

## Decision 9: Test Scenario Generation

### Decision
Generate 4 standard personas plus domain-specific edge cases per agent.

### Standard Personas

| Persona | Purpose | Traits |
|---------|---------|--------|
| Cooperative Expert | Happy path | Open, detailed, knowledgeable |
| Vague Responder | Probing test | "It depends", incomplete answers |
| Reluctant Participant | Rapport test | Guarded, minimal responses |
| Distracted User | Edge case | Topic jumps, tangents |

### Rationale
- Standard personas cover common interaction patterns
- Domain-specific edge cases from blueprint context
- Ground truth enables automated evaluation
- Reproducible test scenarios for regression

### Implementation Notes
```python
async def generate_personas(agent: AgentBlueprint) -> list[TestPersona]:
    personas = [
        generate_cooperative(agent),
        generate_vague(agent),
        generate_reluctant(agent),
        generate_distracted(agent),
    ]

    # Domain-specific from extraction schema
    for entity in agent.extraction.entities:
        if entity.name == "PainPoint":
            personas.append(generate_frustrated_user(agent))
        elif entity.name == "System":
            personas.append(generate_technical_expert(agent))

    return personas
```

---

## Decision 10: Error Handling Strategy

### Decision
Fail fast for validation errors, graceful degradation for runtime errors.

### Error Categories

| Category | Strategy | Example |
|----------|----------|---------|
| Schema validation | Fail immediately | Invalid blueprint JSON |
| Business rules | Block with explanation | Missing required agent |
| MCP failures | Degrade gracefully | Confluence unavailable |
| LLM errors | Retry with backoff | Rate limit, timeout |
| State errors | Recover or restart | Redis connection lost |

### Implementation Notes
```python
# Validation: Fail fast
try:
    blueprint = InterviewBlueprint.model_validate(data)
except ValidationError as e:
    raise HTTPException(422, detail=e.errors())

# MCP: Graceful degradation
try:
    context = await gather_mcp_context(servers)
except MCPError as e:
    logger.warning(f"MCP failed: {e}, proceeding without context")
    context = SourceContext()

# LLM: Retry with backoff
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10)
)
async def call_llm(prompt: str) -> str:
    return await agent.run(prompt)
```

---

## Open Questions

### 1. Blueprint Schema Migrations
**Question**: How to handle schema changes across blueprint versions?

**Options**:
- Lazy migration on read
- Eager migration on write
- Maintain multiple schema versions

**Recommendation**: Start with lazy migration, add eager if performance issues arise.

### 2. Multi-Language Support
**Question**: Should blueprints support multiple languages?

**Options**:
- English only for MVP
- Translation layer at runtime
- Separate blueprints per language

**Recommendation**: English only for MVP, design for future i18n.

### 3. Blueprint Sharing/Templates
**Question**: How should blueprint sharing work across projects?

**Options**:
- Copy on use (no linking)
- Reference with overrides
- Template library with versioning

**Recommendation**: Start with copy, add templates in future phase.

---

## Conclusion

These decisions prioritize:
1. **Simplicity** - Avoid over-engineering for MVP
2. **Flexibility** - Design for future expansion
3. **Reliability** - Graceful degradation, clear error handling
4. **Cost Awareness** - Model selection based on value
5. **Developer Experience** - Clear patterns, good observability

Document will be updated as implementation progresses and new decisions are made.
