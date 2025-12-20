"""Design Assistant Agent for creating Interview Blueprints.

The Design Assistant is an Opus-powered agent that helps managers design
comprehensive Interview Blueprints through iterative conversation.

It guides users through:
1. Defining project context and goals
2. Identifying interviewee groups
3. Designing agent personas
4. Creating interview questions with probing guidance
5. Defining entity extraction schemas
6. Setting up synthesis rules
"""

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from clara.models.blueprint import (
    AgentBlueprint,
    AgentConfig,
    AnalysisBlueprint,
    BlueprintMetadata,
    BlueprintStatus,
    DesignRationale,
    EntitySpec,
    ExtractionSpec,
    FieldSpec,
    FieldType,
    GoalSpec,
    IntegrationSpec,
    InterviewBlueprint,
    IntervieweeSpec,
    PersonaSpec,
    ProjectContext,
    QualitySpec,
    QuestionCategory,
    QuestionFlowSpec,
    QuestionSpec,
    RelationshipSpec,
    SentimentScale,
    SentimentSpec,
    SourceContext,
    SynthesisBlueprint,
)


class DesignPhase(StrEnum):
    """Phases of the blueprint design process."""

    WELCOME = "welcome"
    PROJECT_CONTEXT = "project_context"
    INTERVIEWEE_GROUPS = "interviewee_groups"
    AGENT_PERSONA = "agent_persona"
    GOALS = "goals"
    QUESTIONS = "questions"
    EXTRACTION = "extraction"
    SYNTHESIS = "synthesis"
    REVIEW = "review"
    COMPLETE = "complete"


@dataclass
class DesignState:
    """State for the Design Assistant conversation."""

    session_id: str
    project_id: str
    phase: DesignPhase = DesignPhase.WELCOME
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Collected data
    project_context: ProjectContext | None = None
    agents: list[AgentBlueprint] = field(default_factory=list)
    current_agent_index: int = 0

    # Working state for current agent being designed
    current_interviewees: IntervieweeSpec | None = None
    current_persona: PersonaSpec | None = None
    current_goals: list[GoalSpec] = field(default_factory=list)
    current_questions: list[QuestionSpec] = field(default_factory=list)
    current_extraction: ExtractionSpec | None = None
    current_design_rationale: DesignRationale | None = None

    # Synthesis configuration (shared across agents)
    synthesis: SynthesisBlueprint = field(default_factory=SynthesisBlueprint)

    # Conversation history for context
    messages: list[dict] = field(default_factory=list)


class DesignAssistantDeps(BaseModel):
    """Dependencies for the Design Assistant agent."""

    state: DesignState
    user_id: str


def generate_id(prefix: str, length: int = 8) -> str:
    """Generate a random ID with the given prefix."""
    return f"{prefix}{secrets.token_hex(length // 2)}"


# System prompt for the Design Assistant
DESIGN_ASSISTANT_SYSTEM_PROMPT = """You are Clara's Design Assistant, an expert in designing
AI-powered interview discovery initiatives. Your role is to help managers create
comprehensive Interview Blueprints that drive meaningful discovery conversations.

Your Expertise:
- Interview methodology and best practices
- Organizational research and stakeholder analysis
- Entity extraction and knowledge graph design
- Conversational AI design and persona crafting

Your Approach:
1. Ask clarifying questions to understand the project's goals
2. Guide users through each phase of blueprint design systematically
3. Provide recommendations based on best practices
4. Explain the rationale behind your design decisions
5. Create complete, validated blueprints ready for deployment

Current Conversation Phase: {phase}

Design Guidelines:
- Create interview agents that are warm, professional, and adaptive
- Design questions that flow naturally from rapport to discovery to closing
- Include probing triggers for deeper exploration
- Define entities that capture actionable insights
- Consider how findings will be synthesized across interviews

When generating blueprint components, always explain your reasoning to help
the user understand and refine the design."""


# Create the Design Assistant agent
# Use Sonnet for faster iteration, upgrade to Opus for production
design_assistant = Agent(
    "anthropic:claude-sonnet-4-20250514",
    deps_type=DesignAssistantDeps,
    retries=2,
    system_prompt=DESIGN_ASSISTANT_SYSTEM_PROMPT,
)


