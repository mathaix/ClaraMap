"""Interview Agents API endpoints.

Provides CRUD operations for InterviewAgent entities - the first-class
AI interviewer entities that belong to projects.
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clara.db.models import InterviewAgent, InterviewAgentStatus, Project
from clara.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview-agents", tags=["interview-agents"])


class InterviewAgentResponse(BaseModel):
    """Response model for an interview agent."""
    id: str
    project_id: str
    name: str
    persona: str | None
    topics: list[str]
    tone: str | None
    system_prompt: str | None
    capabilities: dict | None
    status: str
    design_session_id: str | None
    created_at: str
    updated_at: str


class InterviewAgentListResponse(BaseModel):
    """Response model for listing agents."""
    agents: list[InterviewAgentResponse]
    total: int


class CreateInterviewAgentRequest(BaseModel):
    """Request to create an interview agent."""
    project_id: str
    name: str
    persona: str | None = None
    topics: list[str] = []
    tone: str | None = None
    system_prompt: str | None = None
    capabilities: dict | None = None
    design_session_id: str | None = None


class UpdateInterviewAgentRequest(BaseModel):
    """Request to update an interview agent."""
    name: str | None = None
    persona: str | None = None
    topics: list[str] | None = None
    tone: str | None = None
    system_prompt: str | None = None
    capabilities: dict | None = None
    status: str | None = None


def agent_to_response(agent: InterviewAgent) -> InterviewAgentResponse:
    """Convert an InterviewAgent model to a response."""
    return InterviewAgentResponse(
        id=agent.id,
        project_id=agent.project_id,
        name=agent.name,
        persona=agent.persona,
        topics=agent.topics or [],
        tone=agent.tone,
        system_prompt=agent.system_prompt,
        capabilities=agent.capabilities,
        status=agent.status,
        design_session_id=agent.design_session_id,
        created_at=agent.created_at.isoformat() if agent.created_at else "",
        updated_at=agent.updated_at.isoformat() if agent.updated_at else "",
    )


@router.get("/project/{project_id}", response_model=InterviewAgentListResponse)
async def list_project_agents(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> InterviewAgentListResponse:
    """List all interview agents for a project.

    Returns agents from the interview_agents table, sorted by creation date.
    """
    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all agents for the project
    result = await db.execute(
        select(InterviewAgent)
        .where(InterviewAgent.project_id == project_id)
        .order_by(InterviewAgent.created_at.desc())
    )
    agents = result.scalars().all()

    return InterviewAgentListResponse(
        agents=[agent_to_response(agent) for agent in agents],
        total=len(agents),
    )


@router.get("/{agent_id}", response_model=InterviewAgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
) -> InterviewAgentResponse:
    """Get a single interview agent by ID."""
    result = await db.execute(
        select(InterviewAgent)
        .where(InterviewAgent.id == agent_id)
        .options(selectinload(InterviewAgent.context_files))
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent_to_response(agent)


@router.post("", response_model=InterviewAgentResponse)
async def create_agent(
    request: CreateInterviewAgentRequest,
    db: AsyncSession = Depends(get_db)
) -> InterviewAgentResponse:
    """Create a new interview agent."""
    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.id == request.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    agent = InterviewAgent(
        id=f"agent_{uuid.uuid4().hex[:16]}",
        project_id=request.project_id,
        name=request.name,
        persona=request.persona,
        topics=request.topics,
        tone=request.tone,
        system_prompt=request.system_prompt,
        capabilities=request.capabilities,
        status=InterviewAgentStatus.DRAFT.value,
        design_session_id=request.design_session_id,
    )
    db.add(agent)
    await db.flush()

    logger.info(f"Created interview agent {agent.id} for project {request.project_id}")
    return agent_to_response(agent)


@router.patch("/{agent_id}", response_model=InterviewAgentResponse)
async def update_agent(
    agent_id: str,
    request: UpdateInterviewAgentRequest,
    db: AsyncSession = Depends(get_db)
) -> InterviewAgentResponse:
    """Update an interview agent."""
    result = await db.execute(
        select(InterviewAgent).where(InterviewAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Update fields if provided
    if request.name is not None:
        agent.name = request.name
    if request.persona is not None:
        agent.persona = request.persona
    if request.topics is not None:
        agent.topics = request.topics
    if request.tone is not None:
        agent.tone = request.tone
    if request.system_prompt is not None:
        agent.system_prompt = request.system_prompt
    if request.capabilities is not None:
        agent.capabilities = request.capabilities
    if request.status is not None:
        if request.status not in [s.value for s in InterviewAgentStatus]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {[s.value for s in InterviewAgentStatus]}"
            )
        agent.status = request.status

    agent.updated_at = datetime.now(UTC)

    logger.info(f"Updated interview agent {agent_id}")
    return agent_to_response(agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an interview agent."""
    result = await db.execute(
        select(InterviewAgent).where(InterviewAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    logger.info(f"Deleted interview agent {agent_id}")

    return {"status": "deleted"}
