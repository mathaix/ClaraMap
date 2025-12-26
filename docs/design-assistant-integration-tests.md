# Design Assistant Integration Test Framework

## Purpose
Provide a deterministic, headless integration test framework for Clara’s Design Assistant that validates AG‑UI event flows (e.g., persona cards) and supports optional feedback loops without auto‑applying fixes.

## Goals
- Exercise real Design Assistant flows (goal → agent config → blueprint design).
- Assert critical AG‑UI contract requirements (cards, steps, phase transitions).
- Support deterministic CI runs without network/LLM access.
- Allow optional live-model runs for nightly validation.
- Offer a safe “fix loop” that proposes patches but never auto‑merges.

## Non‑Goals
- End‑to‑end UI rendering tests (handled separately in frontend).
- Auto‑patching production code without human review.
- Perfect conversational coverage of all domain variants.

## Architecture Overview

### 1) Flow Specs
Define flows in a declarative format (YAML or JSON) stored under:
`src/backend/tests/integration/flows/`

Each flow defines:
- Session setup (project id, optional seed state).
- Turn sequence (messages to send).
- Expected event assertions (AG‑UI events, card types, phase changes).
- Optional snapshots (golden comparisons for specific events).

Example (YAML):
```yaml
flow_name: design_assistant_personas
session:
  project_id: test-project
steps:
  - name: domain
    send: "Start flow"
    expect:
      - event: CUSTOM
        name: clara:ask
        cards:
          must_include_types: [stepper, snapshot, domain_setup]
  - name: personas
    send: "Continue"
    expect:
      - event: CUSTOM
        name: clara:ask
        cards:
          must_include_types: [stepper, snapshot, personas]
```

### 2) Headless Runner
A reusable test harness that:
- Uses `httpx.AsyncClient` with the FastAPI app in‑process.
- Calls `/api/v1/design-sessions` to create a session.
- Streams `/api/v1/design-sessions/{id}/stream` and parses SSE events.
- Applies assertions from the flow spec.

### 3) Scripted LLM (Deterministic)
Default CI mode replaces `ClaudeSDKClient` with a scripted client:
- Replays a predefined sequence of tool calls and assistant text.
- Drives predictable AG‑UI events to validate front‑end contracts.
- Avoids network and model nondeterminism.

### 4) Live Model Mode (Optional)
Optional run mode for nightly or manual validation:
- Uses real model credentials.
- Captures event logs for later replay.
- Not used in CI by default.

### 5) Feedback Loop (Safe)
An optional CLI runner for “fix suggestions” only:
- On failure, collects the flow spec + event logs + minimal context.
- Calls Codex/Claude to propose a patch (stored in `./autofix/`).
- Requires explicit human approval before applying or re‑running.
- Guardrails: max attempts, max diff size, no destructive ops.

## Assertions
Core assertions to support:
- `CUSTOM` events for `clara:ask` emitted per step.
- `cards` include required types per step (e.g., `personas`).
- Phase transitions are monotonic and consistent.
- No `ERROR` events during the flow.

Optional assertions:
- Snapshot payload keys exist (goal, specialist, status).
- Stepper current step increments as expected.

## API & Data Contracts
Event collection:
- Parse SSE events into structured `AGUIEvent` objects.
- Extract `CUSTOM` events and validate `value` shape.

Card requirements:
- `cards` array must include `stepper`, `snapshot`, and a step‑specific card.
- For personas step, `type: "personas"` and `body.personas` required.

## Proposed File Layout
```
src/backend/tests/integration/
  flows/
    design_assistant_personas.yml
  test_design_assistant_flow.py

src/backend/clara/testing/
  flow_runner.py
  scripted_sdk.py
  sse_parser.py
  fix_loop.py
```

## Execution Modes
1) **CI default**: scripted SDK, deterministic flow checks.
2) **Nightly/manual**: live model mode, capture and archive event traces.
3) **Fix‑loop (manual)**: generate patch suggestions only.

## Rollout Plan
1) Add flow spec format and minimal headless runner.
2) Implement one gold‑path flow (personas).
3) Expand flows for context files, capture template, build.
4) Add optional fix‑loop CLI (manual only).

## Risks & Mitigations
- **LLM nondeterminism**: use scripted SDK for CI.
- **API drift**: encode assertions in flow specs, run nightly live mode.
- **Over‑strict assertions**: keep assertions scoped to required contracts.

## Open Questions
- Should flow specs live in backend or a dedicated `testdata/` folder?
- Do we want golden snapshots, or only contract‑level checks?
- Which flows are “release blocking”?
