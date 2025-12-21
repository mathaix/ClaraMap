"""Custom MCP tools for the Design Assistant.

These tools allow the agent to manipulate blueprint state
and trigger UI components.
"""

import logging
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

logger = logging.getLogger(__name__)

# In-memory state storage (keyed by session_id)
# In production, this would be replaced with database calls
_session_state: dict[str, dict[str, Any]] = {}


def get_session_state(session_id: str) -> dict[str, Any]:
    """Get or initialize session state."""
    if session_id not in _session_state:
        _session_state[session_id] = {
            "project": None,
            "entities": [],
            "agents": [],
            "phase": "discovery",
        }
    return _session_state[session_id]


def clear_session_state(session_id: str) -> None:
    """Clear session state when session ends."""
    _session_state.pop(session_id, None)


# Tool input schemas as dicts (for the SDK)
ProjectSchema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Project name"},
        "type": {
            "type": "string",
            "description": "Project type (ma_due_diligence, erp_migration, customer_research)",
        },
        "domain": {"type": "string", "description": "Domain focus (it_systems, finance, hr)"},
        "description": {"type": "string", "description": "Brief project description"},
    },
    "required": ["name", "type"],
}

EntitySchema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Entity type name (System, Process, Person)"},
        "attributes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of attributes to extract for this entity",
        },
        "description": {"type": "string", "description": "What this entity represents"},
    },
    "required": ["name", "attributes"],
}

AgentSchema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Agent name/role"},
        "persona": {"type": "string", "description": "Agent persona description"},
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Topics this agent should cover",
        },
        "tone": {"type": "string", "description": "Communication tone (formal, friendly)"},
    },
    "required": ["name", "topics"],
}

AskSchema = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "Question to ask the user"},
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["id", "label"],
            },
            "description": "Options to present to the user",
        },
        "multi_select": {"type": "boolean", "description": "Allow multiple selections"},
    },
    "required": ["question", "options"],
}

PhaseSchema = {
    "type": "object",
    "properties": {
        "phase": {
            "type": "string",
            "enum": ["discovery", "rubric", "agents", "review", "complete"],
            "description": "Design phase to transition to",
        },
    },
    "required": ["phase"],
}


def create_clara_tools(session_id: str):
    """Create MCP tools bound to a specific session.

    This factory function creates tools that have access to
    the session_id for state management.
    """

    @tool("project", "Set or update the project context", ProjectSchema)
    async def project_tool(args: dict) -> dict[str, Any]:
        """Set project details."""
        state = get_session_state(session_id)
        state["project"] = {
            "name": args["name"],
            "type": args["type"],
            "domain": args.get("domain"),
            "description": args.get("description"),
        }
        logger.info(f"[{session_id}] Project set: {args['name']}")
        return {
            "success": True,
            "project": state["project"],
            "message": f"Project '{args['name']}' configured as {args['type']}",
        }

    @tool("entity", "Add an entity type to extract from interviews", EntitySchema)
    async def entity_tool(args: dict) -> dict[str, Any]:
        """Add an entity type."""
        state = get_session_state(session_id)
        entity = {
            "name": args["name"],
            "attributes": args["attributes"],
            "description": args.get("description"),
        }

        # Check if entity already exists, update if so
        existing = next((e for e in state["entities"] if e["name"] == args["name"]), None)
        if existing:
            existing.update(entity)
            action = "updated"
        else:
            state["entities"].append(entity)
            action = "added"

        logger.info(f"[{session_id}] Entity {action}: {args['name']}")
        return {
            "success": True,
            "entity": entity,
            "action": action,
            "total_entities": len(state["entities"]),
            "message": f"Entity '{args['name']}' {action}",
        }

    @tool("agent", "Configure an interview agent", AgentSchema)
    async def agent_tool(args: dict) -> dict[str, Any]:
        """Add an interview agent configuration."""
        state = get_session_state(session_id)
        agent = {
            "name": args["name"],
            "persona": args.get("persona"),
            "topics": args["topics"],
            "tone": args.get("tone", "professional"),
        }

        # Check if agent already exists, update if so
        existing = next((a for a in state["agents"] if a["name"] == args["name"]), None)
        if existing:
            existing.update(agent)
            action = "updated"
        else:
            state["agents"].append(agent)
            action = "added"

        logger.info(f"[{session_id}] Agent {action}: {args['name']}")
        return {
            "success": True,
            "agent": agent,
            "action": action,
            "total_agents": len(state["agents"]),
            "message": f"Interview agent '{args['name']}' {action}",
        }

    @tool("ask", "Present options to the user for selection", AskSchema)
    async def ask_tool(args: dict) -> dict[str, Any]:
        """Show interactive options to user.

        Note: The actual UI rendering happens on the frontend.
        This tool returns the options structure for the frontend to display.
        """
        logger.info(f"[{session_id}] Asking user: {args['question']}")
        return {
            "type": "user_input_required",
            "question": args["question"],
            "options": args["options"],
            "multi_select": args.get("multi_select", False),
            "message": "Waiting for user selection...",
        }

    @tool("phase", "Transition to a different design phase", PhaseSchema)
    async def phase_tool(args: dict) -> dict[str, Any]:
        """Change the current design phase."""
        state = get_session_state(session_id)
        old_phase = state["phase"]
        state["phase"] = args["phase"]
        logger.info(f"[{session_id}] Phase: {old_phase} -> {args['phase']}")
        return {
            "success": True,
            "previous_phase": old_phase,
            "current_phase": args["phase"],
            "message": f"Transitioned from {old_phase} to {args['phase']}",
        }

    @tool("preview", "Get a preview of the current blueprint", {"type": "object", "properties": {}})
    async def preview_tool(args: dict) -> dict[str, Any]:
        """Return the current blueprint state."""
        state = get_session_state(session_id)
        logger.info(f"[{session_id}] Blueprint preview requested")
        return {
            "blueprint": {
                "project": state["project"],
                "entities": state["entities"],
                "agents": state["agents"],
                "phase": state["phase"],
            },
            "summary": {
                "has_project": state["project"] is not None,
                "entity_count": len(state["entities"]),
                "agent_count": len(state["agents"]),
                "phase": state["phase"],
            },
        }

    # Create the MCP server with all tools
    return create_sdk_mcp_server(
        name="clara",
        version="1.0.0",
        tools=[
            project_tool,
            entity_tool,
            agent_tool,
            ask_tool,
            phase_tool,
            preview_tool,
        ],
    )


# List of tool names for allowed_tools configuration
CLARA_TOOL_NAMES = [
    "mcp__clara__project",
    "mcp__clara__entity",
    "mcp__clara__agent",
    "mcp__clara__ask",
    "mcp__clara__phase",
    "mcp__clara__preview",
]
