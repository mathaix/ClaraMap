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

from clara.agents.router import (
    RouterState,
    UIRouter,
    build_ui_component,
    infer_selection_from_assistant_output,
    is_cancel_intent,
    is_tool_reply,
    parse_ui_submission,
    summarize_ui_submission,
)
from clara.agents.tools import (
    CLARA_TOOL_NAMES,
    clear_session_state,
    create_clara_tools,
    ensure_other_option,
    get_session_state,
    sanitize_ask_options,
)

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
        self._restored = False  # True if this session was restored from DB
        self._first_message_sent = False  # Track if we've sent the first message after restoration
        self.router_state = RouterState()
        self.router = UIRouter()

    def _sync_state_from_tools(self) -> None:
        """Sync session state from tool state.

        This ensures session state (used for STATE_SNAPSHOT events and DB persistence)
        stays in sync with tool state (modified by MCP tools like phase, project, etc).
        """
        tool_state = get_session_state(self.session_id)

        # Sync phase
        if tool_state.get("phase"):
            try:
                self.state.phase = DesignPhase(tool_state["phase"])
            except ValueError:
                logger.warning(f"[{self.session_id}] Unknown phase: {tool_state['phase']}")

        # Sync blueprint preview from project/entities/agents
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
            logger.info(f"[{self.session_id}] Session state phase updated to: {new_phase}")
        except ValueError:
            logger.warning(f"[{self.session_id}] Unknown phase in callback: {new_phase}")

    def _build_restoration_context(self) -> str:
        """Build a context summary for restored sessions.

        This provides the model with context about the session state
        since LLMs don't have persistent memory across connections.
        """
        parts = ["[SESSION CONTEXT - This is a resumed session. Here's the current state:]"]

        # Phase info
        parts.append(f"Current Phase: {self.state.phase.value}")

        # Goal summary
        if self.state.goal_summary:
            parts.append(f"Project Goal: {self.state.goal_summary}")

        # Blueprint preview
        if self.state.blueprint_preview.project_name:
            parts.append(f"Project: {self.state.blueprint_preview.project_name} ({self.state.blueprint_preview.project_type or 'unknown type'})")

        if self.state.blueprint_preview.entity_types:
            parts.append(f"Entity Types: {', '.join(self.state.blueprint_preview.entity_types)}")

        if self.state.blueprint_preview.agent_count > 0:
            parts.append(f"Configured Agents: {self.state.blueprint_preview.agent_count}")

        # Agent capabilities (from Phase 2)
        if self.state.agent_capabilities.role:
            caps = self.state.agent_capabilities
            parts.append(f"Specialist Agent: {caps.role}")
            if caps.expertise_areas:
                parts.append(f"Expertise: {', '.join(caps.expertise_areas)}")
            if caps.interaction_style:
                parts.append(f"Style: {caps.interaction_style}")

        # Turn count
        parts.append(f"Conversation Progress: {self.state.turn_count} turns, {self.state.message_count} messages")

        parts.append("[END SESSION CONTEXT]\n\nUser continues the conversation:")

        return "\n".join(parts)

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

    def _create_subagents(self) -> dict[str, AgentDefinition]:
        """Define phase-based subagents.

        All subagents fetch their hydrated prompts dynamically via mcp__clara__get_prompt.
        This ensures placeholders like {{goal}} and {{role}} are filled from session state.
        """
        # Phase 1 can use static prompt since no prior context needed
        phase1_prompt = load_prompt("phase1_goal_understanding.txt")

        # Phase 2 fetches hydrated prompt to get {{goal}} from Phase 1
        phase2_prompt = """You are configuring a specialist interview agent.

First, call mcp__clara__get_prompt with phase="agent_configuration" to get your full instructions with the project goal.

Then follow those instructions to:
1. Analyze the goal
2. Design the specialist agent configuration
3. Call mcp__clara__agent_summary to save the config
4. Call mcp__clara__hydrate_phase3 with the config
5. Transition to blueprint_design phase
"""

        # Phase 3 fetches hydrated prompt and MUST use ask tool interactively
        phase3_prompt = """You are Clara, designing an Interview Blueprint interactively.

CRITICAL INSTRUCTION: You MUST use mcp__clara__ask for EVERY decision point.
Do NOT proceed to build anything until you have collected user input via ask tool.

Step 1: First, call mcp__clara__get_prompt with phase="blueprint_design" to get your full context.
Step 2: Then call mcp__clara__ask to ask the user what knowledge they want to extract from interviews.
Step 3: Wait for user response. Do NOT call entity/agent/project tools until user confirms via ask.

Your ONLY job in this turn is:
1. Call get_prompt to get context
2. Call ask tool to collect what knowledge the user wants to gather
3. Stop and wait for response

DO NOT build entities, agents, or projects until the user has responded to your ask tool questions.
"""

        return {
            "phase1-goal-discovery": AgentDefinition(
                description=(
                    "Handles Phase 1: Goal Understanding. "
                    "Use this agent to discover the user's project through natural conversation. "
                    "It will explore the 5 key dimensions and use mcp__clara__ask for structured choices. "
                    "After completing, call mcp__clara__hydrate_phase2 with the goal summary."
                ),
                tools=[
                    "mcp__clara__ask",
                    "mcp__clara__request_selection_list",
                    "mcp__clara__request_data_table",
                    "mcp__clara__request_process_map",
                    "mcp__clara__project",
                    "mcp__clara__save_goal_summary",
                    "mcp__clara__hydrate_phase2",
                    "mcp__clara__phase",
                    "mcp__clara__get_prompt",
                ],
                prompt=phase1_prompt,
                model="sonnet"
            ),
            "phase2-agent-config": AgentDefinition(
                description=(
                    "Handles Phase 2: Agent Configuration. "
                    "First call mcp__clara__get_prompt to get hydrated instructions with the goal. "
                    "Then configure the specialist agent and call mcp__clara__hydrate_phase3."
                ),
                tools=[
                    "mcp__clara__agent_summary",
                    "mcp__clara__phase",
                    "mcp__clara__get_prompt",
                    "mcp__clara__hydrate_phase3",
                    "mcp__clara__request_selection_list",
                    "mcp__clara__request_data_table",
                    "mcp__clara__request_process_map",
                ],
                prompt=phase2_prompt,
                model="sonnet"
            ),
            "phase3-blueprint-design": AgentDefinition(
                description=(
                    "Handles Phase 3: Blueprint Design INTERACTIVELY. "
                    "First call mcp__clara__get_prompt to get hydrated instructions. "
                    "This agent MUST use mcp__clara__ask to collect user input before building. "
                    "It should NOT build entities/agents until user confirms via ask tool responses. "
                    "Use mcp__clara__prompt_editor to show generated prompts for user editing. "
                    "Use mcp__clara__get_agent_context to access uploaded context files."
                ),
                tools=[
                    "mcp__clara__project",
                    "mcp__clara__entity",
                    "mcp__clara__agent",
                    "mcp__clara__ask",
                    "mcp__clara__request_selection_list",
                    "mcp__clara__request_data_table",
                    "mcp__clara__request_process_map",
                    "mcp__clara__preview",
                    "mcp__clara__phase",
                    "mcp__clara__get_prompt",
                    "mcp__clara__prompt_editor",
                    "mcp__clara__get_agent_context",
                ],
                prompt=phase3_prompt,
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

            if tool_name in {
                "mcp__clara__request_data_table",
                "mcp__clara__request_process_map",
                "mcp__clara__request_selection_list",
            }:
                normalized_tool = tool_name.replace("mcp__clara__", "")
                self.router_state.pending_tool = normalized_tool
                self.router_state.last_tool = normalized_tool
                self.router_state.last_tool_status = "open"

            # Special handling for ask tool - emit CUSTOM event with UI component
            if tool_name == "mcp__clara__ask":
                options = sanitize_ask_options(tool_input.get("options", []))
                ui_component = {
                    "type": "user_input_required",
                    "question": tool_input.get("question", ""),
                    "options": options,
                    "multi_select": tool_input.get("multi_select", False),
                }
                # Emit as CUSTOM AG-UI event for reliable rendering
                await response_queue.put(AGUIEvent(
                    type="CUSTOM",
                    data={"name": "clara:ask", "value": ui_component}
                ))
                logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:ask")

            if tool_name == "mcp__clara__request_selection_list":
                options = ensure_other_option(sanitize_ask_options(tool_input.get("options", [])))
                ui_component = {
                    "type": "user_input_required",
                    "question": tool_input.get("question", ""),
                    "options": options,
                    "multi_select": tool_input.get("multi_select", False),
                }
                await response_queue.put(AGUIEvent(
                    type="CUSTOM",
                    data={"name": "clara:ask", "value": ui_component}
                ))
                logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:ask (selection list)")

            # Special handling for prompt_editor tool - emit CUSTOM event for editable prompt
            if tool_name == "mcp__clara__prompt_editor":
                ui_component = {
                    "type": "prompt_editor",
                    "title": tool_input.get("title", "System Prompt"),
                    "prompt": tool_input.get("prompt", ""),
                    "description": tool_input.get("description", ""),
                }
                # Emit as CUSTOM AG-UI event for editable prompt UI
                await response_queue.put(AGUIEvent(
                    type="CUSTOM",
                    data={"name": "clara:prompt_editor", "value": ui_component}
                ))
                logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:prompt_editor")

            if tool_name == "mcp__clara__request_data_table":
                ui_component = {
                    "type": "data_table",
                    "title": tool_input.get("title", "Data Table"),
                    "columns": tool_input.get("columns", []),
                    "min_rows": tool_input.get("min_rows", 3),
                    "starter_rows": tool_input.get("starter_rows", 3),
                    "input_modes": tool_input.get("input_modes", ["paste", "inline"]),
                    "summary_prompt": tool_input.get("summary_prompt", ""),
                }
                await response_queue.put(AGUIEvent(
                    type="CUSTOM",
                    data={"name": "clara:data_table", "value": ui_component}
                ))
                logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:data_table")

            if tool_name == "mcp__clara__request_process_map":
                ui_component = {
                    "type": "process_map",
                    "title": tool_input.get("title", "Process Map"),
                    "required_fields": tool_input.get("required_fields", []),
                    "edge_types": tool_input.get("edge_types", []),
                    "min_steps": tool_input.get("min_steps", 3),
                    "seed_nodes": tool_input.get("seed_nodes", []),
                }
                await response_queue.put(AGUIEvent(
                    type="CUSTOM",
                    data={"name": "clara:process_map", "value": ui_component}
                ))
                logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:process_map")

            # Note: agent_summary tool stores config in state but no longer emits UI card

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

        orchestrator_prompt = load_prompt("interview_orchestrator.txt")
        agents = self._create_subagents()
        hooks = self._create_hooks()

        # Create MCP server with custom tools bound to this session
        clara_mcp_server = create_clara_tools(self.session_id)

        # Register phase change callback to keep session state in sync with tool state
        tool_state = get_session_state(self.session_id)
        tool_state["_on_phase_change"] = self._on_phase_change

        options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            system_prompt=orchestrator_prompt,
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

        # Sync state from tools before emitting snapshot
        self._sync_state_from_tools()

        submission = parse_ui_submission(message)
        if submission:
            self.router_state.last_tool = submission.kind
            self.router_state.last_tool_status = "completed"
            self.router_state.pending_tool = None
            self.router_state.pending_payload = None
            message = summarize_ui_submission(submission)

        if (
            not submission
            and self.router_state.pending_tool == "request_selection_list"
            and is_tool_reply(message)
        ):
            self.router_state.last_tool_status = "completed"
            self.router_state.pending_tool = None
            self.router_state.pending_payload = None

        if (
            not submission
            and self.router_state.pending_tool
            and is_cancel_intent(message)
        ):
            self.router_state.last_tool_status = "canceled"
            self.router_state.pending_tool = None
            self.router_state.pending_payload = None

        # For restored sessions, prepend context on first message
        actual_message = message
        if self._restored and not self._first_message_sent:
            context = self._build_restoration_context()
            actual_message = f"{context}\n\n{message}"
            self._first_message_sent = True
            logger.info(f"[{self.session_id}] Prepending restoration context to first message")

        # Emit state snapshot at start of turn
        yield self._build_state_snapshot_event()

        if not submission:
            decision = await self.router.decide(
                message=message,
                state=self.router_state,
                phase=self.state.phase.value,
                flow="design_assistant",
                allow_selection=False,
            )

            if decision.action in {"tool", "clarify"}:
                preamble = ""
                if decision.action == "tool":
                    ui_component = build_ui_component(decision)
                    if not ui_component:
                        decision = None
                    else:
                        tool_name_map = {
                            "request_data_table": "mcp__clara__request_data_table",
                            "request_process_map": "mcp__clara__request_process_map",
                            "request_selection_list": "mcp__clara__request_selection_list",
                        }
                        tool_name = tool_name_map.get(
                            decision.tool_name, "mcp__clara__request_data_table"
                        )
                        if decision.tool_name == "request_data_table":
                            preamble = "Let's capture that in a table so you can paste rows quickly."
                        elif decision.tool_name == "request_process_map":
                            preamble = "Let's map the steps so we capture the workflow accurately."
                        elif decision.tool_name == "request_selection_list":
                            preamble = "Pick the options that apply."
                        tool_state = get_session_state(self.session_id)
                        tool_state["pending_ui_component"] = ui_component
                        self.router_state.pending_tool = decision.tool_name
                        self.router_state.pending_payload = decision.params
                        self.router_state.last_tool = decision.tool_name
                        self.router_state.last_tool_status = "open"

                        yield AGUIEvent(
                            type="TOOL_CALL_START",
                            data={"tool": tool_name, "input": decision.params or {}}
                        )
                        yield AGUIEvent(
                            type="TEXT_MESSAGE_CONTENT",
                            data={"delta": preamble}
                        )
                        yield AGUIEvent(
                            type="CUSTOM",
                            data={
                                "name": (
                                    "clara:data_table"
                                    if decision.tool_name == "request_data_table"
                                    else "clara:process_map"
                                    if decision.tool_name == "request_process_map"
                                    else "clara:ask"
                                ),
                                "value": ui_component,
                            }
                        )
                        yield AGUIEvent(
                            type="TOOL_CALL_END",
                            data={"tool": tool_name}
                        )
                        yield AGUIEvent(type="TEXT_MESSAGE_END", data={})
                        yield self._build_state_snapshot_event()
                        return

                if decision and decision.action == "clarify":
                    self.router_state.last_clarify = decision.clarifying_question
                    yield AGUIEvent(
                        type="TEXT_MESSAGE_CONTENT",
                        data={"delta": decision.clarifying_question or "Can you clarify?"}
                    )
                    yield AGUIEvent(type="TEXT_MESSAGE_END", data={})
                    yield self._build_state_snapshot_event()
                    return

        # Send message to agent (uses actual_message which may include restoration context)
        await self.client.query(prompt=actual_message)

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
                                # Check if this is a continuation or a new message
                                # If new_text starts with current_text, it's a continuation
                                # Otherwise, it's a new message (e.g., after a tool call)
                                if current_text and new_text.startswith(current_text):
                                    # Continuation - emit just the delta
                                    delta = new_text[len(current_text):]
                                else:
                                    # New message - emit the full text
                                    delta = new_text
                                current_text = new_text
                                if delta:  # Only emit if there's actual content
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

                # Note: UI components are now handled via CUSTOM events in pre_tool_hook
                # No need to parse [UI_COMPONENT] markers from tool results

                yield AGUIEvent(
                    type="TOOL_CALL_END",
                    data={}
                )

        # Final drain of any remaining queued events
        async for event in drain_queue():
            yield event

        if current_text and not self.router_state.pending_tool:
            selection_decision = infer_selection_from_assistant_output(current_text)
            if selection_decision:
                ui_component = build_ui_component(selection_decision)
                if ui_component:
                    tool_state = get_session_state(self.session_id)
                    tool_state["pending_ui_component"] = ui_component
                    self.router_state.pending_tool = selection_decision.tool_name
                    self.router_state.pending_payload = selection_decision.params
                    self.router_state.last_tool = selection_decision.tool_name
                    self.router_state.last_tool_status = "open"
                    yield AGUIEvent(
                        type="TOOL_CALL_START",
                        data={
                            "tool": "mcp__clara__request_selection_list",
                            "input": selection_decision.params or {},
                        }
                    )
                    yield AGUIEvent(
                        type="CUSTOM",
                        data={"name": "clara:ask", "value": ui_component}
                    )
                    yield AGUIEvent(
                        type="TOOL_CALL_END",
                        data={"tool": "mcp__clara__request_selection_list"}
                    )

        # Sync state from tools after all tool calls complete
        self._sync_state_from_tools()

        # Emit final state snapshot with any changes from this turn
        yield self._build_state_snapshot_event()

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
        from clara.agents.tools import get_session_state

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
