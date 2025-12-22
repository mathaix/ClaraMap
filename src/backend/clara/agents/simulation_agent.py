"""Simulation Agent for testing interview prompts.

Supports two modes:
1. Manual mode: Human plays interviewee, Interview Agent responds
2. Auto mode: Simulated User (with persona from website) plays interviewee

The Interview Agent always introduces itself first when the simulation starts.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

logger = logging.getLogger(__name__)

# Session TTL in minutes
SESSION_TTL_MINUTES = 60
# Maximum message history
MAX_MESSAGE_HISTORY = 20


@dataclass
class AGUIEvent:
    """AG-UI compatible event."""
    type: str
    data: dict = field(default_factory=dict)


@dataclass
class PersonaConfig:
    """Configuration for a simulated user persona."""
    role: str  # e.g., "Product Manager", "Senior Engineer"
    company_url: str | None = None  # Website to fetch context from
    company_context: str | None = None  # Fetched context about the company
    name: str | None = None  # Optional name for the persona
    experience_years: int | None = None
    communication_style: str = "professional"  # professional, casual, detailed, brief


@dataclass
class SimulationSession:
    """A simulation session for testing interview prompts.

    The session contains:
    - Interview Agent: Uses the blueprint's system prompt to conduct interviews
    - Simulated User (optional): AI persona that plays the interviewee role
    """

    session_id: str
    interviewer_prompt: str  # The system prompt for the interview agent
    persona: PersonaConfig | None = None  # For auto-simulation mode
    messages: list[dict] = field(default_factory=list)

    # Timestamps for TTL cleanup
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # Internal state
    _interviewer_client: ClaudeSDKClient | None = field(default=None, repr=False)
    _simulated_user_client: ClaudeSDKClient | None = field(default=None, repr=False)
    _running: bool = field(default=False, repr=False)
    _introduction_sent: bool = field(default=False, repr=False)

    async def start(self) -> None:
        """Start the simulation session."""
        if self._running:
            return

        # Create the Interview Agent
        interviewer_options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            system_prompt=self.interviewer_prompt,
            allowed_tools=[],
            model="sonnet"
        )
        self._interviewer_client = ClaudeSDKClient(options=interviewer_options)
        await self._interviewer_client.__aenter__()

        # Create Simulated User if persona is configured
        if self.persona:
            simulated_user_prompt = self._build_simulated_user_prompt()
            user_options = ClaudeAgentOptions(
                permission_mode="bypassPermissions",
                system_prompt=simulated_user_prompt,
                allowed_tools=[],
                model="haiku"  # Use faster model for simulated user
            )
            self._simulated_user_client = ClaudeSDKClient(options=user_options)
            await self._simulated_user_client.__aenter__()

        self._running = True
        logger.info(f"Started simulation session {self.session_id}")

    async def stop(self) -> None:
        """Stop the simulation session."""
        if self._interviewer_client and self._running:
            await self._interviewer_client.__aexit__(None, None, None)
        if self._simulated_user_client:
            await self._simulated_user_client.__aexit__(None, None, None)
        self._running = False
        logger.info(f"Stopped simulation session {self.session_id}")

    def _build_simulated_user_prompt(self) -> str:
        """Build the system prompt for the simulated user."""
        if not self.persona:
            return ""

        parts = [
            "You are playing the role of an interviewee in a discovery interview.",
            f"Your role is: {self.persona.role}",
        ]

        if self.persona.name:
            parts.append(f"Your name is: {self.persona.name}")

        if self.persona.experience_years:
            years = self.persona.experience_years
            parts.append(f"You have {years} years of experience in this role.")

        if self.persona.company_context:
            ctx = self.persona.company_context
            parts.append(f"\nHere is context about your company/organization:\n{ctx}")

        parts.extend([
            f"\nCommunication style: {self.persona.communication_style}",
            "\nInstructions:",
            "- Respond naturally as someone in this role would",
            "- Draw on the company context to provide realistic answers",
            "- If asked about something not in context, improvise realistic details",
            "- Be helpful and engaged, but realistic about challenges",
            "- Keep responses conversational and appropriately detailed",
            "- Don't break character or mention that you're an AI",
        ])

        return "\n".join(parts)

    async def get_introduction(self) -> AsyncGenerator[AGUIEvent, None]:
        """Get the interview agent's introduction.

        This should be called when the simulation starts to have the
        interviewer introduce themselves and explain the interview context.
        """
        if not self._running or not self._interviewer_client:
            raise RuntimeError("Session not started")

        if self._introduction_sent:
            return

        # Ask the interviewer to introduce themselves
        intro_prompt = (
            "Please introduce yourself to the interviewee. Explain who you are, "
            "the purpose of this interview, what topics you'll cover, and how the "
            "interview will proceed. Make the interviewee feel comfortable."
        )

        await self._interviewer_client.query(prompt=intro_prompt)

        current_text = ""
        async for msg in self._interviewer_client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            new_text = block.text
                            if new_text and new_text != current_text:
                                if current_text and new_text.startswith(current_text):
                                    delta = new_text[len(current_text):]
                                else:
                                    delta = new_text
                                current_text = new_text
                                if delta:
                                    yield AGUIEvent(
                                        type="TEXT_MESSAGE_CONTENT",
                                        data={"delta": delta, "role": "assistant"}
                                    )

        # Store the introduction message
        if current_text:
            self.messages.append({"role": "assistant", "content": current_text})
            self._introduction_sent = True

        yield AGUIEvent(type="TEXT_MESSAGE_END", data={"role": "assistant"})

    async def send_user_message(self, user_message: str) -> AsyncGenerator[AGUIEvent, None]:
        """Send a message from the user (human or simulated) and get the interviewer's response."""
        if not self._running or not self._interviewer_client:
            raise RuntimeError("Session not started")

        # Update last activity
        self.last_activity = datetime.now()

        # Store user message
        self.messages.append({"role": "user", "content": user_message})

        # Limit message history
        if len(self.messages) > MAX_MESSAGE_HISTORY:
            self.messages = self.messages[-MAX_MESSAGE_HISTORY:]

        try:
            await self._interviewer_client.query(prompt=user_message)

            current_text = ""
            async for msg in self._interviewer_client.receive_response():
                msg_type = type(msg).__name__

                if msg_type == 'AssistantMessage':
                    if hasattr(msg, 'content'):
                        for block in msg.content:
                            if hasattr(block, 'text'):
                                new_text = block.text
                                if new_text and new_text != current_text:
                                    if current_text and new_text.startswith(current_text):
                                        delta = new_text[len(current_text):]
                                    else:
                                        delta = new_text
                                    current_text = new_text
                                    if delta:
                                        yield AGUIEvent(
                                            type="TEXT_MESSAGE_CONTENT",
                                            data={"delta": delta, "role": "assistant"}
                                        )

            # Store assistant message
            if current_text:
                self.messages.append({"role": "assistant", "content": current_text})

            yield AGUIEvent(type="TEXT_MESSAGE_END", data={"role": "assistant"})

        except Exception as e:
            logger.exception(f"Error in simulation: {e}")
            yield AGUIEvent(
                type="ERROR",
                data={"message": str(e)}
            )

    async def get_simulated_user_response(
        self, interviewer_message: str
    ) -> AsyncGenerator[AGUIEvent, None]:
        """Get a response from the simulated user to an interviewer message.

        This is used in auto-simulation mode where an AI plays the interviewee.
        """
        if not self._simulated_user_client:
            raise RuntimeError("No simulated user configured")

        try:
            await self._simulated_user_client.query(prompt=interviewer_message)

            current_text = ""
            async for msg in self._simulated_user_client.receive_response():
                msg_type = type(msg).__name__

                if msg_type == 'AssistantMessage':
                    if hasattr(msg, 'content'):
                        for block in msg.content:
                            if hasattr(block, 'text'):
                                new_text = block.text
                                if new_text and new_text != current_text:
                                    if current_text and new_text.startswith(current_text):
                                        delta = new_text[len(current_text):]
                                    else:
                                        delta = new_text
                                    current_text = new_text
                                    if delta:
                                        yield AGUIEvent(
                                            type="SIMULATED_USER_CONTENT",
                                            data={"delta": delta, "role": "simulated_user"}
                                        )

            yield AGUIEvent(
                type="SIMULATED_USER_END",
                data={"role": "simulated_user", "content": current_text}
            )

        except Exception as e:
            logger.exception(f"Error getting simulated user response: {e}")
            yield AGUIEvent(
                type="ERROR",
                data={"message": str(e)}
            )

    async def run_auto_simulation(self, num_turns: int = 5) -> AsyncGenerator[AGUIEvent, None]:
        """Run an automated simulation with the simulated user.

        Args:
            num_turns: Number of back-and-forth turns to simulate
        """
        if not self._simulated_user_client:
            raise RuntimeError("No simulated user configured for auto simulation")

        # First, get the interviewer's introduction
        if not self._introduction_sent:
            async for event in self.get_introduction():
                yield event

        # Get the last assistant message (the introduction)
        last_interviewer_msg = ""
        for msg in reversed(self.messages):
            if msg["role"] == "assistant":
                last_interviewer_msg = msg["content"]
                break

        # Run the conversation turns
        for turn in range(num_turns):
            # Get simulated user response
            simulated_response = ""
            async for event in self.get_simulated_user_response(last_interviewer_msg):
                yield event
                if event.type == "SIMULATED_USER_END":
                    simulated_response = event.data.get("content", "")

            if not simulated_response:
                break

            # Store as user message and send to interviewer
            self.messages.append({"role": "user", "content": simulated_response})

            # Get interviewer response
            async for event in self.send_user_message(simulated_response):
                yield event

            # Get last interviewer message for next turn
            for msg in reversed(self.messages):
                if msg["role"] == "assistant":
                    last_interviewer_msg = msg["content"]
                    break

        yield AGUIEvent(type="SIMULATION_COMPLETE", data={"turns": num_turns})

    def reset(self):
        """Reset conversation history."""
        self.messages = []
        self._introduction_sent = False