@design_assistant.tool
async def set_project_context(
    ctx: RunContext[DesignAssistantDeps],
    name: str,
    project_type: str,
    description: str,
    business_context: str,
    decision_to_inform: str,
    stakeholders: list[str],
    timeline: str | None = None,
    constraints: list[str] | None = None,
) -> str:
    """Set the project context for the blueprint.

    Args:
        name: Project name
        project_type: Type of project (e.g., 'erp_discovery', 'ma_due_diligence')
        description: Detailed project description
        business_context: Why this project exists
        decision_to_inform: What decisions will this inform
        stakeholders: List of stakeholder names/roles
        timeline: Optional timeline description
        constraints: Optional list of constraints
    """
    state = ctx.deps.state

    state.project_context = ProjectContext(
        name=name,
        type=project_type,
        description=description,
        business_context=business_context,
        decision_to_inform=decision_to_inform,
        stakeholders=stakeholders,
        timeline=timeline,
        constraints=constraints or [],
        source_context=SourceContext(),
    )

    state.phase = DesignPhase.INTERVIEWEE_GROUPS
    return f"Project context set for '{name}'. Ready to define interviewee groups."


@design_assistant.tool
async def define_interviewee_group(
    ctx: RunContext[DesignAssistantDeps],
    roles: list[str],
    departments: list[str],
    expertise_areas: list[str],
    count_target: int,
    selection_criteria: str,
) -> str:
    """Define the target interviewee group for the current agent.

    Args:
        roles: Target roles (e.g., ['IT Director', 'Systems Architect'])
        departments: Target departments (e.g., ['IT', 'Operations'])
        expertise_areas: Required expertise areas
        count_target: Target number of interviews
        selection_criteria: Additional selection criteria
    """
    state = ctx.deps.state

    state.current_interviewees = IntervieweeSpec(
        roles=roles,
        departments=departments,
        expertise_areas=expertise_areas,
        count_target=count_target,
        selection_criteria=selection_criteria,
    )

    state.phase = DesignPhase.AGENT_PERSONA
    return f"Interviewee group defined: {', '.join(roles)}. Ready to design the agent persona."


@design_assistant.tool
async def design_agent_persona(
    ctx: RunContext[DesignAssistantDeps],
    role: str,
    tone: str,
    expertise: list[str],
    communication_style: str,
    rapport_building_approach: str,
    handling_reluctance: str,
) -> str:
    """Design the persona for the interview agent.

    Args:
        role: Agent's professional role (e.g., 'Senior Technical Consultant')
        tone: Desired conversational tone
        expertise: List of expertise areas
        communication_style: How the agent communicates
        rapport_building_approach: How to build rapport
        handling_reluctance: How to handle reluctant interviewees
    """
    state = ctx.deps.state

    state.current_persona = PersonaSpec(
        role=role,
        tone=tone,
        expertise=expertise,
        communication_style=communication_style,
        rapport_building_approach=rapport_building_approach,
        handling_reluctance=handling_reluctance,
    )

    state.phase = DesignPhase.GOALS
    return f"Agent persona designed: {role}. Ready to define interview goals."


@design_assistant.tool
async def add_interview_goal(
    ctx: RunContext[DesignAssistantDeps],
    goal: str,
    priority: int,
    success_criteria: list[str],
) -> str:
    """Add an interview goal with success criteria.

    Args:
        goal: The interview goal description
        priority: Priority level (1=highest, 10=lowest)
        success_criteria: List of criteria for goal success
    """
    state = ctx.deps.state

    goal_id = generate_id("goal_")
    new_goal = GoalSpec(
        id=goal_id,
        goal=goal,
        priority=priority,
        success_criteria=success_criteria,
        related_questions=[],
    )

    state.current_goals.append(new_goal)
    return f"Goal added (ID: {goal_id}): {goal[:50]}... Now have {len(state.current_goals)} goals."


@design_assistant.tool
async def finalize_goals(ctx: RunContext[DesignAssistantDeps]) -> str:
    """Mark goals as complete and proceed to questions phase."""
    state = ctx.deps.state

    if not state.current_goals:
        return "No goals defined yet. Please add at least one goal."

    state.phase = DesignPhase.QUESTIONS
    return f"Goals finalized ({len(state.current_goals)} goals). Ready to design questions."


