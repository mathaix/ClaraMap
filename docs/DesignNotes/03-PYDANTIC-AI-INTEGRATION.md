# Pydantic AI Ecosystem Integration

## Overview

Clara uses the Pydantic ecosystem for all AI agent functionality. This document details how each component fits into the architecture.

## Ecosystem Components

| Component | Purpose | Clara Usage |
|-----------|---------|-------------|
| **Pydantic AI** | Agent framework | Interview agents, Design Assistant |
| **Pydantic Graph** | State machines | Interview flow, Synthesis pipeline |
| **Logfire** | Observability | Tracing, cost tracking, debugging |
| **Pydantic AI Gateway** | LLM routing | Multi-provider, cost limits |

## Pydantic AI Agent Patterns

### Interview Agent (Dynamic Configuration)

Unlike static agents, Clara's interview agents are configured at runtime from blueprints:

```python
# clara/agents/interview_agent.py

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from typing import Annotated


class InterviewTurn(BaseModel):
    """Structured output for each interview turn."""
    response: str
    extracted_entities: list[ExtractedEntity]
    topics_covered: list[str]
    suggested_ui_component: str | None = None
    should_wrap_up: bool = False


class InterviewDeps(BaseModel):
    """Dependencies injected into the agent."""
    interview_id: str
    interviewee_name: str
    interviewee_role: str
    agent_config: AgentConfig  # From blueprint
    conversation_history: list[dict]
    extracted_entities: list[ExtractedEntity]
    covered_topics: set[str]


class InterviewAgent:
    """Dynamically configured interview agent."""

    def __init__(self, blueprint: AgentBlueprint):
        self.blueprint = blueprint
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent[InterviewDeps, InterviewTurn]:
        """Create Pydantic AI agent from blueprint."""

        agent = Agent(
            self._get_model(),
            deps_type=InterviewDeps,
            result_type=InterviewTurn,
        )

        # Register dynamic system prompt
        @agent.system_prompt
        async def build_prompt(ctx: RunContext[InterviewDeps]) -> str:
            return self._build_system_prompt(ctx.deps)

        # Register tools based on blueprint
        self._register_tools(agent)

        return agent

    def _get_model(self) -> str:
        """Get model string from blueprint config."""
        model_map = {
            "haiku": "anthropic:claude-3-5-haiku-latest",
            "sonnet": "anthropic:claude-sonnet-4-20250514",
            "opus": "anthropic:claude-opus-4-20250514",
        }
        return model_map.get(
            self.blueprint.config.model,
            "anthropic:claude-sonnet-4-20250514"
        )

    def _build_system_prompt(self, deps: InterviewDeps) -> str:
        """Build dynamic system prompt from blueprint."""
        bp = self.blueprint

        return f"""You are an expert interviewer conducting a discovery interview.

## Your Persona
Role: {bp.persona.role}
Tone: {bp.persona.tone}
Expertise: {', '.join(bp.persona.expertise)}

Communication Style: {bp.persona.communication_style}

Rapport Building: {bp.persona.rapport_building_approach}

Handling Reluctance: {bp.persona.handling_reluctance}

## Interviewee
Name: {deps.interviewee_name}
Role: {deps.interviewee_role}

## Interview Goals (Priority Order)
{self._format_goals()}

## Questions to Cover
{self._format_questions(deps.covered_topics)}

## Extraction Targets
{self._format_extraction_guidance()}

## Already Extracted
{self._format_extracted(deps.extracted_entities)}

## Guidelines
- Build rapport before sensitive topics
- Ask one question at a time
- Probe when answers are vague or incomplete
- Use detect_entity tool when entities are mentioned
- Trigger UI components when context warrants structured input
"""

    def _register_tools(self, agent: Agent) -> None:
        """Register tools based on blueprint configuration."""

        @agent.tool
        async def detect_entity(
            ctx: RunContext[InterviewDeps],
            entity_type: str,
            name: str,
            attributes: dict,
            context: str,
            confidence: float = 0.8
        ) -> str:
            """Record an entity detected during the interview."""
            entity = ExtractedEntity(
                id=generate_id("ent"),
                type=entity_type,
                name=name,
                attributes=attributes,
                confidence=confidence,
                source_quote=context,
                timestamp=datetime.utcnow()
            )
            ctx.deps.extracted_entities.append(entity)
            return f"Recorded {entity_type}: {name}"

        @agent.tool
        async def mark_topic_covered(
            ctx: RunContext[InterviewDeps],
            topic_id: str
        ) -> str:
            """Mark an interview topic as covered."""
            ctx.deps.covered_topics.add(topic_id)
            return f"Topic {topic_id} marked as covered"

        # Only register UI tools if enabled in blueprint
        if self.blueprint.config.enable_ui_components:
            @agent.tool
            async def trigger_ui_component(
                ctx: RunContext[InterviewDeps],
                component_type: str,
                data: dict
            ) -> str:
                """Trigger an adaptive UI component."""
                # This will be handled by AG-UI event system
                return f"UI component {component_type} triggered"

        # Only register file upload if enabled
        if self.blueprint.config.file_upload_enabled:
            @agent.tool
            async def request_file_upload(
                ctx: RunContext[InterviewDeps],
                prompt: str,
                file_types: list[str]
            ) -> str:
                """Request the interviewee to upload a file."""
                return f"File upload requested: {prompt}"
```

