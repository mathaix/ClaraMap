# Design Assistant Architecture

## Overview

The Design Assistant is an Opus-powered conversational agent that helps managers create Interview Blueprints through guided dialogue, transparent reasoning, and optional MCP context integration.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DESIGN ASSISTANT SYSTEM                              │
│                                                                           │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐  │
│  │  Manager UI      │     │   FastAPI        │     │  Claude Opus     │  │
│  │  (React)         │◄───►│   Backend        │◄───►│  (Reasoning)     │  │
│  └──────────────────┘     └────────┬─────────┘     └──────────────────┘  │
│           │                        │                         │            │
│           │ AG-UI/WebSocket        │ Session State           │ MCP        │
│           │                        │                         │            │
│  ┌────────▼─────────┐     ┌────────▼─────────┐     ┌────────▼─────────┐  │
│  │ Conversation     │     │  Design Session  │     │  Context         │  │
│  │ Interface        │     │  Store (Redis)   │     │  Gatherer        │  │
│  │                  │     │                  │     │  (Jira/Conf)     │  │
│  └──────────────────┘     └────────┬─────────┘     └──────────────────┘  │
│                                    │                                      │
│                           ┌────────▼─────────┐                           │
│                           │  Blueprint       │                           │
│                           │  Generator       │                           │
│                           └────────┬─────────┘                           │
│                                    │                                      │
│                           ┌────────▼─────────┐                           │
│                           │  Blueprint       │                           │
│                           │  Storage (PG)    │                           │
│                           └──────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Design Session Lifecycle

### Phase Model

```python
# clara/models/design_session.py

class DesignPhase(StrEnum):
    """Design session phases."""
    DISCOVERY = "discovery"      # Understanding manager's needs (3-5 questions)
    CONTEXT = "context"          # Gathering MCP context (optional)
    DRAFTING = "drafting"        # Creating initial blueprint
    REFINEMENT = "refinement"    # Iterating on feedback
    VALIDATION = "validation"    # Quality checks
    FINALIZATION = "finalization"  # Final approval
```

### State Machine

```
        ┌─────────────┐
        │   START     │
        └──────┬──────┘
               │ create_session()
               ▼
        ┌─────────────┐
        │  DISCOVERY  │◄─────────────────────┐
        └──────┬──────┘                      │
               │ has_sufficient_context()     │ need_more_info()
               ▼                              │
        ┌─────────────┐                      │
        │   CONTEXT   │──────────────────────┘
        │  (optional) │
        └──────┬──────┘
               │ context_complete()
               ▼
        ┌─────────────┐
        │  DRAFTING   │
        └──────┬──────┘
               │ draft_complete()
               ▼
        ┌─────────────┐
        │ REFINEMENT  │◄─────────────────────┐
        └──────┬──────┘                      │
               │                              │ request_changes()
               ├──────────────────────────────┘
               │ approve()
               ▼
        ┌─────────────┐
        │ VALIDATION  │
        └──────┬──────┘
               │ quality_passed()
               ▼
        ┌─────────────┐
        │FINALIZATION │
        └──────┬──────┘
               │ finalize()
               ▼
        ┌─────────────┐
        │    END      │
        └─────────────┘
```

## Core Components

### DesignSession Model

```python
# clara/models/design_session.py

from pydantic import BaseModel, Field
from datetime import datetime

class DesignSessionMessage(BaseModel):
    """Single message in design conversation."""
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    phase: DesignPhase
    timestamp: datetime
    metadata: dict = Field(default_factory=dict)  # reasoning, tools used, etc.


class DesignSession(BaseModel):
    """Complete design session state."""
    id: str = Field(..., pattern=r"^ds_[a-z0-9]{16}$")
    project_id: str
    manager_id: str

    # Current state
    phase: DesignPhase = DesignPhase.DISCOVERY
    messages: list[DesignSessionMessage] = Field(default_factory=list)

    # Context gathered
    mcp_context: dict = Field(default_factory=dict)  # From Jira/Confluence
    uploaded_documents: list[dict] = Field(default_factory=list)

    # Current draft
    current_draft: InterviewBlueprint | None = None
    draft_history: list[dict] = Field(default_factory=list)  # version snapshots

    # Quality
    quality_score: float | None = None
    validation_issues: list[dict] = Field(default_factory=list)

    # Metadata
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
```

### Design Assistant Agent

