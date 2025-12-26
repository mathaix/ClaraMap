# Recommended Integration Testing Strategy for Clara

## Executive Summary

After analyzing both approaches, I recommend a **layered testing strategy** that separates concerns:

1. **Deterministic Contract Tests** (CI) - Test the plumbing without LLM
2. **LLM Compliance Tests** (Developer-supervised) - Test prompt adherence with real LLM
3. **Claude Code as the Feedback Loop** - No automation needed for fixes

The key insight: **the persona card bug could not have been caught by scripted SDK tests** because the bug was the LLM not following the prompt. We need both layers.

---

## The Core Problem

Clara has two distinct failure modes:

| Failure Type | Example | Can Mock Catch It? |
|--------------|---------|-------------------|
| **Plumbing Bug** | SSE stream doesn't emit events | Yes |
| **LLM Compliance Bug** | LLM outputs `type: "info"` instead of `type: "personas"` | No |

The existing spec's "Scripted SDK" approach only catches plumbing bugs. The persona card issue we just debugged was an LLM compliance bug - the scripted SDK would have been programmed to output correct cards, masking the real problem.

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Testing Layers                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 1: Unit Tests (CI - Always Run)                                      │
│  ────────────────────────────────────                                       │
│  • Test MCP tools in isolation                                              │
│  • Test SSE event formatting                                                │
│  • Test card schema validation                                              │
│  • No LLM, no network, fast                                                 │
│                                                                              │
│  Layer 2: Contract Tests (CI - Always Run)                                  │
│  ─────────────────────────────────────────                                  │
│  • Mock orchestrator → verify SSE output                                    │
│  • Mock tools → verify event aggregation                                    │
│  • Test error handling paths                                                │
│  • Deterministic, in-process                                                │
│                                                                              │
│  Layer 3: LLM Compliance Tests (Developer-Supervised)                       │
│  ───────────────────────────────────────────────────────                    │
│  • Real LLM, real prompts                                                   │
│  • Run manually or via Claude Code                                          │
│  • Verify prompts produce expected card types                               │
│  • Non-deterministic, requires human judgment                               │
│                                                                              │
│  Layer 4: End-to-End Smoke Tests (Nightly/Release)                          │
│  ──────────────────────────────────────────────────                         │
│  • Full stack with real LLM                                                 │
│  • Capture event traces for regression analysis                             │
│  • Run against known scenarios, log results                                 │
│  • Human reviews failures next morning                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Unit Tests for Tools

These test that each MCP tool produces correct AG-UI events when called directly.

```python
# tests/unit/test_clara_tools.py

import pytest
from clara.agents.tools import ask_tool, phase_tool, project_tool


class TestAskTool:
    """Test the mcp__clara__ask tool produces correct events."""

    def test_ask_emits_custom_event(self):
        """Verify ask tool emits CUSTOM event with clara:ask name."""
        result = ask_tool(
            question="Test question?",
            options=[{"id": "a", "label": "Option A"}],
            cards=[{"card_id": "test", "type": "stepper", "title": "Test"}]
        )

        assert result["type"] == "CUSTOM"
        assert result["name"] == "clara:ask"
        assert "question" in result["value"]
        assert "options" in result["value"]
        assert "cards" in result["value"]

    def test_ask_validates_card_schema(self):
        """Verify ask tool validates card envelope schema."""
        with pytest.raises(ValueError, match="card_id required"):
            ask_tool(
                question="Test?",
                options=[],
                cards=[{"type": "stepper"}]  # Missing card_id
            )

    def test_ask_requires_options(self):
        """Verify ask tool requires at least one option."""
        with pytest.raises(ValueError, match="at least one option"):
            ask_tool(question="Test?", options=[], cards=[])


class TestPhaseTool:
    """Test the mcp__clara__phase tool."""

    def test_phase_emits_state_delta(self):
        """Verify phase tool emits STATE_DELTA event."""
        result = phase_tool(phase="agent_configuration")

        assert result["type"] == "STATE_DELTA"
        assert result["delta"]["phase"] == "agent_configuration"

    def test_phase_validates_phase_name(self):
        """Verify phase tool rejects invalid phase names."""
        with pytest.raises(ValueError, match="Invalid phase"):
            phase_tool(phase="invalid_phase")
```

**Why this works:** These tests verify the contract between tools and AG-UI events. They run fast, are deterministic, and catch regressions in event structure.

---

## Layer 2: Contract Tests for SSE Streaming

These test that the SSE endpoint correctly streams events from the orchestrator.

