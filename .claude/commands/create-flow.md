# Create a New Test Flow

Create a new YAML test flow for LLM compliance testing.

## Usage
```
/create-flow <flow_name>
```

## Instructions

Create a new flow spec file at `src/backend/tests/integration/flows/$ARGUMENTS.yml`.

### Template

```yaml
name: $ARGUMENTS
description: |
  [DESCRIBE: What this flow tests and why it matters]

version: "1.0"

context:
  goal: "[DESCRIBE: The project goal for this test scenario]"
  project_type: "ma_due_diligence"

session:
  project_id: test-$ARGUMENTS

steps:
  - name: initial_step
    description: "[DESCRIBE: What this step does]"
    user_says: "[USER MESSAGE: What the user sends]"
    expect:
      phase: goal_understanding
      event: CUSTOM
      event_name: clara:ask
      cards:
        must_include_types:
          - stepper
          - snapshot

  # Add more steps as needed...

assertions:
  - name: primary_assertion
    description: "[DESCRIBE: What we're validating]"
    critical: true
    check: |
      # Python validation code
      pass

compliance_notes: |
  If this flow fails:
  1. Check the relevant prompt file
  2. Verify the LLM outputs correct card types
  3. Review the event trace for debugging

failure_actions:
  - action: show_event_trace
    description: "Display the actual event for debugging"
```

### Steps to Complete

1. Create the file with the template above
2. Replace all `[PLACEHOLDERS]` with actual values
3. Add the appropriate steps for this flow
4. Define expectations for each step using:
   - `phase`: Expected phase (goal_understanding, agent_configuration, blueprint_design)
   - `event`: Event type (CUSTOM, TEXT_MESSAGE_START, etc.)
   - `event_name`: For CUSTOM events (clara:ask, clara:confirm, etc.)
   - `cards.must_include_types`: List of required card types
   - `cards.must_include`: Detailed card requirements with body validation
   - `cards.stepper_current_step_contains`: Text in active stepper step

### Available Card Types
- `stepper` - Progress indicator
- `snapshot` - Project snapshot
- `domain_setup` - Domain configuration
- `personas` - Persona selection
- `info` - General information
- `agent_configured` - Agent configuration complete

### Verify the Flow

```bash
cd src/backend

# Check it appears in the list
uv run python -m clara.testing.flow_runner --list

# Run the flow (requires backend running)
uv run python -m clara.testing.flow_runner $ARGUMENTS
```

### Example Flows to Reference
- `personas_step.yml` - Tests persona card type compliance
