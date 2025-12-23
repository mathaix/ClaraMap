"""Phase 1: Goal Understanding Agent.

This agent handles the initial goal discovery phase where we:
1. Ask the user for their project goal
2. Confirm the goal with a simple Yes/No
3. Transition to Phase 2 once confirmed
"""

import asyncio
import logging
from typing import Any

from clara.agents.phase_agents.base import AGUIEvent, BasePhaseAgent, load_prompt

logger = logging.getLogger(__name__)


class GoalUnderstandingAgent(BasePhaseAgent):
    """Agent for Phase 1: Goal Understanding.

    This is a simple two-turn phase:
    1. User provides goal → Agent confirms
    2. User confirms Yes/No → Agent transitions or asks again
    """

    phase = "goal_understanding"

    tools = [
        "mcp__clara__ask",
        "mcp__clara__request_selection_list",
        "mcp__clara__request_data_table",
        "mcp__clara__request_process_map",
        "mcp__clara__project",
        "mcp__clara__save_goal_summary",
        "mcp__clara__hydrate_phase2",
        "mcp__clara__phase",
        "mcp__clara__get_prompt",
    ]

    def __init__(self, session_id: str, event_queue: asyncio.Queue[AGUIEvent]):
        super().__init__(session_id, event_queue)
        self._prompt: str | None = None

    def get_prompt(self, session_state: dict[str, Any]) -> str:
        """Get the Phase 1 prompt.

        Phase 1 uses a static prompt since there's no prior context needed.
        """
        if self._prompt is None:
            self._prompt = load_prompt("phase1_goal_understanding.txt")
        return self._prompt

    def get_description(self) -> str:
        """Get the agent description for the SDK."""
        return (
            "Handles Phase 1: Goal Confirmation. "
            "Use this agent to discover the user's project through "
            "natural conversation. It will explore the core discovery areas "
            "and use mcp__clara__ask for structured choices. "
            "After completing, call mcp__clara__hydrate_phase2."
        )
