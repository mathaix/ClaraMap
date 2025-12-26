"""Unit tests for Clara MCP tools."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from clara.agents.tools import (
    get_session_state,
    clear_session_state,
    cleanup_stale_sessions,
    hydrate_template,
    load_template,
    SESSION_TTL_MINUTES,
    _session_state,
)
from clara.security import InputSanitizer


class TestSessionState:
    """Tests for session state management."""

    def setup_method(self):
        """Clear session state before each test."""
        _session_state.clear()

    def test_get_session_state_creates_new(self):
        """Test that get_session_state creates new state for unknown session."""
        state = get_session_state("test-session-123")
        assert state["project"] is None
        assert state["entities"] == []
        assert state["agents"] == []
        assert state["phase"] == "goal_understanding"
        assert "_created_at" in state
        assert "_last_activity" in state

    def test_get_session_state_returns_existing(self):
        """Test that get_session_state returns existing state."""
        # Create initial state
        state1 = get_session_state("test-session-456")
        state1["project"] = {"name": "Test Project"}

        # Get same session
        state2 = get_session_state("test-session-456")
        assert state2["project"]["name"] == "Test Project"

    def test_get_session_state_updates_last_activity(self):
        """Test that getting state updates last_activity timestamp."""
        state = get_session_state("test-session-789")
        first_activity = state["_last_activity"]

        # Small delay and get again
        import time
        time.sleep(0.01)
        state = get_session_state("test-session-789")

        assert state["_last_activity"] >= first_activity

    def test_clear_session_state(self):
        """Test that clear_session_state removes session."""
        get_session_state("test-session-clear")
        assert "test-session-clear" in _session_state

        clear_session_state("test-session-clear")
        assert "test-session-clear" not in _session_state

    def test_clear_nonexistent_session(self):
        """Test that clearing non-existent session doesn't error."""
        clear_session_state("nonexistent-session")  # Should not raise

    def test_cleanup_stale_sessions(self):
        """Test TTL-based session cleanup."""
        # Create a stale session
        stale_state = get_session_state("stale-session")
        stale_state["_last_activity"] = datetime.now() - timedelta(
            minutes=SESSION_TTL_MINUTES + 5
        )

        # Create a fresh session
        get_session_state("fresh-session")

        # Run cleanup
        cleaned = cleanup_stale_sessions()

        assert cleaned == 1
        assert "stale-session" not in _session_state
        assert "fresh-session" in _session_state


class TestHydrateTemplate:
    """Tests for template hydration."""

    def test_hydrate_simple_placeholder(self):
        """Test basic placeholder replacement."""
        template = "Hello, {{name}}!"
        result = hydrate_template(template, {"name": "World"})
        assert result == "Hello, World!"

    def test_hydrate_multiple_placeholders(self):
        """Test multiple placeholder replacement."""
        template = "{{greeting}}, {{name}}! Welcome to {{place}}."
        context = {
            "greeting": "Hello",
            "name": "User",
            "place": "Clara",
        }
        result = hydrate_template(template, context)
        assert result == "Hello, User! Welcome to Clara."

    def test_hydrate_missing_placeholder(self):
        """Test that missing placeholders are replaced with empty string."""
        template = "Hello, {{name}}! Your role: {{role}}"
        result = hydrate_template(template, {"name": "Test"})
        assert result == "Hello, Test! Your role: "

    def test_hydrate_list_value(self):
        """Test list values are joined with commas."""
        template = "Topics: {{topics}}"
        result = hydrate_template(template, {"topics": ["A", "B", "C"]})
        assert result == "Topics: A, B, C"

    def test_hydrate_none_value(self):
        """Test that None values are replaced with empty string."""
        template = "Value: {{value}}"
        result = hydrate_template(template, {"value": None})
        assert result == "Value: "

    def test_hydrate_sanitizes_injection_attempt(self):
        """Test that template injection attempts are sanitized."""
        template = "Goal: {{goal}}"
        # Try to inject another template marker
        result = hydrate_template(template, {"goal": "Test {{malicious}}"})
        # The {{ should be escaped to prevent injection
        assert "{{" not in result or "{ {" in result


