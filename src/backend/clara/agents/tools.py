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
        ui_component = {
            "type": "user_input_required",
            "question": args["question"],
            "options": args["options"],
            "multi_select": args.get("multi_select", False),
        }
        state["pending_ui_component"] = ui_component
        # UI is rendered via CUSTOM event - just return confirmation
        return {
            "content": [{
                "type": "text",
                "text": f"Presenting options to user: {args['question']}"
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

        summary_parts = []
        if project.get("name"):
            summary_parts.append(f"Project: {project['name']}")
        summary_parts.append(f"Knowledge Areas: {len(state['entities'])}")
        if agent_caps.get("role"):
            summary_parts.append(f"Interviewer: {agent_caps['role']}")

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
            agent_summary_tool,
            get_phase_context_tool,
            save_goal_summary_tool,
            hydrate_phase2_tool,
            hydrate_phase3_tool,
            get_hydrated_prompt_tool,
            prompt_editor_tool,
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
    "mcp__clara__agent_summary",
    "mcp__clara__get_phase_context",
    "mcp__clara__save_goal_summary",
    "mcp__clara__hydrate_phase2",
    "mcp__clara__hydrate_phase3",
    "mcp__clara__get_prompt",
    "mcp__clara__prompt_editor",
]
