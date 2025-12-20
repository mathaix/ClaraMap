# Interview Blueprint Schema Design

## Overview

The Interview Blueprint is a comprehensive specification that drives all downstream Clara systems. This document details the schema design, storage considerations, and implementation approach.

## Schema Architecture

The blueprint is structured in layers, from project context down to individual field specifications:

```
InterviewBlueprint
├── metadata (id, version, timestamps)
├── project: ProjectContext
│   ├── basic info (name, type, description)
│   ├── business_context, decision_to_inform
│   └── source_context: SourceContext (MCP data)
│
├── agents: list[AgentBlueprint]
│   ├── target_interviewees: IntervieweeSpec
│   ├── persona: PersonaSpec
│   ├── goals: list[GoalSpec]
│   ├── questions: list[QuestionSpec]
│   ├── question_flow: QuestionFlowSpec
│   ├── extraction: ExtractionSpec
│   │   ├── entities: list[EntitySpec]
│   │   │   └── fields: list[FieldSpec]
│   │   ├── relationships: list[RelationshipSpec]
│   │   └── sentiments: list[SentimentSpec]
│   ├── config: AgentConfig
│   └── design_rationale: DesignRationale
│
├── synthesis: SynthesisBlueprint
│   ├── entity_resolution_rules: list[ResolutionRule]
│   ├── correlation_rules: list[CorrelationRule]
│   ├── analysis_frameworks: list[AnalysisFramework]
│   └── conflict_resolution: ConflictResolutionSpec
│
├── analysis: AnalysisBlueprint
│   ├── deliverables: list[DeliverableSpec]
│   ├── success_metrics: list[MetricSpec]
│   └── report_templates: list[ReportTemplate]
│
├── quality: QualitySpec
│   ├── interview_quality_thresholds
│   ├── extraction_quality_thresholds
│   ├── coverage_requirements
│   └── test_scenarios: list[TestScenario]
│
└── integrations: IntegrationSpec
    ├── output_destinations
    ├── notifications
    └── webhooks
```

## Core Pydantic Models

### Blueprint Metadata

```python
# clara/models/blueprint/core.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
from enum import StrEnum


class ProjectType(StrEnum):
    MA_DUE_DILIGENCE = "ma_due_diligence"
    ERP_DISCOVERY = "erp_discovery"
    PROCESS_OPTIMIZATION = "process_optimization"
    COMPLIANCE_AUDIT = "compliance_audit"
    KNOWLEDGE_CAPTURE = "knowledge_capture"
    VENDOR_ASSESSMENT = "vendor_assessment"
    CUSTOMER_RESEARCH = "customer_research"
    CUSTOM = "custom"


class BlueprintMetadata(BaseModel):
    """Blueprint identification and versioning."""
    id: str = Field(..., pattern=r"^bp_[a-z0-9]{16}$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    created_at: datetime
    updated_at: datetime
    created_by: str  # Manager who approved
    designed_by: str = "opus"  # AI that designed it
    project_id: str = Field(..., pattern=r"^proj_[a-z0-9]{16}$")
```

### Project Context

```python
# clara/models/blueprint/project.py

class SourceContext(BaseModel):
    """Context gathered from MCP integrations."""
    jira_projects: list[str] = Field(default_factory=list)
    confluence_spaces: list[str] = Field(default_factory=list)
    key_documents: list[dict] = Field(default_factory=list)  # {name, path, summary}
    org_context: dict = Field(default_factory=dict)
    existing_knowledge: list[dict] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ProjectContext(BaseModel):
    """Project-level context for the interview initiative."""
    name: str = Field(..., min_length=1, max_length=200)
    type: ProjectType
    description: str = Field(..., min_length=10, max_length=5000)
    business_context: str  # Why this project exists
    decision_to_inform: str  # What decisions will this inform
    stakeholders: list[str] = Field(default_factory=list)
    timeline: str | None = None
    constraints: list[str] = Field(default_factory=list)
    source_context: SourceContext = Field(default_factory=SourceContext)
```