```python
# clara/agents/design_assistant.py

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

class DesignAssistantDeps(BaseModel):
    """Dependencies for the design assistant."""
    session: DesignSession
    project_context: ProjectContext
    available_templates: list[str]
    mcp_servers: list[str]


# Discovery Agent (initial questions)
discovery_agent = Agent(
    'anthropic:claude-opus-4-20250514',
    deps_type=DesignAssistantDeps,
    system_prompt=DISCOVERY_SYSTEM_PROMPT
)


# Drafting Agent (creates blueprint)
drafting_agent = Agent(
    'anthropic:claude-opus-4-20250514',
    deps_type=DesignAssistantDeps,
    result_type=InterviewBlueprint,
    system_prompt=DRAFTING_SYSTEM_PROMPT
)


# Refinement Agent (iterates on feedback)
refinement_agent = Agent(
    'anthropic:claude-opus-4-20250514',
    deps_type=DesignAssistantDeps,
    result_type=RefinementResult,
    system_prompt=REFINEMENT_SYSTEM_PROMPT
)
```

### System Prompts

```python
# clara/agents/prompts/design_assistant.py

DISCOVERY_SYSTEM_PROMPT = """You are an expert interview designer starting a design session.

Your goal is to deeply understand what the manager needs BEFORE designing anything.

## Your Approach
1. Ask focused, clarifying questions (3-5 total)
2. Understand business context, interviewees, and success criteria
3. Identify constraints and sensitivities
4. Build rapport and confidence

## Information to Gather
- Business context: What project is this for? What decisions will it inform?
- Interviewees: Who will be interviewed? Roles, expertise, potential concerns?
- Information needs: What specific data must be captured?
- Constraints: Time limits, sensitivity, special considerations?
- Success criteria: How will they know interviews succeeded?

## Guidelines
- Ask ONE question at a time (avoid overwhelming)
- Be conversational but purposeful
- Acknowledge what you've learned before asking more
- Signal when you have enough to proceed

CURRENT PROJECT:
{project_context}

AVAILABLE MCP CONTEXT:
{mcp_servers}
"""

DRAFTING_SYSTEM_PROMPT = """You are creating an Interview Blueprint based on discovery.

## Your Task
Create a comprehensive Interview Blueprint that specifies:
1. Agent personas tailored to interviewees
2. Strategic questions with probing guidance
3. Precise extraction schemas
4. Synthesis rules for processing results
5. Quality metrics and success criteria

## Design Principles
- SPECIFIC over vague: "What ERP system do you use?" not "Tell me about systems"
- SEQUENCED well: Rapport before sensitive topics
- EXTRACTION-FOCUSED: Every question should yield extractable entities
- EVIDENCE-BASED: All insights must link back to interview quotes

## Required Output
Return a complete InterviewBlueprint JSON matching the schema.
Include design_rationale explaining key decisions.

CONVERSATION HISTORY:
{conversation_summary}

MCP CONTEXT:
{mcp_context}
"""

REFINEMENT_SYSTEM_PROMPT = """You are refining an Interview Blueprint based on feedback.

## Current Blueprint
{current_blueprint}

## Manager Feedback
{feedback}

## Your Task
1. Carefully consider the feedback
2. Make targeted adjustments
3. Explain what you changed and why
4. If you disagree, explain your reasoning but offer alternatives
5. Return the updated blueprint

## Guidelines
- Track changes explicitly
- Maintain design coherence
- Don't over-fit to single feedback point
- Preserve what's working well
"""
```

## API Design

### REST Endpoints

```python
# clara/api/design.py

from fastapi import APIRouter, WebSocket, Depends

router = APIRouter(prefix="/design", tags=["design"])


@router.post("/sessions")
async def create_design_session(
    project_id: str,
    manager_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DesignSessionResponse:
    """Start a new design session for a project."""


@router.get("/sessions/{session_id}")
async def get_design_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> DesignSessionResponse:
    """Get current state of a design session."""


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: str,
    message: str,
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """Send a message in the design conversation."""


@router.post("/sessions/{session_id}/approve")
async def approve_draft(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> BlueprintResponse:
    """Approve current draft and move to finalization."""


@router.post("/sessions/{session_id}/finalize")
async def finalize_blueprint(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> BlueprintResponse:
    """Finalize blueprint and create agents."""


@router.delete("/sessions/{session_id}")
async def cancel_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Cancel an in-progress design session."""
```

