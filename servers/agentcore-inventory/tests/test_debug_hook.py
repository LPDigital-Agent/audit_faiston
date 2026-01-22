# =============================================================================
# Tests for Debug Hook
# =============================================================================
# Unit tests for DebugHook (error interception and enrichment via Debug Agent).
#
# These tests verify:
# - Hook registration with Strands HookRegistry
# - Error interception from tool calls and invocations
# - Circuit breaker integration
# - Timeout handling
# - Graceful degradation when Debug Agent is unavailable
#
# Run: cd server/agentcore-inventory && python -m pytest tests/test_debug_hook.py -v
# =============================================================================

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# Mock Classes for Strands Events
# =============================================================================

class MockAfterToolCallEvent:
    """Mock for strands.hooks.events.AfterToolCallEvent."""

    def __init__(self, tool_name: str = "test_tool", error: Exception = None):
        self.tool_name = tool_name
        self.error = error


class MockAfterInvocationEvent:
    """Mock for strands.hooks.events.AfterInvocationEvent."""

    def __init__(self, stop_reason: str = "end_turn", response: dict = None):
        self.stop_reason = stop_reason
        self.response = response or {}


class MockHookRegistry:
    """Mock for strands.hooks.HookRegistry."""

    def __init__(self):
        self.callbacks = {}

    def add_callback(self, event_type, callback):
        self.callbacks[event_type.__name__] = callback


class MockA2AResult:
    """Mock for A2A invocation result."""

    def __init__(self, success: bool = True, response: dict = None, error: str = None):
        self.success = success
        self.response = response or {}
        self.error = error


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_a2a_client():
    """Mock A2A client for testing."""
    client = MagicMock()
    client.invoke_agent = AsyncMock(
        return_value=MockA2AResult(
            success=True,
            response={
                "error_type": "TestError",
                "analysis": {
                    "explanation": "Test explanation",
                    "root_causes": ["cause1"],
                    "debugging_steps": ["step1"],
                },
            },
        )
    )
    return client


@pytest.fixture
def debug_hook(mock_a2a_client):
    """Create DebugHook with mocked dependencies."""
    with patch("shared.hooks.debug_hook.CircuitBreaker") as MockCB:
        # Mock circuit breaker
        mock_cb = MagicMock()
        mock_cb.can_execute.return_value = True
        mock_cb.is_open = False
        mock_cb.record_success = AsyncMock()
        mock_cb.record_failure = AsyncMock()
        mock_cb.reset = AsyncMock()  # HIGH-001: reset() is now async
        mock_cb.get_status.return_value = {"state": "closed", "failure_count": 0}
        MockCB.return_value = mock_cb

        from shared.hooks.debug_hook import DebugHook

        hook = DebugHook(
            timeout_seconds=5.0,
            enabled=True,
            failure_threshold=3,
            reset_timeout=60.0,
        )
        hook._a2a_client = mock_a2a_client
        hook.circuit_breaker = mock_cb

        return hook


@pytest.fixture
def disabled_hook():
    """Create disabled DebugHook."""
    with patch("shared.hooks.debug_hook.CircuitBreaker"):
        from shared.hooks.debug_hook import DebugHook

        return DebugHook(enabled=False)


# =============================================================================
# Tests for Initialization
# =============================================================================