@design_assistant.tool
async def add_question(
    ctx: RunContext[DesignAssistantDeps],
    question: str,
    purpose: str,
    category: str,
    sequence_position: int,
    probing_triggers: list[str] | None = None,
    follow_up_questions: list[str] | None = None,
    skip_conditions: list[str] | None = None,
    expected_entities: list[str] | None = None,
    related_goal_ids: list[str] | None = None,
) -> str:
    """Add a question to the interview script.

    Args:
        question: The question text
        purpose: Purpose of this question
        category: Question category (rapport, discovery, probing, sensitive, closing)
        sequence_position: Position in the sequence
        probing_triggers: Responses that should trigger follow-up probing
        follow_up_questions: Follow-up questions to ask
        skip_conditions: Conditions to skip this question
        expected_entities: Entity types expected from this question
        related_goal_ids: IDs of goals this question addresses
    """
    state = ctx.deps.state

    question_id = generate_id("q_")

    # Map string category to enum
    try:
        cat = QuestionCategory(category.lower())
    except ValueError:
        cat = QuestionCategory.DISCOVERY

    new_question = QuestionSpec(
        id=question_id,
        question=question,
        purpose=purpose,
        category=cat,
        sequence_position=sequence_position,
        probing_triggers=probing_triggers or [],
        follow_up_questions=follow_up_questions or [],
        skip_conditions=skip_conditions or [],
        expected_entities=expected_entities or [],
    )

    state.current_questions.append(new_question)

    # Link to goals
    if related_goal_ids:
        for goal in state.current_goals:
            if goal.id in related_goal_ids:
                goal.related_questions.append(question_id)

    count = len(state.current_questions)
    return f"Question added (ID: {question_id}): {question[:40]}... ({count} total)"


@design_assistant.tool
async def finalize_questions(ctx: RunContext[DesignAssistantDeps]) -> str:
    """Mark questions as complete and proceed to extraction phase."""
    state = ctx.deps.state

    if len(state.current_questions) < 3:
        return "Need at least 3 questions. Please add more questions."

    state.phase = DesignPhase.EXTRACTION
    return f"Questions finalized ({len(state.current_questions)}). Ready for extraction schema."


@design_assistant.tool
async def define_entity(
    ctx: RunContext[DesignAssistantDeps],
    name: str,
    description: str,
    fields: list[dict],
    examples: list[dict] | None = None,
) -> str:
    """Define an entity type for extraction.

    Args:
        name: Entity name (PascalCase, e.g., 'System', 'Process')
        description: Entity description
        fields: List of field specs [{name, type, required, description}]
        examples: Optional example instances
    """
    state = ctx.deps.state

    field_specs = []
    for f in fields:
        try:
            field_type = FieldType(f.get("type", "string"))
        except ValueError:
            field_type = FieldType.STRING

        field_specs.append(
            FieldSpec(
                name=f["name"],
                type=field_type,
                required=f.get("required", False),
                description=f.get("description", ""),
            )
        )

    entity = EntitySpec(
        name=name,
        description=description,
        fields=field_specs,
        examples=examples or [],
    )

    if state.current_extraction is None:
        state.current_extraction = ExtractionSpec(entities=[entity])
    else:
        state.current_extraction.entities.append(entity)

    return f"Entity defined: {name} with {len(field_specs)} fields."


@design_assistant.tool
async def define_relationship(
    ctx: RunContext[DesignAssistantDeps],
    name: str,
    source_entity: str,
    target_entity: str,
    relationship_type: str,
    description: str,
) -> str:
    """Define a relationship between entities.

    Args:
        name: Relationship name
        source_entity: Source entity type
        target_entity: Target entity type
        relationship_type: Neo4j relationship type (USES, OWNS, etc.)
        description: Relationship description
    """
    state = ctx.deps.state

    if state.current_extraction is None:
        return "Please define at least one entity first."

    relationship = RelationshipSpec(
        name=name,
        source_entity=source_entity,
        target_entity=target_entity,
        relationship_type=relationship_type,
    )

    state.current_extraction.relationships.append(relationship)
    return f"Relationship defined: {source_entity} -{relationship_type}-> {target_entity}"


@design_assistant.tool
async def add_sentiment_tracking(
    ctx: RunContext[DesignAssistantDeps],
    topic: str,
    scale: str,
    description: str | None = None,
) -> str:
    """Add sentiment tracking for a topic.

    Args:
        topic: Topic to track sentiment for
        scale: Scale type (positive_negative, satisfaction, urgency, confidence)
        description: Optional description
    """
    state = ctx.deps.state

    if state.current_extraction is None:
        state.current_extraction = ExtractionSpec(entities=[])

    try:
        scale_enum = SentimentScale(scale)
    except ValueError:
        scale_enum = SentimentScale.POSITIVE_NEGATIVE

    sentiment = SentimentSpec(
        topic=topic,
        scale=scale_enum,
        description=description,
    )

    state.current_extraction.sentiments.append(sentiment)
    return f"Sentiment tracking added for topic: {topic}"


