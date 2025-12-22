"""Unit tests for Simulation Agent."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from clara.agents.simulation_agent import (
    SimulationSession,
    SimulationSessionManager,
    PersonaConfig,
    AGUIEvent,
    SESSION_TTL_MINUTES,
    MAX_MESSAGE_HISTORY,
    is_safe_url,
)


class TestPersonaConfig:
    """Tests for PersonaConfig dataclass."""

    def test_persona_config_defaults(self):
        """Test PersonaConfig default values."""
        persona = PersonaConfig(role="Product Manager")
        assert persona.role == "Product Manager"
        assert persona.company_url is None
        assert persona.company_context is None
        assert persona.name is None
        assert persona.experience_years is None
        assert persona.communication_style == "professional"

    def test_persona_config_with_all_fields(self):
        """Test PersonaConfig with all fields set."""
        persona = PersonaConfig(
            role="Senior Engineer",
            company_url="https://example.com",
            company_context="Tech company",
            name="Jane Doe",
            experience_years=10,
            communication_style="casual",
        )
        assert persona.role == "Senior Engineer"
        assert persona.company_url == "https://example.com"
        assert persona.company_context == "Tech company"
        assert persona.name == "Jane Doe"
        assert persona.experience_years == 10
        assert persona.communication_style == "casual"


class TestSimulationSession:
    """Tests for SimulationSession dataclass."""

    def test_session_initialization(self):
        """Test SimulationSession initialization."""
        session = SimulationSession(
            session_id="test-session-123",
            interviewer_prompt="You are an interviewer.",
        )
        assert session.session_id == "test-session-123"
        assert session.interviewer_prompt == "You are an interviewer."
        assert session.persona is None
        assert session.messages == []
        assert session.created_at is not None
        assert session.last_activity is not None

    def test_session_with_persona(self):
        """Test SimulationSession with persona."""
        persona = PersonaConfig(role="Designer", name="Alex")
        session = SimulationSession(
            session_id="test-session-456",
            interviewer_prompt="You are an interviewer.",
            persona=persona,
        )
        assert session.persona is not None
        assert session.persona.role == "Designer"
        assert session.persona.name == "Alex"

    def test_build_simulated_user_prompt_basic(self):
        """Test building simulated user prompt with basic persona."""
        persona = PersonaConfig(role="Product Manager")
        session = SimulationSession(
            session_id="test",
            interviewer_prompt="test",
            persona=persona,
        )
        prompt = session._build_simulated_user_prompt()
        assert "Product Manager" in prompt
        assert "interviewee" in prompt.lower()
        assert "professional" in prompt

    def test_build_simulated_user_prompt_with_details(self):
        """Test building simulated user prompt with full persona details."""
        persona = PersonaConfig(
            role="Senior Engineer",
            name="John Smith",
            experience_years=15,
            company_context="We build cloud infrastructure solutions.",
            communication_style="detailed",
        )
        session = SimulationSession(
            session_id="test",
            interviewer_prompt="test",
            persona=persona,
        )
        prompt = session._build_simulated_user_prompt()
        assert "Senior Engineer" in prompt
        assert "John Smith" in prompt
        assert "15 years" in prompt
        assert "cloud infrastructure" in prompt
        assert "detailed" in prompt

    def test_build_simulated_user_prompt_no_persona(self):
        """Test building simulated user prompt without persona returns empty."""
        session = SimulationSession(
            session_id="test",
            interviewer_prompt="test",
            persona=None,
        )
        prompt = session._build_simulated_user_prompt()
        assert prompt == ""

    def test_reset_clears_messages(self):
        """Test that reset clears message history."""
        session = SimulationSession(
            session_id="test",
            interviewer_prompt="test",
        )
        session.messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        session._introduction_sent = True

        session.reset()

        assert session.messages == []
        assert session._introduction_sent is False


class TestAGUIEvent:
    """Tests for AGUIEvent dataclass."""

    def test_agui_event_creation(self):
        """Test AGUIEvent creation."""
        event = AGUIEvent(type="TEXT_MESSAGE_CONTENT", data={"delta": "Hello"})
        assert event.type == "TEXT_MESSAGE_CONTENT"
        assert event.data == {"delta": "Hello"}

    def test_agui_event_default_data(self):
        """Test AGUIEvent with default empty data."""
        event = AGUIEvent(type="TEXT_MESSAGE_END")
        assert event.type == "TEXT_MESSAGE_END"
        assert event.data == {}


class TestSimulationSessionManager:
    """Tests for SimulationSessionManager."""

    @pytest.fixture
    def manager(self):
        """Create a fresh session manager for each test."""
        return SimulationSessionManager()

    @pytest.mark.asyncio
    async def test_create_session(self, manager):
        """Test creating a simulation session."""
        with patch('clara.agents.simulation_agent.ClaudeSDKClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            session = await manager.create_session(
                session_id="test-123",
                interviewer_prompt="You are an interviewer.",
            )

            assert session.session_id == "test-123"
            assert session.interviewer_prompt == "You are an interviewer."
            assert "test-123" in manager._sessions

    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        """Test getting an existing session."""
        with patch('clara.agents.simulation_agent.ClaudeSDKClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            await manager.create_session(
                session_id="test-456",
                interviewer_prompt="test prompt",
            )

            session = await manager.get_session("test-456")
            assert session is not None
            assert session.session_id == "test-456"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, manager):
        """Test getting a non-existent session returns None."""
        session = await manager.get_session("nonexistent")
        assert session is None

    @pytest.mark.asyncio
    async def test_close_session(self, manager):
        """Test closing a session."""
        with patch('clara.agents.simulation_agent.ClaudeSDKClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            await manager.create_session(
                session_id="test-close",
                interviewer_prompt="test prompt",
            )

            await manager.close_session("test-close")

            assert "test-close" not in manager._sessions

    @pytest.mark.asyncio
    async def test_cleanup_stale_sessions(self, manager):
        """Test cleanup of stale sessions."""
        with patch('clara.agents.simulation_agent.ClaudeSDKClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            # Create a session
            session = await manager.create_session(
                session_id="stale-session",
                interviewer_prompt="test",
            )

            # Make the session stale by setting last_activity in the past
            session.last_activity = datetime.now() - timedelta(minutes=SESSION_TTL_MINUTES + 5)

            # Create a fresh session
            fresh_session = await manager.create_session(
                session_id="fresh-session",
                interviewer_prompt="test",
            )

            # Run cleanup
            cleaned = await manager.cleanup_stale_sessions()

            assert cleaned == 1
            assert "stale-session" not in manager._sessions
            assert "fresh-session" in manager._sessions

    @pytest.mark.asyncio
    async def test_update_prompt(self, manager):
        """Test updating a session's prompt."""
        with patch('clara.agents.simulation_agent.ClaudeSDKClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            await manager.create_session(
                session_id="test-update",
                interviewer_prompt="original prompt",
            )

            await manager.update_prompt("test-update", "new prompt")

            session = await manager.get_session("test-update")
            assert session.interviewer_prompt == "new prompt"
            assert session.messages == []  # Should be reset


