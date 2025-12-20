# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Clara is an AI-powered interview discovery platform that enables organizations to conduct structured discovery interviews at scale. A human manager orchestrates the process by configuring specialized AI interview agents via an Interview Blueprint, setting context, defining outcomes, and inviting interviewees.

## Design Documents

All design specifications are located at `/Users/mantiz/Clara-Analysis/`:

| Document | Purpose |
|----------|---------|
| `PRD.md` | Product requirements (v2.0, Phase 3 architecture) |
| `CLARA-DATA-MODEL.md` | Neo4j + PostgreSQL schema, entity resolution |
| `CLARA-UI-INTERACTION-FLOW.md` | AG-UI event flows, state models, UI components |
| `DESIGN-ASSISTANT-SDK-INTEGRATION.md` | Interview Blueprint schema, MCP integrations |
| `SYNTHESIS-PIPELINE.md` | 4-stage extraction → synthesis pipeline |
| `ANALYSIS-TEMPLATES.md` | Project type analysis frameworks |
| `ADAPTIVE-INTERVIEW-UI.md` | Dynamic UI component triggers |
| `PYDANTIC-ECOSYSTEM-ARCHITECTURE.md` | Pydantic AI/Graph/Logfire/Gateway usage |
| `TESTING-EVALUATION-FRAMEWORK.md` | Eval methodology, LLM-as-judge |
| `AGENT-DESIGN-ASSISTANT.md` | Opus-powered design helper |
| `SECURITY-GOVERNANCE.md` | Security controls, data governance, threat model |
| `DEPLOYMENT-OPTIONS.md` | SaaS to air-gapped deployment |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.12, FastAPI |
| Agent Framework | Pydantic AI with AG-UI adapter |
| Agent Coordination | A2A Protocol |
| Knowledge Graph | Neo4j 5.x |
| Relational DB | PostgreSQL 15+ |
| Real-time | AG-UI Protocol (SSE) |
| Enterprise Integrations | MCP servers (Jira, Confluence) |
| File Storage | S3 |
| Observability | Logfire |
| Frontend | React, TypeScript, @ag-ui/react, Tailwind CSS |

## Project Structure

```
ClaraMap/
├── src/
│   ├── backend/
│   │   ├── clara/                    # Main Python package
│   │   │   ├── main.py               # FastAPI app entry point
│   │   │   ├── config.py             # Settings/configuration
│   │   │   ├── api/                  # FastAPI routers
│   │   │   ├── agents/               # Pydantic AI agents
│   │   │   │   ├── interview_agent.py    # Dynamic agent configured by blueprint
│   │   │   │   ├── design_assistant.py   # Opus-powered blueprint designer
│   │   │   │   └── synthesis_agent.py    # A2A synthesis coordinator
│   │   │   ├── blueprints/           # Blueprint schema and loading
│   │   │   ├── services/             # Business logic
│   │   │   ├── models/               # Pydantic models
│   │   │   ├── graph/                # Neo4j operations
│   │   │   ├── db/                   # PostgreSQL/SQLAlchemy
│   │   │   ├── integrations/         # MCP, A2A, S3
│   │   │   └── security/             # Auth, sanitization, audit
│   │   │
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── evaluation/           # LLM evaluation suite
│   │   │
│   │   └── pyproject.toml
│   │
│   └── frontend/
│       ├── src/
│       │   ├── components/
│       │   ├── pages/
│       │   └── hooks/                # AG-UI hooks
│       ├── tests/
│       └── package.json
│
├── docs/
├── docker/
├── README.md
└── CLAUDE.md
```

## Development Commands

### Backend

```bash
cd src/backend

# Install dependencies
uv sync

# Run development server
uv run uvicorn clara.main:app --reload --port 8000

# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_interview_agent.py -v

# Type checking
uv run mypy clara

# Linting
uv run ruff check clara

# Format
uv run ruff format clara
```

### Frontend

```bash
cd src/frontend

# Install dependencies
pnpm install

# Run development server
pnpm dev

# Run tests
pnpm test

# Build
pnpm build
```

### Docker

```bash
# Start all services (Neo4j, PostgreSQL, backend, frontend)
docker-compose up -d

# View logs
docker-compose logs -f backend
```

## Key Architecture Concepts

### Interview Agents are Dynamic

Interview agents are NOT statically defined. They are configured at runtime from an Interview Blueprint created by the Design Assistant. The blueprint specifies:

- Agent persona (role, tone, expertise)
- Interview topics and goals
- Entity extraction schema
- Adaptive UI triggers
- Follow-up behavior

```python
# Example: Creating an agent from a blueprint
from clara.agents.interview_agent import InterviewAgent
from clara.blueprints.loader import load_blueprint

blueprint = await load_blueprint(blueprint_id)
agent = InterviewAgent.from_blueprint(blueprint, agent_config_id)
app = agent.to_ag_ui(deps=StateDeps(InterviewState(...)))
```

### AG-UI State Management

All real-time interview state flows through AG-UI protocol:

```python
from pydantic_ai import Agent
from pydantic_ai.ag_ui import StateDeps
from ag_ui.core import StateSnapshotEvent, StateDeltaEvent, CustomEvent

# Interview state synchronized with frontend
class InterviewState(BaseModel):
    interview_id: str
    phase: InterviewPhase
    detected_entities: list[DetectedEntity]
    topics: list[TopicCoverage]
    active_components: list[ActiveUIComponent]

# Tools return AG-UI events
@agent.tool_plain
async def detect_entity(entity_type: str, name: str, context: str) -> list:
    return [
        StateDeltaEvent(type=EventType.STATE_DELTA, delta=[...]),
        CustomEvent(type=EventType.CUSTOM, name="clara:entity_detected", value={...})
    ]
```

### Neo4j Knowledge Graph

All extracted entities link to evidence (interview quotes):

```cypher
// Entity structure with evidence chain
(:System {id, project_id, name, vendor, owner})
  -[:SUPPORTED_BY]->(:Evidence {quote, timestamp, confidence})
  -[:FROM_INTERVIEW]->(:Interview {id})

// Always scope queries by project_id
MATCH (n:System {project_id: $project_id})
```

### Entity Resolution

Uses blocking strategy (not O(n²)) and preserves relationship types during merges. See `CLARA-DATA-MODEL.md` for full implementation.

## Security Requirements

Reference `SECURITY-GOVERNANCE.md` for full details.

- **Input Sanitization**: All interviewee input through `InputSanitizer`
- **File Uploads**: Malware scanning required before storage
- **Tool Policy**: Design Assistant tools restricted via `ToolPolicyEnforcer`
- **PII Handling**: Redact from logs, classify by level
- **Audit Logging**: All data access logged to immutable store
- **Structured Rationales**: Never expose raw chain-of-thought

## Testing Strategy

- **Unit Tests**: pytest for services, models, utilities
- **Integration Tests**: Test against real Neo4j/PostgreSQL (Docker)
- **Evaluation Suite**:
  - Ground truth datasets for entity extraction
  - LLM-as-judge for conversation quality
  - Regression gates for prompt changes

## Common Patterns

### Creating a New API Endpoint

```python
# clara/api/interviews.py
from fastapi import APIRouter, Depends
from clara.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["interviews"])

@router.get("/{interview_id}")
async def get_interview(
    interview_id: str,
    service: InterviewService = Depends()
):
    return await service.get_interview(interview_id)
```

### Adding a New Entity Type to Graph

1. Define Pydantic model in `clara/models/entities.py`
2. Add node creation in `clara/graph/entities.py`
3. Update extraction schema in blueprint templates
4. Add to entity resolution service
