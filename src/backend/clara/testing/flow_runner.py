"""Flow runner for LLM compliance testing.

This module provides a developer-supervised flow runner that:
1. Loads YAML flow specs from tests/integration/flows/
2. Executes steps against a running Design Assistant
3. Validates AG-UI event responses against expectations
4. Reports failures with actionable fix suggestions

Usage:
    # From command line
    uv run python -m clara.testing.flow_runner personas_step

    # From Python
    from clara.testing.flow_runner import FlowRunner
    runner = FlowRunner()
    await runner.run("personas_step")
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml


@dataclass
class StepExpectation:
    """Expected outcomes for a flow step."""

    phase: str | None = None
    event: str | None = None
    event_name: str | None = None
    cards: dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowStep:
    """A single step in a flow spec."""

    name: str
    description: str
    user_says: str
    expect: StepExpectation


@dataclass
class FlowSpec:
    """A complete flow specification."""

    name: str
    description: str
    version: str
    context: dict[str, Any]
    session: dict[str, Any]
    steps: list[FlowStep]
    assertions: list[dict[str, Any]]
    compliance_notes: str
    failure_actions: list[dict[str, Any]]


@dataclass
class StepResult:
    """Result of executing a flow step."""

    step_name: str
    passed: bool
    events: list[dict[str, Any]]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class FlowRunner:
    """Runs LLM compliance flow tests against Design Assistant."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        flows_dir: Path | None = None,
    ):
        self.base_url = base_url
        self.flows_dir = flows_dir or Path(__file__).parent.parent.parent / "tests" / "integration" / "flows"
        self.session_id: str | None = None
        self.collected_events: list[dict[str, Any]] = []

    def load_flow(self, flow_name: str) -> FlowSpec:
        """Load a flow spec from YAML file."""
        flow_file = self.flows_dir / f"{flow_name}.yml"
        if not flow_file.exists():
            flow_file = self.flows_dir / f"{flow_name}.yaml"

        if not flow_file.exists():
            available = [f.stem for f in self.flows_dir.glob("*.y*ml")]
            raise FileNotFoundError(
                f"Flow '{flow_name}' not found. Available flows: {available}"
            )

        with open(flow_file) as f:
            data = yaml.safe_load(f)

        steps = []
        for step_data in data.get("steps", []):
            expect_data = step_data.get("expect", {})
            expect = StepExpectation(
                phase=expect_data.get("phase"),
                event=expect_data.get("event"),
                event_name=expect_data.get("event_name"),
                cards=expect_data.get("cards", {}),
            )
            steps.append(
                FlowStep(
                    name=step_data["name"],
                    description=step_data.get("description", ""),
                    user_says=step_data["user_says"],
                    expect=expect,
                )
            )

        return FlowSpec(
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            context=data.get("context", {}),
            session=data.get("session", {}),
            steps=steps,
            assertions=data.get("assertions", []),
            compliance_notes=data.get("compliance_notes", ""),
            failure_actions=data.get("failure_actions", []),
        )

    async def create_session(self, project_id: str) -> str:
        """Create a new design session."""
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.post(
                "/api/v1/design-sessions",
                json={"project_id": project_id},
            )
            response.raise_for_status()
            data = response.json()
            return data["session_id"]

    async def send_message(self, message: str) -> list[dict[str, Any]]:
        """Send a message and collect SSE events."""
        events: list[dict[str, Any]] = []

        async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"/api/v1/design-sessions/{self.session_id}/stream",
                json={"message": message},
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            event_data = json.loads(line[5:].strip())
                            events.append(event_data)
                        except json.JSONDecodeError:
                            pass

        return events

    def validate_step(
        self, step: FlowStep, events: list[dict[str, Any]]
    ) -> StepResult:
        """Validate events against step expectations."""
        errors: list[str] = []
        warnings: list[str] = []

        # Find CUSTOM events
        custom_events = [e for e in events if e.get("type") == "CUSTOM"]

        # Check event type
        if step.expect.event and step.expect.event_name:
            matching = [
                e for e in custom_events if e.get("name") == step.expect.event_name
            ]
            if not matching:
                errors.append(
                    f"Expected event '{step.expect.event_name}' not found. "
                    f"Got events: {[e.get('name') for e in custom_events]}"
                )

        # Check cards
        if step.expect.cards:
            cards_spec = step.expect.cards

            # Get cards from the last CUSTOM event
            actual_cards: list[dict[str, Any]] = []
            for e in reversed(custom_events):
                if "value" in e and "cards" in e.get("value", {}):
                    actual_cards = e["value"]["cards"]
                    break

            actual_types = [c.get("type") for c in actual_cards]

            # Check must_include_types
            for required_type in cards_spec.get("must_include_types", []):
                if required_type not in actual_types:
                    errors.append(
                        f"Required card type '{required_type}' not found. "
                        f"Got: {actual_types}"
                    )

            # Check must_include (detailed card requirements)
            for required_card in cards_spec.get("must_include", []):
                card_type = required_card.get("type")
                matching_cards = [c for c in actual_cards if c.get("type") == card_type]

                if not matching_cards:
                    errors.append(
                        f"Required card type '{card_type}' not found. "
                        f"Got types: {actual_types}. "
                        f"This may be the persona card bug - check if LLM is "
                        f"outputting 'info' instead of 'personas'."
                    )
                else:
                    # Validate body requirements
                    body_req = required_card.get("body", {})
                    for key, spec in body_req.items():
                        for card in matching_cards:
                            body = card.get("body", {})
                            if key not in body:
                                errors.append(
                                    f"Card '{card_type}' missing required body key '{key}'"
                                )
                            elif isinstance(spec, dict) and "min_count" in spec:
                                if len(body.get(key, [])) < spec["min_count"]:
                                    errors.append(
                                        f"Card '{card_type}' body.{key} has "
                                        f"{len(body.get(key, []))} items, "
                                        f"expected at least {spec['min_count']}"
                                    )

            # Check stepper_current_step_contains
            if "stepper_current_step_contains" in cards_spec:
                expected_text = cards_spec["stepper_current_step_contains"].lower()
                stepper_cards = [c for c in actual_cards if c.get("type") == "stepper"]
                if stepper_cards:
                    stepper = stepper_cards[0]
                    steps_list = stepper.get("body", {}).get("steps", [])
                    active_step = next(
                        (s for s in steps_list if s.get("status") == "active"), None
                    )
                    if active_step:
                        label = active_step.get("label", "").lower()
                        if expected_text not in label:
                            warnings.append(
                                f"Stepper active step '{label}' does not contain "
                                f"'{expected_text}'"
                            )
                    else:
                        warnings.append("No active step found in stepper")

        return StepResult(
            step_name=step.name,
            passed=len(errors) == 0,
            events=events,
            errors=errors,
            warnings=warnings,
        )

    async def run(self, flow_name: str, verbose: bool = True) -> list[StepResult]:
        """Run a flow and return results."""
        spec = self.load_flow(flow_name)
        results: list[StepResult] = []

        if verbose:
            print(f"\n{'='*60}")
            print(f"Running flow: {spec.name}")
            print(f"Description: {spec.description}")
            print(f"{'='*60}\n")

        # Create session
        project_id = spec.session.get("project_id", f"test-{flow_name}")
        self.session_id = await self.create_session(project_id)

        if verbose:
            print(f"Created session: {self.session_id}\n")

        # Execute steps
        for i, step in enumerate(spec.steps, 1):
            if verbose:
                print(f"Step {i}/{len(spec.steps)}: {step.name}")
                print(f"  Sending: \"{step.user_says}\"")

            try:
                events = await self.send_message(step.user_says)
                self.collected_events.extend(events)
                result = self.validate_step(step, events)
                results.append(result)

                if verbose:
                    if result.passed:
                        print(f"  \u2713 PASSED")
                    else:
                        print(f"  \u2717 FAILED")
                        for error in result.errors:
                            print(f"    Error: {error}")
                    for warning in result.warnings:
                        print(f"    Warning: {warning}")
                    print()

            except Exception as e:
                result = StepResult(
                    step_name=step.name,
                    passed=False,
                    events=[],
                    errors=[f"Exception: {e}"],
                )
                results.append(result)
                if verbose:
                    print(f"  \u2717 FAILED with exception: {e}\n")

        # Summary
        if verbose:
            passed = sum(1 for r in results if r.passed)
            print(f"{'='*60}")
            print(f"Results: {passed}/{len(results)} steps passed")

            if passed < len(results):
                print(f"\nCompliance Notes:")
                print(spec.compliance_notes)

            print(f"{'='*60}\n")

        return results

    async def cleanup(self) -> None:
        """Delete the test session."""
        if self.session_id:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                await client.delete(f"/api/v1/design-sessions/{self.session_id}")


async def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run LLM compliance flow tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python -m clara.testing.flow_runner personas_step
  uv run python -m clara.testing.flow_runner --list
  uv run python -m clara.testing.flow_runner personas_step --base-url http://localhost:8001
        """,
    )
    parser.add_argument("flow_name", nargs="?", help="Name of the flow to run")
    parser.add_argument("--list", action="store_true", help="List available flows")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the Design Assistant API",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")

    args = parser.parse_args()

    runner = FlowRunner(base_url=args.base_url)

    if args.list:
        flows = list(runner.flows_dir.glob("*.y*ml"))
        print("Available flows:")
        for flow in flows:
            print(f"  - {flow.stem}")
        return 0

    if not args.flow_name:
        parser.print_help()
        return 1

    try:
        results = await runner.run(args.flow_name, verbose=not args.quiet)
        await runner.cleanup()

        # Return non-zero if any step failed
        failed = sum(1 for r in results if not r.passed)
        return 1 if failed > 0 else 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except httpx.ConnectError:
        print(
            f"Error: Could not connect to {args.base_url}. "
            "Is the Design Assistant running?",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