class TestDebugHookInit:
    """Tests for DebugHook initialization."""

    def test_default_configuration(self):
        """Test that default configuration is applied."""
        with patch("shared.hooks.debug_hook.CircuitBreaker"):
            from shared.hooks.debug_hook import DebugHook

            hook = DebugHook()
            # TIMEOUT-FIX: Default timeout increased to 30.0s for Gemini 2.5 Pro with Thinking
            assert hook.timeout == 30.0
            assert hook.enabled is True

    def test_custom_configuration(self):
        """Test that custom configuration is applied."""
        with patch("shared.hooks.debug_hook.CircuitBreaker"):
            from shared.hooks.debug_hook import DebugHook

            hook = DebugHook(
                timeout_seconds=10.0,
                enabled=False,
                failure_threshold=5,
                reset_timeout=120.0,
            )
            assert hook.timeout == 10.0
            assert hook.enabled is False

    def test_environment_variable_override(self):
        """Test that environment variables override parameters."""
        import os

        with patch.dict(os.environ, {"DEBUG_HOOK_TIMEOUT": "15.0", "DEBUG_HOOK_ENABLED": "false"}):
            with patch("shared.hooks.debug_hook.CircuitBreaker"):
                from shared.hooks.debug_hook import DebugHook

                hook = DebugHook()
                assert hook.timeout == 15.0
                assert hook.enabled is False


# =============================================================================
# Tests for Hook Registration
# =============================================================================

class TestHookRegistration:
    """Tests for hook registration with Strands registry."""

    def test_register_hooks_adds_callbacks(self, debug_hook):
        """Test that register_hooks adds callbacks for events."""
        registry = MockHookRegistry()
        debug_hook.register_hooks(registry)

        assert "AfterToolCallEvent" in registry.callbacks
        assert "AfterInvocationEvent" in registry.callbacks

    def test_callbacks_are_callable(self, debug_hook):
        """Test that registered callbacks are callable."""
        registry = MockHookRegistry()
        debug_hook.register_hooks(registry)

        # Both callbacks should be callable
        assert callable(registry.callbacks["AfterToolCallEvent"])
        assert callable(registry.callbacks["AfterInvocationEvent"])


# =============================================================================
# Tests for Tool Error Interception
# =============================================================================

class TestToolErrorInterception:
    """Tests for _on_tool_end callback."""

    @pytest.mark.asyncio
    async def test_no_error_does_nothing(self, debug_hook, mock_a2a_client):
        """Test that events without errors are ignored."""
        event = MockAfterToolCallEvent(tool_name="test_tool", error=None)

        await debug_hook._on_tool_end(event)

        # A2A client should NOT be called
        mock_a2a_client.invoke_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_triggers_enrichment(self, debug_hook, mock_a2a_client):
        """Test that errors trigger Debug Agent enrichment."""
        error = ValueError("Test error")
        event = MockAfterToolCallEvent(tool_name="failing_tool", error=error)

        await debug_hook._on_tool_end(event)

        # A2A client should be called
        mock_a2a_client.invoke_agent.assert_called_once()
        call_args = mock_a2a_client.invoke_agent.call_args
        assert call_args[0][0] == "debug"  # Agent ID

    @pytest.mark.asyncio
    async def test_disabled_hook_does_nothing(self, disabled_hook):
        """Test that disabled hook ignores errors."""
        error = ValueError("Test error")
        event = MockAfterToolCallEvent(tool_name="test_tool", error=error)

        # Should not raise and should not call A2A
        await disabled_hook._on_tool_end(event)
        # No assertion needed - just shouldn't raise

    @pytest.mark.asyncio
    async def test_circuit_open_skips_enrichment(self, debug_hook, mock_a2a_client):
        """Test that open circuit skips enrichment."""
        debug_hook.circuit_breaker.is_open = True

        error = ValueError("Test error")
        event = MockAfterToolCallEvent(tool_name="test_tool", error=error)

        await debug_hook._on_tool_end(event)

        # A2A client should NOT be called
        mock_a2a_client.invoke_agent.assert_not_called()


# =============================================================================
# Tests for Invocation Error Interception
# =============================================================================

