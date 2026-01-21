# =============================================================================
# Debug Hook for Strands Agents
# =============================================================================
# Intercepts errors from agent tool calls and sends them to Debug Agent
# for intelligent analysis and enrichment.
#
# NON-BLOCKING: Uses circuit breaker and timeout to ensure agent execution
# is not degraded if Debug Agent is unavailable.
#
# Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/
# =============================================================================

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    AfterToolCallEvent,
    AfterInvocationEvent,
)

from shared.circuit_breaker import CircuitBreaker
from shared.data_contracts import ensure_dict

logger = logging.getLogger(__name__)


class DebugHook(HookProvider):
    """
    Error interception hook that sends errors to Debug Agent for analysis.

    This hook intercepts tool call errors and agent invocation errors,
    sending them to the Debug Agent for intelligent analysis. The Debug Agent
    returns enriched error information including:
    - Technical explanation (pt-BR)
    - Root cause analysis with confidence levels
    - Debugging steps
    - Relevant documentation links

    NON-BLOCKING DESIGN:
    - Uses circuit breaker to prevent cascade failures
    - Configurable timeout (default 5s) for fast fail
    - Returns original error if Debug Agent unavailable
    - Graceful degradation - agents continue working even if Debug Agent fails

    Usage:
        agent = Agent(hooks=[LoggingHook(), MetricsHook(), DebugHook()])

    Configuration via environment variables:
        DEBUG_HOOK_ENABLED: Enable/disable hook (default: true)
        DEBUG_HOOK_TIMEOUT: Timeout in seconds (default: 5.0)
        DEBUG_CIRCUIT_THRESHOLD: Failures before opening circuit (default: 3)
        DEBUG_CIRCUIT_RESET: Reset timeout in seconds (default: 60.0)
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,  # TIMEOUT-FIX: Maximum for Gemini 2.5 Pro with Thinking
        enabled: bool = True,
        failure_threshold: int = 3,
        reset_timeout: float = 60.0,
    ):
        """
        Initialize DebugHook.

        Args:
            timeout_seconds: Max time to wait for Debug Agent (default: 5.0)
            enabled: Whether hook is active (default: True)
            failure_threshold: Failures before circuit opens (default: 3)
            reset_timeout: Seconds before circuit resets (default: 60.0)
        """
        # Configuration from environment or parameters
        self.timeout = float(os.environ.get("DEBUG_HOOK_TIMEOUT", timeout_seconds))
        self.enabled = os.environ.get("DEBUG_HOOK_ENABLED", str(enabled)).lower() == "true"

        # Circuit breaker for self-protection
        threshold = int(os.environ.get("DEBUG_CIRCUIT_THRESHOLD", failure_threshold))
        reset = float(os.environ.get("DEBUG_CIRCUIT_RESET", reset_timeout))
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=threshold,
            reset_timeout=reset,
            name="debug_hook",
        )

        # Lazy-loaded A2A client (avoid import at startup)
        self._a2a_client = None

        # Track enriched errors for downstream access
        self._last_enrichment: Optional[Dict[str, Any]] = None

        logger.info(
            f"[DebugHook] Initialized: enabled={self.enabled}, "
            f"timeout={self.timeout}s, threshold={threshold}, reset={reset}s"
        )

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register callbacks for error interception."""
        registry.add_callback(AfterToolCallEvent, self._on_tool_end)
        registry.add_callback(AfterInvocationEvent, self._on_invocation_end)

    async def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        """
        Intercept tool errors and enrich them via Debug Agent.

        Called after every tool call completes. Only processes events
        that have an error attached.

        CRITICAL-002 FIX: Now stores enrichment for downstream access and
        attempts to attach to event context if available.
        """
        error = getattr(event, "error", None)
        if error is None:
            return  # No error, nothing to do

        # Skip if disabled or circuit is open
        if not self.enabled:
            logger.debug("[DebugHook] Disabled, skipping error enrichment")
            return

        if self.circuit_breaker.is_open:
            logger.debug("[DebugHook] Circuit open, skipping error enrichment")
            return

        # Enrich the error
        enrichment = await self._enrich_error(
            error=error,
            operation=getattr(event, "tool_name", "unknown_tool"),
            event_type="tool_call",
        )

        # CRITICAL-002 FIX: Store enrichment for downstream access
        self._last_enrichment = enrichment

        # Try to attach to event context if available (for tool errors)
        if hasattr(event, "context") and isinstance(event.context, dict):
            if enrichment.get("enriched"):
                event.context["debug_analysis"] = enrichment.get("analysis", {})
                event.context["_debug_enriched"] = True
                logger.info(
                    f"[DebugHook] Tool error enriched and attached to context: "
                    f"{type(error).__name__}"
                )

    async def _on_invocation_end(self, event: AfterInvocationEvent) -> None:
        """
        Intercept agent invocation errors.

        Called after agent invocation completes. Checks for error conditions
        in the stop_reason or response.

        BUG-022 FIX: Now also intercepts 'soft errors' (success: false) not just
        exceptions, enabling Debug Agent enrichment for ALL error types.
        """
        # Skip if disabled or circuit is open
        if not self.enabled or self.circuit_breaker.is_open:
            return

        # Try to extract response
        response = getattr(event, "response", None)

        # BUG-022 FIX: Intercept 'soft errors' (success: false) not just exceptions
        if isinstance(response, dict):
            # Check for soft error pattern (success: false)
            if response.get("success") is False:
                # Skip if already enriched
                if response.get("_debug_enriched"):
                    return

                error_msg = response.get("error", response.get("message", "Unknown error"))

                # Enrich the soft error
                enrichment = await self._enrich_error(
                    error=Exception(str(error_msg)),
                    operation=response.get("action", response.get("operation", "unknown")),
                    event_type="soft_error",
                    context=response,
                )

                if enrichment.get("enriched"):
                    response["debug_analysis"] = enrichment.get("analysis", {})
                    response["_debug_enriched"] = True
                    logger.info(
                        f"[DebugHook] Soft error enriched: {str(error_msg)[:100]}"
                    )
                return

            # Check if response contains error_context (our standard error pattern)
            if response.get("error_context"):
                await self._enrich_error(
                    error=Exception(response.get("error", "Unknown error")),
                    operation=response.get("error_context", {}).get("operation", "unknown"),
                    event_type="invocation",
                    context=response.get("error_context"),
                )
                return

        # Original behavior: Check for error indicators in stop_reason
        stop_reason = getattr(event, "stop_reason", "")
        error_indicators = ["error", "exception", "failed", "timeout"]
        if any(indicator in str(stop_reason).lower() for indicator in error_indicators):
            if isinstance(response, dict) and response.get("error_context"):
                await self._enrich_error(
                    error=Exception(response.get("error", "Unknown error")),
                    operation=response.get("error_context", {}).get("operation", "unknown"),
                    event_type="invocation",
                    context=response.get("error_context"),
                )

    async def _enrich_error(
        self,
        error: Exception,
        operation: str,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send error to Debug Agent for enrichment.

        This method handles the actual A2A call to Debug Agent with
        circuit breaker protection and timeout handling.

        Args:
            error: The exception that occurred
            operation: Operation name that failed
            event_type: Type of event (tool_call, invocation)
            context: Additional error context

        Returns:
            Enrichment result dict with keys:
            - enriched: bool (True if enrichment succeeded)
            - reason: str (if enriched=False)
            - analysis: dict (if enriched=True)
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.debug("[DebugHook] Circuit breaker blocking request")
            return {"enriched": False, "reason": "circuit_open"}

        try:
            client = self._get_a2a_client()

            # Build error payload for Debug Agent
            error_payload = {
                "action": "analyze_error",
                "error_type": type(error).__name__,
                "message": str(error),
                "operation": operation,
                "stack_trace": self._get_stack_trace(error),
                "context": {
                    "agent_id": os.environ.get("AGENT_ID", "unknown"),
                    "session_id": context.get("session_id") if context else None,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "event_type": event_type,
                    **(context or {}),
                },
                "recoverable": self._is_recoverable(error),
            }

            logger.debug(
                f"[DebugHook] Sending error to Debug Agent: "
                f"{error_payload['error_type']} in {operation}"
            )

            # Invoke Debug Agent with timeout
            result = await asyncio.wait_for(
                client.invoke_agent("debug", error_payload),
                timeout=self.timeout,
            )

            # Record success
            await self.circuit_breaker.record_success()

            if result.success:
                # Store enrichment for downstream access
                self._last_enrichment = {
                    "enriched": True,
                    "analysis": ensure_dict(result.response, "debug_hook_analysis"),
                }
                logger.info(
                    f"[DebugHook] Error enriched successfully: "
                    f"{error_payload['error_type']}"
                )
                return self._last_enrichment
            else:
                logger.warning(
                    f"[DebugHook] Debug Agent returned error: {result.error}"
                )
                return {"enriched": False, "reason": result.error or "unknown_error"}

        except asyncio.TimeoutError:
            logger.warning(
                f"[DebugHook] Timeout ({self.timeout}s) waiting for Debug Agent"
            )
            return {"enriched": False, "reason": "timeout"}

        except asyncio.CancelledError:
            logger.warning("[DebugHook] Request cancelled")
            return {"enriched": False, "reason": "cancelled"}

        except Exception as e:
            # Record failure for circuit breaker
            await self.circuit_breaker.record_failure()
            logger.error(f"[DebugHook] Error invoking Debug Agent: {e}")
            return {"enriched": False, "reason": str(e)}

    def _get_a2a_client(self):
        """
        Lazy-load A2A client.

        Defers import to avoid circular dependencies and
        unnecessary initialization at agent startup.
        """
        if self._a2a_client is None:
            from shared.a2a_client import A2AClient
            self._a2a_client = A2AClient()
        return self._a2a_client

    def _get_stack_trace(self, error: Exception) -> Optional[str]:
        """Extract stack trace from exception if available."""
        import traceback

        try:
            if error.__traceback__:
                return "".join(traceback.format_tb(error.__traceback__))
        except Exception:
            pass
        return None

    def _is_recoverable(self, error: Exception) -> bool:
        """
        Determine if error is likely recoverable.

        Recoverable errors are transient and may succeed on retry:
        - Network timeouts
        - Connection errors
        - Rate limiting (429)
        """
        recoverable_types = (
            TimeoutError,
            ConnectionError,
            OSError,
            asyncio.TimeoutError,
        )
        return isinstance(error, recoverable_types)

    def get_last_enrichment(self) -> Optional[Dict[str, Any]]:
        """
        Get the last enrichment result.

        Returns:
            Last enrichment dict or None if no enrichment occurred
        """
        return self._last_enrichment

    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status for monitoring.

        Returns:
            Circuit breaker status dict
        """
        return self.circuit_breaker.get_status()

    def disable(self) -> None:
        """Temporarily disable the hook."""
        self.enabled = False
        logger.info("[DebugHook] Disabled")

    def enable(self) -> None:
        """Re-enable the hook."""
        self.enabled = True
        logger.info("[DebugHook] Enabled")

    async def reset_circuit(self) -> None:
        """
        Reset circuit breaker to CLOSED state.

        Use for testing or administrative override.

        HIGH-001 FIX: Now properly async to match CircuitBreaker.reset().
        """
        await self.circuit_breaker.reset()
