"""AG-UI router for switching between chat and rich UI tools."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import anthropic
from pydantic import ValidationError

from clara.agents.structured_output import RouterDecisionModel
from clara.config import settings
from clara.security import InputSanitizer

logger = logging.getLogger(__name__)

DATA_TABLE_MARKER_START = "[DATA_TABLE_SUBMIT]"
DATA_TABLE_MARKER_END = "[/DATA_TABLE_SUBMIT]"
PROCESS_MAP_MARKER_START = "[PROCESS_MAP_SUBMIT]"
PROCESS_MAP_MARKER_END = "[/PROCESS_MAP_SUBMIT]"

TOOL_CONFIDENCE_THRESHOLD = 0.75
CLARIFY_CONFIDENCE_THRESHOLD = 0.45

ROUTER_MODEL_MAP = {
    "haiku": "claude-3-5-haiku-20241022",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
}

ROUTER_TOOL_NAME = "router_decision"

DATA_TABLE_COLUMN_TYPES = {"text", "number", "enum", "date", "url"}

LIST_KEYWORDS = {
    "stakeholder",
    "stakeholders",
    "list",
    "table",
    "spreadsheet",
    "excel",
    "bulk",
    "batch",
    "inventory",
    "items",
    "risks",
    "issues",
    "dependencies",
    "systems",
    "users",
    "customers",
    "vendors",
}

PROCESS_KEYWORDS = {
    "process",
    "workflow",
    "steps",
    "step",
    "approval",
    "approvals",
    "pipeline",
    "migration",
    "sequence",
    "timeline",
    "handoff",
    "hand-off",
    "handover",
    "stage",
    "stages",
    "phase",
    "phases",
}

SEQUENCE_MARKERS = {"first", "then", "next", "after", "before", "finally", "last"}

SELECTION_KEYWORDS = {
    "choose",
    "pick",
    "select",
    "which",
    "options",
    "choices",
    "prefer",
}

INTERNAL_SELECTION_PHRASES = {
    "project context",
    "subject matter experts",
    "key information needs",
    "output requirements",
    "constraints",
    "constraints & preferences",
}

MAX_SELECTION_QUESTION_LEN = 160
MAX_SELECTION_OPTION_LEN = 80
SELECTION_MULTI_PATTERNS = [
    r"select all",
    r"choose all",
    r"pick all",
    r"all that apply",
    r"which ones",
    r"which of these apply",
    r"what (?:key )?information",
    r"what (?:areas|topics|aspects|issues|needs)",
    r"which (?:areas|topics|aspects|issues|needs)",
    r"are you focused on",
    r"what are you focused on",
]

SELECTION_SINGLE_PATTERNS = [
    r"choose one",
    r"pick one",
    r"which one",
    r"either",
    r"choose between",
    r"pick between",
]


@dataclass
class RouterDecision:
    """Router decision output."""
    action: Literal["tool", "chat", "clarify"]
    tool_name: str | None = None
    confidence: float = 0.0
    params: dict[str, Any] | None = None
    rationale: str | None = None
    clarifying_question: str | None = None


@dataclass
class RouterState:
    """Per-session router state."""
    last_tool: str | None = None
    last_tool_status: Literal["open", "completed", "canceled"] | None = None
    pending_tool: str | None = None
    pending_payload: dict[str, Any] | None = None
    last_clarify: str | None = None


@dataclass
class UISubmission:
    """Structured payload submitted via a rich UI component."""
    kind: Literal["data_table", "process_map"]
    payload: dict[str, Any]


def parse_ui_submission(message: str) -> UISubmission | None:
    """Extract structured UI submissions from a message."""
    if not message:
        return None

    table_match = re.search(
        re.escape(DATA_TABLE_MARKER_START) + r"(.*?)" + re.escape(DATA_TABLE_MARKER_END),
        message,
        flags=re.DOTALL,
    )
    if table_match:
        payload = _load_json_payload(table_match.group(1))
        if payload is not None:
            return UISubmission(kind="data_table", payload=payload)

    process_match = re.search(
        re.escape(PROCESS_MAP_MARKER_START) + r"(.*?)" + re.escape(PROCESS_MAP_MARKER_END),
        message,
        flags=re.DOTALL,
    )
    if process_match:
        payload = _load_json_payload(process_match.group(1))
        if payload is not None:
            return UISubmission(kind="process_map", payload=payload)

    return None


def summarize_ui_submission(submission: UISubmission) -> str:
    """Create a compact structured summary for the main model."""
    if submission.kind == "data_table":
        payload = _normalize_table_payload(submission.payload)
        summary = {
            "type": "data_table",
            "title": payload.get("title"),
            "columns": payload.get("columns", []),
            "row_count": len(payload.get("rows", [])),
            "rows": payload.get("rows", []),
        }
        return f"[UI_DATA_TABLE]{json.dumps(summary, ensure_ascii=True)}[/UI_DATA_TABLE]"

    payload = _normalize_process_payload(submission.payload)
    summary = {
        "type": "process_map",
        "title": payload.get("title"),
        "step_count": len(payload.get("steps", [])),
        "steps": payload.get("steps", []),
    }
    return f"[UI_PROCESS_MAP]{json.dumps(summary, ensure_ascii=True)}[/UI_PROCESS_MAP]"


def is_cancel_intent(message: str) -> bool:
    """Detect user intent to cancel a pending UI flow."""
    normalized = message.lower().strip()
    cancel_terms = {"cancel", "skip", "not now", "back to chat", "no thanks"}
    return any(term in normalized for term in cancel_terms)


def is_tool_reply(message: str) -> bool:
    """Detect a user reply that came from a UI selection."""
    return _is_tool_reply(message)


class UIRouter:
    """Router for deciding when to render rich UI components."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.router_model
        self._client: anthropic.AsyncAnthropic | None = None

    async def decide(
        self,
        message: str,
        state: RouterState,
        phase: str | None = None,
        flow: str | None = None,
        allow_selection: bool = True,
    ) -> RouterDecision:
        """Return a routing decision for a user message."""
        message = InputSanitizer.sanitize_message(message)
        if not message:
            return RouterDecision(action="chat", confidence=0.0, rationale="empty_message")

        if state.pending_tool and state.last_tool_status == "open":
            return RouterDecision(action="chat", confidence=0.2, rationale="pending_tool_open")

        if _is_tool_reply(message):
            return RouterDecision(action="chat", confidence=0.1, rationale="tool_reply")

        if parse_ui_submission(message):
            return RouterDecision(action="chat", confidence=0.1, rationale="ui_submission")

        if self._use_llm_router():
            decision = await self._llm_decide(message=message, phase=phase, flow=flow)
            if decision:
                decision = _normalize_selection_decision(message, decision)
                if (
                    not allow_selection
                    and decision.action == "tool"
                    and decision.tool_name == "request_selection_list"
                ):
                    return RouterDecision(
                        action="chat",
                        confidence=decision.confidence,
                        rationale="selection_disabled_on_input",
                    )
                return _apply_thresholds(decision)

        decision = _heuristic_decide(message=message, allow_selection=allow_selection)
        if allow_selection:
            decision = _normalize_selection_decision(message, decision)
        elif decision.action == "tool" and decision.tool_name == "request_selection_list":
            decision = RouterDecision(
                action="chat",
                confidence=decision.confidence,
                rationale="selection_disabled_on_input",
            )
        return _apply_thresholds(decision)

    def _use_llm_router(self) -> bool:
        if self.model == "heuristic":
            return False
        if settings.anthropic_api_key:
            return True
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    async def _llm_decide(
        self,
        message: str,
        phase: str | None,
        flow: str | None,
    ) -> RouterDecision | None:
        """Call a small model to decide routing using tool-forced JSON."""
        model_id = ROUTER_MODEL_MAP.get(self.model, self.model)

        try:
            if not self._client:
                if settings.anthropic_api_key:
                    self._client = anthropic.AsyncAnthropic(
                        api_key=settings.anthropic_api_key
                    )
                else:
                    self._client = anthropic.AsyncAnthropic()

            system_prompt = _router_system_prompt()
            user_prompt = _router_user_prompt(message=message, phase=phase, flow=flow)

            response = await self._client.messages.create(
                model=model_id,
                max_tokens=512,
                max_retries=2,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[_router_tool_definition()],
                tool_choice={"type": "tool", "name": ROUTER_TOOL_NAME},
            )

            tool_input = _extract_tool_input(response, ROUTER_TOOL_NAME)
            if not isinstance(tool_input, dict):
                return None

            try:
                decision_model = RouterDecisionModel.model_validate(tool_input)
            except ValidationError as exc:
                logger.warning("Router decision invalid: %s", exc)
                return None

            # Convert Pydantic model to RouterDecision dataclass
            return RouterDecision(
                action=decision_model.action,
                tool_name=decision_model.tool_name,
                confidence=decision_model.confidence,
                rationale=decision_model.rationale,
                clarifying_question=decision_model.clarifying_question,
            )
        except Exception as exc:  # pragma: no cover - network failure fallback
            logger.warning("Router model failed, using heuristics: %s", exc)

        return None


