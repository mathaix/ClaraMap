"""Phase 2: Agent Configuration Agent.

This agent handles the automatic agent configuration phase where we:
1. Analyze the confirmed goal from Phase 1
2. Design a specialist agent persona (role, capabilities, expertise)
3. Display the agent card to the user
4. Transition to Phase 3
"""

import asyncio
import logging
from typing import Any

from clara.agents.phase_agents.base import AGUIEvent, BasePhaseAgent, load_prompt

logger = logging.getLogger(__name__)


class AgentConfigurationAgent(BasePhaseAgent):
    """Agent for Phase 2: Agent Configuration.

    This is a mostly automatic phase:
    1. LLM analyzes the goal
    2. LLM designs a specialist agent
    3. Agent card is displayed to user
    4. Transition to Phase 3
    """

    phase = "agent_configuration"

    tools = [
        "mcp__clara__agent_summary",
        "mcp__clara__phase",
        "mcp__clara__get_prompt",
        "mcp__clara__hydrate_phase3",
        "mcp__clara__request_selection_list",
        "mcp__clara__request_data_table",
        "mcp__clara__request_process_map",
    ]

    def __init__(self, session_id: str, event_queue: asyncio.Queue[AGUIEvent]):
        super().__init__(session_id, event_queue)
        self._base_prompt: str | None = None

    def get_prompt(self, session_state: dict[str, Any]) -> str:
        """Get the Phase 2 prompt, hydrated with the goal from Phase 1.

        The prompt has a {{goal}} placeholder that gets filled in.
        """
        if self._base_prompt is None:
            self._base_prompt = load_prompt("phase2_agent_configuration.txt")

        # Get the goal from session state
        goal = ""
        if session_state.get("goal_summary"):
            goal_summary = session_state["goal_summary"]
            goal = goal_summary.get("goal_text") or goal_summary.get("primary_goal", "")

        # Hydrate the prompt
        return self._base_prompt.replace("{{goal}}", goal)

    def get_description(self) -> str:
        """Get the agent description for the SDK."""
        return (
            "Handles Phase 2: Agent Configuration. "
            "First call mcp__clara__get_prompt to get hydrated instructions with the goal. "
            "Then configure the specialist agent and call mcp__clara__hydrate_phase3."
        )