```python
# tests/integration/test_sse_streaming.py

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from clara.main import app
from clara.agents.orchestrator import AGUIEvent


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


class TestSSEStreaming:
    """Test SSE streaming without LLM."""

    @pytest.mark.asyncio
    async def test_streams_text_events(self, client):
        """Verify TEXT_MESSAGE_CONTENT events stream correctly."""
        mock_events = [
            AGUIEvent(type="TEXT_MESSAGE_START", data={}),
            AGUIEvent(type="TEXT_MESSAGE_CONTENT", data={"delta": "Hello "}),
            AGUIEvent(type="TEXT_MESSAGE_CONTENT", data={"delta": "world"}),
            AGUIEvent(type="TEXT_MESSAGE_END", data={}),
        ]

        with patch("clara.agents.orchestrator.session_manager") as mock:
            mock.get_session.return_value.send_message = AsyncMock(
                return_value=iter(mock_events)
            )

            # Create session first
            resp = await client.post(
                "/api/design-sessions",
                json={"project_id": "test"}
            )
            session_id = resp.json()["session_id"]

            # Stream message
            events = []
            async with client.stream(
                "POST",
                f"/api/design-sessions/{session_id}/stream",
                json={"message": "test"}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        events.append(line)

            assert len(events) == 4
            assert "TEXT_MESSAGE_START" in events[0]
            assert "Hello " in events[1]

    @pytest.mark.asyncio
    async def test_streams_custom_events(self, client):
        """Verify CUSTOM events (clara:ask) stream correctly."""
        mock_events = [
            AGUIEvent(
                type="CUSTOM",
                data={
                    "name": "clara:ask",
                    "value": {
                        "question": "Test?",
                        "options": [{"id": "a", "label": "A"}],
                        "cards": [
                            {"card_id": "s1", "type": "stepper", "title": "Progress"},
                            {"card_id": "p1", "type": "personas", "title": "Select Persona"},
                        ]
                    }
                }
            ),
        ]

        # ... similar test structure
```

**Why this works:** These tests verify the SSE plumbing without calling the LLM. They're fast and deterministic.

---

## Layer 3: LLM Compliance Tests (Developer-Supervised)

This is where the YAML flow specs come in, but they're used **interactively** rather than in CI.

### Flow Spec Format

```yaml
# tests/integration/flows/personas_step.yml

name: personas_step_compliance
description: |
  Verify the LLM outputs correct card types at the Personas step.
  This tests prompt compliance, not plumbing.

context:
  goal: "Build an IT incident discovery system"

steps:
  - name: initial_goal
    user_says: "I want to build an IT incident discovery system"
    expect:
      phase: goal_understanding
      cards:
        - type: stepper
        - type: snapshot
        - type: domain_setup  # or info - LLM decides

  - name: confirm_domain
    user_says: "Confirm"
    expect:
      phase: goal_understanding

  - name: skip_context
    user_says: "Skip"
    expect:
      phase: agent_configuration

  - name: personas_step
    user_says: "Continue"
    expect:
      phase: agent_configuration
      cards:
        - type: stepper
          body:
            current_step_contains: "Persona"
        - type: personas  # CRITICAL: Must be "personas", not "info"
          body:
            personas:
              min_count: 2

compliance_notes: |
  If the LLM outputs type: "info" instead of type: "personas" at the
  personas step, this is a prompt compliance failure. Fix by:
  1. Adding explicit type requirements to the prompt
  2. Adding examples of correct card output
  3. Adding "CRITICAL" markers for required behaviors
```

### Developer Workflow with Claude Code

```
Developer: Run the personas flow compliance test

Claude Code: Starting personas_step_compliance flow...

Step 1/4: initial_goal
  Sending: "I want to build an IT incident discovery system"
  ✓ Phase: goal_understanding
  ✓ Cards: stepper, snapshot, domain_setup

Step 2/4: confirm_domain
  Sending: "Confirm"
  ✓ Phase: goal_understanding

Step 3/4: skip_context
  Sending: "Skip"
  ✓ Phase: agent_configuration

Step 4/4: personas_step
  Sending: "Continue"
  ✗ FAILED: Expected card type "personas", got "info"

  Event trace:
  - CUSTOM clara:ask with cards: [stepper, snapshot, info]

  The LLM is not following the prompt. The stepper shows
  "Personas" as current step, but the main card has type: "info".

  Recommended fixes (choose one):

  1. Add explicit constraint to prompt:
     File: prompts/phase3_blueprint_design.txt
     Add after line 64:
     ```
     ## CRITICAL: Card Type Requirements
     At the Personas step, the main card MUST have type: "personas"
     Do NOT use type: "info" for persona cards.
     ```

  2. Add example to prompt showing correct output

  3. Fix frontend to be lenient (already done in CardStack.tsx)

  Which approach? [1/2/3/skip]

Developer: 1

Claude Code: Applying fix to prompts/phase3_blueprint_design.txt...
             Re-running step 4...

Step 4/4: personas_step (retry)
  Sending: "Continue"
  ✓ Phase: agent_configuration
  ✓ Cards: stepper, snapshot, personas (2 personas)

All steps passed. Shall I commit the prompt change?
```

