"""Simulation Sessions API endpoints.

Provides SSE streaming endpoints for testing interview agent prompts.
Users can simulate conversations with the generated interviewer agent
before deploying it to actual interviews.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clara.agents.simulation_agent import AGUIEvent, simulation_manager
from clara.db.models import DesignSession
from clara.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation-sessions", tags=["simulation-sessions"])


class CreateSimulationRequest(BaseModel):
    """Request to create a new simulation session."""
    system_prompt: str
    design_session_id: str | None = None  # Optional link to design session


class CreateSimulationResponse(BaseModel):
    """Response after creating a simulation session."""
    session_id: str
    system_prompt_preview: str  # First 200 chars


class UpdatePromptRequest(BaseModel):
    """Request to update the system prompt."""
    system_prompt: str


class SendMessageRequest(BaseModel):
    """Request to send a message to the simulation agent."""
    message: str


class SimulationStateResponse(BaseModel):
    """Current state of the simulation session."""
    session_id: str
    system_prompt: str
    messages: list[dict]


def format_sse_event(event: AGUIEvent) -> str:
    """Format an AG-UI event as an SSE event."""
    data = json.dumps({"type": event.type, **event.data})
    return f"event: {event.type}\ndata: {data}\n\n"


@router.post("", response_model=CreateSimulationResponse)
async def create_simulation(
    request: CreateSimulationRequest,
) -> CreateSimulationResponse:
    """Create a new simulation session with the given system prompt."""
    session_id = str(uuid.uuid4())

    await simulation_manager.create_session(
        session_id=session_id,
        system_prompt=request.system_prompt,
    )

    logger.info(f"Created simulation session {session_id}")

    return CreateSimulationResponse(
        session_id=session_id,
        system_prompt_preview=request.system_prompt[:200] + "..." if len(request.system_prompt) > 200 else request.system_prompt,
    )


@router.post("/from-design-session/{design_session_id}", response_model=CreateSimulationResponse)
async def create_simulation_from_design_session(
    design_session_id: str,
    db: AsyncSession = Depends(get_db),
) -> CreateSimulationResponse:
    """Create a simulation session using the system prompt from a design session's blueprint."""
    # Get the design session
    result = await db.execute(
        select(DesignSession).where(DesignSession.id == design_session_id)
    )
    design_session = result.scalar_one_or_none()

    if not design_session:
        raise HTTPException(status_code=404, detail="Design session not found")

    # Extract system prompt from blueprint_state
    blueprint_state = design_session.blueprint_state or {}
    agents = blueprint_state.get("agents", [])

    if not agents:
        raise HTTPException(
            status_code=400,
            detail="No agents configured in blueprint. Complete the design process first."
        )

    # Use the first agent's system prompt
    agent = agents[0]
    system_prompt = agent.get("system_prompt")

    if not system_prompt:
        raise HTTPException(
            status_code=400,
            detail="No system prompt found in agent configuration. Complete Phase 3 first."
        )

    # Create simulation session
    session_id = str(uuid.uuid4())

    await simulation_manager.create_session(
        session_id=session_id,
        system_prompt=system_prompt,
    )

    logger.info(f"Created simulation session {session_id} from design session {design_session_id}")

    return CreateSimulationResponse(
        session_id=session_id,
        system_prompt_preview=system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt,
    )


@router.get("/{session_id}", response_model=SimulationStateResponse)
async def get_simulation(session_id: str) -> SimulationStateResponse:
    """Get the current state of a simulation session."""
    session = await simulation_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Simulation session not found")

    return SimulationStateResponse(
        session_id=session.session_id,
        system_prompt=session.system_prompt,
        messages=session.messages,
    )


@router.put("/{session_id}/prompt")
async def update_simulation_prompt(
    session_id: str,
    request: UpdatePromptRequest,
):
    """Update the system prompt for a simulation session.

    This resets the conversation history.
    """
    session = await simulation_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Simulation session not found")

    await simulation_manager.update_prompt(session_id, request.system_prompt)

    return {"status": "updated", "message": "Prompt updated and conversation reset"}


@router.post("/{session_id}/reset")
async def reset_simulation(session_id: str):
    """Reset the conversation history while keeping the prompt."""
    session = await simulation_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Simulation session not found")

    session.reset()

    return {"status": "reset", "message": "Conversation history cleared"}


@router.delete("/{session_id}")
async def delete_simulation(session_id: str):
    """Close and delete a simulation session."""
    session = await simulation_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Simulation session not found")

    await simulation_manager.close_session(session_id)

    return {"status": "deleted"}


@router.post("/{session_id}/stream")
async def stream_simulation_message(
    session_id: str,
    request: SendMessageRequest,
):
    """Send a message and stream the response as SSE events."""
    session = await simulation_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Simulation session not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the simulation response."""
        try:
            async for event in session.send_message(request.message):
                yield format_sse_event(event)
        except Exception as e:
            logger.exception("Error streaming simulation response")
            error_event = AGUIEvent(
                type="ERROR",
                data={"message": str(e)}
            )
            yield format_sse_event(error_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
