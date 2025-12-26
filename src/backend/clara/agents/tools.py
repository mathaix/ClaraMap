"""Custom MCP tools for the Design Assistant.

These tools allow the agent to manipulate blueprint state
and trigger UI components.
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from clara.security import InputSanitizer

logger = logging.getLogger(__name__)

# Session TTL in minutes (for memory leak prevention)
SESSION_TTL_MINUTES = 60

# Path to prompt templates
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Template file mapping
PHASE_TEMPLATES = {
    "goal_understanding": "phase1_goal_understanding.txt",
    "agent_configuration": "phase2_agent_configuration.txt",
    "blueprint_design": "phase3_blueprint_design.txt",
}


def load_template(phase: str) -> str:
    """Load a template from the prompts directory."""
    template_file = PHASE_TEMPLATES.get(phase)
    if not template_file:
        raise ValueError(f"Unknown phase: {phase}")
    template_path = PROMPTS_DIR / template_file
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def hydrate_template(template: str, context: dict[str, Any]) -> str:
    """Replace {{placeholders}} in template with context values.

    Sanitizes all values to prevent template injection attacks.
    """
    def replace_placeholder(match: re.Match) -> str:
        key = match.group(1).strip()
        value = context.get(key, "")
        if value is None:
            return ""
        if isinstance(value, list):
            # Sanitize each item in the list
            sanitized = [InputSanitizer.sanitize_template_value(str(v)) for v in value]
            return ", ".join(sanitized)
        # Sanitize the value to prevent template injection
        return InputSanitizer.sanitize_template_value(str(value))

    return re.sub(r"\{\{(\w+)\}\}", replace_placeholder, template)

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
            "phase": "goal_understanding",
            "agent_capabilities": None,
            "goal_summary": None,
            "hydrated_prompts": {},  # phase -> hydrated prompt text
            "_created_at": datetime.now(),
            "_last_activity": datetime.now(),
        }
    else:
        # Update last activity timestamp
        _session_state[session_id]["_last_activity"] = datetime.now()
    return _session_state[session_id]


def clear_session_state(session_id: str) -> None:
    """Clear session state when session ends."""
    _session_state.pop(session_id, None)


def cleanup_stale_sessions() -> int:
    """Remove sessions that have exceeded the TTL.

    Returns:
        Number of sessions cleaned up
    """
    cutoff = datetime.now() - timedelta(minutes=SESSION_TTL_MINUTES)
    stale_ids = [
        sid for sid, state in _session_state.items()
        if state.get("_last_activity", datetime.now()) < cutoff
    ]

    for sid in stale_ids:
        _session_state.pop(sid, None)

    if stale_ids:
        logger.info(f"Cleaned up {len(stale_ids)} stale design session states")

    return len(stale_ids)


def _safe_int(value: Any, default: int) -> int:
    """Safely convert values to int with a fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def sanitize_ask_options(options: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    """Normalize option payloads for selection-style UIs."""
    if not isinstance(options, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        label = InputSanitizer.sanitize_name(option.get("label", ""))
        if not label:
            continue
        option_id = InputSanitizer.sanitize_name(option.get("id") or label) or "option"
        description = InputSanitizer.sanitize_description(option.get("description"))
        requires_input = bool(option.get("requires_input"))
        if label.strip().lower().startswith("other"):
            requires_input = True
        entry: dict[str, Any] = {
            "id": option_id,
            "label": label,
        }
        if description:
            entry["description"] = description
        if requires_input:
            entry["requires_input"] = True
        sanitized.append(entry)
    return sanitized


def _sanitize_card_value(value: Any, depth: int = 0) -> Any:
    """Sanitize nested card payload values."""
    if depth > 4:
        return None
    if isinstance(value, str):
        return InputSanitizer.sanitize_description(value)
    if isinstance(value, list):
        cleaned = [_sanitize_card_value(item, depth + 1) for item in value]
        return [item for item in cleaned if item is not None][:50]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_str = InputSanitizer.sanitize_name(str(key)) or str(key)
            cleaned_value = _sanitize_card_value(item, depth + 1)
            if cleaned_value is not None:
                cleaned[key_str] = cleaned_value
        return cleaned
    return value


def sanitize_cards(cards: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    """Normalize card payloads for card-orchestrated UI."""
    if not isinstance(cards, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_id = InputSanitizer.sanitize_name(card.get("card_id", "")) or f"card_{len(sanitized) + 1}"
        card_type = InputSanitizer.sanitize_name(card.get("type", "")) or "card"
        title = InputSanitizer.sanitize_description(card.get("title", "")) or "Card"
        subtitle = InputSanitizer.sanitize_description(card.get("subtitle", "")) or ""
        body = _sanitize_card_value(card.get("body", {}))

        entry: dict[str, Any] = {
            "card_id": card_id,
            "type": card_type,
            "title": title,
            "body": body if body is not None else {},
        }

        if subtitle:
            entry["subtitle"] = subtitle

        actions = card.get("actions", [])
        if isinstance(actions, list):
            cleaned_actions: list[dict[str, Any]] = []
            for action in actions:
                if not isinstance(action, dict):
                    continue
                action_id = InputSanitizer.sanitize_name(action.get("id", "")) or f"action_{len(cleaned_actions) + 1}"
                label = InputSanitizer.sanitize_description(action.get("label", "")) or "Action"
                action_entry: dict[str, Any] = {"id": action_id, "label": label}
                style = InputSanitizer.sanitize_name(action.get("style", ""))
                if style:
                    action_entry["style"] = style
                cleaned_actions.append(action_entry)
            if cleaned_actions:
                entry["actions"] = cleaned_actions

        helper = card.get("helper")
        if isinstance(helper, dict):
            why_this = InputSanitizer.sanitize_array(helper.get("why_this", []), max_item_length=200)
            risks = InputSanitizer.sanitize_array(helper.get("risks_if_skipped", []), max_item_length=200)
            helper_entry: dict[str, Any] = {}
            if why_this:
                helper_entry["why_this"] = why_this
            if risks:
                helper_entry["risks_if_skipped"] = risks
            if helper_entry:
                entry["helper"] = helper_entry

        sanitized.append(entry)
    return sanitized


def ensure_other_option(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append an Other option if missing, and mark it as requiring input."""
    for option in options:
        label = str(option.get("label", "")).strip().lower()
        if label.startswith("other"):
            option["requires_input"] = True
            return options

    other_id = "other"
    existing_ids = {str(option.get("id")) for option in options}
    if other_id in existing_ids:
        suffix = 2
        while f"other_{suffix}" in existing_ids:
            suffix += 1
        other_id = f"other_{suffix}"

    return [
        *options,
        {
            "id": other_id,
            "label": "Other",
            "description": "Something else",
            "requires_input": True,
        },
    ]


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
        "tone": {"type": "string", "description": "Communication tone (formal, conversational, technical)"},
        "system_prompt": {
            "type": "string",
            "description": "Full system prompt template for the interviewer agent",
        },
    },
    "required": ["name", "topics", "system_prompt"],
}

AskSchema = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "Question to ask the user"},
        "cards": {
            "type": "array",
            "description": "Optional card stack to render above the question.",
            "items": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string"},
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "body": {
                        "type": "object",
                        "description": "Card body payload.",
                        "additionalProperties": True,
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "style": {"type": "string"},
                            },
                            "required": ["id", "label"],
                        },
                    },
                    "helper": {
                        "type": "object",
                        "properties": {
                            "why_this": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "risks_if_skipped": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["card_id", "type", "title", "body"],
            },
        },
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "requires_input": {
                        "type": "boolean",
                        "description": "If true, require a free-text input when selected (e.g., Other).",
                    },
                },
                "required": ["id", "label"],
            },
            "description": "Options to present to the user",
        },
        "multi_select": {"type": "boolean", "description": "Allow multiple selections"},
    },
    "required": ["question", "options"],
}

SelectionListSchema = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "Question to ask the user"},
        "cards": {
            "type": "array",
            "description": "Optional card stack to render above the question.",
            "items": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string"},
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "body": {
                        "type": "object",
                        "description": "Card body payload.",
                        "additionalProperties": True,
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "style": {"type": "string"},
                            },
                            "required": ["id", "label"],
                        },
                    },
                    "helper": {
                        "type": "object",
                        "properties": {
                            "why_this": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "risks_if_skipped": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["card_id", "type", "title", "body"],
            },
        },
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "requires_input": {
                        "type": "boolean",
                        "description": "If true, require a free-text input when selected (e.g., Other).",
                    },
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
            "enum": ["goal_understanding", "agent_configuration", "blueprint_design", "complete"],
            "description": "Design phase to transition to",
        },
    },
    "required": ["phase"],
}

AgentSummarySchema = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "description": "The specialist agent's role/title"},
        "expertise_areas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Areas of expertise for this specialist",
        },
        "interaction_style": {"type": "string", "description": "How the agent interacts"},
        "capabilities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific capabilities of the agent",
        },
        "focus_areas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Primary topics the agent will focus on",
        },
    },
    "required": ["role", "expertise_areas", "interaction_style"],
}

GetPhaseContextSchema = {
    "type": "object",
    "properties": {
        "phase": {
            "type": "string",
            "enum": ["goal_understanding", "agent_configuration", "blueprint_design"],
            "description": "The phase to get context for",
        },
    },
    "required": ["phase"],
}

GoalSummarySchema = {
    "type": "object",
    "properties": {
        "project_type": {"type": "string", "description": "Type of project (e.g., ma_due_diligence, erp_migration)"},
        "primary_goal": {"type": "string", "description": "Primary objective of the interviews"},
        "interviewees": {"type": "string", "description": "Who will be interviewed (roles/departments)"},
        "information_needs": {"type": "string", "description": "Key information to gather"},
        "output_requirements": {"type": "string", "description": "How insights will be used"},
        "constraints": {"type": "string", "description": "Time, tone, sensitive topics"},
    },
    "required": ["project_type", "primary_goal"],
}

HydratePhase2Schema = {
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "description": "The project goal summary from Phase 1 (what the user wants to accomplish)",
        },
    },
    "required": ["goal"],
}

HydratePhase3Schema = {
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "description": "The project goal summary from Phase 1",
        },
        "role": {
            "type": "string",
            "description": "The specialist agent's role/title (e.g., 'M&A Technical Due Diligence Specialist')",
        },
        "capabilities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of specific capabilities the agent has",
        },
        "expertise_areas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of knowledge domains the agent demonstrates",
        },
        "interaction_style": {
            "type": "string",
            "description": "How the agent should behave in interviews",
        },
    },
    "required": ["goal", "role", "capabilities", "expertise_areas", "interaction_style"],
}

GetHydratedPromptSchema = {
    "type": "object",
    "properties": {
        "phase": {
            "type": "string",
            "enum": ["goal_understanding", "agent_configuration", "blueprint_design"],
            "description": "The phase to get the hydrated prompt for",
        },
    },
    "required": ["phase"],
}

PromptEditorSchema = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Title for the prompt editor (e.g., 'Interviewer System Prompt')",
        },
        "prompt": {
            "type": "string",
            "description": "The generated system prompt to display for editing",
        },
        "description": {
            "type": "string",
            "description": "Brief description of what this prompt does",
        },
    },
    "required": ["title", "prompt"],
}

DataTableSchema = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Title for the data table"},
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["text", "number", "enum", "date", "url"],
                    },
                    "required": {"type": "boolean"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Allowed values if type is enum",
                    },
                },
                "required": ["name", "type"],
            },
        },
        "min_rows": {"type": "integer", "description": "Minimum number of rows"},
        "starter_rows": {"type": "integer", "description": "Rows to prefill"},
        "input_modes": {
            "type": "array",
            "items": {"type": "string", "enum": ["paste", "inline", "import"]},
        },
        "summary_prompt": {"type": "string", "description": "Short prompt for summarizing the data"},
    },
    "required": ["title", "columns"],
}

ProcessMapSchema = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Title for the process map"},
        "required_fields": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required fields per step",
        },
        "edge_types": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Allowed edge types between steps",
        },
        "min_steps": {"type": "integer", "description": "Minimum number of steps"},
        "seed_nodes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Seed step labels",
        },
    },
    "required": ["title"],
}

GetAgentContextSchema = {
    "type": "object",
    "properties": {
        "agent_index": {
            "type": "integer",
            "description": "Index of the agent to get context files for (0-based)",
        },
    },
    "required": ["agent_index"],
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

        # Sanitize inputs
        name = InputSanitizer.sanitize_name(args.get("name", ""))
        project_type = InputSanitizer.sanitize_name(args.get("type", ""))
        domain = InputSanitizer.sanitize_name(args.get("domain"))
        description = InputSanitizer.sanitize_description(args.get("description"))

        state["project"] = {
            "name": name,
            "type": project_type,
            "domain": domain,
            "description": description,
        }
        logger.info(f"[{session_id}] Project set: {name}")
        return {
            "content": [{
                "type": "text",
                "text": f"Project '{name}' configured as {project_type}"
            }]
        }

    @tool("entity", "Add an entity type to extract from interviews", EntitySchema)
    async def entity_tool(args: dict) -> dict[str, Any]:
        """Add an entity type."""
        state = get_session_state(session_id)

        # Sanitize inputs
        name = InputSanitizer.sanitize_name(args.get("name", ""))
        attributes = InputSanitizer.sanitize_array(args.get("attributes", []))
        description = InputSanitizer.sanitize_description(args.get("description"))

        entity = {
            "name": name,
            "attributes": attributes,
            "description": description,
        }

        # Check if entity already exists, update if so
        existing = next((e for e in state["entities"] if e["name"] == name), None)
        if existing:
            existing.update(entity)
            action = "updated"
        else:
            state["entities"].append(entity)
            action = "added"

        logger.info(f"[{session_id}] Entity {action}: {name}")
        count = len(state["entities"])
        return {
            "content": [{
                "type": "text",
                "text": f"Entity '{name}' {action}. Total entities: {count}"
            }]
        }

    @tool("agent", "Configure an interview agent with system prompt", AgentSchema)
    async def agent_tool(args: dict) -> dict[str, Any]:
        """Add an interview agent configuration with system prompt."""
        state = get_session_state(session_id)

        # Sanitize inputs
        name = InputSanitizer.sanitize_name(args.get("name", ""))
        persona = InputSanitizer.sanitize_description(args.get("persona"))
        topics = InputSanitizer.sanitize_array(args.get("topics", []))
        tone = InputSanitizer.sanitize_name(args.get("tone", "conversational"))
        system_prompt = InputSanitizer.sanitize_system_prompt(args.get("system_prompt", ""))

        agent = {
            "name": name,
            "persona": persona,
            "topics": topics,
            "tone": tone,
            "system_prompt": system_prompt,
        }

        # Check if agent already exists, update if so
        existing = next((a for a in state["agents"] if a["name"] == name), None)
        if existing:
            existing.update(agent)
            action = "updated"
        else:
            state["agents"].append(agent)
            action = "added"

        logger.info(f"[{session_id}] Agent {action}: {name}")
        count = len(state["agents"])
        return {
            "content": [{
                "type": "text",
                "text": f"Interview agent '{name}' {action}. Total agents: {count}"
            }]
        }

    @tool("ask", "Present options to the user for selection", AskSchema)
    async def ask_tool(args: dict) -> dict[str, Any]:
        """Show interactive options to user.

        Note: The actual UI rendering happens via CUSTOM AG-UI events
        emitted by the pre_tool_hook in design_assistant.py.
        """
        logger.info(f"[{session_id}] Asking user: {args['question']}")
        # Store UI component in session state for frontend access
        state = get_session_state(session_id)
        options = sanitize_ask_options(args.get("options", []))
        cards = sanitize_cards(args.get("cards", []))
        ui_component = {
            "type": "user_input_required",
            "question": args["question"],
            "options": options,
            "multi_select": args.get("multi_select", False),
        }
        if cards:
            ui_component["cards"] = cards
        state["pending_ui_component"] = ui_component
        # UI is rendered via CUSTOM event - just return confirmation
        return {
            "content": [{
                "type": "text",
                "text": f"Presenting options to user: {args['question']}"
            }]
        }

    @tool("request_selection_list", "Present a checkbox/radio list for selection", SelectionListSchema)
    async def request_selection_list_tool(args: dict) -> dict[str, Any]:
        """Show a selection list UI to user."""
        logger.info(f"[{session_id}] Requesting selection list: {args['question']}")
        state = get_session_state(session_id)
        options = ensure_other_option(sanitize_ask_options(args.get("options", [])))
        cards = sanitize_cards(args.get("cards", []))
        ui_component = {
            "type": "user_input_required",
            "question": args["question"],
            "options": options,
            "multi_select": args.get("multi_select", False),
        }
        if cards:
            ui_component["cards"] = cards
        state["pending_ui_component"] = ui_component
        return {
            "content": [{
                "type": "text",
                "text": f"Presenting selection list: {args['question']}"
            }]
        }

    @tool("request_data_table", "Request structured data table input", DataTableSchema)
    async def request_data_table_tool(args: dict) -> dict[str, Any]:
        """Show a data table UI to capture structured lists."""
        state = get_session_state(session_id)

        title = InputSanitizer.sanitize_name(args.get("title", "")) or "Data Table"
        columns = []
        for column in args.get("columns", []):
            name = InputSanitizer.sanitize_name(column.get("name", "")) or "Item"
            col_type = column.get("type", "text")
            if col_type not in {"text", "number", "enum", "date", "url"}:
                col_type = "text"
            options = InputSanitizer.sanitize_array(column.get("options"))
            columns.append(
                {
                    "name": name,
                    "type": col_type,
                    "required": bool(column.get("required")),
                    "options": options or None,
                }
            )

        max_rows = 50
        min_rows = _safe_int(args.get("min_rows"), 1)
        min_rows = min(max_rows, max(1, min_rows))
        starter_rows = _safe_int(args.get("starter_rows"), min_rows)
        starter_rows = min(max_rows, max(1, starter_rows), min_rows)
        input_modes = InputSanitizer.sanitize_array(args.get("input_modes", ["paste", "inline"]))

        ui_component = {
            "type": "data_table",
            "title": title,
            "columns": columns,
            "min_rows": min_rows,
            "starter_rows": starter_rows,
            "input_modes": input_modes or ["paste", "inline"],
            "summary_prompt": InputSanitizer.sanitize_description(args.get("summary_prompt")),
        }

        state["pending_ui_component"] = ui_component

        logger.info(f"[{session_id}] Requesting data table: {title}")
        return {
            "content": [{
                "type": "text",
                "text": f"Requesting data table: {title}"
            }]
        }

    @tool("request_process_map", "Request a process map input", ProcessMapSchema)
    async def request_process_map_tool(args: dict) -> dict[str, Any]:
        """Show a process map UI to capture workflows."""
        state = get_session_state(session_id)

        title = InputSanitizer.sanitize_name(args.get("title", "")) or "Process Map"
        required_fields = InputSanitizer.sanitize_array(
            args.get("required_fields", ["step_name", "owner", "outcome"])
        )
        edge_types = InputSanitizer.sanitize_array(
            args.get("edge_types", ["sequence", "approval", "parallel"])
        )
        seed_nodes = InputSanitizer.sanitize_array(args.get("seed_nodes", []))
        min_steps = _safe_int(args.get("min_steps"), 1)
        min_steps = min(min_steps, 20)

        ui_component = {
            "type": "process_map",
            "title": title,
            "required_fields": required_fields or ["step_name", "owner", "outcome"],
            "edge_types": edge_types or ["sequence", "approval", "parallel"],
            "min_steps": min_steps,
            "seed_nodes": seed_nodes,
        }

        state["pending_ui_component"] = ui_component

        logger.info(f"[{session_id}] Requesting process map: {title}")
        return {
            "content": [{
                "type": "text",
                "text": f"Requesting process map: {title}"
            }]
        }

    @tool("phase", "Transition to a different design phase", PhaseSchema)
    async def phase_tool(args: dict) -> dict[str, Any]:
        """Change the current design phase.

        Note: This also needs to update the session state (not just tool state).
        The on_phase_change callback handles this if set.
        """
        state = get_session_state(session_id)
        old_phase = state["phase"]
        new_phase = args["phase"]
        state["phase"] = new_phase

        # Call the phase change callback if registered
        callback = state.get("_on_phase_change")
        if callback:
            callback(new_phase)

        logger.info(f"[{session_id}] Phase: {old_phase} -> {new_phase}")
        return {
            "content": [{
                "type": "text",
                "text": f"Transitioned from {old_phase} to {new_phase}"
            }]
        }

    @tool("preview", "Get a preview of the current blueprint", {"type": "object", "properties": {}})
    async def preview_tool(args: dict) -> dict[str, Any]:
        """Return the current blueprint state as InterviewBlueprint JSON."""
        import json
        from datetime import datetime
        state = get_session_state(session_id)
        logger.info(f"[{session_id}] Blueprint preview requested")

        # Build InterviewBlueprint JSON structure
        project = state["project"] or {}
        agent_caps = state.get("agent_capabilities") or {}

        blueprint = {
            "id": session_id,
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "project": {
                "name": project.get("name"),
                "type": project.get("type"),
                "domain": project.get("domain"),
                "description": project.get("description"),
            },
            "knowledge_areas": [
                {
                    "name": entity["name"],
                    "attributes": entity["attributes"],
                    "description": entity.get("description"),
                }
                for entity in state["entities"]
            ],
            "interview_agent": {
                "role": agent_caps.get("role"),
                "expertise_areas": agent_caps.get("expertise_areas", []),
                "interaction_style": agent_caps.get("interaction_style"),
                "capabilities": agent_caps.get("capabilities", []),
                "focus_areas": agent_caps.get("focus_areas", []),
                # Include the configured agent details
                "config": state["agents"][0] if state["agents"] else None,
            },
        }

        # Add context files info for each agent
        agents = state.get("agents", [])
        total_context_files = 0
        for agent in agents:
            context_files = agent.get("context_files", [])
            if context_files:
                blueprint["interview_agent"]["context_files"] = [
                    {"id": f.get("id"), "name": f.get("name"), "type": f.get("type")}
                    for f in context_files
                ]
                total_context_files += len(context_files)

        summary_parts = []
        if project.get("name"):
            summary_parts.append(f"Project: {project['name']}")
        summary_parts.append(f"Knowledge Areas: {len(state['entities'])}")
        if agent_caps.get("role"):
            summary_parts.append(f"Interviewer: {agent_caps['role']}")
        if total_context_files > 0:
            summary_parts.append(f"Context Files: {total_context_files}")

        blueprint_json = json.dumps(blueprint, indent=2)
        summary = ", ".join(summary_parts)
        return {
            "content": [{
                "type": "text",
                "text": f"InterviewBlueprint:\n```json\n{blueprint_json}\n```\n\nSummary: {summary}"
            }]
        }

    @tool("agent_summary", "Display configured specialist agent to user", AgentSummarySchema)
    async def agent_summary_tool(args: dict) -> dict[str, Any]:
        """Show the user what specialist agent was configured in Phase 2.

        Note: The UI card is rendered via CUSTOM AG-UI events
        emitted by the pre_tool_hook in design_assistant.py.
        """
        state = get_session_state(session_id)

        # Store the agent capabilities in session state
        agent_caps = {
            "role": args["role"],
            "expertise_areas": args["expertise_areas"],
            "interaction_style": args["interaction_style"],
            "capabilities": args.get("capabilities", []),
            "focus_areas": args.get("focus_areas", []),
        }
        state["agent_capabilities"] = agent_caps

        logger.info(f"[{session_id}] Agent configured: {args['role']}")

        # UI is rendered via CUSTOM event - just return confirmation
        return {
            "content": [{
                "type": "text",
                "text": f"Specialist agent configured: {args['role']}"
            }]
        }

    @tool("get_phase_context", "Get hydrated context for a specific phase", GetPhaseContextSchema)
    async def get_phase_context_tool(args: dict) -> dict[str, Any]:
        """Get the context needed for a specific phase.

        Returns the goal summary and agent configuration as appropriate
        for the requested phase.
        """
        state = get_session_state(session_id)
        phase = args["phase"]

        context = {
            "phase": phase,
            "project": state.get("project"),
            "goal_summary": state.get("goal_summary"),
        }

        if phase in ["agent_configuration", "blueprint_design"]:
            context["goal_summary"] = state.get("goal_summary")

        if phase == "blueprint_design":
            context["agent_capabilities"] = state.get("agent_capabilities")
            context["entities"] = state.get("entities", [])
            context["agents"] = state.get("agents", [])

        logger.info(f"[{session_id}] Phase context requested: {phase}")

        import json
        return {
            "content": [{
                "type": "text",
                "text": f"Phase context for {phase}:\n{json.dumps(context, indent=2)}"
            }]
        }

    @tool("save_goal_summary", "Save the goal summary from Phase 1", GoalSummarySchema)
    async def save_goal_summary_tool(args: dict) -> dict[str, Any]:
        """Save the goal summary discovered in Phase 1.

        This is called when Phase 1 is complete to persist the goal
        information for use in Phase 2 and 3.
        """
        state = get_session_state(session_id)

        goal_summary = {
            "project_type": args["project_type"],
            "primary_goal": args["primary_goal"],
            "interviewees": args.get("interviewees"),
            "information_needs": args.get("information_needs"),
            "output_requirements": args.get("output_requirements"),
            "constraints": args.get("constraints"),
        }
        state["goal_summary"] = goal_summary

        logger.info(f"[{session_id}] Goal summary saved: {args['project_type']}")

        return {
            "content": [{
                "type": "text",
                "text": f"Goal summary saved. Project type: {args['project_type']}, Primary goal: {args['primary_goal']}"
            }]
        }

    @tool("hydrate_phase2", "Hydrate Phase 2 (Agent Configuration) prompt with goal", HydratePhase2Schema)
    async def hydrate_phase2_tool(args: dict) -> dict[str, Any]:
        """Hydrate the Phase 2 template with the project goal.

        Call this after Phase 1 is complete to prepare Phase 2's prompt
        with the discovered goal information.
        """
        # Use the bound session_id from the closure
        state = get_session_state(session_id)
        phase = "agent_configuration"
        context = {"goal": args["goal"]}

        try:
            template = load_template(phase)
            hydrated = hydrate_template(template, context)

            # Store in session state
            state["hydrated_prompts"][phase] = {
                "prompt": hydrated,
                "template_name": PHASE_TEMPLATES[phase],
                "context": context,
            }

            # Also store the goal in state for later phases
            state["goal_summary"] = state.get("goal_summary", {})
            state["goal_summary"]["goal_text"] = args["goal"]

            logger.info(f"[{session_id}] Hydrated Phase 2 prompt with goal")

            return {
                "content": [{
                    "type": "text",
                    "text": f"Phase 2 (Agent Configuration) prompt hydrated with goal for session {session_id}. Ready to configure specialist agent."
                }]
            }
        except (ValueError, FileNotFoundError) as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error hydrating Phase 2: {str(e)}"
                }],
                "isError": True
            }

    @tool("hydrate_phase3", "Hydrate Phase 3 (Blueprint Design) prompt with agent config", HydratePhase3Schema)
    async def hydrate_phase3_tool(args: dict) -> dict[str, Any]:
        """Hydrate the Phase 3 template with goal and agent configuration.

        Call this after Phase 2 is complete to prepare Phase 3's prompt
        with the configured specialist agent details.
        """
        # Use the bound session_id from the closure
        state = get_session_state(session_id)
        phase = "blueprint_design"

        # Format capabilities and expertise as bullet lists for the template
        capabilities_str = "\n".join(f"- {c}" for c in args["capabilities"])
        expertise_str = "\n".join(f"- {e}" for e in args["expertise_areas"])

        context = {
            "goal": args["goal"],
            "role": args["role"],
            "capabilities": capabilities_str,
            "expertise_areas": expertise_str,
            "interaction_style": args["interaction_style"],
        }

        try:
            template = load_template(phase)
            hydrated = hydrate_template(template, context)

            # Store in session state
            state["hydrated_prompts"][phase] = {
                "prompt": hydrated,
                "template_name": PHASE_TEMPLATES[phase],
                "context": context,
            }

            # Also store the agent capabilities in state
            state["agent_capabilities"] = {
                "role": args["role"],
                "capabilities": args["capabilities"],
                "expertise_areas": args["expertise_areas"],
                "interaction_style": args["interaction_style"],
            }

            logger.info(f"[{session_id}] Hydrated Phase 3 prompt with agent config: {args['role']}")

            return {
                "content": [{
                    "type": "text",
                    "text": f"Phase 3 (Blueprint Design) prompt hydrated with {args['role']} configuration for session {session_id}. Ready to design blueprint."
                }]
            }
        except (ValueError, FileNotFoundError) as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error hydrating Phase 3: {str(e)}"
                }],
                "isError": True
            }

    @tool("get_prompt", "Get the hydrated prompt for a phase", GetHydratedPromptSchema)
    async def get_hydrated_prompt_tool(args: dict) -> dict[str, Any]:
        """Retrieve the hydrated prompt for a given phase.

        Returns the previously hydrated prompt from session state.
        If no hydrated prompt exists, returns an error.
        """
        # Use the bound session_id from the closure
        state = get_session_state(session_id)
        phase = args["phase"]

        hydrated_data = state["hydrated_prompts"].get(phase)

        if not hydrated_data:
            # If not hydrated yet, try to hydrate with current state
            # Map state keys to template placeholders correctly
            context = {}

            # Extract goal from goal_summary - templates use {{goal}}
            goal_summary = state.get("goal_summary") or {}
            if goal_summary.get("goal_text"):
                context["goal"] = goal_summary["goal_text"]
            elif goal_summary.get("primary_goal"):
                context["goal"] = goal_summary["primary_goal"]

            # Extract agent capabilities - templates use {{role}}, {{capabilities}}, etc.
            agent_caps = state.get("agent_capabilities") or {}
            if agent_caps.get("role"):
                context["role"] = agent_caps["role"]
            if agent_caps.get("capabilities"):
                # Format as bullet list for template
                caps = agent_caps["capabilities"]
                context["capabilities"] = "\n".join(f"- {c}" for c in caps) if isinstance(caps, list) else caps
            if agent_caps.get("expertise_areas"):
                areas = agent_caps["expertise_areas"]
                context["expertise_areas"] = "\n".join(f"- {a}" for a in areas) if isinstance(areas, list) else areas
            if agent_caps.get("interaction_style"):
                context["interaction_style"] = agent_caps["interaction_style"]

            try:
                template = load_template(phase)
                hydrated = hydrate_template(template, context)
                state["hydrated_prompts"][phase] = {
                    "prompt": hydrated,
                    "template_name": PHASE_TEMPLATES[phase],
                    "context": context,
                }
                hydrated_data = state["hydrated_prompts"][phase]
                logger.info(f"[{session_id}] Auto-hydrated prompt for phase '{phase}'")
            except (ValueError, FileNotFoundError) as e:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Error: No hydrated prompt found for session '{session_id}' phase '{phase}' and auto-hydration failed: {str(e)}"
                    }],
                    "isError": True
                }

        return {
            "content": [{
                "type": "text",
                "text": hydrated_data["prompt"]
            }]
        }

    @tool("prompt_editor", "Display a generated prompt for user to review and edit", PromptEditorSchema)
    async def prompt_editor_tool(args: dict) -> dict[str, Any]:
        """Show the generated system prompt in an editable UI.

        The user can review and edit the prompt before saving.
        The UI is rendered via CUSTOM AG-UI events in pre_tool_hook.
        """
        state = get_session_state(session_id)

        # Store the prompt in state for the UI to access
        prompt_data = {
            "title": args["title"],
            "prompt": args["prompt"],
            "description": args.get("description", ""),
        }
        state["pending_prompt_editor"] = prompt_data

        logger.info(f"[{session_id}] Showing prompt editor: {args['title']}")

        # UI is rendered via CUSTOM event - return confirmation
        return {
            "content": [{
                "type": "text",
                "text": f"Displaying prompt editor for: {args['title']}. Waiting for user to review and save."
            }]
        }

    @tool(
        "get_agent_context",
        "Get uploaded context files content for an interview agent",
        GetAgentContextSchema
    )
    async def get_agent_context_tool(args: dict) -> dict[str, Any]:
        """Retrieve the extracted text from context files uploaded for an agent.

        This allows the interview agent's system prompt to reference uploaded
        documents like organization charts, process docs, or policy files.
        """
        from sqlalchemy import select

        from clara.db.models import AgentContextFile
        from clara.db.session import async_session_maker

        state = get_session_state(session_id)
        agent_index = args["agent_index"]

        # Get agents list and validate index
        agents = state.get("agents", [])
        if agent_index < 0 or agent_index >= len(agents):
            msg = f"Error: Invalid agent index {agent_index}. "
            msg += f"Only {len(agents)} agents configured."
            return {
                "content": [{"type": "text", "text": msg}],
                "isError": True
            }

        agent = agents[agent_index]
        agent_name = agent.get("name", f"Agent {agent_index}")
        context_files_meta = agent.get("context_files", [])

        if not context_files_meta:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No context files uploaded for agent '{agent_name}'"
                }]
            }

        # Fetch extracted text from database
        file_ids = [f["id"] for f in context_files_meta if f.get("id")]

        try:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(AgentContextFile)
                    .where(AgentContextFile.id.in_(file_ids))
                    .where(AgentContextFile.deleted_at.is_(None))
                )
                files = result.scalars().all()

                context_parts = []
                for f in files:
                    if f.extracted_text and f.extraction_status == "success":
                        context_parts.append(
                            f"## {f.original_filename}\n\n{f.extracted_text}"
                        )
                    elif f.extraction_status == "partial":
                        context_parts.append(
                            f"## {f.original_filename} (truncated)\n\n{f.extracted_text}"
                        )
                    else:
                        context_parts.append(
                            f"## {f.original_filename}\n\n[Content could not be extracted]"
                        )

                combined = "\n\n---\n\n".join(context_parts) if context_parts else ""

                logger.info(
                    f"[{session_id}] Fetched {len(files)} context files "
                    f"for agent {agent_index}"
                )

                if combined:
                    result_text = f"Context files for agent '{agent_name}':"
                    result_text += f"\n\n{combined}"
                else:
                    result_text = "No extractable content in uploaded files."

                return {"content": [{"type": "text", "text": result_text}]}

        except Exception as e:
            logger.warning(f"[{session_id}] Failed to fetch context files: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error fetching context files: {str(e)}"
                }],
                "isError": True
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
            request_selection_list_tool,
            request_data_table_tool,
            request_process_map_tool,
            phase_tool,
            preview_tool,
            agent_summary_tool,
            get_phase_context_tool,
            save_goal_summary_tool,
            hydrate_phase2_tool,
            hydrate_phase3_tool,
            get_hydrated_prompt_tool,
            prompt_editor_tool,
            get_agent_context_tool,
        ],
    )


# List of tool names for allowed_tools configuration
CLARA_TOOL_NAMES = [
    "mcp__clara__project",
    "mcp__clara__entity",
    "mcp__clara__agent",
    "mcp__clara__ask",
    "mcp__clara__request_selection_list",
    "mcp__clara__request_data_table",
    "mcp__clara__request_process_map",
    "mcp__clara__phase",
    "mcp__clara__preview",
    "mcp__clara__agent_summary",
    "mcp__clara__get_phase_context",
    "mcp__clara__save_goal_summary",
    "mcp__clara__hydrate_phase2",
    "mcp__clara__hydrate_phase3",
    "mcp__clara__get_prompt",
    "mcp__clara__prompt_editor",
    "mcp__clara__get_agent_context",
]