### WebSocket for Streaming

```python
# clara/api/design_ws.py

@router.websocket("/sessions/{session_id}/ws")
async def design_session_websocket(
    websocket: WebSocket,
    session_id: str
):
    """WebSocket for real-time design conversation."""
    await websocket.accept()

    session = await get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    try:
        while True:
            # Receive manager input
            data = await websocket.receive_json()

            if data["type"] == "message":
                # Process through design assistant
                async for event in process_message(session, data["content"]):
                    await websocket.send_json(event)

            elif data["type"] == "edit":
                # Direct edit to blueprint component
                response = await apply_edit(session, data)
                await websocket.send_json(response)

            elif data["type"] == "approve":
                # Approve current draft
                response = await approve_draft(session)
                await websocket.send_json(response)

    except WebSocketDisconnect:
        await save_session(session)  # Preserve state
```

## MCP Integration

### Context Gathering Service

```python
# clara/services/mcp_context.py

from mcp import Client

class MCPContextGatherer:
    """Gathers context from enterprise systems via MCP."""

    def __init__(self, mcp_servers: list[str]):
        self.clients = {
            server: Client(server)
            for server in mcp_servers
        }

    async def gather_project_context(
        self,
        jira_project: str | None = None,
        confluence_space: str | None = None,
        keywords: list[str] = []
    ) -> SourceContext:
        """Gather relevant context for agent design."""
        context = SourceContext()

        if jira_project and "jira" in self.clients:
            context.jira_projects.append(jira_project)
            # Get project details, epics, recent issues
            project_data = await self._fetch_jira_context(jira_project)
            context.existing_knowledge.append(project_data)

        if confluence_space and "confluence" in self.clients:
            context.confluence_spaces.append(confluence_space)
            # Search for relevant pages
            pages = await self._fetch_confluence_context(confluence_space, keywords)
            context.existing_knowledge.extend(pages)

        return context

    async def _fetch_jira_context(self, project_key: str) -> dict:
        """Fetch Jira project context."""
        client = self.clients["jira"]

        project = await client.call_tool("get_project", {"key": project_key})
        epics = await client.call_tool("search_issues", {
            "jql": f"project={project_key} AND type=Epic"
        })

        return {
            "source": "jira",
            "project": project,
            "epics": epics,
            "themes": self._extract_themes(epics)
        }
```

## Session Persistence

### Redis for Active Sessions

```python
# clara/services/session_store.py

import redis.asyncio as redis
import json

class DesignSessionStore:
    """Redis-backed session store for design sessions."""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.ttl = 86400  # 24 hours

    async def save(self, session: DesignSession) -> None:
        """Save session state to Redis."""
        key = f"design_session:{session.id}"
        await self.redis.set(
            key,
            session.model_dump_json(),
            ex=self.ttl
        )

    async def get(self, session_id: str) -> DesignSession | None:
        """Retrieve session from Redis."""
        key = f"design_session:{session_id}"
        data = await self.redis.get(key)
        if data:
            return DesignSession.model_validate_json(data)
        return None

    async def delete(self, session_id: str) -> None:
        """Remove session from Redis."""
        key = f"design_session:{session_id}"
        await self.redis.delete(key)
```

### PostgreSQL for Completed Sessions

```python
# clara/db/models.py (additions)

class DesignSessionRecord(Base):
    """Completed design session record for audit."""
    __tablename__ = "design_sessions"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    blueprint_id: Mapped[str | None] = mapped_column(ForeignKey("blueprints.id"))
    manager_id: Mapped[str] = mapped_column(String(30))

    # Conversation log (for audit/analysis)
    conversation: Mapped[list[dict]] = mapped_column(JSON)
    mcp_context_used: Mapped[dict] = mapped_column(JSON, default=dict)

    # Metrics
    duration_seconds: Mapped[int] = mapped_column(Integer)
    message_count: Mapped[int] = mapped_column(Integer)
    refinement_iterations: Mapped[int] = mapped_column(Integer)
    final_quality_score: Mapped[float | None] = mapped_column(Float)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(String(20))  # completed, cancelled, abandoned
```

## Quality Assurance

### Automated Checks