class TestMessageHistoryLimit:
    """Tests for message history limiting."""

    def test_message_history_limit_constant(self):
        """Test that MAX_MESSAGE_HISTORY is set."""
        assert MAX_MESSAGE_HISTORY == 20

    def test_session_ttl_constant(self):
        """Test that SESSION_TTL_MINUTES is set."""
        assert SESSION_TTL_MINUTES == 60


class TestSSRFProtection:
    """Tests for SSRF protection in URL validation."""

    def test_allows_valid_https_url(self):
        """Test that valid HTTPS URLs are allowed."""
        assert is_safe_url("https://example.com") is True
        assert is_safe_url("https://www.google.com/search?q=test") is True

    def test_allows_valid_http_url(self):
        """Test that valid HTTP URLs are allowed."""
        assert is_safe_url("http://example.com") is True

    def test_blocks_localhost(self):
        """Test that localhost URLs are blocked."""
        assert is_safe_url("http://localhost") is False
        assert is_safe_url("http://localhost:8080") is False
        assert is_safe_url("https://localhost/path") is False

    def test_blocks_loopback_ip(self):
        """Test that 127.0.0.1 is blocked."""
        assert is_safe_url("http://127.0.0.1") is False
        assert is_safe_url("http://127.0.0.1:3000") is False
        assert is_safe_url("https://127.0.0.1/api") is False

    def test_blocks_ipv6_loopback(self):
        """Test that IPv6 loopback is blocked."""
        assert is_safe_url("http://[::1]") is False

    def test_blocks_zero_ip(self):
        """Test that 0.0.0.0 is blocked."""
        assert is_safe_url("http://0.0.0.0") is False
        assert is_safe_url("http://0.0.0.0:5000") is False

    def test_blocks_private_ip_ranges(self):
        """Test that private IP ranges are blocked."""
        # 10.x.x.x
        assert is_safe_url("http://10.0.0.1") is False
        assert is_safe_url("http://10.255.255.255") is False
        # 172.16.x.x - 172.31.x.x
        assert is_safe_url("http://172.16.0.1") is False
        assert is_safe_url("http://172.31.255.255") is False
        # 192.168.x.x
        assert is_safe_url("http://192.168.1.1") is False
        assert is_safe_url("http://192.168.0.100") is False

    def test_blocks_cloud_metadata_endpoints(self):
        """Test that cloud metadata endpoints are blocked."""
        assert is_safe_url("http://169.254.169.254") is False
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_blocks_internal_hostnames(self):
        """Test that .local and .internal hostnames are blocked."""
        assert is_safe_url("http://myservice.local") is False
        assert is_safe_url("http://database.internal") is False

    def test_blocks_non_http_schemes(self):
        """Test that non-HTTP schemes are blocked."""
        assert is_safe_url("ftp://example.com") is False
        assert is_safe_url("file:///etc/passwd") is False
        assert is_safe_url("javascript:alert(1)") is False

    def test_blocks_missing_host(self):
        """Test that URLs without host are blocked."""
        assert is_safe_url("http://") is False
        assert is_safe_url("https://") is False

    def test_blocks_invalid_urls(self):
        """Test that invalid URLs are blocked."""
        assert is_safe_url("not-a-url") is False
        assert is_safe_url("") is False
