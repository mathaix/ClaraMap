"""Design Sessions API endpoints.

Provides SSE streaming endpoints for the Design Assistant agent.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from clara.agents.design_assistant import AGUIEvent, session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/design-sessions", tags=["design-sessions"])


class CreateSessionRequest(BaseModel):
    """Request to create a new design session."""
    project_id: str


class CreateSessionResponse(BaseModel):
    """Response after creating a design session."""
    session_id: str
    project_id: str


class SendMessageRequest(BaseModel):
    """Request to send a message to the design assistant."""
    message: str


def format_sse_event(event: AGUIEvent) -> str:
    """Format an AG-UI event as an SSE event."""
    data = json.dumps({"type": event.type, **event.data})
    return f"event: {event.type}\ndata: {data}\n\n"


@router.post("", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
    """Create a new design assistant session."""
    session_id = str(uuid.uuid4())

    try:
        await session_manager.get_or_create_session(
            session_id=session_id,
            project_id=request.project_id
        )
    except Exception as e:
        logger.exception("Failed to create design session")
        raise HTTPException(status_code=500, detail=str(e))

    return CreateSessionResponse(
        session_id=session_id,
        project_id=request.project_id
    )


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get the current state of a design session."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "project_id": session.project_id,
        "phase": session.state.phase.value,
        "turn_count": session.state.turn_count,
        "message_count": session.state.message_count,
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Close and delete a design session."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await session_manager.close_session(session_id)
    return {"status": "deleted"}


@router.post("/{session_id}/stream")
async def stream_message(session_id: str, request: SendMessageRequest):
    """Send a message and stream the response as SSE events."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the agent response."""
        try:
            async for event in session.send_message(request.message):
                yield format_sse_event(event)
        except Exception as e:
            logger.exception("Error streaming response")
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