```python
# clara/services/design_quality.py

class DesignQualityChecker:
    """Automated quality checks for blueprints."""

    def check(self, blueprint: InterviewBlueprint) -> QualityResult:
        issues = []
        strengths = []

        # Structural checks
        issues.extend(self._check_completeness(blueprint))
        issues.extend(self._check_references(blueprint))

        # Content quality checks
        issues.extend(self._check_persona_quality(blueprint))
        issues.extend(self._check_question_quality(blueprint))
        issues.extend(self._check_extraction_coverage(blueprint))

        # Identify strengths
        strengths.extend(self._identify_strengths(blueprint))

        # Calculate score
        score = self._calculate_score(issues)

        return QualityResult(
            passed=score >= 70,
            score=score,
            issues=issues,
            strengths=strengths
        )

    def _check_question_quality(self, bp: InterviewBlueprint) -> list[Issue]:
        issues = []
        for agent in bp.agents:
            # Check for rapport-building questions
            categories = [q.category for q in agent.questions]
            if QuestionCategory.RAPPORT not in categories:
                issues.append(Issue(
                    severity="warning",
                    category="questions",
                    message=f"Agent {agent.name}: No rapport-building questions",
                    suggestion="Add opening questions to build trust"
                ))

            # Check question ordering
            positions = [(q.category, q.sequence_position) for q in agent.questions]
            if not self._is_well_ordered(positions):
                issues.append(Issue(
                    severity="warning",
                    category="questions",
                    message=f"Agent {agent.name}: Sensitive questions too early",
                    suggestion="Reorder to put sensitive topics after rapport"
                ))

        return issues
```

### Test Scenario Generation

```python
# clara/services/test_generator.py

class TestScenarioGenerator:
    """Generates test scenarios for designed agents."""

    async def generate(
        self,
        blueprint: InterviewBlueprint
    ) -> list[TestScenario]:
        """Generate test personas and scenarios."""

        scenarios = []

        for agent in blueprint.agents:
            # Happy path persona
            scenarios.append(await self._generate_cooperative_persona(agent))

            # Vague responder
            scenarios.append(await self._generate_vague_persona(agent))

            # Reluctant participant
            scenarios.append(await self._generate_reluctant_persona(agent))

            # Domain-specific edge cases
            scenarios.extend(await self._generate_edge_cases(agent))

        return scenarios

    async def _generate_cooperative_persona(
        self,
        agent: AgentBlueprint
    ) -> TestScenario:
        """Generate a cooperative test persona."""
        return TestScenario(
            name="Cooperative Expert",
            description="Helpful interviewee with full knowledge",
            persona_traits=["open", "detailed", "knowledgeable"],
            knowledge=self._generate_ground_truth(agent.extraction),
            expected_coverage=0.95,
            expected_extractions=self._estimate_extractions(agent)
        )
```

## Cost Considerations

| Phase | Model | Est. Tokens | Cost |
|-------|-------|-------------|------|
| Discovery (3-5 turns) | Opus | 15K | ~$1.50 |
| Context Gathering | Sonnet | 10K | ~$0.10 |
| Initial Drafting | Opus | 20K | ~$2.00 |
| Refinement (2-3 iterations) | Opus | 30K | ~$3.00 |
| Quality Check | Sonnet | 5K | ~$0.05 |
| Test Scenario Generation | Opus | 15K | ~$1.50 |
| **Total per agent design** | | ~95K | **~$8.15** |

This cost is negligible compared to the value of well-designed interview agents that conduct effective discovery.

## Implementation Stories

### Story #9: Conversation Interface
- FastAPI endpoints for session CRUD
- WebSocket handler for streaming
- Basic UI wireframe integration

### Story #10: Discovery Phase
- Discovery agent implementation
- Question sequencing logic
- Context sufficiency detection

### Story #11: MCP Context Gathering
- MCP client integration
- Jira/Confluence context fetchers
- Context summarization

### Story #12: Blueprint Drafting
- Drafting agent implementation
- Blueprint generation logic
- Reasoning capture and display

### Story #13: Refinement & Iteration
- Refinement agent implementation
- Change tracking and diff
- Iteration loop management

### Story #14: Quality Checks
- Automated validation rules
- Quality scoring algorithm
- Issue resolution suggestions

### Story #15: Test Scenario Generation
- Persona generation logic
- Ground truth synthesis
- Edge case identification

### Story #16: State Management
- Redis session store
- PostgreSQL audit records
- State recovery logic
