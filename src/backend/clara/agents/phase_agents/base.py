"""Base class for phase agents.

Each phase agent encapsulates:
- The prompt for that phase
- The tools available in that phase
- Hook handlers for UI event emission
- Transition logic to detect when to move to the next phase
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookMatcher

logger = logging.getLogger(__name__)

# Paths to prompt files
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = PROMPTS_DIR / filename
    with open(prompt_path, encoding="utf-8") as f:
        return f.read().strip()


@dataclass
class AGUIEvent:
    """Base AG-UI event structure."""
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class BasePhaseAgent(ABC):
    """Base class for phase agents.

    Each phase agent is responsible for:
    1. Providing the prompt for its phase
    2. Defining the tools available in its phase
    3. Handling hooks for UI event emission
    4. Processing messages and yielding AG-UI events
    """

    # Phase identifier (e.g., "goal_understanding")
    phase: str

    # Tools available to this phase
    tools: list[str]

    def __init__(self, session_id: str, event_queue: asyncio.Queue[AGUIEvent]):
        """Initialize the phase agent.

        Args:
            session_id: The session ID for logging and state access
            event_queue: Queue for emitting AG-UI events from hooks
        """
        self.session_id = session_id
        self._event_queue = event_queue
        self._ui_emitted_in_turn = False

    @abstractmethod
    def get_prompt(self, session_state: dict[str, Any]) -> str:
        """Get the hydrated prompt for this phase.

        Args:
            session_state: Current session state (from tools.py)

        Returns:
            The prompt string, with any placeholders filled in
        """
        pass

    def get_hooks(self) -> dict[str, list[HookMatcher]]:
        """Get hooks for this phase.

        Returns a dictionary mapping hook types to lists of HookMatcher objects.
        Default implementation provides common UI tool hooks.
        """
        return {
            'PreToolUse': [
                HookMatcher(
                    matcher=None,  # Match all tools
                    hooks=[self._pre_tool_hook]
                )
            ],
            'PostToolUse': [
                HookMatcher(
                    matcher=None,
                    hooks=[self._post_tool_hook]
                )
            ]
        }

    async def _pre_tool_hook(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any
    ) -> dict[str, Any]:
        """Default pre-tool hook that handles UI component emission.

        Subclasses can override this to add phase-specific handling.
        """
        from clara.agents.tools import ensure_other_option, sanitize_ask_options

        tool_name = input_data.get("tool_name", input_data.get("name", "unknown"))
        tool_input = input_data.get("tool_input", input_data.get("input", {}))

        logger.info(f"[{self.session_id}] PreToolUse: {tool_name}")

        await self._event_queue.put(AGUIEvent(
            type="TOOL_CALL_START",
            data={"tool": tool_name, "input": tool_input}
        ))

        # Handle ask tool - emit CUSTOM event with UI component
        if tool_name == "mcp__clara__ask":
            options = sanitize_ask_options(tool_input.get("options", []))
            ui_component = {
                "type": "user_input_required",
                "question": tool_input.get("question", ""),
                "options": options,
                "multi_select": tool_input.get("multi_select", False),
            }
            await self._event_queue.put(AGUIEvent(
                type="CUSTOM",
                data={"name": "clara:ask", "value": ui_component}
            ))
            self._ui_emitted_in_turn = True
            logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:ask")

        # Handle selection list
        if tool_name == "mcp__clara__request_selection_list":
            options = ensure_other_option(
                sanitize_ask_options(tool_input.get("options", []))
            )
            ui_component = {
                "type": "user_input_required",
                "question": tool_input.get("question", ""),
                "options": options,
                "multi_select": tool_input.get("multi_select", False),
            }
            await self._event_queue.put(AGUIEvent(
                type="CUSTOM",
                data={"name": "clara:ask", "value": ui_component}
            ))
            self._ui_emitted_in_turn = True
            logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:ask (selection)")

        # Handle data table
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
            await self._event_queue.put(AGUIEvent(
                type="CUSTOM",
                data={"name": "clara:data_table", "value": ui_component}
            ))
            self._ui_emitted_in_turn = True
            logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:data_table")

        # Handle process map
        if tool_name == "mcp__clara__request_process_map":
            ui_component = {
                "type": "process_map",
                "title": tool_input.get("title", "Process Map"),
                "required_fields": tool_input.get("required_fields", []),
                "edge_types": tool_input.get("edge_types", []),
                "min_steps": tool_input.get("min_steps", 3),
                "seed_nodes": tool_input.get("seed_nodes", []),
            }
            await self._event_queue.put(AGUIEvent(
                type="CUSTOM",
                data={"name": "clara:process_map", "value": ui_component}
            ))
            self._ui_emitted_in_turn = True
            logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:process_map")

        # Handle prompt editor
        if tool_name == "mcp__clara__prompt_editor":
            ui_component = {
                "type": "prompt_editor",
                "title": tool_input.get("title", "System Prompt"),
                "prompt": tool_input.get("prompt", ""),
                "description": tool_input.get("description", ""),
            }
            await self._event_queue.put(AGUIEvent(
                type="CUSTOM",
                data={"name": "clara:prompt_editor", "value": ui_component}
            ))
            self._ui_emitted_in_turn = True
            logger.info(f"[{self.session_id}] Emitted CUSTOM event clara:prompt_editor")

        return {}  # No modifications to tool behavior

    async def _post_tool_hook(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any
    ) -> dict[str, Any]:
        """Default post-tool hook."""
        tool_name = input_data.get("tool_name", "unknown")
        logger.debug(f"[{self.session_id}] PostToolUse: {tool_name} completed")
        await self._event_queue.put(AGUIEvent(
            type="TOOL_CALL_END",
            data={"tool": tool_name}
        ))
        return {}

    def reset_turn_state(self) -> None:
        """Reset per-turn state. Called at the start of each message."""
        self._ui_emitted_in_turn = False

    @property
    def ui_emitted(self) -> bool:
        """Whether a UI component was emitted this turn."""
        return self._ui_emitted_in_turn
