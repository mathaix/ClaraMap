"""Agent blueprint models for Interview Blueprint."""

from enum import StrEnum

from pydantic import BaseModel, Field

from clara.models.blueprint.extraction import ExtractionSpec


class IntervieweeSpec(BaseModel):
    """Specification for who should be interviewed by this agent."""

    roles: list[str] = Field(default_factory=list, description="Target roles")
    departments: list[str] = Field(default_factory=list, description="Target departments")
    expertise_areas: list[str] = Field(default_factory=list, description="Required expertise areas")
    suggested_individuals: list[dict] = Field(
        default_factory=list,
        description="Suggested individuals with {name, email, role}",
    )
    count_target: int = Field(ge=1, le=1000, description="Target number of interviews")
    selection_criteria: str | None = Field(None, description="Additional selection criteria")


class PersonaSpec(BaseModel):
    """Agent persona specification."""

    role: str = Field(..., min_length=1, max_length=100, description="Agent's professional role")
    tone: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Desired conversational tone",
    )
    expertise: list[str] = Field(min_length=1, description="Areas of expertise")
    communication_style: str = Field(..., description="How the agent communicates")
    rapport_building_approach: str = Field(..., description="How the agent builds rapport")
    handling_reluctance: str = Field(..., description="How to handle reluctant interviewees")


class GoalSpec(BaseModel):
    """Interview goal with success criteria."""

    id: str = Field(..., pattern=r"^goal_[a-z0-9]{8}$")
    goal: str = Field(..., min_length=10, description="The interview goal")
    priority: int = Field(ge=1, le=10, description="Goal priority (1=highest)")
    success_criteria: list[str] = Field(min_length=1, description="Criteria for goal success")
    related_questions: list[str] = Field(
        default_factory=list, description="Question IDs related to this goal"
    )


class QuestionCategory(StrEnum):
    """Categories of interview questions."""

    RAPPORT = "rapport"
    DISCOVERY = "discovery"
    PROBING = "probing"
    SENSITIVE = "sensitive"
    CLOSING = "closing"


class QuestionSpec(BaseModel):
    """Question specification with probing guidance."""

    id: str = Field(..., pattern=r"^q_[a-z0-9]{8}$")
    question: str = Field(..., min_length=10, description="The question text")
    purpose: str = Field(..., description="Purpose of this question")
    category: QuestionCategory
    sequence_position: int = Field(ge=1, description="Position in sequence")
    probing_triggers: list[str] = Field(
        default_factory=list, description="Responses that should trigger probing"
    )
    follow_up_questions: list[str] = Field(
        default_factory=list, description="Follow-up questions to ask"
    )
    skip_conditions: list[str] = Field(
        default_factory=list, description="Conditions to skip this question"
    )
    expected_entities: list[str] = Field(
        default_factory=list, description="Entities expected from this question"
    )


class QuestionFlowSpec(BaseModel):
    """How questions should flow during the interview."""

    opening_sequence: list[str] = Field(min_length=1, description="Question IDs for opening")
    core_sequence: list[str] = Field(min_length=1, description="Question IDs for core interview")
    sensitive_sequence: list[str] = Field(
        default_factory=list, description="Question IDs for sensitive topics"
    )
    closing_sequence: list[str] = Field(min_length=1, description="Question IDs for closing")
    branching_rules: list[dict] = Field(
        default_factory=list, description="Rules for conditional branching"
    )
    time_allocation: dict[str, int] = Field(
        default_factory=dict, description="Time in minutes per section"
    )


class AgentConfig(BaseModel):
    """Runtime configuration for an agent."""

    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="AI model to use for this agent",
    )
    max_turns: int = Field(default=50, ge=10, le=200, description="Maximum conversation turns")
    target_duration_minutes: int = Field(
        default=30, ge=5, le=120, description="Target interview duration"
    )
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Model temperature")
    enable_adaptive_ui: bool = Field(default=True, description="Enable adaptive UI components")
    enable_real_time_extraction: bool = Field(
        default=True, description="Enable real-time entity extraction"
    )


class DesignRationale(BaseModel):
    """Design rationale captured from Design Assistant."""

    persona_reasoning: str = Field(..., description="Why this persona was chosen")
    question_strategy: str = Field(..., description="Strategy for question selection/ordering")
    extraction_approach: str = Field(..., description="Approach to entity extraction")
    key_considerations: list[str] = Field(
        default_factory=list, description="Key design considerations"
    )
    alternatives_considered: list[dict] = Field(
        default_factory=list, description="Alternative approaches that were considered"
    )


class AgentBlueprint(BaseModel):
    """Complete blueprint for a single interview agent."""

    id: str = Field(..., pattern=r"^agent_[a-z0-9]{8}$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., description="Agent purpose and specialty")
    target_interviewees: IntervieweeSpec
    persona: PersonaSpec
    goals: list[GoalSpec] = Field(min_length=1)
    questions: list[QuestionSpec] = Field(min_length=1)
    question_flow: QuestionFlowSpec
    extraction: ExtractionSpec
    config: AgentConfig = Field(default_factory=AgentConfig)
    design_rationale: DesignRationale | None = None