def _load_json_payload(raw: str) -> dict[str, Any] | None:
    """Parse JSON payload safely."""
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return None


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


def _normalize_table_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize data table submissions for downstream use."""
    title = InputSanitizer.sanitize_name(payload.get("title", "")) or "Data Table"
    columns = payload.get("columns") or []
    rows = payload.get("rows") or []

    sanitized_columns = []
    for col in columns:
        name = InputSanitizer.sanitize_name(col.get("name")) or "Item"
        col_type = col.get("type", "text")
        if col_type not in DATA_TABLE_COLUMN_TYPES:
            col_type = "text"
        sanitized_columns.append(
            {
                "name": name,
                "type": col_type,
                "required": bool(col.get("required")),
                "options": InputSanitizer.sanitize_array(col.get("options")) or None,
            }
        )

    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned = {}
        for key, value in row.items():
            cleaned[str(key)] = str(value).strip()
        if any(cleaned.values()):
            normalized_rows.append(cleaned)

    return {
        "title": title,
        "columns": sanitized_columns,
        "rows": normalized_rows,
    }


def _normalize_process_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize process map submissions for downstream use."""
    title = InputSanitizer.sanitize_name(payload.get("title", "")) or "Process Map"
    steps = payload.get("steps") or []

    normalized_steps = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        normalized_steps.append(
            {
                "step_name": InputSanitizer.sanitize_name(step.get("step_name")),
                "owner": InputSanitizer.sanitize_name(step.get("owner")),
                "outcome": InputSanitizer.sanitize_description(step.get("outcome")),
                "edge_type": InputSanitizer.sanitize_name(step.get("edge_type")),
            }
        )

    return {"title": title, "steps": normalized_steps}


