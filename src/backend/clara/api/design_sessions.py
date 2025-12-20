"""Design Session API endpoints.

Provides endpoints for managing design assistant sessions where users
collaboratively create Interview Blueprints through conversation.
"""

import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from clara.agents import DesignPhase, DesignState, run_design_assistant

router = APIRouter(prefix="/design-sessions", tags=["design-sessions"])

# In-memory session store (replace with Redis/DB in production)
_sessions: dict[str, DesignState] = {}


class CreateSessionRequest(BaseModel):
    """Request to create a new design session."""

    project_id: str = Field(..., description="Project ID for this blueprint design")


class CreateSessionResponse(BaseModel):
    """Response after creating a design session."""

    session_id: str
    project_id: str
    phase: str
    created_at: str
    welcome_message: str


class SendMessageRequest(BaseModel):
    """Request to send a message to the design assistant."""

    message: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    """Response from the design assistant."""

    session_id: str
    phase: str
    response: str
    blueprint_ready: bool = False


class SessionStatus(BaseModel):
    """Current status of a design session."""

    session_id: str
    project_id: str
    phase: str
    created_at: str
    agent_count: int
    current_agent_index: int
    has_project_context: bool
    has_current_agent_data: bool
    message_count: int


class BlueprintPreview(BaseModel):
    """Preview of the generated blueprint."""

    session_id: str
    is_complete: bool
    project_name: str | None
    agent_count: int
    total_questions: int
    total_goals: int
    total_entities: int
    quality_issues: list[str]


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return f"design_{secrets.token_hex(12)}"


def get_welcome_message() -> str:
    """Get the welcome message for a new design session."""
    return """Welcome to Clara's Design Assistant! I'm here to help you create
a comprehensive Interview Blueprint for your discovery project.

I'll guide you through:
1. **Project Context** - Understanding your goals and business needs
2. **Interviewee Groups** - Identifying who should be interviewed
3. **Agent Personas** - Designing how your AI interviewer will engage
4. **Interview Questions** - Crafting questions with probing guidance
5. **Entity Extraction** - Defining what insights to capture
6. **Review & Finalize** - Validating the complete blueprint

Let's start! Tell me about your project:
- What is this discovery initiative about?
- What business decision will the findings inform?
- What type of project is this? (e.g., ERP Discovery, M&A Due Diligence, etc.)"""


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_design_session(request: CreateSessionRequest):
    """Create a new design session for blueprint creation.

    This initializes a conversation with the Design Assistant to
    collaboratively create an Interview Blueprint.
    """
    session_id = generate_session_id()

    # Create session state
    state = DesignState(
        session_id=session_id,
        project_id=request.project_id,
        phase=DesignPhase.WELCOME,
        created_at=datetime.now(UTC),
    )

    # Store session
    _sessions[session_id] = state

    return CreateSessionResponse(
        session_id=session_id,
        project_id=request.project_id,
        phase=state.phase.value,
        created_at=state.created_at.isoformat(),
        welcome_message=get_welcome_message(),
    )


@router.get("/{session_id}", response_model=SessionStatus)
async def get_session_status(session_id: str):
    """Get the current status of a design session."""
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Check if there's current agent data being worked on
    has_current = any(
        [
            state.current_interviewees,
            state.current_persona,
            state.current_goals,
            state.current_questions,
            state.current_extraction,
        ]
    )

    return SessionStatus(
        session_id=state.session_id,
        project_id=state.project_id,
        phase=state.phase.value,
        created_at=state.created_at.isoformat(),
        agent_count=len(state.agents),
        current_agent_index=state.current_agent_index,
        has_project_context=state.project_context is not None,
        has_current_agent_data=has_current,
        message_count=len(state.messages),
    )


@router.post("/{session_id}/messages", response_model=MessageResponse)
async def send_message(session_id: str, request: SendMessageRequest):
    """Send a message to the design assistant and get a response.

    The assistant will guide you through blueprint creation, calling
    appropriate tools to structure the blueprint based on your input.
    """
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # TODO: Get user ID from auth context
    user_id = "user_system"

    try:
        response, updated_state = await run_design_assistant(
            state=state,
            user_id=user_id,
            user_message=request.message,
        )

        # Update session state
        _sessions[session_id] = updated_state

        return MessageResponse(
            session_id=session_id,
            phase=updated_state.phase.value,
            response=response,
            blueprint_ready=updated_state.phase == DesignPhase.COMPLETE,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Design assistant error: {str(e)}",
        )


@router.get("/{session_id}/messages")
async def get_message_history(session_id: str) -> list[dict[str, Any]]:
    """Get the full message history for a design session."""
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    return state.messages


@router.get("/{session_id}/preview", response_model=BlueprintPreview)
async def get_blueprint_preview(session_id: str):
    """Get a preview of the blueprint being designed.

    Returns counts and status without the full blueprint content.
    """
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Count totals across all agents
    total_questions = sum(len(a.questions) for a in state.agents)
    total_questions += len(state.current_questions)

    total_goals = sum(len(a.goals) for a in state.agents)
    total_goals += len(state.current_goals)

    total_entities = 0
    for agent in state.agents:
        total_entities += len(agent.extraction.entities)
    if state.current_extraction:
        total_entities += len(state.current_extraction.entities)

    # Check for issues
    issues: list[str] = []
    if not state.project_context:
        issues.append("Missing project context")
    if not state.agents and not state.current_interviewees:
        issues.append("No agents defined")
    if total_questions < 3:
        issues.append("Need at least 3 questions per agent")
    if total_entities == 0:
        issues.append("No entities defined for extraction")

    return BlueprintPreview(
        session_id=session_id,
        is_complete=state.phase == DesignPhase.COMPLETE,
        project_name=state.project_context.name if state.project_context else None,
        agent_count=len(state.agents),
        total_questions=total_questions,
        total_goals=total_goals,
        total_entities=total_entities,
        quality_issues=issues,
    )


@router.post("/{session_id}/generate")
async def generate_blueprint(session_id: str) -> dict[str, Any]:
    """Generate the final blueprint from the design session.

    This should only be called when the design is complete.
    Returns the full InterviewBlueprint as JSON.
    """
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if not state.agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No agents have been designed yet",
        )

    if not state.project_context:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project context has not been set",
        )

    # Build the blueprint
    from clara.models.blueprint import (
        AnalysisBlueprint,
        BlueprintMetadata,
        BlueprintStatus,
        IntegrationSpec,
        InterviewBlueprint,
        QualitySpec,
    )

    blueprint = InterviewBlueprint(
        metadata=BlueprintMetadata(
            id=f"bp_{secrets.token_hex(8)}",
            version="1.0.0",
            status=BlueprintStatus.DRAFT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            created_by="user_system",  # TODO: Get from auth
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

    # Mark session as complete
    state.phase = DesignPhase.COMPLETE
    _sessions[session_id] = state

    return blueprint.model_dump(mode="json")


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str):
    """Delete a design session and its state."""
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    del _sessions[session_id]
