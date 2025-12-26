# Run LLM Compliance Flow Test

Run a Design Assistant flow compliance test to verify LLM outputs correct AG-UI events.

## Usage
```
/test-flow <flow_name>
```

## Available Flows
- `personas_step` - Tests that the personas step outputs type: "personas" cards (not "info")

## Instructions

Run the specified flow test against the running Design Assistant:

1. First, ensure the backend is running:
   ```bash
   cd src/backend && uv run uvicorn clara.main:app --reload --port 8000
   ```

2. Run the flow test:
   ```bash
   cd src/backend && uv run python -m clara.testing.flow_runner $ARGUMENTS
   ```

3. If the test fails:
   - Review the error output to understand which card types or events are incorrect
   - Check the compliance notes in the flow spec for recommended fixes
   - The most common issue is the LLM outputting `type: "info"` instead of `type: "personas"` at the personas step

4. Report the results including:
   - Which steps passed/failed
   - The specific errors encountered
   - Recommended prompt fixes if applicable

## Flow Specs Location
Flow specs are YAML files in: `src/backend/tests/integration/flows/`

## Example Output
```
============================================================
Running flow: personas_step_compliance
Description: Verify the LLM outputs correct card types at the Personas step.
============================================================

Created session: abc123

Step 1/4: initial_goal
  Sending: "I want to build an IT incident discovery system for M&A due diligence"
  ✓ PASSED

Step 2/4: confirm_domain
  Sending: "Confirm"
  ✓ PASSED

Step 3/4: skip_context
  Sending: "Skip"
  ✓ PASSED

Step 4/4: personas_step
  Sending: "Continue"
  ✓ PASSED

============================================================
Results: 4/4 steps passed
============================================================
```