def _router_system_prompt() -> str:
    return (
        "You are a router that decides when to switch from chat to a rich UI.\n"
        "You must call the router_decision tool with keys:\n"
        "- action: tool|chat|clarify\n"
        "- tool_name: request_data_table|request_process_map|request_selection_list|null\n"
        "- confidence: number 0-1\n"
        "- params: object|null\n"
        "- rationale: short string\n"
        "- clarifying_question: string|null\n"
        "Follow these rules:\n"
        "1) Use request_data_table for lists or bulk structured data.\n"
        "2) Use request_process_map for workflows or step sequences.\n"
        "3) Use request_selection_list when the user is choosing from 2-7 options.\n"
        "3) If unclear, action=clarify with a short question.\n"
        "4) Otherwise action=chat.\n"
    )


def _router_user_prompt(message: str, phase: str | None, flow: str | None) -> str:
    context_parts = []
    if phase:
        context_parts.append(f"phase={phase}")
    if flow:
        context_parts.append(f"flow={flow}")
    context = f"Context: {', '.join(context_parts)}" if context_parts else "Context: none"
    return f"{context}\nUser message: {message}"


def _router_tool_definition() -> dict[str, Any]:
    return {
        "name": ROUTER_TOOL_NAME,
        "description": "Return a routing decision for Clara's UI selection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["tool", "chat", "clarify"],
                    "description": "Routing action to take.",
                },
                "tool_name": {
                    "type": ["string", "null"],
                    "enum": [
                        "request_data_table",
                        "request_process_map",
                        "request_selection_list",
                        None,
                    ],
                    "description": "Tool to use when action=tool.",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence score between 0 and 1.",
                },
                "params": {
                    "type": ["object", "null"],
                    "description": "Tool parameters if action=tool.",
                    "additionalProperties": True,
                },
                "rationale": {
                    "type": "string",
                    "description": "Short explanation for the decision.",
                },
                "clarifying_question": {
                    "type": ["string", "null"],
                    "description": "Question to ask when action=clarify.",
                },
            },
            "required": ["action", "confidence", "rationale"],
        },
    }


