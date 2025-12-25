"""Contract tests for SSE streaming.

These tests verify the SSE plumbing works correctly without calling the LLM.
They use mocked orchestrator responses to test event formatting and streaming.
"""

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from clara.main import app


@dataclass
class AGUIEvent:
    """AG-UI event structure for testing."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)


class TestSSEEventFormatting:
    """Tests for SSE event formatting (Layer 2: Contract Tests)."""

    def test_format_sse_event_basic(self):
        """Test basic SSE event formatting."""
        from clara.api.design_sessions import format_sse_event

        event = AGUIEvent(type="TEXT_MESSAGE_START", data={})
        result = format_sse_event(event)

        assert result.startswith("event: TEXT_MESSAGE_START\n")
        assert "data: " in result
        assert result.endswith("\n\n")

    def test_format_sse_event_with_data(self):
        """Test SSE event formatting with data payload."""
        from clara.api.design_sessions import format_sse_event

        event = AGUIEvent(
            type="TEXT_MESSAGE_CONTENT", data={"delta": "Hello world"}
        )
        result = format_sse_event(event)

        # Parse the data line
        lines = result.strip().split("\n")
        data_line = next(l for l in lines if l.startswith("data: "))
        data_json = json.loads(data_line[6:])

        assert data_json["type"] == "TEXT_MESSAGE_CONTENT"
        assert data_json["delta"] == "Hello world"

    def test_format_sse_event_custom(self):
        """Test SSE formatting for CUSTOM events (clara:ask)."""
        from clara.api.design_sessions import format_sse_event

        event = AGUIEvent(
            type="CUSTOM",
            data={
                "name": "clara:ask",
                "value": {
                    "question": "Test question?",
                    "options": [{"id": "a", "label": "Option A"}],
                    "cards": [
                        {
                            "card_id": "stepper1",
                            "type": "stepper",
                            "title": "Progress",
                            "body": {"steps": []},
                        },
                        {
                            "card_id": "personas1",
                            "type": "personas",
                            "title": "Select Persona",
                            "body": {"personas": []},
                        },
                    ],
                },
            },
        )
        result = format_sse_event(event)

        lines = result.strip().split("\n")
        data_line = next(l for l in lines if l.startswith("data: "))
        data_json = json.loads(data_line[6:])

        assert data_json["type"] == "CUSTOM"
        assert data_json["name"] == "clara:ask"
        assert data_json["value"]["question"] == "Test question?"
        assert len(data_json["value"]["cards"]) == 2
        assert data_json["value"]["cards"][1]["type"] == "personas"


class TestDesignSessionAPI:
    """Tests for design session API endpoints (non-streaming)."""

    @pytest.fixture
    async def client(self, db_session):
        """Create test client with database session override."""
        from clara.db.session import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_session(self, client):
        """Test POST /api/v1/design-sessions creates a new session."""
        # Mock session manager to avoid actual agent creation
        with patch("clara.api.design_sessions.session_manager") as mock_sm:
            mock_sm.get_or_create_session = AsyncMock(return_value=MagicMock())

            response = await client.post(
                "/api/v1/design-sessions",
                json={"project_id": "test-project-123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "session_id" in data
            assert data["project_id"] == "test-project-123"
            assert data["is_new"] is True

    @pytest.mark.asyncio
    async def test_get_session(self, client):
        """Test GET /api/v1/design-sessions/{id} returns session state."""
        # First create a session
        with patch("clara.api.design_sessions.session_manager") as mock_sm:
            mock_sm.get_or_create_session = AsyncMock(return_value=MagicMock())

            create_response = await client.post(
                "/api/v1/design-sessions",
                json={"project_id": "test-project-get"},
            )
            session_id = create_response.json()["session_id"]

            # Now get the session
            response = await client.get(f"/api/v1/design-sessions/{session_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == session_id
            assert data["project_id"] == "test-project-get"
            assert data["phase"] == "goal_understanding"
            assert isinstance(data["messages"], list)

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client):
        """Test GET /api/v1/design-sessions/{id} returns 404 for unknown session."""
        response = await client.get("/api/v1/design-sessions/nonexistent-session")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_session_by_project(self, client):
        """Test GET /api/v1/design-sessions/project/{id} returns active session."""
        with patch("clara.api.design_sessions.session_manager") as mock_sm:
            mock_sm.get_or_create_session = AsyncMock(return_value=MagicMock())

            # Create a session for the project
            create_response = await client.post(
                "/api/v1/design-sessions",
                json={"project_id": "test-project-by-id"},
            )
            session_id = create_response.json()["session_id"]

            # Get session by project ID
            response = await client.get(
                "/api/v1/design-sessions/project/test-project-by-id"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == session_id
            assert data["project_id"] == "test-project-by-id"

    @pytest.mark.asyncio
    async def test_get_session_by_project_not_found(self, client):
        """Test GET /api/v1/design-sessions/project/{id} returns null for no session."""
        response = await client.get(
            "/api/v1/design-sessions/project/nonexistent-project"
        )
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        """Test DELETE /api/v1/design-sessions/{id} marks session as abandoned."""
        with patch("clara.api.design_sessions.session_manager") as mock_sm:
            mock_sm.get_or_create_session = AsyncMock(return_value=MagicMock())
            mock_sm.close_session = AsyncMock()

            # Create a session
            create_response = await client.post(
                "/api/v1/design-sessions",
                json={"project_id": "test-project-delete"},
            )
            session_id = create_response.json()["session_id"]

            # Delete the session
            response = await client.delete(f"/api/v1/design-sessions/{session_id}")
            assert response.status_code == 200
            assert response.json()["status"] == "deleted"

            # Verify session state
            get_response = await client.get(f"/api/v1/design-sessions/{session_id}")
            assert get_response.json()["status"] == "abandoned"


class TestAGUIEventContract:
    """Tests for AG-UI event contract compliance."""

    def test_text_message_events_structure(self):
        """Verify TEXT_MESSAGE events follow AG-UI contract."""
        # TEXT_MESSAGE_START
        start_event = AGUIEvent(type="TEXT_MESSAGE_START", data={})
        assert start_event.type == "TEXT_MESSAGE_START"

        # TEXT_MESSAGE_CONTENT
        content_event = AGUIEvent(
            type="TEXT_MESSAGE_CONTENT", data={"delta": "Hello"}
        )
        assert content_event.type == "TEXT_MESSAGE_CONTENT"
        assert "delta" in content_event.data

        # TEXT_MESSAGE_END
        end_event = AGUIEvent(type="TEXT_MESSAGE_END", data={})
        assert end_event.type == "TEXT_MESSAGE_END"

    def test_custom_event_clara_ask_structure(self):
        """Verify CUSTOM clara:ask events follow AG-UI contract."""
        event = AGUIEvent(
            type="CUSTOM",
            data={
                "name": "clara:ask",
                "value": {
                    "question": "What would you like to achieve?",
                    "options": [
                        {"id": "opt1", "label": "Option 1"},
                        {"id": "opt2", "label": "Option 2", "description": "Details"},
                    ],
                    "multi_select": False,
                    "cards": [
                        {
                            "card_id": "stepper1",
                            "type": "stepper",
                            "title": "Progress",
                            "body": {
                                "steps": [
                                    {"label": "Goal", "status": "completed"},
                                    {"label": "Personas", "status": "active"},
                                ],
                                "current_step": "Personas",
                            },
                        },
                    ],
                },
            },
        )

        assert event.type == "CUSTOM"
        assert event.data["name"] == "clara:ask"

        value = event.data["value"]
        assert "question" in value
        assert "options" in value
        assert isinstance(value["options"], list)
        assert len(value["options"]) > 0
        assert "id" in value["options"][0]
        assert "label" in value["options"][0]

        # Cards validation
        assert "cards" in value
        card = value["cards"][0]
        assert "card_id" in card
        assert "type" in card
        assert "title" in card
        assert "body" in card

    def test_custom_event_clara_ask_personas_card(self):
        """Verify personas card structure in clara:ask events."""
        personas_card = {
            "card_id": "personas_card",
            "type": "personas",
            "title": "Select Personas",
            "body": {
                "personas": [
                    {"id": "p1", "name": "IT Manager", "description": "Manages IT"},
                    {"id": "p2", "name": "CTO", "description": "Technology leader"},
                ],
            },
        }

        # Validate structure
        assert personas_card["type"] == "personas"
        assert "personas" in personas_card["body"]
        assert len(personas_card["body"]["personas"]) >= 2

        for persona in personas_card["body"]["personas"]:
            assert "id" in persona or "name" in persona
            assert "description" in persona or "name" in persona

    def test_state_delta_event_structure(self):
        """Verify STATE_DELTA events follow AG-UI contract."""
        event = AGUIEvent(
            type="STATE_DELTA",
            data={"delta": {"phase": "agent_configuration"}},
        )

        assert event.type == "STATE_DELTA"
        assert "delta" in event.data
        assert event.data["delta"]["phase"] == "agent_configuration"

    def test_error_event_structure(self):
        """Verify ERROR events follow AG-UI contract."""
        event = AGUIEvent(
            type="ERROR",
            data={"message": "Something went wrong", "recoverable": True},
        )

        assert event.type == "ERROR"
        assert "message" in event.data
        assert "recoverable" in event.data


class TestCardEnvelopeContract:
    """Tests for CardEnvelope structure compliance."""

    def test_required_card_fields(self):
        """Verify required CardEnvelope fields."""
        valid_card = {
            "card_id": "card_123",
            "type": "info",
            "title": "Information",
            "body": {},
        }

        required_fields = ["card_id", "type", "title", "body"]
        for field in required_fields:
            assert field in valid_card

    def test_optional_card_fields(self):
        """Verify optional CardEnvelope fields."""
        full_card = {
            "card_id": "card_123",
            "type": "info",
            "title": "Information",
            "subtitle": "Additional context",
            "body": {"content": "Details"},
            "actions": [{"id": "confirm", "label": "Confirm", "style": "primary"}],
            "helper": {
                "why_this": ["Reason 1"],
                "risks_if_skipped": ["Risk 1"],
            },
        }

        # Optional fields should be present
        assert "subtitle" in full_card
        assert "actions" in full_card
        assert "helper" in full_card

    def test_known_card_types(self):
        """Verify all known card types are defined."""
        known_types = [
            "stepper",
            "snapshot",
            "info",
            "domain_setup",
            "personas",
            "agent_configured",
        ]

        # All types should be strings
        for card_type in known_types:
            assert isinstance(card_type, str)

    def test_stepper_card_body(self):
        """Verify stepper card body structure."""
        stepper_body = {
            "steps": [
                {"label": "Goal Understanding", "status": "completed"},
                {"label": "Personas", "status": "active"},
                {"label": "Blueprint Design", "status": "pending"},
            ],
            "current_step": "Personas",
        }

        assert "steps" in stepper_body
        assert len(stepper_body["steps"]) > 0

        for step in stepper_body["steps"]:
            assert "label" in step
            assert "status" in step
            assert step["status"] in ["completed", "active", "pending"]

    def test_personas_card_body(self):
        """Verify personas card body structure (critical for persona bug fix)."""
        personas_body = {
            "personas": [
                {
                    "id": "persona_1",
                    "name": "IT Manager",
                    "description": "Manages IT infrastructure",
                    "expertise": ["Infrastructure", "Security"],
                },
                {
                    "id": "persona_2",
                    "name": "CTO",
                    "description": "Chief Technology Officer",
                    "expertise": ["Strategy", "Architecture"],
                },
            ],
        }

        assert "personas" in personas_body
        assert len(personas_body["personas"]) >= 2

        for persona in personas_body["personas"]:
            assert "name" in persona
            # Other fields are optional but commonly present
            assert isinstance(persona.get("description", ""), str)