class TestInputSanitizer:
    """Tests for InputSanitizer used in tools."""

    def test_sanitize_name_truncates(self):
        """Test name truncation."""
        long_name = "a" * 500
        result = InputSanitizer.sanitize_name(long_name)
        assert len(result) == InputSanitizer.MAX_NAME_LENGTH

    def test_sanitize_name_strips(self):
        """Test name stripping."""
        result = InputSanitizer.sanitize_name("  Test Name  ")
        assert result == "Test Name"

    def test_sanitize_name_handles_none(self):
        """Test None handling."""
        result = InputSanitizer.sanitize_name(None)
        assert result == ""

    def test_sanitize_array_limits_items(self):
        """Test array item limiting."""
        long_array = [f"item{i}" for i in range(100)]
        result = InputSanitizer.sanitize_array(long_array)
        assert len(result) == InputSanitizer.MAX_ARRAY_ITEMS

    def test_sanitize_array_truncates_items(self):
        """Test individual item truncation."""
        items = ["a" * 1000]
        result = InputSanitizer.sanitize_array(items, max_item_length=50)
        assert len(result[0]) == 50

    def test_sanitize_array_handles_none(self):
        """Test None array handling."""
        result = InputSanitizer.sanitize_array(None)
        assert result == []

    def test_sanitize_template_value_escapes_markers(self):
        """Test template marker escaping."""
        result = InputSanitizer.sanitize_template_value("test {{injection}}")
        assert "{{" not in result
        assert "{ {" in result

    def test_sanitize_description_truncates(self):
        """Test description truncation."""
        long_desc = "a" * 5000
        result = InputSanitizer.sanitize_description(long_desc)
        assert len(result) == InputSanitizer.MAX_DESCRIPTION_LENGTH


class TestLoadTemplate:
    """Tests for template loading."""

    def test_load_template_goal_understanding(self):
        """Test loading goal understanding template."""
        template = load_template("goal_understanding")
        assert len(template) > 0
        assert isinstance(template, str)

    def test_load_template_agent_configuration(self):
        """Test loading agent configuration template."""
        template = load_template("agent_configuration")
        assert len(template) > 0

    def test_load_template_blueprint_design(self):
        """Test loading blueprint design template."""
        template = load_template("blueprint_design")
        assert len(template) > 0

    def test_load_template_invalid_phase(self):
        """Test that invalid phase raises ValueError."""
        with pytest.raises(ValueError):
            load_template("invalid_phase")


class TestSanitizeAskOptions:
    """Tests for sanitize_ask_options function.

    This verifies the AG-UI contract for option payloads.
    """

    def test_sanitize_valid_options(self):
        """Test that valid options are preserved."""
        from clara.agents.tools import sanitize_ask_options

        options = [
            {"id": "opt1", "label": "Option 1", "description": "First option"},
            {"id": "opt2", "label": "Option 2"},
        ]
        result = sanitize_ask_options(options)

        assert len(result) == 2
        assert result[0]["id"] == "opt1"
        assert result[0]["label"] == "Option 1"
        assert result[0]["description"] == "First option"
        assert result[1]["id"] == "opt2"
        assert result[1]["label"] == "Option 2"
        assert "description" not in result[1]

    def test_sanitize_options_generates_id_from_label(self):
        """Test that missing id is generated from label."""
        from clara.agents.tools import sanitize_ask_options

        options = [{"label": "My Option"}]
        result = sanitize_ask_options(options)

        assert result[0]["id"] == "My Option"
        assert result[0]["label"] == "My Option"

    def test_sanitize_options_skips_empty_labels(self):
        """Test that options without labels are skipped."""
        from clara.agents.tools import sanitize_ask_options

        options = [
            {"id": "opt1", "label": "Valid"},
            {"id": "opt2", "label": ""},
            {"id": "opt3"},
        ]
        result = sanitize_ask_options(options)

        assert len(result) == 1
        assert result[0]["label"] == "Valid"

    def test_sanitize_options_other_requires_input(self):
        """Test that 'Other' option automatically sets requires_input."""
        from clara.agents.tools import sanitize_ask_options

        options = [
            {"id": "other", "label": "Other option"},
        ]
        result = sanitize_ask_options(options)

        assert result[0]["requires_input"] is True

    def test_sanitize_options_preserves_requires_input(self):
        """Test that explicit requires_input is preserved."""
        from clara.agents.tools import sanitize_ask_options

        options = [
            {"id": "custom", "label": "Custom", "requires_input": True},
        ]
        result = sanitize_ask_options(options)

        assert result[0]["requires_input"] is True

    def test_sanitize_options_handles_non_list(self):
        """Test that non-list input returns empty list."""
        from clara.agents.tools import sanitize_ask_options

        assert sanitize_ask_options(None) == []
        assert sanitize_ask_options("invalid") == []
        assert sanitize_ask_options({"not": "list"}) == []

    def test_sanitize_options_handles_non_dict_items(self):
        """Test that non-dict items are skipped."""
        from clara.agents.tools import sanitize_ask_options

        options = [{"label": "Valid"}, "invalid", 123, None]
        result = sanitize_ask_options(options)

        assert len(result) == 1
        assert result[0]["label"] == "Valid"