def _parse_router_json(text: str) -> RouterDecision | None:
    """Parse router JSON output with fallback to substring extraction."""
    if not text:
        return None

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    action = data.get("action")
    if action not in {"tool", "chat", "clarify"}:
        return None

    return RouterDecision(
        action=action,
        tool_name=data.get("tool_name"),
        confidence=float(data.get("confidence", 0.0) or 0.0),
        params=data.get("params"),
        rationale=data.get("rationale"),
        clarifying_question=data.get("clarifying_question"),
    )


def _heuristic_decide(message: str, allow_selection: bool = True) -> RouterDecision:
    """Heuristic router used when LLM router is unavailable."""
    normalized = message.lower()

    if allow_selection:
        selection_items = _extract_selection_items(message)
        if selection_items:
            multi_select = _selection_is_multi(normalized)
            params = _build_selection_params(message, selection_items, multi_select)
            confidence = 0.82
            return RouterDecision(
                action="tool",
                tool_name="request_selection_list",
                confidence=confidence,
                params=params,
                rationale="selection_list_detected",
            )

    count = _extract_explicit_count(normalized)
    list_score = sum(1 for key in LIST_KEYWORDS if key in normalized)
    process_score = sum(1 for key in PROCESS_KEYWORDS if key in normalized)
    sequence_hits = sum(1 for key in SEQUENCE_MARKERS if key in normalized)

    list_force = count is not None and count >= 3
    list_force = list_force or any(
        term in normalized for term in ["spreadsheet", "excel", "bulk", "paste", "table"]
    )

    process_force = (
        "->" in normalized
        or sequence_hits >= 2
        or ("process" in normalized and sequence_hits >= 1)
    )

    if process_force or (process_score >= 2 and process_score >= list_score):
        params = _build_process_map_params(message=message, min_steps=count)
        confidence = _confidence_from_score(process_score + sequence_hits, base=0.6)
        if process_force:
            confidence = max(confidence, 0.82)
        return RouterDecision(
            action="tool",
            tool_name="request_process_map",
            confidence=confidence,
            params=params,
            rationale="process_markers_detected",
        )

    if list_force or list_score >= 2:
        params = _build_data_table_params(message=message, min_rows=count)
        confidence = _confidence_from_score(list_score, base=0.6)
        if list_force:
            confidence = max(confidence, 0.82)
        return RouterDecision(
            action="tool",
            tool_name="request_data_table",
            confidence=confidence,
            params=params,
            rationale="list_markers_detected",
        )

    if process_score == 1 or sequence_hits == 1:
        return RouterDecision(
            action="clarify",
            confidence=0.55,
            clarifying_question="Want to map the steps in a process map?",
            rationale="weak_process_signal",
        )

    if list_score == 1:
        return RouterDecision(
            action="clarify",
            confidence=0.5,
            clarifying_question="How many items are you capturing?",
            rationale="weak_list_signal",
        )

    return RouterDecision(action="chat", confidence=0.2, rationale="no_signal")


