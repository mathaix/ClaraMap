AG-UI Decision Logic Spec (Tight Loop) v1
========================================

Status: Draft
Owner: Clara Design Assistant
Scope: Decision logic for switching from chat to rich UI (tables, process maps)

This spec is standalone. Do not rely on other design artifacts.

---

1. Goals
--------
- Decide when to switch from chat to a rich UI based on user input and session state.
- Minimize user typing for structured data capture.
- Prevent tool thrash and ambiguous loops.
- Provide deterministic, testable decision rules.
- Use small models for routing and larger models for content.

2. Non-Goals
------------
- UI styling, layout, or frontend implementation details.
- Domain-specific ontology or schema design beyond table/map scaffolds.
- File upload and ingestion pipelines.

3. Key Patterns Adopted (from claude-code analysis)
---------------------------------------------------
- Self-refinement loop with completion promise and max iterations (Ralph loop).
- Multi-phase gating with explicit approvals (feature-dev flow).
- Confidence thresholding to reduce noise (code-review plugin).
- Stateful checkpointing for resumption (advanced workflows).
- User-defined guardrails derived from friction (hookify patterns).
- Decision-point user contribution requests (learning output style).

These patterns are explicitly incorporated in Sections 6-9.

4. Architecture Overview
------------------------
Components:
- Router (small model): decides tool vs chat and generates tool parameters.
- Orchestrator (Sonnet): handles natural language responses, tool explanations, and follow-up.
- Tool Menu: enumerated UI tools with strict schema.
- UI State Store: tracks tool status, completion criteria, and checkpoints.

Data flow:
User Input -> Router -> (Tool Call or Chat) -> UI -> Tool Result -> Orchestrator

5. Router Inputs and Outputs
----------------------------
Inputs:
- user_message (string)
- session_state (see Section 7)
- last_tool (name or null)
- last_tool_status (open, completed, canceled)
- user_preferences (opt-out rules, preferred UI)

Output JSON:
{
  "action": "tool" | "chat" | "clarify",
  "tool_name": "request_data_table" | "request_process_map" | null,
  "confidence": 0.0-1.0,
  "params": { ...tool schema... } | null,
  "rationale": "short string for logs"
}

Routing thresholds:
- confidence >= 0.75: execute tool call immediately
- 0.45 <= confidence < 0.75: ask one clarifying question, then re-route
- confidence < 0.45: forward to Orchestrator for standard chat

6. Tool Menu (v1)
-----------------
6.1 request_data_table
Use when the user needs to provide a list of items, structured data, or bulk entries.
Do NOT use for single items.

Parameters:
{
  "title": "string",
  "columns": [
    { "name": "string", "type": "text|number|enum|date|url", "required": true|false }
  ],
  "min_rows": number,
  "starter_rows": number,
  "input_modes": ["paste", "inline", "import"],
  "summary_prompt": "string"
}

6.2 request_process_map
Use when the user describes a workflow, sequence of steps, timeline, or migration path.
Capture "Step A -> Step B" relationships.

Parameters:
{
  "title": "string",
  "required_fields": ["step_name", "owner", "outcome"],
  "edge_types": ["sequence", "approval", "parallel"],
  "min_steps": number,
  "seed_nodes": ["string"]
}

7. Session State (UI Checkpoints)
---------------------------------
Persisted fields:
{
  "last_tool": "string|null",
  "last_tool_status": "open|completed|canceled",
  "ui_checkpoint": {
    "tool": "string",
    "payload": { ...tool params... },
    "opened_at": "timestamp",
    "completion_criteria": { ... },
    "iteration_count": number,
    "max_iterations": number
  },
  "clarifying_question_pending": boolean,
  "user_opt_out": {
    "all_tools": boolean,
    "tools": ["request_data_table", "request_process_map"],
    "expires_at": "timestamp|null"
  }
}

Checkpointing rule:
- When a tool is opened, create a ui_checkpoint.
- If the session resumes and a checkpoint is open, re-open that UI without re-asking.

8. Decision Rules (Tight Loop)
------------------------------
Hard triggers (no clarifying question):
- List size >= 3 (explicit or inferred: "we have 12 stakeholders").
- User mentions bulk entry, spreadsheet, or "paste a list".
- Workflow markers: "first/then/after/before/next", "approval process", "pipeline", "migration steps".

Soft triggers (ask once, then tool):
- Mentions "process" without steps -> ask: "Want to map the steps now?"
- Mentions "stakeholders/risks/issues" without quantity -> ask for count.
- Mentions multiple roles + any process language -> prefer process map.

Anti-thrash rules:
- If last_tool_status == "open", do not call another tool.
- If user_opt_out.all_tools is true, do not call tools unless user re-enables.
- If user cancels a tool twice in a row, switch to chat for the next turn.

Chat-only cases:
- Greetings, explanations, clarifications, or coaching.
- Single-item edits or short statements.

9. Completion Logic and Self-Refinement Loop
--------------------------------------------
Completion criteria:
- Data table: min_rows satisfied AND required columns filled.
- Process map: min_steps satisfied AND required_fields filled.

Self-refinement loop (Ralph pattern):
- After tool submission, run validation checks.
- If criteria not met, ask a targeted fix question and re-open tool.
- Max iterations: 2 (configurable per tool).
- Never loop without explicit user feedback.

10. Validation and Confidence Gating
------------------------------------
Run parallel validations (code-review pattern):
- missing_required_fields
- duplicate_entries
- contradictory_sequences (for process map)
- low_coverage (too few rows/steps vs stated scope)

Each validation returns a confidence score. Only surface issues with
confidence >= 0.80 to avoid noisy warnings.

11. User Guardrails (Hookify pattern)
-------------------------------------
Allow users to set local rules:
- "Never show tables for stakeholder lists"
- "Always map approval processes"

Rule format:
{
  "intent_pattern": "regex",
  "action": "force_tool|suppress_tool",
  "tool": "request_data_table|request_process_map"
}

Rules are applied before Router decisions.

12. Examples
------------
Example A:
User: "We have 20 stakeholders across finance, ops, and IT."
Router: action=tool, tool=request_data_table, confidence=0.86
Params: columns=[Name, Role, Influence], min_rows=20, input_modes=["paste","inline"]

Example B:
User: "First finance reviews the invoice, then IT signs off, then CFO approves."
Router: action=tool, tool=request_process_map, confidence=0.91
Params: required_fields=[step_name, owner, outcome], min_steps=3

Example C:
User: "We have some risks."
Router: action=clarify, confidence=0.58
Clarify: "How many risks are we capturing?"
Then: tool if count >=3, else chat.

13. Model Routing
-----------------
Router model options:
- Claude 3.5 Haiku (default): fast, strong tool selection.
- Llama 3.1 8B fine-tuned: edge router with 500+ tool-call examples.

Fallback:
- If Router output is invalid or confidence < 0.45, send to Sonnet.
- Orchestrator always validates tool parameters before execution.

14. Telemetry
-------------
Log events (privacy-safe):
- router_decision (action, tool, confidence)
- tool_opened, tool_submitted, tool_canceled
- validation_warning_shown (type, confidence)
- user_opt_out_changed

---

End of spec.