class TestSanitizeCards:
    """Tests for sanitize_cards function.

    This verifies the AG-UI contract for card payloads (CardEnvelope structure).
    """

    def test_sanitize_valid_card(self):
        """Test that valid card structure is preserved."""
        from clara.agents.tools import sanitize_cards

        cards = [{
            "card_id": "card1",
            "type": "stepper",
            "title": "Progress",
            "body": {"current_step": 1, "total_steps": 5},
        }]
        result = sanitize_cards(cards)

        assert len(result) == 1
        assert result[0]["card_id"] == "card1"
        assert result[0]["type"] == "stepper"
        assert result[0]["title"] == "Progress"
        assert result[0]["body"]["current_step"] == 1

    def test_sanitize_card_generates_id_if_missing(self):
        """Test that missing card_id is auto-generated."""
        from clara.agents.tools import sanitize_cards

        cards = [{"type": "info", "title": "Info Card", "body": {}}]
        result = sanitize_cards(cards)

        assert result[0]["card_id"] == "card_1"

    def test_sanitize_card_defaults_type_to_card(self):
        """Test that missing type defaults to 'card'."""
        from clara.agents.tools import sanitize_cards

        cards = [{"card_id": "c1", "title": "Title", "body": {}}]
        result = sanitize_cards(cards)

        assert result[0]["type"] == "card"

    def test_sanitize_card_defaults_title_to_card(self):
        """Test that missing title defaults to 'Card'."""
        from clara.agents.tools import sanitize_cards

        cards = [{"card_id": "c1", "type": "info", "body": {}}]
        result = sanitize_cards(cards)

        assert result[0]["title"] == "Card"

    def test_sanitize_card_with_subtitle(self):
        """Test that subtitle is preserved when provided."""
        from clara.agents.tools import sanitize_cards

        cards = [{
            "card_id": "c1",
            "type": "snapshot",
            "title": "Project",
            "subtitle": "Current State",
            "body": {},
        }]
        result = sanitize_cards(cards)

        assert result[0]["subtitle"] == "Current State"

    def test_sanitize_card_with_actions(self):
        """Test that actions are properly sanitized."""
        from clara.agents.tools import sanitize_cards

        cards = [{
            "card_id": "c1",
            "type": "personas",
            "title": "Personas",
            "body": {},
            "actions": [
                {"id": "select", "label": "Select", "style": "primary"},
                {"id": "skip", "label": "Skip"},
            ],
        }]
        result = sanitize_cards(cards)

        assert len(result[0]["actions"]) == 2
        assert result[0]["actions"][0]["id"] == "select"
        assert result[0]["actions"][0]["label"] == "Select"
        assert result[0]["actions"][0]["style"] == "primary"
        assert result[0]["actions"][1]["id"] == "skip"
        assert "style" not in result[0]["actions"][1]

    def test_sanitize_card_with_helper(self):
        """Test that helper section is properly sanitized."""
        from clara.agents.tools import sanitize_cards

        cards = [{
            "card_id": "c1",
            "type": "domain_setup",
            "title": "Domain",
            "body": {},
            "helper": {
                "why_this": ["Reason 1", "Reason 2"],
                "risks_if_skipped": ["Risk 1"],
            },
        }]
        result = sanitize_cards(cards)

        assert "helper" in result[0]
        assert result[0]["helper"]["why_this"] == ["Reason 1", "Reason 2"]
        assert result[0]["helper"]["risks_if_skipped"] == ["Risk 1"]

    def test_sanitize_card_personas_body(self):
        """Test personas card body structure (critical for AG-UI contract)."""
        from clara.agents.tools import sanitize_cards

        cards = [{
            "card_id": "personas_card",
            "type": "personas",
            "title": "Select Personas",
            "body": {
                "personas": [
                    {"id": "p1", "name": "IT Manager", "description": "Manages IT"},
                    {"id": "p2", "name": "CTO", "description": "Tech leader"},
                ],
            },
        }]
        result = sanitize_cards(cards)

        assert result[0]["type"] == "personas"
        assert len(result[0]["body"]["personas"]) == 2
        assert result[0]["body"]["personas"][0]["name"] == "IT Manager"

    def test_sanitize_card_stepper_body(self):
        """Test stepper card body structure."""
        from clara.agents.tools import sanitize_cards

        cards = [{
            "card_id": "stepper1",
            "type": "stepper",
            "title": "Design Progress",
            "body": {
                "steps": [
                    {"label": "Goal", "status": "completed"},
                    {"label": "Personas", "status": "active"},
                    {"label": "Blueprint", "status": "pending"},
                ],
                "current_step": "Personas",
            },
        }]
        result = sanitize_cards(cards)

        assert result[0]["type"] == "stepper"
        assert len(result[0]["body"]["steps"]) == 3
        assert result[0]["body"]["current_step"] == "Personas"

    def test_sanitize_cards_handles_non_list(self):
        """Test that non-list input returns empty list."""
        from clara.agents.tools import sanitize_cards

        assert sanitize_cards(None) == []
        assert sanitize_cards("invalid") == []
        assert sanitize_cards({"not": "list"}) == []

    def test_sanitize_cards_handles_non_dict_items(self):
        """Test that non-dict items are skipped."""
        from clara.agents.tools import sanitize_cards

        cards = [{"card_id": "c1", "type": "info", "title": "Valid", "body": {}}, "invalid", None]
        result = sanitize_cards(cards)

        assert len(result) == 1
        assert result[0]["title"] == "Valid"

    def test_sanitize_cards_limits_nested_depth(self):
        """Test that deeply nested body is truncated."""
        from clara.agents.tools import sanitize_cards

        # Create deeply nested structure
        deep_body = {"level1": {"level2": {"level3": {"level4": {"level5": "deep"}}}}}
        cards = [{"card_id": "c1", "type": "info", "title": "Deep", "body": deep_body}]
        result = sanitize_cards(cards)

        # Should handle without crashing (depth limit is 4)
        assert "body" in result[0]