def _extract_explicit_count(text: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\b", text)
    if not match:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    return value if value > 0 else None


def _confidence_from_score(score: int, base: float = 0.5) -> float:
    return min(0.95, base + (score * 0.08))


def _build_data_table_params(message: str, min_rows: int | None = None) -> dict[str, Any]:
    normalized = message.lower()
    title = "Data Table"
    columns = _default_columns()

    if "stakeholder" in normalized:
        title = "Stakeholder List"
        columns = [
            {"name": "Name", "type": "text", "required": True},
            {"name": "Role", "type": "text", "required": True},
            {"name": "Influence Level", "type": "enum", "required": False,
             "options": ["Low", "Medium", "High"]},
        ]
    elif "risk" in normalized:
        title = "Risk Register"
        columns = [
            {"name": "Risk", "type": "text", "required": True},
            {"name": "Severity", "type": "enum", "required": False,
             "options": ["Low", "Medium", "High"]},
            {"name": "Owner", "type": "text", "required": False},
        ]
    elif "system" in normalized:
        title = "System Inventory"
        columns = [
            {"name": "System", "type": "text", "required": True},
            {"name": "Owner", "type": "text", "required": False},
            {"name": "Criticality", "type": "enum", "required": False,
             "options": ["Low", "Medium", "High"]},
        ]

    max_rows = 50
    min_rows = min_rows or 3
    min_rows = min(max_rows, min_rows)
    starter_rows = min(5, min_rows)

    return {
        "title": title,
        "columns": columns,
        "min_rows": min_rows,
        "starter_rows": starter_rows,
        "input_modes": ["paste", "inline"],
        "summary_prompt": "Capture the list as structured rows.",
    }


def _default_columns() -> list[dict[str, Any]]:
    return [
        {"name": "Item", "type": "text", "required": True},
        {"name": "Description", "type": "text", "required": False},
        {"name": "Owner", "type": "text", "required": False},
    ]


def _sanitize_columns(columns: Any) -> list[dict[str, Any]]:
    if not isinstance(columns, list):
        return _default_columns()

    sanitized = []
    for column in columns:
        if not isinstance(column, dict):
            continue
        name = InputSanitizer.sanitize_name(column.get("name"))
        if not name:
            continue
        col_type = column.get("type", "text")
        if col_type not in DATA_TABLE_COLUMN_TYPES:
            col_type = "text"
        options = InputSanitizer.sanitize_array(column.get("options")) or None
        sanitized.append(
            {
                "name": name,
                "type": col_type,
                "required": bool(column.get("required")),
                "options": options,
            }
        )

    return sanitized or _default_columns()


def _build_process_map_params(message: str, min_steps: int | None = None) -> dict[str, Any]:
    normalized = message.lower()
    title = "Process Map"
    if "approval" in normalized:
        title = "Approval Process"
    elif "migration" in normalized:
        title = "Migration Workflow"

    min_steps = min_steps or 3
    min_steps = min(min_steps, 20)
    return {
        "title": title,
        "required_fields": ["step_name", "owner", "outcome"],
        "edge_types": ["sequence", "approval", "parallel"],
        "min_steps": min_steps,
        "seed_nodes": [],
    }


def _build_selection_params(
    message: str,
    items: list[str],
    multi_select: bool,
) -> dict[str, Any]:
    question = _extract_question(message)
    if not question:
        question = "Select the options that apply." if multi_select else "Choose one option."

    options = []
    for item in items:
        label = InputSanitizer.sanitize_name(item)
        if not label:
            continue
        option_id = _slugify(label)
        options.append({"id": option_id, "label": label})

    options = _ensure_other_option(options)

    return {
        "question": question,
        "options": options,
        "multi_select": multi_select,
    }


def _is_tool_reply(message: str) -> bool:
    normalized = message.lower().strip()
    if normalized.startswith("i chose:"):
        return True
    if normalized.startswith("[prompt_saved]"):
        return True
    return False


def _extract_selection_items(message: str) -> list[str]:
    normalized = message.lower()
    if not any(keyword in normalized for keyword in SELECTION_KEYWORDS):
        return []

    patterns = [
        r"(?:options|choices)\s*[:\-]\s*(.+)",
        r"(?:choose between|pick between|select from|choose from|pick from)\s+(.+)",
    ]

    segment = None
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            segment = match.group(1)
            break

    if segment is None:
        if any(sep in message for sep in [",", "/", "|", " or "]):
            segment = message
        else:
            return []

    segment = re.split(r"[?.!]", segment)[0]
    items = _split_list_items(segment)

    cleaned = []
    for item in items:
        value = item.strip().strip('"').strip("'")
        if len(value) < 2:
            continue
        cleaned.append(value)

    if 2 <= len(cleaned) <= 7:
        return cleaned
    return []


def _split_list_items(segment: str) -> list[str]:
    if "," in segment or ";" in segment:
        return re.split(r"\s*[,;]\s*", segment)
    if "/" in segment or "|" in segment:
        return re.split(r"\s*[\/|]\s*", segment)
    if re.search(r"\bor\b", segment, flags=re.IGNORECASE):
        return re.split(r"\s+\bor\b\s+", segment, flags=re.IGNORECASE)
    return re.split(r"\s+\band\b\s+", segment, flags=re.IGNORECASE)


def _clean_list_item(item: str) -> str:
    cleaned = re.sub(r"[*_`]+", "", item)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" \t-–—:;.,")


