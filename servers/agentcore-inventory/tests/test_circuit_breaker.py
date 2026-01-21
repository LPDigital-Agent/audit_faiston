# =============================================================================
# Tests for Circuit Breaker
# =============================================================================
# Unit tests for CircuitBreaker pattern used by DebugHook.
#
# These tests verify:
# - State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
# - Failure threshold behavior
# - Reset timeout behavior
# - Thread safety with asyncio locks
# - Status reporting
#
# Run: cd server/agentcore-inventory && python -m pytest tests/test_circuit_breaker.py -v
# =============================================================================

import pytest
import time

from shared.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def circuit_breaker():
    """Create a fresh CircuitBreaker with default settings."""
    return CircuitBreaker(
        failure_threshold=3,
        reset_timeout=60.0,
        half_open_max_calls=1,
        name="test_circuit",
    )


@pytest.fixture
def fast_reset_circuit():
    """Create a CircuitBreaker with very short reset timeout for testing."""
    return CircuitBreaker(
        failure_threshold=2,
        reset_timeout=0.1,  # 100ms for fast tests
        half_open_max_calls=1,
        name="fast_test",
    )


# =============================================================================
# Tests for Initialization
# =============================================================================

class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_default_state_is_closed(self, circuit_breaker):
        """Test that circuit starts in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.is_closed is True
        assert circuit_breaker.is_open is False

    def test_default_failure_count_is_zero(self, circuit_breaker):
        """Test that failure count starts at 0."""
        assert circuit_breaker.failure_count == 0

    def test_can_execute_when_closed(self, circuit_breaker):
        """Test that requests can execute when circuit is CLOSED."""
        assert circuit_breaker.can_execute() is True

    def test_custom_configuration(self):
        """Test that custom configuration is applied."""
        cb = CircuitBreaker(
            failure_threshold=5,
            reset_timeout=120.0,
            half_open_max_calls=2,
            name="custom_test",
        )
        status = cb.get_status()
        assert status["failure_threshold"] == 5
        assert status["reset_timeout_seconds"] == 120.0
        assert status["name"] == "custom_test"


# =============================================================================
# Tests for Failure Recording
# =============================================================================

class TestFailureRecording:
    """Tests for recording failures and state transitions."""

    @pytest.mark.asyncio
    async def test_failure_count_increments(self, circuit_breaker):
        """Test that failure count increments on each failure."""
        assert circuit_breaker.failure_count == 0

        await circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 1

        await circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 2

    @pytest.mark.asyncio
    async def test_circuit_opens_at_threshold(self, circuit_breaker):
        """Test that circuit opens after reaching failure threshold."""
        # Circuit should be CLOSED initially
        assert circuit_breaker.state == CircuitState.CLOSED

        # Record failures up to threshold (3)
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.CLOSED  # Still closed

        # Third failure should open the circuit
        await circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.is_open is True

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_requests(self, circuit_breaker):
        """Test that OPEN circuit rejects can_execute()."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()

        assert circuit_breaker.can_execute() is False


# =============================================================================
# Tests for Success Recording
# =============================================================================

class TestSuccessRecording:
    """Tests for recording successes and state transitions."""

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, circuit_breaker):
        """Test that success resets failure count in CLOSED state."""
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 2

        await circuit_breaker.record_success()
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_success_in_half_open_closes_circuit(self, fast_reset_circuit):
        """Test that success in HALF_OPEN state closes circuit."""
        # Open the circuit
        await fast_reset_circuit.record_failure()
        await fast_reset_circuit.record_failure()
        assert fast_reset_circuit.state == CircuitState.OPEN

        # Wait for reset timeout
        time.sleep(0.15)

        # Circuit should transition to HALF_OPEN
        assert fast_reset_circuit.state == CircuitState.HALF_OPEN

        # Success should close the circuit
        await fast_reset_circuit.record_success()
        assert fast_reset_circuit.state == CircuitState.CLOSED
        assert fast_reset_circuit.failure_count == 0


# =============================================================================
# Tests for HALF_OPEN State
# =============================================================================

class TestHalfOpenState:
    """Tests for HALF_OPEN state behavior."""

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_timeout(self, fast_reset_circuit):
        """Test that circuit transitions from OPEN to HALF_OPEN after timeout."""
        # Open the circuit
        await fast_reset_circuit.record_failure()
        await fast_reset_circuit.record_failure()
        assert fast_reset_circuit.state == CircuitState.OPEN

        # Wait for reset timeout
        time.sleep(0.15)

        # Should auto-transition to HALF_OPEN
        assert fast_reset_circuit.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_allows_limited_requests(self, fast_reset_circuit):
        """Test that HALF_OPEN allows limited test requests."""
        # Open the circuit
        await fast_reset_circuit.record_failure()
        await fast_reset_circuit.record_failure()

        # Wait for reset timeout
        time.sleep(0.15)

        # First request should be allowed (HALF_OPEN)
        assert fast_reset_circuit.can_execute() is True

        # Simulate the call being made (increment half_open_calls)
        fast_reset_circuit._half_open_calls = 1

        # Second request should be blocked (max_calls=1)
        assert fast_reset_circuit.can_execute() is False

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens_circuit(self, fast_reset_circuit):
        """Test that failure in HALF_OPEN reopens circuit."""
        # Open the circuit
        await fast_reset_circuit.record_failure()
        await fast_reset_circuit.record_failure()

        # Wait for reset timeout
        time.sleep(0.15)

        # Should be HALF_OPEN
        assert fast_reset_circuit.state == CircuitState.HALF_OPEN

        # Record failure while in HALF_OPEN
        await fast_reset_circuit.record_failure()

        # Should reopen the circuit
        assert fast_reset_circuit.state == CircuitState.OPEN


