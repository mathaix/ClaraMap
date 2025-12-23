"""Thin Orchestrator for the Design Assistant.

The orchestrator is responsible for:
1. Looking up the current phase from session state
2. Routing messages to the correct phase agent
3. Streaming events from the phase agent
4. Handling phase transitions

It does NOT contain conversation logic - that lives in the phase agents.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, ClaudeSDKClient

from clara.agents.phase_agents import (
    AgentConfigurationAgent,
    BasePhaseAgent,
    BlueprintDesignAgent,
    GoalUnderstandingAgent,
)
from clara.agents.phase_agents.base import AGUIEvent
from clara.agents.tools import (
    CLARA_TOOL_NAMES,
    create_clara_tools,
    get_session_state,
)

logger = logging.getLogger(__name__)


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


class DesignOrchestrator:
    """Thin orchestrator that routes messages to phase agents.

    The orchestrator is intentionally simple - it just routes to agents
    and handles phase transitions. All conversation logic lives in the
    phase agents themselves.
    """

    def __init__(self, session_id: str, project_id: str):
        self.session_id = session_id
        self.project_id = project_id
        self.state = DesignSessionState(
            session_id=session_id,
            project_id=project_id,
        )

        # Event queue for hooks to emit events
        self._event_queue: asyncio.Queue[AGUIEvent] = asyncio.Queue()

        # Phase agents (lazy-initialized)
        self._phase_agents: dict[str, BasePhaseAgent] = {}
        self._client: ClaudeSDKClient | None = None
        self._running = False
        self._restored = False
        self._first_message_sent = False

    def _get_phase_agent(self, phase: DesignPhase) -> BasePhaseAgent:
        """Get or create the agent for a phase."""
        phase_str = phase.value
        if phase_str not in self._phase_agents:
            if phase == DesignPhase.GOAL_UNDERSTANDING:
                self._phase_agents[phase_str] = GoalUnderstandingAgent(
                    self.session_id, self._event_queue
                )
            elif phase == DesignPhase.AGENT_CONFIGURATION:
                self._phase_agents[phase_str] = AgentConfigurationAgent(
                    self.session_id, self._event_queue
                )
            elif phase == DesignPhase.BLUEPRINT_DESIGN:
                self._phase_agents[phase_str] = BlueprintDesignAgent(
                    self.session_id, self._event_queue
                )
            else:
                raise ValueError(f"No agent for phase: {phase}")

        return self._phase_agents[phase_str]

    def _create_subagents(self) -> dict[str, AgentDefinition]:
        """Create SDK agent definitions from phase agents."""
        agents = {}
        tool_state = get_session_state(self.session_id)

        for phase in [
            DesignPhase.GOAL_UNDERSTANDING,
            DesignPhase.AGENT_CONFIGURATION,
            DesignPhase.BLUEPRINT_DESIGN,
        ]:
            agent = self._get_phase_agent(phase)
            prompt = agent.get_prompt(tool_state)

            # Map phase to agent name
            name_map = {
                DesignPhase.GOAL_UNDERSTANDING: "phase1-goal-discovery",
                DesignPhase.AGENT_CONFIGURATION: "phase2-agent-config",
                DesignPhase.BLUEPRINT_DESIGN: "phase3-blueprint-design",
            }

            agents[name_map[phase]] = AgentDefinition(
                description=agent.get_description(),
                tools=agent.tools,
                prompt=prompt,
                model="sonnet"
            )

        return agents

    def _create_hooks(self) -> dict:
        """Create hooks that delegate to the current phase agent."""
        async def pre_tool_hook(
            input_data: dict[str, Any],
            tool_use_id: str | None,
            context: Any
        ) -> dict[str, Any]:
            agent = self._get_phase_agent(self.state.phase)
            return await agent._pre_tool_hook(input_data, tool_use_id, context)

        async def post_tool_hook(
            input_data: dict[str, Any],
            tool_use_id: str | None,
            context: Any
        ) -> dict[str, Any]:
            agent = self._get_phase_agent(self.state.phase)
            return await agent._post_tool_hook(input_data, tool_use_id, context)

        from claude_agent_sdk import HookMatcher
        return {
            'PreToolUse': [
                HookMatcher(matcher=None, hooks=[pre_tool_hook])
            ],
            'PostToolUse': [
                HookMatcher(matcher=None, hooks=[post_tool_hook])
            ]
        }

    def _sync_state_from_tools(self) -> None:
        """Sync session state from tool state."""
        tool_state = get_session_state(self.session_id)

        # Sync phase
        if tool_state.get("phase"):
            try:
                self.state.phase = DesignPhase(tool_state["phase"])
            except ValueError:
                logger.warning(f"[{self.session_id}] Unknown phase: {tool_state['phase']}")

        # Sync blueprint preview
        if tool_state.get("project"):
            project = tool_state["project"]
            self.state.blueprint_preview.project_name = project.get("name")
            self.state.blueprint_preview.project_type = project.get("type")
            self.state.inferred_domain = project.get("domain")

        if tool_state.get("entities"):
            self.state.blueprint_preview.entity_types = [
                e.get("name") for e in tool_state["entities"] if e.get("name")
            ]

        if tool_state.get("agents"):
            self.state.blueprint_preview.agent_count = len(tool_state["agents"])

        # Sync agent capabilities
        if tool_state.get("agent_capabilities"):
            caps = tool_state["agent_capabilities"]
            self.state.agent_capabilities.role = caps.get("role")
            self.state.agent_capabilities.capabilities = caps.get("capabilities", [])
            self.state.agent_capabilities.expertise_areas = caps.get("expertise_areas", [])
            self.state.agent_capabilities.interaction_style = caps.get("interaction_style")
            self.state.agent_capabilities.focus_areas = caps.get("focus_areas", [])

        # Sync goal summary
        if tool_state.get("goal_summary"):
            goal = tool_state["goal_summary"]
            self.state.goal_summary = goal.get("goal_text") or goal.get("primary_goal")

    def _on_phase_change(self, new_phase: str) -> None:
        """Callback when phase changes via mcp__clara__phase tool."""
        try:
            self.state.phase = DesignPhase(new_phase)
            logger.info(f"[{self.session_id}] Phase updated to: {new_phase}")
        except ValueError:
            logger.warning(f"[{self.session_id}] Unknown phase in callback: {new_phase}")

    def _build_state_snapshot_event(self) -> AGUIEvent:
        """Build a STATE_SNAPSHOT event from current session state."""
        return AGUIEvent(
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

    def _build_restoration_context(self) -> str:
        """Build a context summary for restored sessions."""
        parts = [
            "[SESSION CONTEXT - INTERNAL ONLY. Do NOT quote or reveal this to the user.]"
        ]

        parts.append(f"Current Phase: {self.state.phase.value}")

        if self.state.goal_summary:
            parts.append(f"Project Goal: {self.state.goal_summary}")

        if self.state.blueprint_preview.project_name:
            proj_name = self.state.blueprint_preview.project_name
            proj_type = self.state.blueprint_preview.project_type or 'unknown type'
            parts.append(f"Project: {proj_name} ({proj_type})")

        if self.state.blueprint_preview.entity_types:
            parts.append(f"Entity Types: {', '.join(self.state.blueprint_preview.entity_types)}")

        if self.state.blueprint_preview.agent_count > 0:
            parts.append(f"Configured Agents: {self.state.blueprint_preview.agent_count}")

        if self.state.agent_capabilities.role:
            caps = self.state.agent_capabilities
            parts.append(f"Specialist Agent: {caps.role}")
            if caps.expertise_areas:
                parts.append(f"Expertise: {', '.join(caps.expertise_areas)}")

        turns = self.state.turn_count
        msgs = self.state.message_count
        parts.append(f"Conversation Progress: {turns} turns, {msgs} messages")
        parts.append("[END SESSION CONTEXT]\n\nUser continues the conversation:")

        return "\n".join(parts)

    async def start(self) -> None:
        """Start the orchestrator."""
        if self._running:
            return

        from clara.agents.phase_agents.base import load_prompt

        orchestrator_prompt = load_prompt("interview_orchestrator.txt")
        agents = self._create_subagents()
        hooks = self._create_hooks()

        # Create MCP server with custom tools
        clara_mcp_server = create_clara_tools(self.session_id)

        # Register phase change callback
        tool_state = get_session_state(self.session_id)
        tool_state["_on_phase_change"] = self._on_phase_change

        options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            system_prompt=orchestrator_prompt,
            allowed_tools=["Task"] + CLARA_TOOL_NAMES,
            agents=agents,
            hooks=hooks,
            mcp_servers={"clara": clara_mcp_server},
            model="sonnet"
        )

        self._client = ClaudeSDKClient(options=options)
        await self._client.__aenter__()
        self._running = True
        logger.info(f"[{self.session_id}] Orchestrator started")

    async def stop(self) -> None:
        """Stop the orchestrator."""
        if self._client and self._running:
            await self._client.__aexit__(None, None, None)
            self._running = False
            from clara.agents.tools import clear_session_state
            clear_session_state(self.session_id)
            logger.info(f"[{self.session_id}] Orchestrator stopped")

    async def send_message(self, message: str) -> AsyncIterator[AGUIEvent]:
        """Send a message and stream the response as AG-UI events.

        This is the main entry point for processing messages.
        The orchestrator routes to the current phase agent and streams events.
        """
        if not self._running or not self._client:
            raise RuntimeError("Orchestrator not started")

        # Reset turn state
        agent = self._get_phase_agent(self.state.phase)
        agent.reset_turn_state()

        self.state.message_count += 1
        self.state.turn_count += 1

        # Sync state from tools
        self._sync_state_from_tools()

        # Build message with restoration context if needed
        actual_message = message
        if self._restored and not self._first_message_sent:
            context = self._build_restoration_context()
            actual_message = f"{context}\n\n{message}"
            self._first_message_sent = True
            logger.info(f"[{self.session_id}] Prepending restoration context")

        # Emit state snapshot at start
        yield self._build_state_snapshot_event()

        # Send to SDK
        await self._client.query(prompt=actual_message)

        # Helper to drain queued events
        async def drain_queue():
            while not self._event_queue.empty():
                try:
                    event = self._event_queue.get_nowait()
                    yield event
                except asyncio.QueueEmpty:
                    break

        # Stream response
        current_text = ""
        async for msg in self._client.receive_response():
            # Drain hook events
            async for event in drain_queue():
                yield event

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
                                        data={"delta": delta}
                                    )

            elif msg_type == 'ToolUseMessage':
                if hasattr(msg, 'name') and hasattr(msg, 'input'):
                    yield AGUIEvent(
                        type="TOOL_CALL_START",
                        data={"tool": msg.name, "input": msg.input}
                    )

            elif msg_type == 'ToolResultMessage':
                yield AGUIEvent(type="TOOL_CALL_END", data={})

        # Final drain
        async for event in drain_queue():
            yield event

        # Sync state after tool calls
        self._sync_state_from_tools()

        # Emit final state snapshot
        yield self._build_state_snapshot_event()
        yield AGUIEvent(type="TEXT_MESSAGE_END", data={})
