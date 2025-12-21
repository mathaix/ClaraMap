"""Design Assistant using Claude Agent SDK.

This module implements Clara's Design Architect agent that helps users
create Interview Blueprints through collaborative conversation.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

from clara.agents.tools import CLARA_TOOL_NAMES, clear_session_state, create_clara_tools

logger = logging.getLogger(__name__)

# Paths to prompt files
PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = PROMPTS_DIR / filename
    with open(prompt_path, encoding="utf-8") as f:
        return f.read().strip()


class DesignPhase(str, Enum):
    """Phases of the blueprint design process."""
    DISCOVERY = "discovery"
    RUBRIC = "rubric"
    AGENTS = "agents"
    REVIEW = "review"
    COMPLETE = "complete"


@dataclass
class BlueprintPreview:
    """Preview of the blueprint being designed."""
    project_name: str | None = None
    project_type: str | None = None
    entity_types: list[str] = field(default_factory=list)
    agent_count: int = 0
    topics: list[str] = field(default_factory=list)


@dataclass
class DesignSessionState:
    """State for a design assistant session."""
    session_id: str
    project_id: str
    phase: DesignPhase = DesignPhase.DISCOVERY
    blueprint_preview: BlueprintPreview = field(default_factory=BlueprintPreview)
    inferred_domain: str | None = None
    domain_confidence: float = 0.0
    turn_count: int = 0
    message_count: int = 0
    discussed_topics: list[str] = field(default_factory=list)


@dataclass
class AGUIEvent:
    """Base AG-UI event structure."""
    type: str
    data: dict[str, Any]


class DesignAssistantSession:
    """Manages a single design assistant session using Claude Agent SDK."""

    def __init__(self, session_id: str, project_id: str):
        self.session_id = session_id
        self.project_id = project_id
        self.state = DesignSessionState(
            session_id=session_id,
            project_id=project_id,
        )
        self.client: ClaudeSDKClient | None = None
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
        self._response_queue: asyncio.Queue[AGUIEvent] = asyncio.Queue()
        self._running = False

    def _create_subagents(self) -> dict[str, AgentDefinition]:
        """Define specialized subagents."""
        return {
            "domain-expert": AgentDefinition(
                description=(
                    "Analyzes the project domain and suggests interview structures. "
                    "Use this agent when you need to understand the domain context, "
                    "identify relevant interview topics, or get domain-specific recommendations."
                ),
                tools=[],  # No tools needed, just analysis
                prompt=load_prompt("domain_expert.txt"),
                model="haiku"
            ),
            "rubric-designer": AgentDefinition(
                description=(
                    "Creates entity extraction schemas and rubrics. "
                    "Use this agent when you need to define what entities to extract, "
                    "their attributes, and relationships."
                ),
                tools=[],
                prompt=load_prompt("rubric_designer.txt"),
                model="haiku"
            ),
            "agent-configurator": AgentDefinition(
                description=(
                    "Designs interview agent personas and behaviors. "
                    "Use this agent when you need to configure interview agents, "
                    "their personas, goals, and adaptive behaviors."
                ),
                tools=[],
                prompt=load_prompt("agent_configurator.txt"),
                model="haiku"
            ),
        }

    def _create_hooks(self) -> dict:
        """Create hooks for tracking agent activity."""
        async def pre_tool_hook(tool_name: str, tool_input: dict) -> None:
            """Track tool usage before execution."""
            logger.debug(f"[PreToolUse] {tool_name}: {tool_input}")
            await self._response_queue.put(AGUIEvent(
                type="TOOL_CALL_START",
                data={"tool": tool_name, "input": tool_input}
            ))

        async def post_tool_hook(tool_name: str, tool_result: Any) -> None:
            """Track tool completion."""
            logger.debug(f"[PostToolUse] {tool_name} completed")
            await self._response_queue.put(AGUIEvent(
                type="TOOL_CALL_END",
                data={"tool": tool_name}
            ))

        return {
            'PreToolUse': [
                HookMatcher(
                    matcher=None,  # Match all tools
                    hooks=[pre_tool_hook]
                )
            ],
            'PostToolUse': [
                HookMatcher(
                    matcher=None,
                    hooks=[post_tool_hook]
                )
            ]
        }

    async def start(self) -> None:
        """Start the design assistant session."""
        if self._running:
            return

        architect_prompt = load_prompt("architect.txt")
        agents = self._create_subagents()
        hooks = self._create_hooks()

        # Create MCP server with custom tools bound to this session
        clara_mcp_server = create_clara_tools(self.session_id)

        options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            system_prompt=architect_prompt,
            allowed_tools=["Task"] + CLARA_TOOL_NAMES,  # Task for subagents + custom tools
            agents=agents,
            hooks=hooks,
            mcp_servers={"clara": clara_mcp_server},  # Register our custom MCP server
            model="sonnet"
        )

        self.client = ClaudeSDKClient(options=options)
        await self.client.__aenter__()
        self._running = True
        logger.info(f"Design session {self.session_id} started with Clara tools")

    async def stop(self) -> None:
        """Stop the design assistant session."""
        if self.client and self._running:
            await self.client.__aexit__(None, None, None)
            self._running = False
            # Clean up in-memory tool state
            clear_session_state(self.session_id)
            logger.info(f"Design session {self.session_id} stopped")

    async def send_message(self, message: str) -> AsyncIterator[AGUIEvent]:
        """Send a message and stream the response as AG-UI events."""
        if not self._running or not self.client:
            raise RuntimeError("Session not started")

        self.state.message_count += 1
        self.state.turn_count += 1

        # Emit state snapshot at start of turn
        yield AGUIEvent(
            type="STATE_SNAPSHOT",
            data={
                "phase": self.state.phase.value,
                "preview": {
                    "project_name": self.state.blueprint_preview.project_name,
                    "project_type": self.state.blueprint_preview.project_type,
                    "entity_types": self.state.blueprint_preview.entity_types,
                    "agent_count": self.state.blueprint_preview.agent_count,
                    "topics": self.state.blueprint_preview.topics,
                },
                "inferred_domain": self.state.inferred_domain,
                "debug": {
                    "thinking": None,
                    "approach": None,
                    "turn_count": self.state.turn_count,
                    "message_count": self.state.message_count,
                    "domain_confidence": self.state.domain_confidence,
                    "discussed_topics": self.state.discussed_topics,
                }
            }
        )

        # Send message to agent
        await self.client.query(prompt=message)

        # Stream response
        current_text = ""
        async for msg in self.client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                # Extract text content from the message
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            new_text = block.text
                            if new_text and new_text != current_text:
                                # Emit text delta
                                delta = new_text[len(current_text):]
                                current_text = new_text
                                yield AGUIEvent(
                                    type="TEXT_MESSAGE_CONTENT",
                                    data={"delta": delta}
                                )

            elif msg_type == 'ToolUseMessage':
                # Tool being used
                if hasattr(msg, 'name') and hasattr(msg, 'input'):
                    yield AGUIEvent(
                        type="TOOL_CALL_START",
                        data={"tool": msg.name, "input": msg.input}
                    )

            elif msg_type == 'ToolResultMessage':
                # Tool completed
                yield AGUIEvent(
                    type="TOOL_CALL_END",
                    data={}
                )

        # Emit end of message
        yield AGUIEvent(
            type="TEXT_MESSAGE_END",
            data={}
        )


class DesignAssistantManager:
    """Manages multiple design assistant sessions."""

    def __init__(self):
        self._sessions: dict[str, DesignAssistantSession] = {}

    async def get_or_create_session(
        self,
        session_id: str,
        project_id: str
    ) -> DesignAssistantSession:
        """Get an existing session or create a new one."""
        if session_id not in self._sessions:
            session = DesignAssistantSession(session_id, project_id)
            await session.start()
            self._sessions[session_id] = session
        return self._sessions[session_id]

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