class TestInvocationErrorInterception:
    """Tests for _on_invocation_end callback."""

    @pytest.mark.asyncio
    async def test_normal_stop_reason_does_nothing(self, debug_hook, mock_a2a_client):
        """Test that normal stop reasons are ignored."""
        event = MockAfterInvocationEvent(stop_reason="end_turn", response={})

        await debug_hook._on_invocation_end(event)

        mock_a2a_client.invoke_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_stop_reason_triggers_check(self, debug_hook, mock_a2a_client):
        """Test that error stop reasons trigger enrichment check."""
        event = MockAfterInvocationEvent(
            stop_reason="error",
            response={
                "error": "Test error",
                "error_context": {
                    "operation": "test_operation",
                    "session_id": "session_123",
                },
            },
        )

        await debug_hook._on_invocation_end(event)

        # Should call A2A client
        mock_a2a_client.invoke_agent.assert_called_once()


# =============================================================================
# Tests for Error Enrichment
# =============================================================================

class TestErrorEnrichment:
    """Tests for _enrich_error method."""

    @pytest.mark.asyncio
    async def test_successful_enrichment(self, debug_hook, mock_a2a_client):
        """Test successful error enrichment flow."""
        error = ValueError("Test error message")

        result = await debug_hook._enrich_error(
            error=error,
            operation="test_operation",
            event_type="tool_call",
        )

        assert result["enriched"] is True
        assert "analysis" in result
        debug_hook.circuit_breaker.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrichment_with_context(self, debug_hook, mock_a2a_client):
        """Test enrichment includes context in payload."""
        error = RuntimeError("Context error")
        context = {"session_id": "sess_123", "user_id": "user_456"}

        await debug_hook._enrich_error(
            error=error,
            operation="test_op",
            event_type="tool_call",
            context=context,
        )

        call_args = mock_a2a_client.invoke_agent.call_args
        payload = call_args[0][1]
        assert payload["context"]["session_id"] == "sess_123"

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_enrichment(self, debug_hook):
        """Test that circuit breaker can block enrichment."""
        debug_hook.circuit_breaker.can_execute.return_value = False

        error = ValueError("Blocked error")
        result = await debug_hook._enrich_error(
            error=error,
            operation="test_op",
            event_type="tool_call",
        )

        assert result["enriched"] is False
        assert result["reason"] == "circuit_open"

    @pytest.mark.asyncio
    async def test_timeout_handling(self, debug_hook, mock_a2a_client):
        """Test that timeout is handled gracefully."""
        # Make invoke_agent timeout
        mock_a2a_client.invoke_agent = AsyncMock(
            side_effect=asyncio.TimeoutError("Timeout")
        )
        debug_hook.timeout = 0.001  # Very short timeout

        error = ValueError("Timeout test")
        result = await debug_hook._enrich_error(
            error=error,
            operation="slow_op",
            event_type="tool_call",
        )

        assert result["enriched"] is False
        assert result["reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_debug_agent_failure_records_circuit_failure(
        self, debug_hook, mock_a2a_client
    ):
        """Test that Debug Agent failure records circuit breaker failure."""
        mock_a2a_client.invoke_agent = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        error = ValueError("Test error")
        await debug_hook._enrich_error(
            error=error,
            operation="test_op",
            event_type="tool_call",
        )

        debug_hook.circuit_breaker.record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_debug_agent_returns_error(self, debug_hook, mock_a2a_client):
        """Test handling when Debug Agent returns error response."""
        mock_a2a_client.invoke_agent = AsyncMock(
            return_value=MockA2AResult(success=False, error="Analysis failed")
        )

        error = ValueError("Test error")
        result = await debug_hook._enrich_error(
            error=error,
            operation="test_op",
            event_type="tool_call",
        )

        assert result["enriched"] is False
        assert "Analysis failed" in result["reason"]


# =============================================================================
# Tests for Error Payload Building
# =============================================================================

class TestErrorPayload:
    """Tests for error payload construction."""

    @pytest.mark.asyncio
    async def test_payload_includes_required_fields(self, debug_hook, mock_a2a_client):
        """Test that error payload includes all required fields."""
        error = ValueError("Payload test")
        error.__traceback__ = None  # Clear traceback for test

        await debug_hook._enrich_error(
            error=error,
            operation="test_operation",
            event_type="tool_call",
        )

        call_args = mock_a2a_client.invoke_agent.call_args
        payload = call_args[0][1]

        assert payload["action"] == "analyze_error"
        assert payload["error_type"] == "ValueError"
        assert payload["message"] == "Payload test"
        assert payload["operation"] == "test_operation"
        assert "context" in payload
        assert "timestamp" in payload["context"]
        assert "recoverable" in payload