### Agent Blueprint

```python
# clara/models/blueprint/agent.py

class IntervieweeSpec(BaseModel):
    """Who should be interviewed by this agent."""
    roles: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    expertise_areas: list[str] = Field(default_factory=list)
    suggested_individuals: list[dict] = Field(default_factory=list)
    count_target: int = Field(ge=1, le=1000)
    selection_criteria: str | None = None


class PersonaSpec(BaseModel):
    """Agent persona specification."""
    role: str = Field(..., min_length=1, max_length=100)
    tone: str = Field(..., min_length=1, max_length=500)
    expertise: list[str] = Field(min_length=1)
    communication_style: str
    rapport_building_approach: str
    handling_reluctance: str


class GoalSpec(BaseModel):
    """Interview goal with success criteria."""
    id: str = Field(..., pattern=r"^goal_[a-z0-9]{8}$")
    goal: str = Field(..., min_length=10)
    priority: int = Field(ge=1, le=10)
    success_criteria: list[str] = Field(min_length=1)
    related_questions: list[str] = Field(default_factory=list)


class QuestionCategory(StrEnum):
    RAPPORT = "rapport"
    DISCOVERY = "discovery"
    PROBING = "probing"
    SENSITIVE = "sensitive"
    CLOSING = "closing"


class QuestionSpec(BaseModel):
    """Question specification with probing guidance."""
    id: str = Field(..., pattern=r"^q_[a-z0-9]{8}$")
    question: str = Field(..., min_length=10)
    purpose: str
    category: QuestionCategory
    sequence_position: int = Field(ge=1)
    probing_triggers: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    skip_conditions: list[str] = Field(default_factory=list)
    expected_entities: list[str] = Field(default_factory=list)


class QuestionFlowSpec(BaseModel):
    """How questions should flow during the interview."""
    opening_sequence: list[str] = Field(min_length=1)  # Question IDs
    core_sequence: list[str] = Field(min_length=1)
    sensitive_sequence: list[str] = Field(default_factory=list)
    closing_sequence: list[str] = Field(min_length=1)
    branching_rules: list[dict] = Field(default_factory=list)
    time_allocation: dict[str, int] = Field(default_factory=dict)
```

### Extraction Schema

```python
# clara/models/blueprint/extraction.py

class FieldType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    LIST = "list"
    DATE = "date"
    DATETIME = "datetime"


class FieldSpec(BaseModel):
    """Field within an entity."""
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    type: FieldType
    required: bool = False
    description: str
    enum_values: list[str] | None = None
    validation_rules: list[str] | None = None
    default: Any | None = None


class EntitySpec(BaseModel):
    """Entity to extract from interviews."""
    name: str = Field(..., pattern=r"^[A-Z][a-zA-Z0-9]*$")
    description: str
    fields: list[FieldSpec] = Field(min_length=1)
    examples: list[dict] = Field(default_factory=list)
    neo4j_label: str | None = None  # Optional mapping to graph label


class RelationshipSpec(BaseModel):
    """Relationship between entities."""
    name: str
    source_entity: str
    target_entity: str
    relationship_type: str  # Neo4j relationship type
    attributes: list[FieldSpec] = Field(default_factory=list)
    directionality: Literal["directed", "bidirectional"] = "directed"


class SentimentScale(StrEnum):
    POSITIVE_NEGATIVE = "positive_negative"
    SATISFACTION = "satisfaction"
    URGENCY = "urgency"
    CONFIDENCE = "confidence"


class SentimentSpec(BaseModel):
    """Sentiment to track during interviews."""
    topic: str
    scale: SentimentScale
    description: str | None = None


class ExtractionSpec(BaseModel):
    """Complete extraction specification."""
    entities: list[EntitySpec] = Field(min_length=1)
    relationships: list[RelationshipSpec] = Field(default_factory=list)
    sentiments: list[SentimentSpec] = Field(default_factory=list)
```