### Agent Factory

Transform blueprints into runtime agents:

```python
# clara/services/agent_factory.py

from clara.agents.interview_agent import InterviewAgent
from clara.models.blueprint import AgentBlueprint, InterviewBlueprint


class AgentFactory:
    """Creates interview agents from blueprints."""

    def create_from_blueprint(
        self,
        blueprint: InterviewBlueprint,
        agent_id: str
    ) -> InterviewAgent:
        """Create a configured interview agent."""

        # Find agent blueprint by ID
        agent_bp = next(
            (a for a in blueprint.agents if a.id == agent_id),
            None
        )
        if not agent_bp:
            raise ValueError(f"Agent {agent_id} not found in blueprint")

        # Create agent instance
        agent = InterviewAgent(agent_bp)

        # Validate agent configuration
        self._validate_agent(agent)

        return agent

    def _validate_agent(self, agent: InterviewAgent) -> None:
        """Validate agent is properly configured."""
        # Test system prompt generation
        test_deps = InterviewDeps(
            interview_id="test",
            interviewee_name="Test User",
            interviewee_role="Test Role",
            agent_config=agent.blueprint.config,
            conversation_history=[],
            extracted_entities=[],
            covered_topics=set()
        )

        prompt = agent._build_system_prompt(test_deps)
        if len(prompt) < 500:
            raise ValueError("System prompt too short - may be misconfigured")
```

## Pydantic Graph for State Machines

### Interview Flow Graph