def _extract_numbered_items(message: str) -> list[str]:
    pattern = re.compile(
        r"(?:^|\s)(?:\d+)[\.\)]\s*([^\n]+?)(?=\s*\d+[\.\)]|$)",
        flags=re.DOTALL,
    )
    items: list[str] = []
    for match in pattern.finditer(message):
        value = _clean_list_item(match.group(1))
        if value:
            items.append(value)
    return items


def _extract_bulleted_items(message: str) -> list[str]:
    items: list[str] = []
    for line in message.splitlines():
        match = re.match(r"\s*(?:[-*•])\s+(.+)", line)
        if not match:
            continue
        value = _clean_list_item(match.group(1))
        if value:
            items.append(value)
    return items


def strip_selection_list_from_text(message: str) -> str:
    lines: list[str] = []
    for line in message.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        if re.match(r"(?:[-*•]|\d+[.)])\s+", stripped):
            continue
        lowered = stripped.lower()
        if lowered.startswith(("for example", "for instance", "e.g.")):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def infer_selection_from_assistant_output(message: str) -> RouterDecision | None:
    """Infer a selection list from assistant output."""
    sanitized = InputSanitizer.sanitize_message(message)
    if not sanitized:
        return None
    if not _assistant_output_has_selection_prompt(sanitized):
        return None

    question = _extract_question(sanitized)
    if question and len(question) > MAX_SELECTION_QUESTION_LEN:
        return None

    selection_items = _extract_selection_items(sanitized)
    if not selection_items:
        selection_items = _extract_numbered_items(sanitized)
    if not selection_items:
        selection_items = _extract_bulleted_items(sanitized)

    selection_items = _sanitize_selection_items(selection_items)
    if not (2 <= len(selection_items) <= 7):
        return None

    multi_select = _selection_is_multi(sanitized.lower())
    params = _build_selection_params(sanitized, selection_items, multi_select)
    return RouterDecision(
        action="tool",
        tool_name="request_selection_list",
        confidence=0.7,
        params=params,
        rationale="assistant_output_list",
    )


def _assistant_output_has_selection_prompt(message: str) -> bool:
    normalized = message.lower()
    if any(keyword in normalized for keyword in SELECTION_KEYWORDS):
        return True
    if "for example" in normalized or "for instance" in normalized or "e.g." in normalized:
        return True
    if re.search(r"which (?:one|of these|of the following)", normalized):
        return True
    return False