### Synthesis Rules

```python
# clara/models/blueprint/synthesis.py

class MergeStrategy(StrEnum):
    FIRST = "first"
    MOST_RECENT = "most_recent"
    MOST_CONFIDENT = "most_confident"
    MANUAL = "manual"


class ResolutionRule(BaseModel):
    """Rule for resolving entities across interviews."""
    entity_type: str
    matching_fields: list[str]
    similarity_threshold: float = Field(ge=0.0, le=1.0, default=0.8)
    merge_strategy: MergeStrategy = MergeStrategy.MOST_CONFIDENT


class CorrelationRule(BaseModel):
    """Rule for correlating findings across interviews."""
    name: str
    description: str
    entities_involved: list[str]
    correlation_logic: str
    output_type: str
    min_occurrences: int = Field(ge=1, default=2)


class AnalysisFramework(BaseModel):
    """Analysis framework to apply to correlated data."""
    name: str
    description: str
    inputs: list[str]  # Entity types needed
    algorithm: str  # Description of analysis approach
    output_schema: dict
    visualization: str | None = None


class ConflictResolutionSpec(BaseModel):
    """How to handle conflicting information."""
    detection_rules: list[str]
    resolution_strategies: list[dict]
    escalation_threshold: float = Field(ge=0.0, le=1.0, default=0.3)
    require_human_review: bool = True


class SynthesisBlueprint(BaseModel):
    """Complete synthesis specification."""
    entity_resolution_rules: list[ResolutionRule]
    correlation_rules: list[CorrelationRule]
    analysis_frameworks: list[AnalysisFramework]
    conflict_resolution: ConflictResolutionSpec
```

## Database Storage Design

### Option A: JSONB Storage (Recommended for MVP)

Store the entire blueprint as JSONB with indexed extraction for queries.

```python
# clara/db/models.py (additions)

class Blueprint(Base):
    """Interview Blueprint - stored as JSONB."""
    __tablename__ = "blueprints"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Full blueprint as JSONB
    content: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Extracted fields for querying (denormalized)
    project_type: Mapped[str] = mapped_column(String(50))
    agent_count: Mapped[int] = mapped_column(Integer)

    # Metadata
    status: Mapped[str] = mapped_column(String(20), default="draft")
    quality_score: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    created_by: Mapped[str] = mapped_column(String(30))

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="blueprints")
    versions: Mapped[list["BlueprintVersion"]] = relationship(back_populates="blueprint")


class BlueprintVersion(Base):
    """Version history for blueprints."""
    __tablename__ = "blueprint_versions"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    blueprint_id: Mapped[str] = mapped_column(ForeignKey("blueprints.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String(30))

    blueprint: Mapped["Blueprint"] = relationship(back_populates="versions")
```

### Option B: Normalized Storage (Future Consideration)

For complex querying needs, consider normalizing:

```
blueprints (id, project_id, version, status)
blueprint_agents (id, blueprint_id, name, specialty, persona_json)
blueprint_questions (id, agent_id, question, category, sequence)
blueprint_entities (id, blueprint_id, name, description)
blueprint_entity_fields (id, entity_id, name, type, required)
```

**Trade-offs**:
- More complex queries but better performance for large-scale
- Schema migrations more complex
- Harder to serialize/deserialize complete blueprint

## Validation Strategy

### Layer 1: Pydantic Schema Validation
- Field types and constraints
- Required fields
- Pattern matching (IDs, enums)

### Layer 2: Business Rule Validation

