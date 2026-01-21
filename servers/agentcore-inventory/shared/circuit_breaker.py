# =============================================================================
# Circuit Breaker for Debug Agent Protection
# =============================================================================
# Thread-safe circuit breaker pattern to protect system from cascade failures.
# Used by DebugHook to prevent degradation when Debug Agent is unavailable.
#
# States:
# - CLOSED: Normal operation, requests pass through
# - OPEN: After failure_threshold failures, reject all requests
# - HALF_OPEN: After reset_timeout, allow one test request
#
# Reference: https://martinfowler.com/bliki/CircuitBreaker.html
# =============================================================================

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failures exceeded threshold, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Thread-safe circuit breaker for protecting against cascade failures.

    The circuit breaker prevents repeated calls to a failing service,
    allowing it time to recover while providing fast failure responses.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: After failure_threshold failures, reject all requests immediately
    - HALF_OPEN: After reset_timeout, allow one test request to check recovery

    Usage:
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)

        if cb.can_execute():
            try:
                result = await call_external_service()
                await cb.record_success()
                return result
            except Exception as e:
                await cb.record_failure()
                raise
        else:
            # Circuit is open, fail fast
            raise CircuitOpenError("Service unavailable")

    Thread Safety:
        Uses asyncio.Lock for thread-safe state transitions in async contexts.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        name: str = "default",
    ):
        """
        Initialize CircuitBreaker.

        Args:
            failure_threshold: Number of failures before opening circuit (default: 3)
            reset_timeout: Seconds to wait before transitioning to HALF_OPEN (default: 60.0)
            half_open_max_calls: Max test calls allowed in HALF_OPEN state (default: 1)
            name: Circuit breaker name for logging (default: "default")
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._half_open_max_calls = half_open_max_calls

        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

        # Thread safety
        self._lock = asyncio.Lock()

        logger.info(
            f"[CircuitBreaker:{self._name}] Initialized with "
            f"threshold={failure_threshold}, reset_timeout={reset_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """
        Current circuit state.

        Note: This property auto-transitions from OPEN to HALF_OPEN
        if the reset_timeout has elapsed.
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    f"[CircuitBreaker:{self._name}] Transitioned to HALF_OPEN "
                    f"after {self._reset_timeout}s timeout"
                )
        return self._state

    @property
    def is_open(self) -> bool:
        """True if circuit is OPEN (rejecting requests)."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """True if circuit is CLOSED (allowing requests)."""
        return self.state == CircuitState.CLOSED

    @property
    def failure_count(self) -> int:
        """Current failure count."""
        return self._failure_count

    def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns:
            True if request should be allowed, False if circuit is OPEN
        """
        current_state = self.state  # This triggers auto-transition check

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            # Allow limited test calls in HALF_OPEN
            if self._half_open_calls < self._half_open_max_calls:
                return True
            return False

        # OPEN state - reject
        return False

    async def record_success(self) -> None:
        """
        Record successful execution.

        Resets failure count and closes circuit if in HALF_OPEN state.
        """
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Success in HALF_OPEN means service recovered
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                logger.info(
                    f"[CircuitBreaker:{self._name}] Transitioned to CLOSED "
                    f"after successful test call"
                )
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """
        Record failed execution.

        Increments failure count and may trip circuit to OPEN state.
        """
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Failure in HALF_OPEN means service still failing
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    f"[CircuitBreaker:{self._name}] Reopened after failure in HALF_OPEN"
                )

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"[CircuitBreaker:{self._name}] Opened after "
                        f"{self._failure_count} failures (threshold: {self._failure_threshold})"
                    )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self._reset_timeout

    async def reset(self) -> None:
        """
        Manually reset circuit to CLOSED state.

        Use with caution - only for testing or administrative override.
        Thread-safe via asyncio.Lock.
        """
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            logger.info(f"[CircuitBreaker:{self._name}] Manually reset to CLOSED")

    def get_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status for health checks.

        Returns:
            Status dict with state, failure_count, and configuration
        """
        return {
            "name": self._name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "reset_timeout_seconds": self._reset_timeout,
            "last_failure_time": self._last_failure_time,
            "time_until_half_open": self._time_until_half_open(),
        }

    def _time_until_half_open(self) -> Optional[float]:
        """Calculate time remaining until HALF_OPEN transition."""
        if self._state != CircuitState.OPEN:
            return None
        if self._last_failure_time is None:
            return None
        elapsed = time.monotonic() - self._last_failure_time
        remaining = self._reset_timeout - elapsed
        return max(0.0, remaining)


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str = "Circuit breaker is open"):
        self.message = message
        super().__init__(self.message)
