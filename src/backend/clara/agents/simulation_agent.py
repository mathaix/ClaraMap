"""Simulation Agent for testing interview prompts.

A simple conversational agent that uses a custom system prompt to simulate
how the interviewer agent would behave during an actual interview.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


@dataclass
class AGUIEvent:
    """AG-UI compatible event."""
    type: str
    data: dict = field(default_factory=dict)


@dataclass
class SimulationSession:
    """A simulation session for testing interview prompts."""

    session_id: str
    system_prompt: str
    messages: list[dict] = field(default_factory=list)
    _client: AsyncAnthropic | None = None

    def __post_init__(self):
        self._client = AsyncAnthropic()

    async def send_message(self, user_message: str) -> AsyncGenerator[AGUIEvent, None]:
        """Send a message and stream the response as AG-UI events."""
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Build messages for API call
        api_messages = self.messages.copy()

        try:
            # Stream response from Claude
            async with self._client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=self.system_prompt,
                messages=api_messages,
            ) as stream:
                assistant_content = ""

                async for text in stream.text_stream:
                    assistant_content += text
                    yield AGUIEvent(
                        type="TEXT_MESSAGE_CONTENT",
                        data={"delta": text}
                    )

                # Store assistant message
                self.messages.append({"role": "assistant", "content": assistant_content})

                yield AGUIEvent(type="TEXT_MESSAGE_END", data={})

        except Exception as e:
            logger.exception(f"Error in simulation: {e}")
            yield AGUIEvent(
                type="ERROR",
                data={"message": str(e)}
            )

    def reset(self):
        """Reset conversation history."""
        self.messages = []


class SimulationSessionManager:
    """Manages simulation sessions."""

    def __init__(self):
        self._sessions: dict[str, SimulationSession] = {}

    async def create_session(
        self,
        session_id: str,
        system_prompt: str,
    ) -> SimulationSession:
        """Create a new simulation session."""
        session = SimulationSession(
            session_id=session_id,
            system_prompt=system_prompt,
        )
        self._sessions[session_id] = session
        logger.info(f"Created simulation session {session_id}")
        return session

    async def get_session(self, session_id: str) -> SimulationSession | None:
        """Get an existing simulation session."""
        return self._sessions.get(session_id)

    async def update_prompt(self, session_id: str, system_prompt: str):
        """Update the system prompt for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.system_prompt = system_prompt
            session.reset()  # Reset conversation when prompt changes
            logger.info(f"Updated prompt for simulation session {session_id}")

    async def close_session(self, session_id: str):
        """Close and remove a simulation session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Closed simulation session {session_id}")


# Global session manager
simulation_manager = SimulationSessionManager()