```python
# clara/graphs/interview_graph.py

from dataclasses import dataclass
from pydantic_graph import BaseNode, End, Graph


@dataclass
class InterviewState:
    """State persisted across interview turns."""
    interview_id: str
    agent_config: dict
    interviewee: dict

    # Conversation
    transcript: list[dict]
    turn_count: int = 0

    # Extraction
    extracted_entities: list[dict]
    covered_topics: set[str]

    # Status
    status: str = "in_progress"  # invited, in_progress, paused, completed
    phase: str = "introduction"  # introduction, discovery, deep_dive, wrap_up


@dataclass
class WelcomeNode(BaseNode[InterviewState]):
    """Start interview with welcome message."""

    async def run(self, ctx) -> "DiscoveryNode":
        # Generate welcome using agent
        response = await interview_agent.run(
            "Begin with a warm introduction",
            deps=build_deps(ctx.state)
        )

        ctx.state.transcript.append({
            "role": "assistant",
            "content": response.data.response,
            "turn": ctx.state.turn_count
        })
        ctx.state.turn_count += 1
        ctx.state.phase = "discovery"

        return DiscoveryNode()


@dataclass
class DiscoveryNode(BaseNode[InterviewState]):
    """Main interview loop - process user messages."""
    user_message: str = ""

    async def run(self, ctx) -> "DiscoveryNode | WrapUpNode | End[InterviewState]":
        # Add user message
        if self.user_message:
            ctx.state.transcript.append({
                "role": "user",
                "content": self.user_message,
                "turn": ctx.state.turn_count
            })

        # Check if should wrap up
        if self._should_wrap_up(ctx.state):
            return WrapUpNode()

        # Get agent response
        response = await interview_agent.run(
            self.user_message,
            deps=build_deps(ctx.state)
        )

        # Update state
        ctx.state.transcript.append({
            "role": "assistant",
            "content": response.data.response,
            "turn": ctx.state.turn_count
        })

        for entity in response.data.extracted_entities:
            ctx.state.extracted_entities.append(entity.model_dump())

        ctx.state.covered_topics.update(response.data.topics_covered)
        ctx.state.turn_count += 1

        if response.data.should_wrap_up:
            return WrapUpNode()

        # Wait for next user input (graph pauses here)
        return DiscoveryNode()

    def _should_wrap_up(self, state: InterviewState) -> bool:
        max_turns = state.agent_config.get("max_turns", 50)
        required_coverage = 0.8

        coverage = len(state.covered_topics) / len(
            state.agent_config.get("topics", []) or [1]
        )

        return (
            state.turn_count >= max_turns or
            coverage >= required_coverage
        )


@dataclass
class WrapUpNode(BaseNode[InterviewState]):
    """Conclude the interview."""

    async def run(self, ctx) -> End[InterviewState]:
        response = await interview_agent.run(
            "Please wrap up the interview gracefully",
            deps=build_deps(ctx.state)
        )

        ctx.state.transcript.append({
            "role": "assistant",
            "content": response.data.response,
            "turn": ctx.state.turn_count
        })
        ctx.state.status = "completed"
        ctx.state.phase = "wrap_up"

        return End(ctx.state)


# Build the graph
interview_graph = Graph(
    nodes=[WelcomeNode, DiscoveryNode, WrapUpNode],
    state_type=InterviewState
)
```

### Graph Persistence

```python
# clara/services/interview_runner.py

class InterviewRunner:
    """Runs interview graphs with persistence."""

    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session

    async def start_interview(
        self,
        interview_id: str,
        agent: InterviewAgent,
        interviewee: dict
    ) -> InterviewState:
        """Start a new interview."""
        state = InterviewState(
            interview_id=interview_id,
            agent_config=agent.blueprint.config.model_dump(),
            interviewee=interviewee,
            transcript=[],
            extracted_entities=[],
            covered_topics=set()
        )

        # Run welcome node
        result = await interview_graph.run(WelcomeNode(), state=state)

        # Persist state
        await self._save_state(result.state)

        return result.state

    async def process_message(
        self,
        interview_id: str,
        message: str
    ) -> InterviewState:
        """Process a user message in an interview."""
        # Load state
        state = await self._load_state(interview_id)

        # Run graph from discovery node with message
        result = await interview_graph.run(
            DiscoveryNode(user_message=message),
            state=state
        )

        # Persist updated state
        await self._save_state(result.state)

        return result.state

    async def _save_state(self, state: InterviewState) -> None:
        """Save interview state to Redis."""
        key = f"interview:{state.interview_id}"
        # Convert state to JSON-serializable format
        state_dict = {
            **state.__dict__,
            "covered_topics": list(state.covered_topics)
        }
        await self.redis.set(key, json.dumps(state_dict), ex=86400)

    async def _load_state(self, interview_id: str) -> InterviewState:
        """Load interview state from Redis."""
        key = f"interview:{interview_id}"
        data = await self.redis.get(key)
        if not data:
            raise ValueError(f"Interview {interview_id} not found")

        state_dict = json.loads(data)
        state_dict["covered_topics"] = set(state_dict["covered_topics"])
        return InterviewState(**state_dict)
```

## Logfire Integration

### Basic Setup