async def fetch_website_context(url: str) -> str:
    """Fetch and extract relevant context from a website."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Get raw HTML
            html = response.text

            # Simple extraction - get text content
            # In production, you'd use a proper HTML parser
            import re

            # Remove script and style tags
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', html)

            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()

            # Limit to reasonable size
            if len(text) > 5000:
                text = text[:5000] + "..."

            return text

    except Exception as e:
        logger.warning(f"Failed to fetch website context from {url}: {e}")
        return f"(Could not fetch website content: {e})"


class SimulationSessionManager:
    """Manages simulation sessions."""

    def __init__(self):
        self._sessions: dict[str, SimulationSession] = {}

    async def cleanup_stale_sessions(self) -> int:
        """Remove sessions that have exceeded the TTL.

        Returns:
            Number of sessions cleaned up
        """
        cutoff = datetime.now() - timedelta(minutes=SESSION_TTL_MINUTES)
        stale_ids = [
            sid for sid, session in self._sessions.items()
            if session.last_activity < cutoff
        ]

        for sid in stale_ids:
            await self.close_session(sid)

        if stale_ids:
            logger.info(f"Cleaned up {len(stale_ids)} stale simulation sessions")

        return len(stale_ids)

    async def create_session(
        self,
        session_id: str,
        interviewer_prompt: str,
        persona: PersonaConfig | None = None,
    ) -> SimulationSession:
        """Create a new simulation session."""
        # Fetch website context if persona has a URL
        if persona and persona.company_url and not persona.company_context:
            persona.company_context = await fetch_website_context(persona.company_url)

        session = SimulationSession(
            session_id=session_id,
            interviewer_prompt=interviewer_prompt,
            persona=persona,
        )
        await session.start()
        self._sessions[session_id] = session
        logger.info(f"Created simulation session {session_id}")
        return session

    async def get_session(self, session_id: str) -> SimulationSession | None:
        """Get an existing simulation session."""
        return self._sessions.get(session_id)

    async def update_persona(
        self,
        session_id: str,
        persona: PersonaConfig,
    ) -> None:
        """Update the persona for a session."""
        session = self._sessions.get(session_id)
        if session:
            # Fetch website context if needed
            if persona.company_url and not persona.company_context:
                persona.company_context = await fetch_website_context(persona.company_url)

            # Need to restart session with new persona
            await session.stop()
            session.persona = persona
            session.reset()
            await session.start()
            logger.info(f"Updated persona for simulation session {session_id}")

    async def close_session(self, session_id: str):
        """Close and remove a simulation session."""
        if session_id in self._sessions:
            session = self._sessions.pop(session_id)
            await session.stop()
            logger.info(f"Closed simulation session {session_id}")

    async def update_prompt(self, session_id: str, new_prompt: str) -> None:
        """Update the system prompt for a session.

        This restarts the session with the new prompt and resets conversation history.
        """
        session = self._sessions.get(session_id)
        if session:
            await session.stop()
            session.interviewer_prompt = new_prompt
            session.reset()
            await session.start()
            logger.info(f"Updated prompt for simulation session {session_id}")


# Global session manager
simulation_manager = SimulationSessionManager()