# =============================================================================
# Tests for Recoverable Error Detection
# =============================================================================

class TestRecoverableErrors:
    """Tests for _is_recoverable method."""

    def test_timeout_is_recoverable(self, debug_hook):
        """Test that TimeoutError is marked as recoverable."""
        error = TimeoutError("Connection timeout")
        assert debug_hook._is_recoverable(error) is True

    def test_connection_error_is_recoverable(self, debug_hook):
        """Test that ConnectionError is marked as recoverable."""
        error = ConnectionError("Network unavailable")
        assert debug_hook._is_recoverable(error) is True

    def test_value_error_is_not_recoverable(self, debug_hook):
        """Test that ValueError is NOT marked as recoverable."""
        error = ValueError("Invalid input")
        assert debug_hook._is_recoverable(error) is False

    def test_key_error_is_not_recoverable(self, debug_hook):
        """Test that KeyError is NOT marked as recoverable."""
        error = KeyError("missing_key")
        assert debug_hook._is_recoverable(error) is False


# =============================================================================
# Tests for State Management
# =============================================================================

class TestStateManagement:
    """Tests for hook state management."""

    def test_get_last_enrichment(self, debug_hook):
        """Test that last enrichment can be retrieved."""
        debug_hook._last_enrichment = {"enriched": True, "analysis": {}}
        result = debug_hook.get_last_enrichment()
        assert result["enriched"] is True

    def test_get_circuit_status(self, debug_hook):
        """Test that circuit status can be retrieved."""
        status = debug_hook.get_circuit_status()
        assert "state" in status

    def test_disable_hook(self, debug_hook):
        """Test that hook can be disabled."""
        debug_hook.disable()
        assert debug_hook.enabled is False

    def test_enable_hook(self, debug_hook):
        """Test that hook can be re-enabled."""
        debug_hook.disable()
        debug_hook.enable()
        assert debug_hook.enabled is True

    @pytest.mark.asyncio
    async def test_reset_circuit(self, debug_hook):
        """Test that circuit breaker can be reset."""
        # HIGH-001 FIX: reset_circuit() is now async
        await debug_hook.reset_circuit()
        debug_hook.circuit_breaker.reset.assert_called_once()


# =============================================================================
# Tests for Lazy Loading
# =============================================================================

class TestLazyLoading:
    """Tests for lazy-loaded A2A client."""

    def test_a2a_client_is_lazy_loaded(self):
        """Test that A2A client is not loaded at init."""
        with patch("shared.hooks.debug_hook.CircuitBreaker"):
            from shared.hooks.debug_hook import DebugHook

            hook = DebugHook()
            assert hook._a2a_client is None

    def test_get_a2a_client_loads_on_demand(self, debug_hook):
        """Test that _get_a2a_client loads client on first call."""
        debug_hook._a2a_client = None

        with patch("shared.a2a_client.A2AClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            result = debug_hook._get_a2a_client()
            assert result == mock_client


# =============================================================================
# Tests for Stack Trace Extraction
# =============================================================================

class TestStackTraceExtraction:
    """Tests for _get_stack_trace method."""

    def test_extracts_stack_trace_when_available(self, debug_hook):
        """Test that stack trace is extracted from exception."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            trace = debug_hook._get_stack_trace(e)
            assert trace is not None
            assert "ValueError" in trace or "test_debug_hook" in trace

    def test_returns_none_when_no_traceback(self, debug_hook):
        """Test that None is returned when no traceback."""
        error = ValueError("No traceback")
        error.__traceback__ = None
        trace = debug_hook._get_stack_trace(error)
        assert trace is None
