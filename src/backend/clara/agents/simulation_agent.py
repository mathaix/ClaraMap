"""Simulation Agent for testing interview prompts.

Supports two modes:
1. Manual mode: Human plays interviewee, Interview Agent responds
2. Auto mode: Simulated User (with persona from website) plays interviewee

The Interview Agent always introduces itself first when the simulation starts.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse

import anthropic
import httpx
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from clara.config import settings

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


# Valid model options for simulation
VALID_MODELS = {"sonnet", "haiku", "opus"}

# Map friendly names to Claude SDK model identifiers
MODEL_ID_MAP = {
    "sonnet": "claude-sonnet-4-20250514",
    "haiku": "claude-3-5-haiku-20241022",  # Claude 3.5 Haiku (fast model)
    "opus": "claude-opus-4-20250514",
}


@dataclass
class SimulationSession:
    """A simulation session for testing interview prompts.

    The session contains:
    - Interview Agent: Uses the blueprint's system prompt to conduct interviews
    - Simulated User (optional): AI persona that plays the interviewee role
    """

    session_id: str
    interviewer_prompt: str  # The system prompt for the interview agent
    model: str = field(default_factory=lambda: settings.simulation_interviewer_model)
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

        # Convert friendly model name to full Claude SDK model identifier
        model_id = MODEL_ID_MAP.get(self.model, MODEL_ID_MAP["sonnet"])

        # Create the Interview Agent
        interviewer_options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            system_prompt=self.interviewer_prompt,
            allowed_tools=[],
            model=model_id
        )
        self._interviewer_client = ClaudeSDKClient(options=interviewer_options)
        await self._interviewer_client.__aenter__()

        # Create Simulated User if persona is configured
        if self.persona:
            simulated_user_prompt = self._build_simulated_user_prompt()
            user_model_id = MODEL_ID_MAP.get(
                settings.simulation_user_model, MODEL_ID_MAP["haiku"]
            )
            user_options = ClaudeAgentOptions(
                permission_mode="bypassPermissions",
                system_prompt=simulated_user_prompt,
                allowed_tools=[],
                model=user_model_id
            )
            self._simulated_user_client = ClaudeSDKClient(options=user_options)
            await self._simulated_user_client.__aenter__()

        self._running = True
        logger.info(f"Started simulation session {self.session_id}")

    async def stop(self) -> None:
        """Stop the simulation session."""
        # Always cleanup both clients if they exist, regardless of _running state
        try:
            if self._interviewer_client:
                await self._interviewer_client.__aexit__(None, None, None)
                self._interviewer_client = None
        except Exception as e:
            logger.warning(f"Error closing interviewer client: {e}")

        try:
            if self._simulated_user_client:
                await self._simulated_user_client.__aexit__(None, None, None)
                self._simulated_user_client = None
        except Exception as e:
            logger.warning(f"Error closing simulated user client: {e}")

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


def is_safe_url(url: str) -> bool:
    """Check if a URL is safe to fetch (not localhost/internal)."""
    import ipaddress
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)

        # Must be http or https
        if parsed.scheme not in ("http", "https"):
            return False

        # Must have a host
        if not parsed.hostname:
            return False

        hostname = parsed.hostname.lower()

        # Block localhost variations
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        # Block common internal hostnames
        if hostname.endswith(".local") or hostname.endswith(".internal"):
            return False

        # Try to parse as IP and block private/reserved ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return False
            # Block cloud metadata endpoints
            if str(ip).startswith("169.254."):
                return False
        except ValueError:
            # Not an IP address, that's fine
            pass

        return True
    except Exception:
        return False


# Constants for fetch_website_context
MAX_CONTENT_LENGTH = 1_000_000  # 1MB max
MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = {"text/html", "text/plain", "application/xhtml+xml"}
MAX_TEXT_LENGTH = 5000


async def fetch_website_context(url: str) -> str:
    """Fetch and extract relevant context from a website.

    Includes SSRF protection to block internal/localhost URLs.
    """
    # Validate URL to prevent SSRF
    if not is_safe_url(url):
        logger.warning(f"Blocked unsafe URL: {url}")
        return "(URL blocked: only public HTTP/HTTPS URLs are allowed)"

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Validate Content-Type
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                logger.warning(f"Blocked non-HTML content type: {content_type}")
                return f"(Content type not supported: {content_type})"

            # Check Content-Length if available
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_CONTENT_LENGTH:
                logger.warning(f"Content too large: {content_length} bytes")
                return "(Content too large to process)"

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
            if len(text) > MAX_TEXT_LENGTH:
                text = text[:MAX_TEXT_LENGTH] + "..."

            return text

    except httpx.TooManyRedirects:
        logger.warning(f"Too many redirects for URL: {url}")
        return "(Too many redirects)"
    except Exception as e:
        logger.warning(f"Failed to fetch website context from {url}: {e}")
        return f"(Could not fetch website content: {e})"


def extract_company_name_from_url(url: str) -> str:
    """Extract a clean company name from a URL."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        # Remove common prefixes
        hostname = hostname.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]

        # Get the main domain part (before TLD)
        parts = hostname.split(".")
        if len(parts) >= 2:
            # Return the main domain name (e.g., "facebook" from "facebook.com")
            return parts[0].capitalize()
        return hostname.capitalize()
    except Exception:
        return "the company"


