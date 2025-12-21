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
    GOAL_UNDERSTANDING = "goal_understanding"
    AGENT_CONFIGURATION = "agent_configuration"
    BLUEPRINT_DESIGN = "blueprint_design"
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
class AgentCapabilities:
    """Configured specialist agent capabilities from Phase 2."""
    role: str | None = None
    capabilities: list[str] = field(default_factory=list)
    expertise_areas: list[str] = field(default_factory=list)
    interaction_style: str | None = None
    focus_areas: list[str] = field(default_factory=list)


@dataclass
class DesignSessionState:
    """State for a design assistant session."""
    session_id: str
    project_id: str
    phase: DesignPhase = DesignPhase.GOAL_UNDERSTANDING
    blueprint_preview: BlueprintPreview = field(default_factory=BlueprintPreview)
    agent_capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    goal_summary: str | None = None
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
        """Define phase-based subagents.

        Each subagent should call mcp__clara__get_prompt at the start to get
        its hydrated instructions based on the current session state.
        """
        # Base instruction for subagents to fetch their hydrated prompt
        get_prompt_instruction = (
            "IMPORTANT: First call mcp__clara__get_prompt with your phase to get your full instructions. "
            "Execute based on those instructions.\n\n"
        )

        return {
            "phase1-goal-discovery": AgentDefinition(
                description=(
                    "Handles Phase 1: Goal Understanding. "
                    "Use this agent to discover the user's project through natural conversation. "
                    "It will explore the 5 key dimensions and use mcp__clara__ask for structured choices. "
                    "After completing, call mcp__clara__hydrate_phase2 with the goal summary."
                ),
                tools=["mcp__clara__ask", "mcp__clara__project", "mcp__clara__save_goal_summary",
                       "mcp__clara__hydrate_phase2", "mcp__clara__get_prompt"],
                prompt=get_prompt_instruction + load_prompt("phase1_goal_understanding.txt"),
                model="sonnet"
            ),
            "phase2-agent-config": AgentDefinition(
                description=(
                    "Handles Phase 2: Agent Configuration. "
                    "Use this agent to analyze the goal and configure a specialized interview agent. "
                    "It will call mcp__clara__agent_summary to display the specialist card. "
                    "After completing, call mcp__clara__hydrate_phase3 with the agent config."
                ),
                tools=["mcp__clara__agent_summary", "mcp__clara__phase", "mcp__clara__get_prompt",
                       "mcp__clara__hydrate_phase3"],
                prompt=get_prompt_instruction + load_prompt("phase2_agent_configuration.txt"),
                model="sonnet"
            ),
            "phase3-blueprint-design": AgentDefinition(
                description=(
                    "Handles Phase 3: Blueprint Design. "
                    "Use this agent to design the complete interview blueprint. "
                    "It will use Mode 1 (Clarification) or Mode 2 (Blueprint Design) based on goal clarity."
                ),
                tools=["mcp__clara__project", "mcp__clara__entity", "mcp__clara__agent",
                       "mcp__clara__ask", "mcp__clara__preview", "mcp__clara__phase",
                       "mcp__clara__get_prompt"],
                prompt=get_prompt_instruction + load_prompt("phase3_blueprint_design.txt"),
                model="sonnet"
            ),
        }

    def _create_hooks(self) -> dict:
        """Create hooks for tracking agent activity."""
        response_queue = self._response_queue

        async def pre_tool_hook(
            input_data: dict[str, Any],
            tool_use_id: str | None,
            context: Any
        ) -> dict[str, Any]:
            """Track tool usage before execution."""
            import json
            # Log full input_data to understand structure
            logger.info(f"[PreToolUse] input_data keys: {list(input_data.keys())}")
            logger.info(f"[PreToolUse] full input_data: {input_data}")
            tool_name = input_data.get("tool_name", input_data.get("name", "unknown"))
            tool_input = input_data.get("tool_input", input_data.get("input", {}))
            logger.info(f"[PreToolUse] {tool_name}: {tool_input}")
            await response_queue.put(AGUIEvent(
                type="TOOL_CALL_START",
                data={"tool": tool_name, "input": tool_input}
            ))

            # Special handling for ask tool - emit UI component directly
            if tool_name == "mcp__clara__ask":
                ui_component = {
                    "type": "user_input_required",
                    "question": tool_input.get("question", ""),
                    "options": tool_input.get("options", []),
                    "multi_select": tool_input.get("multi_select", False),
                }
                ui_json = json.dumps(ui_component)
                # Emit as text content with UI_COMPONENT markers
                await response_queue.put(AGUIEvent(
                    type="TEXT_MESSAGE_CONTENT",
                    data={"delta": f"\n\n[UI_COMPONENT]{ui_json}[/UI_COMPONENT]"}
                ))
                logger.info(f"[{self.session_id}] Emitted UI component for ask tool")

            # Special handling for agent_summary tool - emit specialist agent card
            if tool_name == "mcp__clara__agent_summary":
                ui_component = {
                    "type": "agent_configured",
                    "role": tool_input.get("role", ""),
                    "expertise_areas": tool_input.get("expertise_areas", []),
                    "interaction_style": tool_input.get("interaction_style", ""),
                    "capabilities": tool_input.get("capabilities", []),
                    "focus_areas": tool_input.get("focus_areas", []),
                }
                ui_json = json.dumps(ui_component)
                await response_queue.put(AGUIEvent(
                    type="TEXT_MESSAGE_CONTENT",
                    data={"delta": f"\n\n[UI_COMPONENT]{ui_json}[/UI_COMPONENT]"}
                ))
                logger.info(f"[{self.session_id}] Emitted UI component for agent_summary tool")

            return {}  # No modifications to tool behavior

        async def post_tool_hook(
            input_data: dict[str, Any],
            tool_use_id: str | None,
            context: Any
        ) -> dict[str, Any]:
            """Track tool completion."""
            tool_name = input_data.get("tool_name", "unknown")
            logger.debug(f"[PostToolUse] {tool_name} completed")
            await response_queue.put(AGUIEvent(
                type="TOOL_CALL_END",
                data={"tool": tool_name}
            ))
            return {}

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

        # Helper to drain queued events from hooks
        async def drain_queue():
            """Yield any events queued by hooks."""
            while not self._response_queue.empty():
                try:
                    event = self._response_queue.get_nowait()
                    yield event
                except asyncio.QueueEmpty:
                    break

        # Stream response
        current_text = ""
        async for msg in self.client.receive_response():
            # First, drain any events queued by hooks
            async for event in drain_queue():
                yield event

            msg_type = type(msg).__name__
            logger.debug(f"[{self.session_id}] Message type: {msg_type}, attrs: {dir(msg)}")

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
                # Tool completed - extract and stream any text content
                tool_text = ""
                logger.info(f"[{self.session_id}] ToolResultMessage: {msg}")
                if hasattr(msg, 'content'):
                    # Content can be a list of blocks or a string
                    content = msg.content
                    logger.info(f"[{self.session_id}] Tool content type: {type(content)}, value: {content}")
                    if isinstance(content, list):
                        for block in content:
                            if hasattr(block, 'text'):
                                tool_text += block.text
                            elif isinstance(block, dict) and 'text' in block:
                                tool_text += block['text']
                    elif isinstance(content, str):
                        tool_text = content
                # Also check for 'result' attribute
                elif hasattr(msg, 'result'):
                    result = msg.result
                    logger.info(f"[{self.session_id}] Tool result type: {type(result)}, value: {result}")
                    if isinstance(result, str):
                        tool_text = result
                    elif isinstance(result, dict) and 'content' in result:
                        for block in result['content']:
                            if isinstance(block, dict) and 'text' in block:
                                tool_text += block['text']

                logger.info(f"[{self.session_id}] Extracted tool_text: {tool_text[:200] if tool_text else 'empty'}")

                # If tool result contains UI_COMPONENT, stream it
                if tool_text and '[UI_COMPONENT]' in tool_text:
                    yield AGUIEvent(
                        type="TEXT_MESSAGE_CONTENT",
                        data={"delta": tool_text}
                    )

                yield AGUIEvent(
                    type="TOOL_CALL_END",
                    data={}
                )

        # Final drain of any remaining queued events
        async for event in drain_queue():
            yield event

        # Emit end of message
        yield AGUIEvent(
            type="TEXT_MESSAGE_END",
            data={}
        )


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
        project_id: str
    ) -> DesignAssistantSession:
        """Get an existing session or create a new one."""
        if session_id not in self._sessions:
            session = DesignAssistantSession(session_id, project_id)
            await session.start()
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
        from clara.agents.tools import get_session_state

        # If session already exists in memory, return it
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Create new in-memory session
        session = DesignAssistantSession(session_id, project_id)
        await session.start()

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

        # Restore goal summary
        if db_session.goal_summary:
            session.state.goal_summary = db_session.goal_summary.get("goal_text")

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