```python
# clara/main.py

import logfire

# Initialize Logfire
logfire.configure(
    service_name="clara",
    environment=settings.environment,
)

# Instrument Pydantic AI (auto-traces all LLM calls)
logfire.instrument_pydantic_ai()

# Instrument FastAPI
logfire.instrument_fastapi(app)

# Instrument SQLAlchemy
logfire.instrument_sqlalchemy(engine)

# Instrument Redis
logfire.instrument_redis(redis_client)
```

### Custom Spans

```python
# clara/services/interview_service.py

import logfire

class InterviewService:
    """Service for managing interviews."""

    async def process_turn(
        self,
        interview_id: str,
        message: str
    ) -> InterviewTurn:
        # Custom span for business logic
        with logfire.span(
            "interview_turn",
            interview_id=interview_id,
            message_length=len(message)
        ):
            # Load interview
            state = await self.runner.load_state(interview_id)

            logfire.info(
                "processing_message",
                turn_number=state.turn_count,
                covered_topics=len(state.covered_topics)
            )

            # Process through graph
            result = await self.runner.process_message(interview_id, message)

            # Log extraction results
            logfire.info(
                "entities_extracted",
                count=len(result.extracted_entities),
                types=[e["type"] for e in result.extracted_entities]
            )

            return result
```

### Cost Tracking Queries

```sql
-- Cost per project (Logfire SQL)
SELECT
    attributes->>'project_id' as project_id,
    SUM(CAST(attributes->>'cost_usd' AS FLOAT)) as total_cost,
    COUNT(*) as llm_calls
FROM spans
WHERE span_name = 'pydantic_ai.llm_call'
AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY project_id
ORDER BY total_cost DESC;

-- Interview completion funnel
SELECT
    attributes->>'status' as status,
    COUNT(*) as count
FROM spans
WHERE span_name = 'interview_session'
GROUP BY status;

-- Slow LLM calls
SELECT
    span_id,
    duration_ms,
    attributes->>'model' as model,
    attributes->>'prompt_tokens' as prompt_tokens,
    attributes->>'completion_tokens' as completion_tokens
FROM spans
WHERE span_name = 'pydantic_ai.llm_call'
AND duration_ms > 5000
ORDER BY duration_ms DESC
LIMIT 20;
```

## AG-UI Protocol Integration

### Interview Agent with AG-UI

```python
# clara/agents/interview_agent_agui.py

from pydantic_ai import Agent
from pydantic_ai.ag_ui import StateDeps
from ag_ui.core import (
    EventType,
    StateSnapshotEvent,
    StateDeltaEvent,
    CustomEvent,
)


# Define state for AG-UI sync
class AGUIInterviewState(BaseModel):
    """State synchronized with frontend via AG-UI."""
    interview_id: str
    phase: str
    turn_count: int
    detected_entities: list[dict]
    topics: list[dict]  # {id, name, covered: bool, coverage_percent}
    active_components: list[dict]
    overall_progress: float


# Create agent with AG-UI integration
interview_agent = Agent(
    'anthropic:claude-sonnet-4-20250514',
    deps_type=StateDeps[AGUIInterviewState],
)


@interview_agent.tool_plain
async def detect_entity(
    entity_type: str,
    name: str,
    attributes: dict,
    context: str,
    confidence: float = 0.8
) -> list:
    """Detect entity and emit AG-UI events."""
    entity = {
        "id": generate_id("ent"),
        "type": entity_type,
        "name": name,
        "attributes": attributes,
        "confidence": confidence,
        "source_quote": context,
    }

    return [
        # Update state with new entity
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[{
                "op": "add",
                "path": "/detected_entities/-",
                "value": entity
            }]
        ),
        # Emit custom event for UI highlight
        CustomEvent(
            type=EventType.CUSTOM,
            name="clara:entity_detected",
            value={"entity": entity, "highlight": True}
        )
    ]


@interview_agent.tool_plain
async def trigger_ui_component(
    component_type: str,
    data: dict
) -> CustomEvent:
    """Trigger adaptive UI component."""
    component = {
        "id": generate_id("comp"),
        "type": component_type,
        "data": data,
        "visible": True
    }

    return CustomEvent(
        type=EventType.CUSTOM,
        name="clara:ui_component_trigger",
        value=component
    )


# Create AG-UI endpoint
def create_agui_app(state: AGUIInterviewState):
    """Create AG-UI app for interview."""
    return interview_agent.to_ag_ui(
        deps=StateDeps(state)
    )
```

