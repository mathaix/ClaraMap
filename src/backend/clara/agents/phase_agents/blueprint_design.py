"""Phase 3: Blueprint Design Agent.

This agent handles the interactive blueprint design phase where we:
1. Ask the user what knowledge to extract
2. Ask about details for each knowledge area
3. Ask about interview topics and style
4. Build the blueprint with entities and agents
5. Show the prompt editor for the interviewer prompt
6. Get final approval and transition to complete
"""

import asyncio
import logging
from typing import Any

from clara.agents.phase_agents.base import AGUIEvent, BasePhaseAgent, load_prompt

logger = logging.getLogger(__name__)


class BlueprintDesignAgent(BasePhaseAgent):
    """Agent for Phase 3: Blueprint Design.

    This is an interactive phase with multiple tasks:
    1. What knowledge to extract (multi-select)
    2. Details for each knowledge area
    3. Interview topics
    4. Interview style
    5. Build blueprint (project, entities, agent)
    6. Prompt editor
    7. Final approval
    """

    phase = "blueprint_design"

    tools = [
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
    ]

    def __init__(self, session_id: str, event_queue: asyncio.Queue[AGUIEvent]):
        super().__init__(session_id, event_queue)
        self._base_prompt: str | None = None

    def get_prompt(self, session_state: dict[str, Any]) -> str:
        """Get the Phase 3 prompt, hydrated with goal and agent config.

        The prompt has {{goal}} and {{role}} placeholders that get filled in.
        """
        if self._base_prompt is None:
            self._base_prompt = load_prompt("phase3_blueprint_design.txt")

        # Get the goal from session state
        goal = ""
        if session_state.get("goal_summary"):
            goal_summary = session_state["goal_summary"]
            goal = goal_summary.get("goal_text") or goal_summary.get("primary_goal", "")

        # Get the agent role from session state
        role = ""
        if session_state.get("agent_capabilities"):
            agent_caps = session_state["agent_capabilities"]
            role = agent_caps.get("role", "")

        # Hydrate the prompt
        prompt = self._base_prompt.replace("{{goal}}", goal)
        prompt = prompt.replace("{{role}}", role)
        return prompt

    def get_description(self) -> str:
        """Get the agent description for the SDK."""
        return (
            "Handles Phase 3: Blueprint Design INTERACTIVELY. "
            "First call mcp__clara__get_prompt to get hydrated instructions. "
            "This agent MUST use mcp__clara__ask to collect user input "
            "before building. It should NOT build entities/agents until "
            "user confirms via ask tool responses. "
            "Use mcp__clara__prompt_editor for editing prompts. "
            "Use mcp__clara__get_agent_context for context files."
        )