class TestEnsureOtherOption:
    """Tests for ensure_other_option function."""

    def test_adds_other_when_missing(self):
        """Test that 'Other' option is added when missing."""
        from clara.agents.tools import ensure_other_option

        options = [{"id": "opt1", "label": "Option 1"}]
        result = ensure_other_option(options)

        assert len(result) == 2
        assert result[1]["id"] == "other"
        assert result[1]["label"] == "Other"
        assert result[1]["requires_input"] is True

    def test_preserves_existing_other(self):
        """Test that existing 'Other' option is preserved."""
        from clara.agents.tools import ensure_other_option

        options = [
            {"id": "opt1", "label": "Option 1"},
            {"id": "custom_other", "label": "Other choice"},
        ]
        result = ensure_other_option(options)

        # Should not add another Other
        assert len(result) == 2
        # Should mark existing as requires_input
        assert result[1]["requires_input"] is True

    def test_avoids_duplicate_other_id(self):
        """Test that duplicate 'other' id is avoided."""
        from clara.agents.tools import ensure_other_option

        options = [
            {"id": "other", "label": "Something"},  # Uses 'other' id but not "Other" label
        ]
        result = ensure_other_option(options)

        # Should add new Other with different id
        assert len(result) == 2
        assert result[1]["id"] == "other_2"
        assert result[1]["label"] == "Other"


class TestPhaseValidation:
    """Tests for phase tool validation."""

    def test_valid_phases(self):
        """Test that all valid phases are accepted."""
        from clara.agents.tools import PhaseSchema

        valid_phases = PhaseSchema["properties"]["phase"]["enum"]

        assert "goal_understanding" in valid_phases
        assert "agent_configuration" in valid_phases
        assert "blueprint_design" in valid_phases
        assert "complete" in valid_phases

    def test_phase_schema_requires_phase(self):
        """Test that phase is required."""
        from clara.agents.tools import PhaseSchema

        assert "phase" in PhaseSchema["required"]


class TestCardSchemas:
    """Tests for card-related schemas (AG-UI contract)."""

    def test_ask_schema_supports_cards(self):
        """Test that AskSchema includes cards field."""
        from clara.agents.tools import AskSchema

        assert "cards" in AskSchema["properties"]
        cards_schema = AskSchema["properties"]["cards"]
        assert cards_schema["type"] == "array"

    def test_ask_schema_card_requires_essential_fields(self):
        """Test that card items require essential fields."""
        from clara.agents.tools import AskSchema

        card_schema = AskSchema["properties"]["cards"]["items"]
        required = card_schema["required"]

        assert "card_id" in required
        assert "type" in required
        assert "title" in required
        assert "body" in required

    def test_ask_schema_card_supports_actions(self):
        """Test that card items support actions."""
        from clara.agents.tools import AskSchema

        card_schema = AskSchema["properties"]["cards"]["items"]

        assert "actions" in card_schema["properties"]
        actions_schema = card_schema["properties"]["actions"]
        assert actions_schema["type"] == "array"

    def test_ask_schema_card_supports_helper(self):
        """Test that card items support helper section."""
        from clara.agents.tools import AskSchema

        card_schema = AskSchema["properties"]["cards"]["items"]

        assert "helper" in card_schema["properties"]
        helper_schema = card_schema["properties"]["helper"]
        assert "why_this" in helper_schema["properties"]
        assert "risks_if_skipped" in helper_schema["properties"]