async def search_company_products(url: str, role: str | None = None) -> str:
    """Use web search to gather information about a company's products.

    Uses Claude with web search to understand what products/services
    the company offers, which provides richer context for the persona.

    Args:
        url: The company's website URL
        role: Optional role to focus the search (e.g., "Product Manager for Instagram")

    Returns:
        A summary of the company's products and services
    """
    company_name = extract_company_name_from_url(url)

    # Build a focused search query
    if role:
        # Extract product name if role mentions it (e.g., "Product Manager for Instagram")
        role_lower = role.lower()
        search_query = f"{company_name} products services overview"
        if "for " in role_lower:
            product_focus = role.split("for ")[-1].strip()
            search_query = f"{company_name} {product_focus} product features"
    else:
        search_query = f"{company_name} products services overview"

    logger.info(f"Searching for company products: {search_query}")

    try:
        client = anthropic.Anthropic()

        # Build the research prompt
        focus_item = ""
        if role and "for " in role.lower():
            focus_item = f"\n5. Specifically focus on: {role.split('for ')[-1]}"

        research_prompt = f"""Research {company_name} (website: {url}) and provide a \
comprehensive summary of their products and services.

Focus on:
1. Main products and services offered
2. Key features and capabilities
3. Target customers/market
4. Recent developments or notable features{focus_item}

Provide a detailed summary that would help someone understand what it's like \
to work at this company in a product/technical role."""

        # Use Claude with web search tool
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": research_prompt}],
        )

        # Extract the text response
        result_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                result_text += block.text

        if result_text:
            logger.info(f"Successfully gathered company context via web search for {company_name}")
            return result_text

        return f"(Could not find detailed product information for {company_name})"

    except anthropic.APIError as e:
        logger.warning(f"Anthropic API error during web search: {e}")
        return f"(Web search unavailable: {e})"
    except Exception as e:
        logger.warning(f"Error during company product search: {e}")
        return f"(Could not search for company products: {e})"


async def gather_company_context(url: str, role: str | None = None) -> str:
    """Gather comprehensive context about a company using web search and website scraping.

    This combines web search results with direct website content for richer context.

    Args:
        url: The company's website URL
        role: Optional role to focus the research

    Returns:
        Combined context about the company
    """
    # Run web search and website fetch in parallel
    search_task = asyncio.create_task(search_company_products(url, role))
    website_task = asyncio.create_task(fetch_website_context(url))

    search_result, website_result = await asyncio.gather(
        search_task, website_task, return_exceptions=True
    )

    # Handle any exceptions
    if isinstance(search_result, Exception):
        search_result = f"(Web search failed: {search_result})"
    if isinstance(website_result, Exception):
        website_result = f"(Website fetch failed: {website_result})"

    # Combine results
    company_name = extract_company_name_from_url(url)
    context_parts = [f"## Company: {company_name}"]

    if search_result and not search_result.startswith("("):
        context_parts.append("\n### Product & Service Information (from web search)")
        context_parts.append(search_result)

    if website_result and not website_result.startswith("("):
        context_parts.append("\n### Website Content")
        context_parts.append(website_result[:2000])  # Limit website content

    if len(context_parts) == 1:
        # Neither source worked
        return f"(Could not gather information about {company_name})"

    return "\n".join(context_parts)


class SimulationSessionManager:
    """Manages simulation sessions with thread-safe operations."""

    def __init__(self):
        self._sessions: dict[str, SimulationSession] = {}
        self._lock = asyncio.Lock()

    async def cleanup_stale_sessions(self) -> int:
        """Remove sessions that have exceeded the TTL.

        Returns:
            Number of sessions cleaned up
        """
        async with self._lock:
            cutoff = datetime.now() - timedelta(minutes=SESSION_TTL_MINUTES)
            stale_ids = [
                sid for sid, session in self._sessions.items()
                if session.last_activity < cutoff
            ]

            for sid in stale_ids:
                if sid in self._sessions:
                    session = self._sessions.pop(sid)
                    await session.stop()

            if stale_ids:
                logger.info(f"Cleaned up {len(stale_ids)} stale simulation sessions")

            return len(stale_ids)

    async def create_session(
        self,
        session_id: str,
        interviewer_prompt: str,
        persona: PersonaConfig | None = None,
        model: str | None = None,
    ) -> SimulationSession:
        """Create a new simulation session.

        Args:
            session_id: Unique identifier for the session
            interviewer_prompt: System prompt for the interview agent
            persona: Optional persona config for auto-simulation mode
            model: Optional model to use (sonnet, haiku, opus). Defaults to config setting.
        """
        # Validate model if provided
        if model and model not in VALID_MODELS:
            raise ValueError(f"Invalid model '{model}'. Must be one of: {', '.join(VALID_MODELS)}")

        # Gather company context using web search if persona has a URL
        # (outside lock for performance)
        if persona and persona.company_url and not persona.company_context:
            persona.company_context = await gather_company_context(
                persona.company_url, persona.role
            )

        session = SimulationSession(
            session_id=session_id,
            interviewer_prompt=interviewer_prompt,
            model=model or settings.simulation_interviewer_model,
            persona=persona,
        )
        await session.start()

        async with self._lock:
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
            # Gather company context using web search if needed
            if persona.company_url and not persona.company_context:
                persona.company_context = await gather_company_context(
                    persona.company_url, persona.role
                )

            # Need to restart session with new persona
            await session.stop()
            session.persona = persona
            session.reset()
            await session.start()
            logger.info(f"Updated persona for simulation session {session_id}")

    async def close_session(self, session_id: str):
        """Close and remove a simulation session."""
        async with self._lock:
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
