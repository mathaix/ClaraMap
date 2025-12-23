"""Design Assistant using Claude Agent SDK.

This module provides the public interface for Clara's Design Architect agent.
The actual implementation is delegated to the DesignOrchestrator which routes
messages to specialized phase agents.

This file maintains backward compatibility with existing code that uses
DesignAssistantSession and session_manager.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from clara.agents.orchestrator import (
    AgentCapabilities,
    AGUIEvent,
    BlueprintPreview,
    DesignOrchestrator,
    DesignPhase,
    DesignSessionState,
)
from clara.agents.tools import get_session_state

logger = logging.getLogger(__name__)


# Re-export types for backward compatibility
__all__ = [
    "DesignPhase",
    "BlueprintPreview",
    "AgentCapabilities",
    "DesignSessionState",
    "AGUIEvent",
    "DesignAssistantSession",
    "DesignAssistantManager",
    "session_manager",
]


class DesignAssistantSession:
    """Thin wrapper around DesignOrchestrator for backward compatibility.

    This class maintains the same public interface as the original
    DesignAssistantSession but delegates all work to the orchestrator.
    """

    def __init__(self, session_id: str, project_id: str):
        self._orchestrator = DesignOrchestrator(session_id, project_id)

    @property
    def session_id(self) -> str:
        return self._orchestrator.session_id

    @property
    def project_id(self) -> str:
        return self._orchestrator.project_id

    @property
    def state(self) -> DesignSessionState:
        return self._orchestrator.state

    @state.setter
    def state(self, value: DesignSessionState) -> None:
        self._orchestrator.state = value

    @property
    def _restored(self) -> bool:
        return self._orchestrator._restored

    @_restored.setter
    def _restored(self, value: bool) -> None:
        self._orchestrator._restored = value

    @property
    def _first_message_sent(self) -> bool:
        return self._orchestrator._first_message_sent

    @_first_message_sent.setter
    def _first_message_sent(self, value: bool) -> None:
        self._orchestrator._first_message_sent = value

    async def start(self) -> None:
        """Start the design assistant session."""
        await self._orchestrator.start()

    async def stop(self) -> None:
        """Stop the design assistant session."""
        await self._orchestrator.stop()

    async def send_message(self, message: str) -> AsyncIterator[AGUIEvent]:
        """Send a message and stream the response as AG-UI events."""
        async for event in self._orchestrator.send_message(message):
            yield event


@dataclass
class _SessionWrapper:
    """Internal wrapper to track both orchestrator and session."""
    session: DesignAssistantSession
    orchestrator: DesignOrchestrator


class DesignAssistantManager:
    """Manages multiple design assistant sessions."""

    def __init__(self):
        self._sessions: dict[str, DesignAssistantSession] = {}
        # Import here to avoid circular imports
        from clara.db.session import async_session_maker
        self._db_session_maker = async_session_maker

    async def get_or_create_session(
        self,
        session_id: str,
        project_id: str,
        initial_blueprint_state: dict | None = None
    ) -> DesignAssistantSession:
        """Get an existing session or create a new one.

        Args:
            session_id: The session ID
            project_id: The project ID
            initial_blueprint_state: Optional blueprint state to initialize with
                (used for add-agent mode to preserve existing agents)
        """
        if session_id not in self._sessions:
            session = DesignAssistantSession(session_id, project_id)
            await session.start()

            # If initial blueprint state provided, populate the tools state
            if initial_blueprint_state:
                tool_state = get_session_state(session_id)
                tool_state["project"] = initial_blueprint_state.get("project")
                tool_state["entities"] = initial_blueprint_state.get("entities", [])
                tool_state["agents"] = initial_blueprint_state.get("agents", [])
                tool_state["phase"] = DesignPhase.AGENT_CONFIGURATION.value

                # Update session state to reflect the blueprint
                if initial_blueprint_state.get("project"):
                    proj = initial_blueprint_state["project"]
                    session.state.blueprint_preview.project_name = proj.get("name")
                    session.state.blueprint_preview.project_type = proj.get("type")
                    session.state.inferred_domain = proj.get("domain")
                session.state.blueprint_preview.agent_count = len(
                    initial_blueprint_state.get("agents", [])
                )
                session.state.blueprint_preview.entity_types = [
                    e.get("name") for e in initial_blueprint_state.get("entities", [])
                ]
                session.state.phase = DesignPhase.AGENT_CONFIGURATION

                logger.info(
                    f"Initialized session {session_id} with existing blueprint "
                    f"({len(initial_blueprint_state.get('agents', []))} agents)"
                )

            self._sessions[session_id] = session
        return self._sessions[session_id]

    async def restore_session(
        self,
        session_id: str,
        project_id: str,
        db_session: Any  # DesignSession model instance
    ) -> DesignAssistantSession:
        """Restore a session from database state.

        This creates a new in-memory session and populates it with
        the state from the database record.
        """
        # If session already exists in memory, return it
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Create new in-memory session
        session = DesignAssistantSession(session_id, project_id)
        await session.start()

        # Mark as restored so context will be prepended on first message
        session._restored = True

        # Restore state from DB
        if db_session.phase:
            session.state.phase = DesignPhase(db_session.phase)
        session.state.turn_count = db_session.turn_count or 0
        session.state.message_count = db_session.message_count or 0

        # Restore blueprint preview state
        blueprint_state = db_session.blueprint_state or {}
        if blueprint_state.get("project"):
            project = blueprint_state["project"]
            session.state.blueprint_preview.project_name = project.get("name")
            session.state.blueprint_preview.project_type = project.get("type")
        session.state.blueprint_preview.entity_types = [
            e.get("name") for e in blueprint_state.get("entities", [])
        ]
        session.state.blueprint_preview.agent_count = len(blueprint_state.get("agents", []))

        # Restore goal summary (handle both goal_text and primary_goal keys)
        if db_session.goal_summary:
            goal = db_session.goal_summary
            session.state.goal_summary = goal.get("goal_text") or goal.get("primary_goal")

        # Restore agent capabilities
        if db_session.agent_capabilities:
            caps = db_session.agent_capabilities
            session.state.agent_capabilities.role = caps.get("role")
            session.state.agent_capabilities.capabilities = caps.get("capabilities", [])
            session.state.agent_capabilities.expertise_areas = caps.get("expertise_areas", [])
            session.state.agent_capabilities.interaction_style = caps.get("interaction_style")

        # Restore tools state
        tool_state = get_session_state(session_id)
        tool_state["project"] = blueprint_state.get("project")
        tool_state["entities"] = blueprint_state.get("entities", [])
        tool_state["agents"] = blueprint_state.get("agents", [])
        tool_state["phase"] = db_session.phase
        tool_state["goal_summary"] = db_session.goal_summary
        tool_state["agent_capabilities"] = db_session.agent_capabilities

        self._sessions[session_id] = session
        logger.info(f"Restored session {session_id} from database (phase: {db_session.phase})")
        return session

    async def get_session(self, session_id: str) -> DesignAssistantSession | None:
        """Get an existing session."""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close and remove a session."""
        if session_id in self._sessions:
            session = self._sessions.pop(session_id)
            await session.stop()

    async def close_all(self) -> None:
        """Close all active sessions."""
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)


# Global session manager
session_manager = DesignAssistantManager()