### FastAPI AG-UI Endpoint

```python
# clara/api/interview_agui.py

from fastapi import APIRouter
from pydantic_ai.ag_ui import create_endpoint

router = APIRouter()


@router.post("/interview/{interview_id}/agui")
async def interview_agui_endpoint(
    interview_id: str,
    request: Request
):
    """AG-UI endpoint for interview agent."""
    # Load interview state
    state = await load_interview_state(interview_id)

    # Create AG-UI app
    app = create_agui_app(state)

    # Create endpoint handler
    handler = create_endpoint(app)

    # Process request
    return await handler(request)
```

## Model Selection Strategy

### Per-Agent Model Configuration

```python
# clara/models/blueprint/agent.py

class ModelConfig(BaseModel):
    """Model configuration for an agent."""
    primary: str = "sonnet"  # haiku, sonnet, opus
    fallback: str | None = "haiku"
    max_tokens: int = 4096
    temperature: float = 0.7

    @property
    def model_string(self) -> str:
        """Get Pydantic AI model string."""
        models = {
            "haiku": "anthropic:claude-3-5-haiku-latest",
            "sonnet": "anthropic:claude-sonnet-4-20250514",
            "opus": "anthropic:claude-opus-4-20250514",
        }
        return models[self.primary]
```

### Cost-Aware Model Selection

```python
# clara/services/model_selector.py

class ModelSelector:
    """Selects models based on context and budget."""

    def select_for_interview(
        self,
        blueprint: AgentBlueprint,
        remaining_budget: float
    ) -> str:
        """Select appropriate model for interview."""

        # Use blueprint default
        default = blueprint.config.model

        # Check if budget allows
        estimated_cost = self._estimate_interview_cost(default)
        if estimated_cost > remaining_budget:
            # Fallback to cheaper model
            return "haiku"

        return default

    def _estimate_interview_cost(self, model: str) -> float:
        """Estimate cost for a typical interview."""
        costs_per_1k_tokens = {
            "haiku": 0.001,
            "sonnet": 0.003,
            "opus": 0.015,
        }

        # Estimate ~20K tokens per interview
        return costs_per_1k_tokens.get(model, 0.003) * 20
```

## Testing Pydantic AI Agents

```python
# tests/unit/test_interview_agent.py

import pytest
from pydantic_ai.testing import TestModel


class TestInterviewAgent:
    """Tests for interview agent."""

    @pytest.fixture
    def mock_model(self):
        """Create mock model for testing."""
        return TestModel()

    @pytest.fixture
    def agent(self, mock_model, sample_blueprint):
        """Create agent with mock model."""
        agent = InterviewAgent(sample_blueprint)
        agent.agent.model = mock_model
        return agent

    async def test_entity_detection_tool(self, agent):
        """Test entity detection creates proper output."""
        deps = InterviewDeps(
            interview_id="test",
            interviewee_name="John",
            interviewee_role="Engineer",
            agent_config={},
            conversation_history=[],
            extracted_entities=[],
            covered_topics=set()
        )

        # Run agent
        result = await agent.agent.run(
            "We use SAP for our ERP system",
            deps=deps
        )

        # Check entity was extracted
        assert len(deps.extracted_entities) == 1
        assert deps.extracted_entities[0].type == "system"
        assert deps.extracted_entities[0].name == "SAP"

    async def test_topic_coverage_tracking(self, agent):
        """Test topic coverage is tracked."""
        deps = InterviewDeps(
            interview_id="test",
            interviewee_name="John",
            interviewee_role="Engineer",
            agent_config={"topics": ["systems", "integrations"]},
            conversation_history=[],
            extracted_entities=[],
            covered_topics=set()
        )

        # Simulate conversation
        await agent.agent.run("Let me tell you about our systems...", deps=deps)

        # Check topic was marked
        assert "systems" in deps.covered_topics
```
