"""Design Sessions API endpoints.

Provides SSE streaming endpoints for the Design Assistant agent.
Sessions are persisted to the database so users can resume where they left off.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clara.agents.design_assistant import AGUIEvent, session_manager
from clara.db.models import DesignPhase, DesignSession, DesignSessionStatus
from clara.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/design-sessions", tags=["design-sessions"])


class CreateSessionRequest(BaseModel):
    """Request to create a new design session."""
    project_id: str
    add_agent: bool = False  # When True, creates a fresh new session for another agent


class CreateSessionResponse(BaseModel):
    """Response after creating a design session."""
    session_id: str
    project_id: str
    is_new: bool  # True if new session, False if resuming existing


class SessionStateResponse(BaseModel):
    """Full session state for frontend restoration."""
    session_id: str
    project_id: str
    phase: str
    messages: list[dict]
    blueprint_state: dict
    goal_summary: dict | None
    agent_capabilities: dict | None
    turn_count: int
    message_count: int
    status: str


class SendMessageRequest(BaseModel):
    """Request to send a message to the design assistant."""
    message: str


def format_sse_event(event: AGUIEvent) -> str:
    """Format an AG-UI event as an SSE event."""
    data = json.dumps({"type": event.type, **event.data})
    return f"event: {event.type}\ndata: {data}\n\n"


@router.post("", response_model=CreateSessionResponse)
async def create_or_resume_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db)
) -> CreateSessionResponse:
    """Create a new design session or resume an existing one for the project.

    If an active session exists for the project, returns that session.
    Otherwise creates a new session.

    If add_agent=True, always creates a fresh new session (ignores existing sessions).
    """
    # If add_agent mode, skip checking for existing session - always create fresh
    if request.add_agent:
        existing_session = None
    else:
        # Check for existing active session for this project
        result = await db.execute(
            select(DesignSession)
            .where(DesignSession.project_id == request.project_id)
            .where(DesignSession.status == DesignSessionStatus.ACTIVE.value)
            .order_by(DesignSession.updated_at.desc())
            .limit(1)
        )
        existing_session = result.scalar_one_or_none()

    if existing_session:
        # Resume existing session
        session_id = existing_session.id
        is_new = False
        logger.info(
            f"Resuming existing session {session_id} for project {request.project_id}"
        )

        # Restore in-memory state from DB
        try:
            await session_manager.restore_session(
                session_id=session_id,
                project_id=request.project_id,
                db_session=existing_session
            )
        except Exception as e:
            logger.exception("Failed to restore design session")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Create new session
        session_id = str(uuid.uuid4())
        is_new = True

        # Create DB record
        db_session = DesignSession(
            id=session_id,
            project_id=request.project_id,
            status=DesignSessionStatus.ACTIVE.value,
            phase=DesignPhase.GOAL_UNDERSTANDING.value,
            messages=[],
            blueprint_state={"project": None, "entities": [], "agents": []},
        )
        db.add(db_session)
        await db.flush()  # Ensure ID is available

        logger.info(f"Created new session {session_id} for project {request.project_id}")

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
        project_id=request.project_id,
        is_new=is_new
    )


@router.get("/{session_id}", response_model=SessionStateResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> SessionStateResponse:
    """Get the full state of a design session including conversation history."""
    result = await db.execute(
        select(DesignSession).where(DesignSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStateResponse(
        session_id=db_session.id,
        project_id=db_session.project_id,
        phase=db_session.phase,
        messages=db_session.messages or [],
        blueprint_state=db_session.blueprint_state or {},
        goal_summary=db_session.goal_summary,
        agent_capabilities=db_session.agent_capabilities,
        turn_count=db_session.turn_count,
        message_count=db_session.message_count,
        status=db_session.status,
    )


@router.get("/project/{project_id}", response_model=SessionStateResponse | None)
async def get_session_by_project(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> SessionStateResponse | None:
    """Get the active design session for a project, if one exists."""
    result = await db.execute(
        select(DesignSession)
        .where(DesignSession.project_id == project_id)
        .where(DesignSession.status == DesignSessionStatus.ACTIVE.value)
        .order_by(DesignSession.updated_at.desc())
        .limit(1)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        return None

    return SessionStateResponse(
        session_id=db_session.id,
        project_id=db_session.project_id,
        phase=db_session.phase,
        messages=db_session.messages or [],
        blueprint_state=db_session.blueprint_state or {},
        goal_summary=db_session.goal_summary,
        agent_capabilities=db_session.agent_capabilities,
        turn_count=db_session.turn_count,
        message_count=db_session.message_count,
        status=db_session.status,
    )


class ProjectAgentInfo(BaseModel):
    """Agent info with session reference for project-level listing."""
    session_id: str
    agent_index: int
    name: str
    persona: str | None
    topics: list[str]
    tone: str | None
    system_prompt: str | None
    context_files: list[dict] | None


class ProjectAgentsResponse(BaseModel):
    """All agents for a project, aggregated from all sessions."""
    project_id: str
    agents: list[ProjectAgentInfo]
    session_count: int


@router.get("/project/{project_id}/agents", response_model=ProjectAgentsResponse)
async def get_project_agents(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> ProjectAgentsResponse:
    """Get all agents for a project, aggregated from all active sessions.

    Each agent includes a reference to its session for simulation/editing.
    """
    # Get ALL active sessions for this project
    result = await db.execute(
        select(DesignSession)
        .where(DesignSession.project_id == project_id)
        .where(DesignSession.status == DesignSessionStatus.ACTIVE.value)
        .order_by(DesignSession.created_at.asc())  # Oldest first for consistent ordering
    )
    sessions = result.scalars().all()

    all_agents: list[ProjectAgentInfo] = []

    for session in sessions:
        blueprint_state = session.blueprint_state or {}
        agents = blueprint_state.get("agents", [])

        for idx, agent in enumerate(agents):
            all_agents.append(ProjectAgentInfo(
                session_id=session.id,
                agent_index=idx,
                name=agent.get("name", f"Agent {len(all_agents) + 1}"),
                persona=agent.get("persona"),
                topics=agent.get("topics", []),
                tone=agent.get("tone"),
                system_prompt=agent.get("system_prompt"),
                context_files=agent.get("context_files"),
            ))

    return ProjectAgentsResponse(
        project_id=project_id,
        agents=all_agents,
        session_count=len(sessions),
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Close and mark a design session as abandoned."""
    result = await db.execute(
        select(DesignSession).where(DesignSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Mark as abandoned in DB
    db_session.status = DesignSessionStatus.ABANDONED.value
    db_session.updated_at = datetime.now(UTC)

    # Close in-memory session (ignore errors if not in memory)
    try:
        await session_manager.close_session(session_id)
    except Exception:
        pass

    return {"status": "deleted"}


@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a message and stream the response as SSE events.

    Also persists the conversation to the database.
    """
    # Get DB session record
    result = await db.execute(
        select(DesignSession).where(DesignSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found in database")

    # Get in-memory session
    session = await session_manager.get_session(session_id)
    if not session:
        # Try to restore from DB
        try:
            await session_manager.restore_session(
                session_id=session_id,
                project_id=db_session.project_id,
                db_session=db_session
            )
            session = await session_manager.get_session(session_id)
        except Exception as e:
            logger.exception("Failed to restore session")
            raise HTTPException(status_code=500, detail=f"Failed to restore session: {e}")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Add user message to DB
    messages = list(db_session.messages or [])
    messages.append({"role": "user", "content": request.message})
    db_session.messages = messages
    db_session.message_count = len(messages)
    db_session.updated_at = datetime.now(UTC)
    await db.commit()

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the agent response."""
        assistant_content = ""
        streaming_error = None

        try:
            async for event in session.send_message(request.message):
                yield format_sse_event(event)

                # Accumulate assistant text for persistence
                if event.type == "TEXT_MESSAGE_CONTENT":
                    delta = event.data.get("delta", "")
                    assistant_content += delta

        except Exception as e:
            streaming_error = e
            logger.exception("Error streaming response")
            error_event = AGUIEvent(
                type="ERROR",
                data={"message": str(e), "recoverable": True}
            )
            yield format_sse_event(error_event)

        # After streaming completes, persist assistant response and state
        persistence_error = None
        try:
            async with session_manager._db_session_maker() as save_db:
                result = await save_db.execute(
                    select(DesignSession).where(DesignSession.id == session_id)
                )
                db_sess = result.scalar_one_or_none()
                if db_sess and assistant_content:
                    messages = list(db_sess.messages or [])
                    messages.append({"role": "assistant", "content": assistant_content})
                    db_sess.messages = messages
                    db_sess.message_count = len(messages)
                    db_sess.turn_count = (db_sess.turn_count or 0) + 1

                    # Sync state from in-memory session
                    if session:
                        db_sess.phase = session.state.phase.value
                        # Get blueprint state from tools
                        from clara.agents.tools import get_session_state
                        tool_state = get_session_state(session_id)
                        db_sess.blueprint_state = {
                            "project": tool_state.get("project"),
                            "entities": tool_state.get("entities", []),
                            "agents": tool_state.get("agents", []),
                        }
                        db_sess.goal_summary = tool_state.get("goal_summary")
                        db_sess.agent_capabilities = tool_state.get("agent_capabilities")

                    db_sess.updated_at = datetime.now(UTC)
                    await save_db.commit()
        except Exception as e:
            persistence_error = e
            logger.exception(f"Failed to persist session state: {e}")

        # Notify user if persistence failed (but streaming succeeded)
        if persistence_error and not streaming_error:
            warning_event = AGUIEvent(
                type="WARNING",
                data={
                    "message": "Response received but failed to save. Please retry.",
                    "code": "PERSISTENCE_FAILED"
                }
            )
            yield format_sse_event(warning_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
