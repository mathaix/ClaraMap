"""Structured output models for Clara's Design Assistant.

This module defines Pydantic models and a tool-forced parser that ensure
the LLM produces structured, validated responses that clearly separate
display text from interactive UI components.
"""

import logging
import os
import re
from typing import Any, Literal, Self

import anthropic
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from clara.config import settings
from clara.security import InputSanitizer

logger = logging.getLogger(__name__)

STRUCTURED_OUTPUT_MODEL_MAP = {
    "haiku": "claude-3-5-haiku-20241022",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
}

STRUCTURED_OUTPUT_TOOL_NAME = "structured_response"

INTERNAL_SELECTION_PHRASES = {
    "project context",
    "subject matter experts",
    "key information needs",
    "output requirements",
    "constraints",
    "constraints & preferences",
}

class SelectionOption(BaseModel):
    """A single option in a selection list."""

    id: str = Field(description="Unique identifier for the option")
    label: str = Field(description="Display label for the option")
    description: str | None = Field(
        default=None, description="Optional description of the option"
    )
    requires_input: bool = Field(
        default=False,
        description="True if selecting this option requires additional text input",
    )


def _normalize_selection_options(options: list[SelectionOption]) -> list[SelectionOption]:
    if len(options) < 2:
        raise ValueError("Selection must have at least 2 options")

    normalized: list[SelectionOption] = []
    other_option: SelectionOption | None = None

    for option in options:
        is_other = option.label.lower().startswith("other") or option.id == "other"
        if is_other:
            if not option.requires_input:
                option = option.model_copy(update={"requires_input": True})
            if other_option is None:
                other_option = option
            continue
        normalized.append(option)

    if other_option is None:
        other_option = SelectionOption(
            id="other",
            label="Other",
            description="Something else",
            requires_input=True,
        )

    max_non_other = 6
    if len(normalized) > max_non_other:
        normalized = normalized[:max_non_other]

    normalized.append(other_option)

    if len(normalized) < 2:
        raise ValueError("Selection must have at least 2 options")
    return normalized


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "option"