def _sanitize_selection_items(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        value = _clean_list_item(item)
        if not value or len(value) > MAX_SELECTION_OPTION_LEN:
            continue
        if _is_internal_option(value):
            continue
        cleaned.append(value)
    return cleaned


def _is_internal_option(label: str) -> bool:
    normalized = label.lower()
    return any(phrase in normalized for phrase in INTERNAL_SELECTION_PHRASES)


def _selection_is_multi(normalized: str) -> bool:
    for pattern in SELECTION_MULTI_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return True
    for pattern in SELECTION_SINGLE_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return False
    return False


def _selection_is_explicit(normalized: str) -> bool:
    keywords = {"options", "choices", "choose", "select", "pick"}
    return any(keyword in normalized for keyword in keywords)


def _extract_question(message: str) -> str | None:
    if "?" in message:
        question = message.split("?", 1)[0].strip()
        if question:
            return f"{question}?"
    return None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "option"


def _ensure_other_option(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for option in options:
        label = str(option.get("label", "")).lower().strip()
        if label.startswith("other") or label in {"something else"}:
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


def _normalize_selection_decision(message: str, decision: RouterDecision) -> RouterDecision:
    if decision.tool_name != "request_selection_list":
        return decision

    params = dict(decision.params or {})
    params["multi_select"] = _selection_is_multi(message.lower())
    if "options" in params and isinstance(params["options"], list):
        params["options"] = _ensure_other_option(params["options"])
    decision.params = params
    return decision


def build_ui_component(decision: RouterDecision) -> dict[str, Any] | None:
    """Convert router params into UI component payloads."""
    if decision.action != "tool" or not decision.tool_name:
        return None

    params = decision.params or {}

    if decision.tool_name == "request_data_table":
        min_rows = _safe_int(params.get("min_rows"), 3)
        min_rows = min(min_rows, 50)
        starter_rows = _safe_int(params.get("starter_rows"), min_rows)
        starter_rows = min(starter_rows, min_rows)
        input_modes = InputSanitizer.sanitize_array(params.get("input_modes"))
        title = InputSanitizer.sanitize_name(params.get("title")) or "Data Table"
        return {
            "type": "data_table",
            "title": title,
            "columns": _sanitize_columns(params.get("columns")),
            "min_rows": min_rows,
            "starter_rows": starter_rows,
            "input_modes": input_modes or ["paste", "inline"],
            "summary_prompt": params.get("summary_prompt", ""),
        }

    if decision.tool_name == "request_process_map":
        min_steps = _safe_int(params.get("min_steps"), 3)
        min_steps = min(min_steps, 20)
        required_fields = InputSanitizer.sanitize_array(params.get("required_fields"))
        edge_types = InputSanitizer.sanitize_array(params.get("edge_types"))
        seed_nodes = InputSanitizer.sanitize_array(params.get("seed_nodes"))
        title = InputSanitizer.sanitize_name(params.get("title")) or "Process Map"
        return {
            "type": "process_map",
            "title": title,
            "required_fields": required_fields or ["step_name", "owner", "outcome"],
            "edge_types": edge_types or ["sequence", "approval", "parallel"],
            "min_steps": min_steps,
            "seed_nodes": seed_nodes,
        }

    if decision.tool_name == "request_selection_list":
        question = InputSanitizer.sanitize_description(params.get("question"))
        options = params.get("options") or []
        sanitized_options = []
        for option in options:
            if not isinstance(option, dict):
                continue
            label = InputSanitizer.sanitize_name(option.get("label"))
            if not label:
                continue
            option_id = option.get("id") or _slugify(label)
            requires_input = bool(option.get("requires_input"))
            if label.strip().lower().startswith("other"):
                requires_input = True
            sanitized_options.append(
                {
                    "id": InputSanitizer.sanitize_name(option_id),
                    "label": label,
                    "description": InputSanitizer.sanitize_description(option.get("description")),
                    "requires_input": requires_input,
                }
            )

        return {
            "type": "user_input_required",
            "question": question or "Choose an option.",
            "options": sanitized_options,
            "multi_select": bool(params.get("multi_select")),
        }

    return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _apply_thresholds(decision: RouterDecision) -> RouterDecision:
    """Apply confidence thresholds to router decisions."""
    if decision.action == "tool" and decision.confidence < TOOL_CONFIDENCE_THRESHOLD:
        if decision.confidence >= CLARIFY_CONFIDENCE_THRESHOLD:
            return RouterDecision(
                action="clarify",
                confidence=decision.confidence,
                clarifying_question=decision.clarifying_question
                or _clarify_question_for_tool(decision.tool_name),
                rationale="threshold_downgrade_to_clarify",
            )
        return RouterDecision(
            action="chat",
            confidence=decision.confidence,
            rationale="threshold_downgrade_to_chat",
        )

    if decision.action == "clarify" and decision.confidence < CLARIFY_CONFIDENCE_THRESHOLD:
        return RouterDecision(
            action="chat",
            confidence=decision.confidence,
            rationale="clarify_below_threshold",
        )

    return decision


def _clarify_question_for_tool(tool_name: str | None) -> str:
    if tool_name == "request_data_table":
        return "How many items are you capturing?"
    if tool_name == "request_process_map":
        return "Want to map the steps in a process map?"
    if tool_name == "request_selection_list":
        return "Do you want to pick from a short list?"
    return "Can you clarify what you need captured?"