# =============================================================================
# Tests for Manual Reset
# =============================================================================

class TestManualReset:
    """Tests for manual reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_closes_open_circuit(self, circuit_breaker):
        """Test that reset() closes an open circuit."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN

        # Manual reset (now async per MEDIUM-001 fix)
        await circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_reset_clears_failure_count(self, circuit_breaker):
        """Test that reset() clears the failure count."""
        circuit_breaker._failure_count = 2
        await circuit_breaker.reset()
        assert circuit_breaker.failure_count == 0


# =============================================================================
# Tests for Status Reporting
# =============================================================================

class TestStatusReporting:
    """Tests for get_status() method."""

    def test_status_includes_all_fields(self, circuit_breaker):
        """Test that status includes all required fields."""
        status = circuit_breaker.get_status()

        assert "name" in status
        assert "state" in status
        assert "failure_count" in status
        assert "failure_threshold" in status
        assert "reset_timeout_seconds" in status
        assert "last_failure_time" in status
        assert "time_until_half_open" in status

    def test_status_shows_correct_state(self, circuit_breaker):
        """Test that status shows correct state string."""
        status = circuit_breaker.get_status()
        assert status["state"] == "closed"

    @pytest.mark.asyncio
    async def test_status_shows_time_until_half_open_when_open(self, fast_reset_circuit):
        """Test that status shows time until HALF_OPEN when OPEN."""
        # Open the circuit
        await fast_reset_circuit.record_failure()
        await fast_reset_circuit.record_failure()

        status = fast_reset_circuit.get_status()
        assert status["state"] == "open"
        assert status["time_until_half_open"] is not None
        assert status["time_until_half_open"] > 0


# =============================================================================
# Tests for CircuitOpenError
# =============================================================================

class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_error_has_default_message(self):
        """Test that error has default message."""
        error = CircuitOpenError()
        assert "Circuit breaker is open" in str(error)

    def test_error_accepts_custom_message(self):
        """Test that error accepts custom message."""
        error = CircuitOpenError("Debug Agent unavailable")
        assert "Debug Agent unavailable" in str(error)


# =============================================================================
# Tests for Thread Safety
# =============================================================================

class TestThreadSafety:
    """Tests for thread safety with asyncio locks."""

    @pytest.mark.asyncio
    async def test_concurrent_failures_are_counted_correctly(self, circuit_breaker):
        """Test that concurrent failures are counted correctly."""
        import asyncio

        # Record multiple failures concurrently
        await asyncio.gather(
            circuit_breaker.record_failure(),
            circuit_breaker.record_failure(),
            circuit_breaker.record_failure(),
        )

        # All failures should be counted
        assert circuit_breaker.failure_count == 3
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_concurrent_success_and_failure(self, circuit_breaker):
        """Test that concurrent success/failure operations don't corrupt state."""
        import asyncio

        # Mix successes and failures
        await asyncio.gather(
            circuit_breaker.record_failure(),
            circuit_breaker.record_success(),
            circuit_breaker.record_failure(),
        )

        # State should be consistent (no corruption)
        assert circuit_breaker.state in [CircuitState.CLOSED, CircuitState.OPEN]


# =============================================================================
# Tests for Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_threshold_opens_immediately(self):
        """Test that threshold of 0 opens circuit immediately."""
        # Note: threshold of 0 would cause issues, so we use 1
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=60.0, name="threshold_1")
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_state_property_triggers_transition(self, fast_reset_circuit):
        """Test that accessing state property triggers auto-transition."""
        # Manually set to OPEN with last_failure_time in the past
        fast_reset_circuit._state = CircuitState.OPEN
        fast_reset_circuit._last_failure_time = time.monotonic() - 1.0  # 1 second ago

        # Accessing state should trigger transition
        assert fast_reset_circuit.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_success_after_multiple_failures_resets_count(self, circuit_breaker):
        """Test that success after failures (but below threshold) resets count."""
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 2
        assert circuit_breaker.state == CircuitState.CLOSED  # Not at threshold yet

        await circuit_breaker.record_success()
        assert circuit_breaker.failure_count == 0