```python
# clara/services/blueprint_validator.py

class BlueprintValidator:
    """Validates blueprint business rules."""

    def validate(self, blueprint: InterviewBlueprint) -> ValidationResult:
        issues = []

        # Cross-reference checks
        issues.extend(self._validate_question_references(blueprint))
        issues.extend(self._validate_entity_references(blueprint))
        issues.extend(self._validate_goal_coverage(blueprint))

        # Quality checks
        issues.extend(self._check_question_quality(blueprint))
        issues.extend(self._check_persona_completeness(blueprint))
        issues.extend(self._check_extraction_coverage(blueprint))

        score = self._calculate_quality_score(issues)

        return ValidationResult(
            valid=not any(i.severity == "error" for i in issues),
            issues=issues,
            quality_score=score
        )

    def _validate_question_references(self, bp: InterviewBlueprint) -> list[Issue]:
        """Ensure question IDs in flows exist."""
        issues = []
        for agent in bp.agents:
            question_ids = {q.id for q in agent.questions}
            flow = agent.question_flow

            for seq_name in ["opening", "core", "sensitive", "closing"]:
                seq = getattr(flow, f"{seq_name}_sequence")
                for qid in seq:
                    if qid not in question_ids:
                        issues.append(Issue(
                            severity="error",
                            category="references",
                            message=f"Question {qid} in {seq_name} sequence not found"
                        ))
        return issues
```

### Layer 3: AI Quality Assessment

Use Sonnet to evaluate design quality:

```python
quality_agent = Agent(
    'anthropic:claude-sonnet-4-20250514',
    system_prompt="""Evaluate interview agent design quality.
    Score each dimension 0-100:
    - Persona appropriateness for target interviewees
    - Question coverage of goals
    - Question sequencing (rapport before sensitive)
    - Extraction schema completeness
    - Follow-up trigger effectiveness
    """
)
```

## Implementation Recommendations

### Story #18: Blueprint Core Schema
1. Create `clara/models/blueprint/` package
2. Implement core models: `BlueprintMetadata`, `ProjectContext`, `SourceContext`
3. Add Pydantic validators for cross-field rules
4. Write unit tests for serialization/deserialization

### Story #19: Agent Blueprint Schema
1. Implement `IntervieweeSpec`, `PersonaSpec`, `GoalSpec`
2. Implement `QuestionSpec`, `QuestionFlowSpec`
3. Implement `AgentConfig`, `DesignRationale`
4. Create `AgentBlueprint` composite model

### Story #20: Extraction Schema
1. Implement `FieldSpec`, `EntitySpec`
2. Implement `RelationshipSpec`, `SentimentSpec`
3. Add validation for Neo4j label compatibility
4. Create example extraction schemas per project type

### Story #21: Synthesis Rules
1. Implement `ResolutionRule`, `CorrelationRule`
2. Implement `AnalysisFramework`, `ConflictResolutionSpec`
3. Create default rules per project type

### Story #22: Storage & Versioning
1. Create `Blueprint`, `BlueprintVersion` database models
2. Implement CRUD operations with versioning
3. Add version comparison/diff functionality
4. Implement migration from old to new versions

### Story #23: Validation Service
1. Implement `BlueprintValidator` service
2. Add reference validation
3. Add quality scoring
4. Integrate with storage (validate on save)

### Story #24: Agent Factory
1. Implement `AgentFactory.create_from_blueprint()`
2. Generate system prompts from blueprint
3. Configure Pydantic AI agent with tools
4. Validate agent configuration before return

## Testing Strategy

```python
# tests/unit/test_blueprint_schema.py

class TestBlueprintSchema:
    def test_valid_blueprint_serialization(self):
        """Full blueprint round-trips through JSON."""

    def test_invalid_question_reference_fails(self):
        """Cross-reference validation catches errors."""

    def test_version_increment_on_update(self):
        """Version auto-increments correctly."""

    def test_quality_score_calculation(self):
        """Quality score reflects issue severity."""


# tests/integration/test_blueprint_storage.py

class TestBlueprintStorage:
    async def test_create_and_retrieve_blueprint(self):
        """Blueprint persists and retrieves correctly."""

    async def test_version_history_preserved(self):
        """Updates create version records."""

    async def test_blueprint_to_agent_factory(self):
        """Agent factory creates valid agent from blueprint."""
```
