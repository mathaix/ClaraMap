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