def _compact_text(value: str | None, max_len: int) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[`*_>#]+", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t-:;.,")
    if not cleaned or len(cleaned) > max_len:
        return ""
    return cleaned


def _is_internal_option(label: str) -> bool:
    normalized = label.lower()
    return any(phrase in normalized for phrase in INTERNAL_SELECTION_PHRASES)


class DataTableColumn(BaseModel):
    """Column definition for a data table."""

    name: str = Field(description="Column header name")
    type: Literal["text", "number", "enum", "date", "url"] = Field(
        default="text", description="Data type for the column"
    )
    required: bool = Field(default=False, description="Whether the column is required")
    options: list[str] | None = Field(
        default=None, description="Options for enum columns"
    )


class SelectionUIComponent(BaseModel):
    """Selection list UI component."""

    type: Literal["selection"] = "selection"
    question: str = Field(description="Question to ask the user")
    options: list[SelectionOption] = Field(description="Available options to choose from")
    multi_select: bool = Field(
        default=False, description="Whether multiple options can be selected"
    )

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[SelectionOption]) -> list[SelectionOption]:
        return _normalize_selection_options(list(v))


class DataTableUIComponent(BaseModel):
    """Data table UI component for bulk data entry."""

    type: Literal["data_table"] = "data_table"
    title: str = Field(description="Title of the data table")
    columns: list[DataTableColumn] = Field(description="Column definitions")
    min_rows: int = Field(default=3, ge=1, le=50, description="Minimum rows required")
    starter_rows: int = Field(default=3, ge=1, le=50, description="Initial empty rows")
    input_modes: list[Literal["paste", "inline", "import"]] = Field(
        default_factory=lambda: ["paste", "inline"],
        description="Allowed input modes for the table",
    )
    summary_prompt: str | None = Field(
        default=None, description="Prompt for summarizing collected data"
    )


class ProcessMapUIComponent(BaseModel):
    """Process map UI component for workflow capture."""

    type: Literal["process_map"] = "process_map"
    title: str = Field(description="Title of the process map")
    required_fields: list[str] = Field(
        default_factory=lambda: ["step_name", "owner", "outcome"],
        description="Required fields per step",
    )
    edge_types: list[str] = Field(
        default_factory=lambda: ["sequence", "approval", "parallel"],
        description="Types of connections between steps",
    )
    min_steps: int = Field(default=3, ge=2, le=20, description="Minimum steps required")
    seed_nodes: list[str] = Field(
        default_factory=list, description="Pre-filled step names"
    )


class NoUIComponent(BaseModel):
    """Marker for responses that don't include UI components."""

    type: Literal["none"] = "none"


# Union type for all UI components
UIComponent = SelectionUIComponent | DataTableUIComponent | ProcessMapUIComponent | NoUIComponent


class DesignAssistantResponse(BaseModel):
    """Structured response from Clara's Design Assistant.

    This model ensures the LLM clearly separates display text from
    interactive UI components, preventing the duplicate content issue.
    """

    display_text: str = Field(
        description=(
            "Conversational text to show the user. "
            "Do NOT include numbered lists if presenting options as a selection UI. "
            "Keep this concise when a UI component is present."
        )
    )
    ui_component: UIComponent = Field(
        default_factory=lambda: NoUIComponent(),
        description=(
            "Interactive UI component for user input. "
            "Use 'selection' for choices, 'data_table' for bulk data, "
            "'process_map' for workflows, 'none' for chat-only responses."
        ),
    )
    phase_transition: str | None = Field(
        default=None,
        description=(
            "If phase should change, specify: goal_understanding, "
            "agent_configuration, blueprint_design, or complete"
        ),
    )

    @field_validator("display_text")
    @classmethod
    def validate_display_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("display_text cannot be empty")
        return v.strip()


class StructuredOutputPayload(BaseModel):
    """Payload shape returned by the structured_response tool."""

    display_text: str = Field(description="Conversational text to show the user.")
    ui_type: Literal["none", "selection", "data_table", "process_map"] = Field(
        default="none",
        description="Type of UI component to render.",
    )
    ui: dict[str, Any] | None = Field(
        default=None,
        description="UI payload for the selected ui_type.",
    )
    phase_transition: str | None = Field(
        default=None,
        description=(
            "If phase should change, specify: goal_understanding, "
            "agent_configuration, blueprint_design, or complete"
        ),
    )

    @field_validator("display_text")
    @classmethod
    def validate_display_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("display_text cannot be empty")
        return v.strip()


class RouterDecisionModel(BaseModel):
    """Structured model for routing decisions.

    Used by the small router model (Haiku) to decide whether
    to render a rich UI component for user input.
    """

    action: Literal["tool", "chat", "clarify"] = Field(
        description=(
            "'tool' = render a rich UI component, "
            "'chat' = continue with normal conversation, "
            "'clarify' = ask a clarifying question before deciding"
        )
    )
    tool_name: Literal[
        "request_data_table", "request_process_map", "request_selection_list"
    ] | None = Field(
        default=None,
        description="Which tool to use. Required if action='tool'.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the decision (0-1)",
    )
    rationale: str = Field(
        description="Brief explanation of why this decision was made"
    )
    clarifying_question: str | None = Field(
        default=None,
        description="Question to ask if action='clarify'",
    )

    @model_validator(mode="after")
    def validate_action_requirements(self) -> Self:
        """Validate that action-specific fields are provided."""
        if self.action == "tool" and self.tool_name is None:
            raise ValueError("tool_name is required when action='tool'")
        if self.action == "clarify" and not self.clarifying_question:
            raise ValueError("clarifying_question is required when action='clarify'")
        return self


class DataTableParams(BaseModel):
    """Parameters for request_data_table tool."""

    title: str = Field(description="Title for the data table")
    columns: list[DataTableColumn] = Field(description="Column definitions")
    min_rows: int = Field(default=3, ge=1, le=50)
    starter_rows: int = Field(default=3, ge=1, le=50)
    input_modes: list[Literal["paste", "inline", "import"]] = Field(
        default_factory=lambda: ["paste", "inline"]
    )
    summary_prompt: str | None = None


class ProcessMapParams(BaseModel):
    """Parameters for request_process_map tool."""

    title: str = Field(description="Title for the process map")
    required_fields: list[str] = Field(
        default_factory=lambda: ["step_name", "owner", "outcome"]
    )
    edge_types: list[str] = Field(
        default_factory=lambda: ["sequence", "approval", "parallel"]
    )
    min_steps: int = Field(default=3, ge=2, le=20)
    seed_nodes: list[str] = Field(default_factory=list)


class SelectionListParams(BaseModel):
    """Parameters for request_selection_list tool."""

    question: str = Field(description="Question to ask the user")
    options: list[SelectionOption] = Field(description="Options to choose from")
    multi_select: bool = Field(default=False)

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[SelectionOption]) -> list[SelectionOption]:
        return _normalize_selection_options(list(v))


def ui_component_to_payload(component: UIComponent) -> dict[str, Any] | None:
    """Convert a structured UI component into the UI payload expected by the frontend."""
    if isinstance(component, NoUIComponent):
        return None

    payload = component.model_dump()
    if isinstance(component, SelectionUIComponent):
        payload["type"] = "user_input_required"
    return payload


def _structured_output_tool_definition() -> dict[str, Any]:
    return {
        "name": STRUCTURED_OUTPUT_TOOL_NAME,
        "description": "Return structured output for Clara UI rendering.",
        "input_schema": {
            "type": "object",
            "properties": {
                "display_text": {
                    "type": "string",
                    "description": "Conversational text to show the user.",
                },
                "ui_type": {
                    "type": "string",
                    "enum": ["none", "selection", "data_table", "process_map"],
                    "description": "Type of UI component to render.",
                },
                "ui": {
                    "type": "object",
                    "description": (
                        "UI payload for the selected ui_type. Use: "
                        "selection -> {question, options, multi_select}; "
                        "data_table -> {title, columns, min_rows, starter_rows, input_modes, summary_prompt}; "
                        "process_map -> {title, required_fields, edge_types, min_steps, seed_nodes}."
                    ),
                    "additionalProperties": True,
                },
                "phase_transition": {
                    "type": "string",
                    "enum": [
                        "goal_understanding",
                        "agent_configuration",
                        "blueprint_design",
                        "complete",
                    ],
                    "description": "Phase transition, if needed.",
                },
            },
            "required": ["display_text", "ui_type"],
        },
    }


def _extract_tool_input(response: Any, tool_name: str) -> dict[str, Any] | None:
    if not response or not hasattr(response, "content"):
        return None
    for block in response.content:
        if isinstance(block, dict):
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                return block.get("input")
            continue
        block_type = getattr(block, "type", None)
        if block_type == "tool_use" and getattr(block, "name", None) == tool_name:
            return getattr(block, "input", None)
    return None


def _ui_payload_from_tool_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    ui_payload = tool_input.get("ui")
    if isinstance(ui_payload, dict):
        return ui_payload
    fallback = {
        key: value
        for key, value in tool_input.items()
        if key not in {"display_text", "ui_type", "phase_transition"}
    }
    return fallback if fallback else {}


def _build_ui_component(
    payload: StructuredOutputPayload,
    tool_input: dict[str, Any],
) -> UIComponent:
    if payload.ui_type == "none":
        return NoUIComponent()

    ui_payload = _ui_payload_from_tool_input(tool_input)

    if payload.ui_type == "selection":
        raw_options = ui_payload.get("options") or []
        question = _compact_text(ui_payload.get("question"), 160)
        if not question:
            question = _compact_text(payload.display_text, 160)
        if not question:
            raise ValueError("Selection question is missing or too long")

        cleaned_options: list[SelectionOption] = []
        for option in raw_options:
            if not isinstance(option, dict):
                continue
            label = _compact_text(option.get("label"), 80)
            if not label or _is_internal_option(label):
                continue
            description = _compact_text(option.get("description"), 140) or None
            option_id = option.get("id")
            if not isinstance(option_id, str) or not option_id.strip():
                option_id = _slugify(label)
            cleaned_options.append(
                SelectionOption(
                    id=InputSanitizer.sanitize_name(option_id),
                    label=label,
                    description=description,
                    requires_input=bool(option.get("requires_input")),
                )
            )

        return SelectionUIComponent(
            question=question,
            options=cleaned_options,
            multi_select=bool(ui_payload.get("multi_select")),
        )

    if payload.ui_type == "data_table":
        title = _compact_text(ui_payload.get("title"), 120) or "Data Table"
        return DataTableUIComponent(
            title=title,
            columns=ui_payload.get("columns") or [],
            min_rows=ui_payload.get("min_rows", 3),
            starter_rows=ui_payload.get("starter_rows", 3),
            input_modes=ui_payload.get("input_modes") or ["paste", "inline"],
            summary_prompt=_compact_text(ui_payload.get("summary_prompt"), 240) or None,
        )

    if payload.ui_type == "process_map":
        title = _compact_text(ui_payload.get("title"), 120) or "Process Map"
        return ProcessMapUIComponent(
            title=title,
            required_fields=ui_payload.get("required_fields") or ["step_name", "owner", "outcome"],
            edge_types=ui_payload.get("edge_types") or ["sequence", "approval", "parallel"],
            min_steps=ui_payload.get("min_steps", 3),
            seed_nodes=ui_payload.get("seed_nodes") or [],
        )

    return NoUIComponent()


def _structured_output_system_prompt() -> str:
    return (
        "You are a formatter that converts Clara assistant replies into structured JSON.\n"
        "You must call the structured_response tool with the fields described below.\n"
        "Rules:\n"
        "1) Use ui_type='selection' only if the assistant is explicitly asking the user to choose.\n"
        "2) If the assistant asks a question and then provides example options (e.g., 'For example...'),\n"
        "   treat those options as selectable choices and set ui_type='selection'.\n"
        "3) Default multi_select=true when the question implies multiple answers\n"
        "   (e.g., 'what key information', 'which areas', 'what topics', 'are you focused on').\n"
        "4) If you set a selection UI, keep display_text and ui.question short (<= 160 chars) and remove option lists from display_text.\n"
        "5) Informational lists stay in display_text with ui_type='none'.\n"
        "6) Use 'data_table' for bulk lists and 'process_map' for workflows.\n"
        "7) Always include an 'Other' option for selections.\n"
        "8) Put the UI payload inside the 'ui' field when ui_type is not 'none'.\n"
        "9) Never use internal checklist labels (Project Context, Subject Matter Experts, Key Information Needs, Output Requirements, Constraints) as options.\n"
    )


def _structured_output_user_prompt(
    message: str,
    phase: str | None,
    flow: str | None,
) -> str:
    context_parts = []
    if phase:
        context_parts.append(f"phase={phase}")
    if flow:
        context_parts.append(f"flow={flow}")
    context = ", ".join(context_parts)
    context_line = f"Context: {context}\n" if context else ""
    return f"{context_line}Assistant reply:\n{message}"


class StructuredOutputParser:
    """Parse assistant output into structured responses via tool-forced JSON."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.structured_output_model
        self._client: anthropic.AsyncAnthropic | None = None

    def is_available(self) -> bool:
        if not self.model:
            return False
        return bool(settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"))

    async def parse(
        self,
        message: str,
        phase: str | None = None,
        flow: str | None = None,
    ) -> DesignAssistantResponse | None:
        if not self.is_available():
            return None

        sanitized = InputSanitizer.sanitize_message(message)
        if not sanitized:
            return None

        model_id = STRUCTURED_OUTPUT_MODEL_MAP.get(self.model, self.model)
        try:
            if not self._client:
                if settings.anthropic_api_key:
                    self._client = anthropic.AsyncAnthropic(
                        api_key=settings.anthropic_api_key
                    )
                else:
                    self._client = anthropic.AsyncAnthropic()

            response = await self._client.messages.create(
                model=model_id,
                max_tokens=800,
                system=_structured_output_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": _structured_output_user_prompt(
                            message=sanitized, phase=phase, flow=flow
                        ),
                    }
                ],
                tools=[_structured_output_tool_definition()],
                tool_choice={"type": "tool", "name": STRUCTURED_OUTPUT_TOOL_NAME},
            )

            tool_input = _extract_tool_input(response, STRUCTURED_OUTPUT_TOOL_NAME)
            if not isinstance(tool_input, dict):
                return None

            try:
                payload = StructuredOutputPayload.model_validate(tool_input)
            except ValidationError as exc:
                logger.warning("Structured output payload invalid: %s", exc)
                return None

            try:
                ui_component = _build_ui_component(payload, tool_input)
            except ValidationError as exc:
                logger.warning("Structured output UI invalid: %s", exc)
                ui_component = NoUIComponent()

            return DesignAssistantResponse(
                display_text=payload.display_text,
                ui_component=ui_component,
                phase_transition=payload.phase_transition,
            )
        except Exception as exc:  # pragma: no cover - network failure fallback
            logger.warning("Structured output parse failed: %s", exc)
            return None