---

## Layer 4: Nightly Smoke Tests

Run full flows with real LLM, capture traces, human reviews in morning.

```python
# scripts/nightly_smoke_test.py
"""
Run nightly smoke tests against real LLM.
Captures event traces for human review.
NOT run in CI - triggered by cron or manually.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

TRACES_DIR = Path("./test_traces")
FLOWS = ["personas_step", "full_happy_path", "context_files"]


async def run_flow(flow_name: str) -> dict:
    """Run a flow and capture all events."""
    # ... implementation using real HTTP client against running server
    pass


async def main():
    TRACES_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = {}
    for flow in FLOWS:
        try:
            trace = await run_flow(flow)
            results[flow] = {"status": "pass", "trace": trace}
        except AssertionError as e:
            results[flow] = {"status": "fail", "error": str(e)}

    # Save for morning review
    output = TRACES_DIR / f"smoke_{timestamp}.json"
    output.write_text(json.dumps(results, indent=2))

    # Summary
    passed = sum(1 for r in results.values() if r["status"] == "pass")
    print(f"Smoke test complete: {passed}/{len(FLOWS)} passed")
    print(f"Traces saved to: {output}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Why NOT to Automate LLM Fix Loops

| Reason | Explanation |
|--------|-------------|
| **Wrong fixes** | LLM might make tests pass without fixing root cause |
| **Prompt drift** | Auto-changes to prompts compound over time |
| **No learning** | Developer doesn't understand what went wrong |
| **Context loss** | Automated fixes lack domain knowledge |
| **Trust erosion** | "Magic" fixes reduce confidence in system |

The developer IS the feedback loop. Claude Code provides:
- Analysis of failures
- Proposed fixes
- Context from the full codebase
- Interactive refinement

This is better than any automated system.

---

## Recommended File Structure

```
src/backend/
├── tests/
│   ├── unit/
│   │   ├── test_clara_tools.py      # Layer 1: Tool unit tests
│   │   └── test_event_schemas.py    # Layer 1: Schema validation
│   │
│   ├── integration/
│   │   ├── test_sse_streaming.py    # Layer 2: Contract tests
│   │   ├── test_session_lifecycle.py
│   │   │
│   │   └── flows/                   # Layer 3: LLM compliance specs
│   │       ├── personas_step.yml
│   │       ├── domain_setup.yml
│   │       ├── context_files.yml
│   │       └── full_happy_path.yml
│   │
│   └── conftest.py
│
├── scripts/
│   └── nightly_smoke_test.py        # Layer 4: Smoke tests
│
└── clara/
    └── testing/
        ├── flow_runner.py           # Runs YAML flows interactively
        └── trace_analyzer.py        # Analyzes captured traces
```

---

## What to Build (Priority Order)

### Phase 1: Essential (This Week)
1. **Unit tests for MCP tools** - Verify event structure
2. **Contract tests for SSE** - Verify streaming works
3. **One YAML flow spec** - `personas_step.yml` as template

### Phase 2: Developer Experience (Next Week)
4. **Flow runner script** - `uv run python -m clara.testing.flow_runner personas_step`
5. **Claude Code slash command** - `/test-flow personas_step`

### Phase 3: Observability (Later)
6. **Nightly smoke test script**
7. **Trace storage and diffing**

---

## Key Differences from Previous Approaches

| Aspect | Existing Spec | My First Design | This Recommendation |
|--------|---------------|-----------------|---------------------|
| LLM in CI | Scripted (fake) | Live (real) | **None** (mock orchestrator) |
| Fix loop | Propose only | Auto-apply | **Claude Code interactive** |
| Flow format | YAML | Python | **YAML** |
| Primary goal | Determinism | Coverage | **Separation of concerns** |
| Catches LLM bugs | No | Yes (flaky) | **Yes (developer-supervised)** |

---

## Summary

1. **Don't put LLM in CI** - It's slow, costly, and non-deterministic
2. **Unit test the tools** - Fast, deterministic, catches real bugs
3. **Contract test the SSE** - Verify the plumbing works
4. **Use YAML flows for LLM testing** - But run interactively
5. **Claude Code is the feedback loop** - Developer reviews every fix
6. **Nightly smoke tests** - Catch regressions, human reviews

The goal is not to automate everything. The goal is to catch bugs at the right layer with the right tool.