@design_assistant.tool
async def finalize_agent(
    ctx: RunContext[DesignAssistantDeps],
    agent_name: str,
    agent_description: str,
    persona_reasoning: str,
    question_strategy: str,
    extraction_approach: str,
) -> str:
    """Finalize the current agent and optionally add another.

    Args:
        agent_name: Name for this agent
        agent_description: Description of agent's specialty
        persona_reasoning: Why this persona was chosen
        question_strategy: Strategy for question selection/ordering
        extraction_approach: Approach to entity extraction
    """
    state = ctx.deps.state

    if not all(
        [
            state.current_interviewees,
            state.current_persona,
            state.current_goals,
            state.current_questions,
            state.current_extraction,
        ]
    ):
        return "Agent incomplete. Please complete all sections first."

    # Build question flow from questions
    questions = sorted(state.current_questions, key=lambda q: q.sequence_position)

    opening = [q.id for q in questions if q.category == QuestionCategory.RAPPORT]
    core_cats = [QuestionCategory.DISCOVERY, QuestionCategory.PROBING]
    core = [q.id for q in questions if q.category in core_cats]
    sensitive = [q.id for q in questions if q.category == QuestionCategory.SENSITIVE]
    closing = [q.id for q in questions if q.category == QuestionCategory.CLOSING]

    # Ensure at least one question in each required section
    if not opening:
        opening = [questions[0].id]
    if not core:
        core = [q.id for q in questions[1:-1] if q.id not in opening + closing]
    if not closing:
        closing = [questions[-1].id]

    question_flow = QuestionFlowSpec(
        opening_sequence=opening,
        core_sequence=core,
        sensitive_sequence=sensitive,
        closing_sequence=closing,
    )

    design_rationale = DesignRationale(
        persona_reasoning=persona_reasoning,
        question_strategy=question_strategy,
        extraction_approach=extraction_approach,
    )

    agent = AgentBlueprint(
        id=generate_id("agent_"),
        name=agent_name,
        description=agent_description,
        target_interviewees=state.current_interviewees,
        persona=state.current_persona,
        goals=state.current_goals,
        questions=state.current_questions,
        question_flow=question_flow,
        extraction=state.current_extraction,
        config=AgentConfig(),
        design_rationale=design_rationale,
    )

    state.agents.append(agent)

    # Reset working state for potential next agent
    state.current_interviewees = None
    state.current_persona = None
    state.current_goals = []
    state.current_questions = []
    state.current_extraction = None
    state.current_design_rationale = None
    state.current_agent_index += 1

    state.phase = DesignPhase.REVIEW
    return f"Agent '{agent_name}' finalized. Total agents: {len(state.agents)}. Ready for review."


@design_assistant.tool
async def add_another_agent(ctx: RunContext[DesignAssistantDeps]) -> str:
    """Start designing another agent for a different interviewee group."""
    state = ctx.deps.state
    state.phase = DesignPhase.INTERVIEWEE_GROUPS
    return "Ready to design another agent. Please define the next interviewee group."


@design_assistant.tool
async def generate_blueprint(ctx: RunContext[DesignAssistantDeps]) -> dict:
    """Generate the final Interview Blueprint.

    Returns the complete blueprint as a dictionary.
    """
    state = ctx.deps.state

    if not state.agents:
        raise ValueError("No agents defined. Please complete at least one agent.")

    if not state.project_context:
        raise ValueError("Project context not set.")

    blueprint = InterviewBlueprint(
        metadata=BlueprintMetadata(
            id=generate_id("bp_", 16),
            version="1.0.0",
            status=BlueprintStatus.DRAFT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            created_by=ctx.deps.user_id,
            designed_by="design_assistant",
            project_id=state.project_id,
        ),
        project=state.project_context,
        agents=state.agents,
        synthesis=state.synthesis,
        analysis=AnalysisBlueprint(),
        quality=QualitySpec(),
        integrations=IntegrationSpec(),
    )

    state.phase = DesignPhase.COMPLETE
    return blueprint.model_dump(mode="json")


async def create_design_session(project_id: str, user_id: str) -> DesignState:
    """Create a new design session for blueprint creation."""
    return DesignState(
        session_id=generate_id("design_", 16),
        project_id=project_id,
    )


async def run_design_assistant(
    state: DesignState,
    user_id: str,
    user_message: str,
) -> tuple[str, DesignState]:
    """Run the Design Assistant with a user message.

    Args:
        state: Current design state
        user_id: ID of the user
        user_message: User's message

    Returns:
        Tuple of (assistant response, updated state)
    """
    # Add user message to history
    state.messages.append({"role": "user", "content": user_message})

    # Create deps
    deps = DesignAssistantDeps(state=state, user_id=user_id)

    # Run the agent
    result = await design_assistant.run(
        user_message,
        deps=deps,
    )

    # Add assistant response to history
    response = result.data
    state.messages.append({"role": "assistant", "content": response})

    return response, state
