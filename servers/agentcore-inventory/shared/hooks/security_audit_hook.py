# =============================================================================
# Security Audit Hook for Strands Agents
# =============================================================================
# Forensic audit logging for RepairAgent - captures ALL lifecycle events
# and logs them to DynamoDB with security-specific attributes.
#
# FAIL-CLOSED DESIGN (CRITICAL):
# - DynamoDB is a HARD dependency - agent BLOCKS if audit fails
# - SOC 2 / ISO 27001 compliance requires complete audit trail
# - NO try/except suppression - exceptions propagate to stop execution
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
    BeforeInvocationEvent,
    AfterInvocationEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
)

from shared.circuit_breaker import CircuitBreaker

# BUG-033 FIX: SGAAuditLogger is imported lazily in __init__ to avoid namespace collision
# between agents/tools/ and root tools/ packages. See config.py for full explanation.

logger = logging.getLogger(__name__)


class SecurityAuditHook(HookProvider):
    """
    Forensic audit logging hook for RepairAgent.

    Captures ALL lifecycle events and logs to DynamoDB table
    faiston-one-sga-audit-log-prod with security-specific attributes.

    FAIL-CLOSED DESIGN (CRITICAL):
    - If DynamoDB write fails → Hook raises exception → Agent execution BLOCKS
    - Rationale: SOC 2 compliance requires audit trail for all automated code changes
    - No silent failures allowed - audit integrity is paramount

    Circuit breaker still provides protection against cascading failures,
    but when open, the agent STOPS (rather than degrading gracefully).

    Usage:
        agent = Agent(hooks=[LoggingHook(), MetricsHook(), SecurityAuditHook()])

    Configuration via environment variables:
        SECURITY_AUDIT_ENABLED: Enable/disable hook (default: true)
        SECURITY_AUDIT_TIMEOUT: Timeout in seconds (default: 5.0)
        SECURITY_CIRCUIT_THRESHOLD: Failures before opening circuit (default: 3)
        SECURITY_CIRCUIT_RESET: Reset timeout in seconds (default: 60.0)
        AUDIT_LOG_TABLE: DynamoDB table name (default: faiston-one-sga-audit-log-prod)
    """

    def __init__(
        self,
        timeout_seconds: float = 5.0,
        enabled: bool = True,
        failure_threshold: int = 3,
        reset_timeout: float = 60.0,
    ):
        """
        Initialize SecurityAuditHook.

        Args:
            timeout_seconds: Max time to wait for DynamoDB write (default: 5.0)
            enabled: Whether hook is active (default: True)
            failure_threshold: Failures before circuit opens (default: 3)
            reset_timeout: Seconds before circuit resets (default: 60.0)
        """
        # Configuration from environment or parameters
        self.timeout = float(os.environ.get("SECURITY_AUDIT_TIMEOUT", timeout_seconds))
        self.enabled = os.environ.get("SECURITY_AUDIT_ENABLED", str(enabled)).lower() == "true"

        # Circuit breaker for cascading failure prevention
        threshold = int(os.environ.get("SECURITY_CIRCUIT_THRESHOLD", failure_threshold))
        reset = float(os.environ.get("SECURITY_CIRCUIT_RESET", reset_timeout))
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=threshold,
            reset_timeout=reset,
            name="security_audit_hook",
        )

        # BUG-033 FIX: Lazy import SGAAuditLogger to avoid namespace collision
        # between agents/tools/ and root tools/ packages.
        import sys

        # Compute project root from this file's location
        # File: /var/task/shared/hooks/security_audit_hook.py
        # Root: /var/task (up 2 levels: security_audit_hook.py → hooks → shared → root)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../.."))

        # Ensure project root is first in sys.path to resolve tools/ correctly
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        try:
            from tools.dynamodb_client import SGAAuditLogger
            self.audit_logger = SGAAuditLogger()
        except ImportError as e:
            logger.error(f"[SecurityAuditHook] Failed to import tools.dynamodb_client: {e}")
            raise

        # Track session context
        self._current_session_id: Optional[str] = None
        self._current_agent_id: Optional[str] = None

        logger.info(
            f"[SecurityAuditHook] Initialized: enabled={self.enabled}, "
            f"timeout={self.timeout}s, threshold={threshold}, reset={reset}s"
        )

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register callbacks for security audit logging."""
        registry.add_callback(BeforeInvocationEvent, self._on_invocation_start)
        registry.add_callback(AfterInvocationEvent, self._on_invocation_end)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_start)
        registry.add_callback(AfterToolCallEvent, self._on_tool_end)

    async def _on_invocation_start(self, event: BeforeInvocationEvent) -> None:
        """
        Log agent invocation start with full payload capture.

        FAIL-CLOSED: If audit logging fails, agent invocation is BLOCKED.
        """
        # Skip if disabled
        if not self.enabled:
            logger.debug("[SecurityAuditHook] Disabled, skipping invocation start audit")
            return

        # Check circuit breaker
        if self.circuit_breaker.is_open:
            # FAIL-CLOSED: Raise exception to block execution
            raise RuntimeError(
                "[SecurityAuditHook] Circuit breaker OPEN - cannot guarantee audit trail. "
                "Agent execution BLOCKED for security compliance."
            )

        # Extract session and agent context
        self._current_session_id = getattr(event, "session_id", None)
        self._current_agent_id = os.environ.get("AGENT_ID", "unknown")

        # Build audit payload
        payload = {
            "event_type": "invocation_start",
            "agent_id": self._current_agent_id,
            "session_id": self._current_session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "input_payload": self._extract_input_payload(event),
            "model": getattr(event, "model", "unknown"),
        }

        # Log to DynamoDB (FAIL-CLOSED: no try/except)
        await self._log_audit_event(
            event_type="invocation_start",
            action="agent_invocation_start",
            details=payload,
        )

    async def _on_invocation_end(self, event: AfterInvocationEvent) -> None:
        """
        Log agent invocation completion with response capture.

        FAIL-CLOSED: If audit logging fails, execution is BLOCKED.
        """
        # Skip if disabled
        if not self.enabled:
            return

        # Check circuit breaker
        if self.circuit_breaker.is_open:
            raise RuntimeError(
                "[SecurityAuditHook] Circuit breaker OPEN - cannot guarantee audit trail. "
                "Agent execution BLOCKED for security compliance."
            )

        # Extract response
        response = getattr(event, "response", None)
        stop_reason = getattr(event, "stop_reason", "unknown")

        # Build audit payload
        payload = {
            "event_type": "invocation_end",
            "agent_id": self._current_agent_id,
            "session_id": self._current_session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stop_reason": stop_reason,
            "response_summary": self._summarize_response(response),
            "success": not self._is_error_response(response),
        }

        # Log to DynamoDB (FAIL-CLOSED)
        await self._log_audit_event(
            event_type="invocation_end",
            action="agent_invocation_end",
            details=payload,
        )

    async def _on_tool_start(self, event: BeforeToolCallEvent) -> None:
        """
        Log tool call start with input parameters.

        FAIL-CLOSED: Blocks execution if audit fails.
        """
        # Skip if disabled
        if not self.enabled:
            return

        # Check circuit breaker
        if self.circuit_breaker.is_open:
            raise RuntimeError(
                "[SecurityAuditHook] Circuit breaker OPEN - cannot guarantee audit trail. "
                "Agent execution BLOCKED for security compliance."
            )

        # Extract tool context
        tool_name = getattr(event, "tool_name", "unknown_tool")
        tool_input = getattr(event, "tool_input", {})

        # Build audit payload
        payload = {
            "event_type": "tool_start",
            "agent_id": self._current_agent_id,
            "session_id": self._current_session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool_name": tool_name,
            "tool_input": tool_input,  # CRITICAL: Full payload for Git operations
        }

        # Log to DynamoDB (FAIL-CLOSED)
        await self._log_audit_event(
            event_type="tool_start",
            action=f"tool_call_{tool_name}",
            details=payload,
        )

    async def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        """
        Log tool call completion with output/error capture.

        CRITICAL: For Git operations, captures full diff/commit details.
        FAIL-CLOSED: Blocks execution if audit fails.
        """
        # Skip if disabled
        if not self.enabled:
            return

        # Check circuit breaker
        if self.circuit_breaker.is_open:
            raise RuntimeError(
                "[SecurityAuditHook] Circuit breaker OPEN - cannot guarantee audit trail. "
                "Agent execution BLOCKED for security compliance."
            )

        # Extract tool context
        tool_name = getattr(event, "tool_name", "unknown_tool")
        tool_output = getattr(event, "tool_output", None)
        error = getattr(event, "error", None)

        # Build audit payload
        payload = {
            "event_type": "tool_end",
            "agent_id": self._current_agent_id,
            "session_id": self._current_session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool_name": tool_name,
            "success": error is None,
            "error": str(error) if error else None,
            "output_summary": self._summarize_output(tool_output),
        }

        # CRITICAL: For Git operations, capture full details
        if tool_name in ["commit_fix_tool", "create_pr_tool", "create_fix_branch_tool"]:
            payload["git_operation"] = True
            payload["full_output"] = tool_output  # Complete audit trail

        # Log to DynamoDB (FAIL-CLOSED)
        await self._log_audit_event(
            event_type="tool_end",
            action=f"tool_complete_{tool_name}",
            details=payload,
        )

    async def _log_audit_event(
        self,
        event_type: str,
        action: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Log audit event to DynamoDB with timeout and circuit breaker.

        FAIL-CLOSED: Raises exception if logging fails.

        Args:
            event_type: Type of event (invocation_start, tool_end, etc.)
            action: Action being audited
            details: Full event details (including payloads)

        Raises:
            RuntimeError: If circuit breaker is open
            Exception: If DynamoDB write fails (propagates to caller)
        """
        # Check circuit breaker (already checked in caller, but defensive)
        if not self.circuit_breaker.can_execute():
            raise RuntimeError(
                "[SecurityAuditHook] Circuit breaker blocking request. "
                "Agent execution STOPPED to maintain audit integrity."
            )

        try:
            # Log to DynamoDB with timeout
            # FAIL-CLOSED: NO try/except suppression - let exceptions propagate
            await asyncio.wait_for(
                self._write_to_dynamodb(event_type, action, details),
                timeout=self.timeout,
            )

            # Record success for circuit breaker
            await self.circuit_breaker.record_success()

            logger.debug(
                f"[SecurityAuditHook] Audit event logged: {event_type} - {action}"
            )

        except asyncio.TimeoutError:
            # Record failure and BLOCK execution
            await self.circuit_breaker.record_failure()
            logger.error(
                f"[SecurityAuditHook] TIMEOUT ({self.timeout}s) logging audit event. "
                f"Agent execution BLOCKED."
            )
            # FAIL-CLOSED: Raise exception to stop agent
            raise RuntimeError(
                f"[SecurityAuditHook] Audit logging timeout. "
                f"Cannot guarantee compliance - execution BLOCKED."
            )

        except Exception as e:
            # Record failure and BLOCK execution
            await self.circuit_breaker.record_failure()
            logger.error(
                f"[SecurityAuditHook] ERROR logging audit event: {e}. "
                f"Agent execution BLOCKED."
            )
            # FAIL-CLOSED: Propagate exception to stop agent
            raise

    async def _write_to_dynamodb(
        self,
        event_type: str,
        action: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Write audit event to DynamoDB using SGAAuditLogger.

        Args:
            event_type: Type of event
            action: Action being audited
            details: Event details
        """
        # Use existing SGAAuditLogger
        success = self.audit_logger.log_event(
            event_type=event_type,
            actor_type="agent",
            actor_id=self._current_agent_id or "unknown",
            entity_type="repair_operation",
            entity_id=self._current_session_id or "unknown",
            action=action,
            details=details,
            session_id=self._current_session_id,
        )

        if not success:
            raise RuntimeError(
                f"[SecurityAuditHook] DynamoDB write failed for event: {event_type}"
            )

    def _extract_input_payload(self, event: BeforeInvocationEvent) -> Dict[str, Any]:
        """
        Extract input payload from invocation event.

        Returns:
            Input payload dict (safe for JSON serialization)
        """
        try:
            # Try to extract input from event
            if hasattr(event, "input"):
                input_data = event.input
                if isinstance(input_data, dict):
                    return input_data
                return {"raw_input": str(input_data)}
            return {}
        except Exception as e:
            logger.warning(f"[SecurityAuditHook] Error extracting input payload: {e}")
            return {}

    def _summarize_response(self, response: Any) -> Dict[str, Any]:
        """
        Summarize agent response for audit log.

        Returns:
            Response summary (safe for JSON)
        """
        try:
            if isinstance(response, dict):
                # Extract key fields
                return {
                    "success": response.get("success"),
                    "fix_applied": response.get("fix_applied"),
                    "branch_name": response.get("branch_name"),
                    "pr_url": response.get("pr_url"),
                    "error": response.get("error"),
                }
            return {"raw_response": str(response)[:500]}  # Truncate for safety
        except Exception as e:
            logger.warning(f"[SecurityAuditHook] Error summarizing response: {e}")
            return {}

    def _summarize_output(self, output: Any) -> Dict[str, Any]:
        """
        Summarize tool output for audit log.

        Returns:
            Output summary (safe for JSON)
        """
        try:
            if isinstance(output, dict):
                return output
            if isinstance(output, str):
                return {"output": output[:1000]}  # Truncate long strings
            return {"output": str(output)[:1000]}
        except Exception as e:
            logger.warning(f"[SecurityAuditHook] Error summarizing output: {e}")
            return {}

    def _is_error_response(self, response: Any) -> bool:
        """
        Check if response indicates an error.

        Returns:
            True if response is an error
        """
        if isinstance(response, dict):
            return response.get("success") is False or response.get("error") is not None
        return False

    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status for monitoring.

        Returns:
            Circuit breaker status dict
        """
        return self.circuit_breaker.get_status()

    def disable(self) -> None:
        """
        Temporarily disable the hook.

        WARNING: Disabling security audit hook may violate compliance requirements.
        """
        self.enabled = False
        logger.warning("[SecurityAuditHook] DISABLED - compliance audit trail may be incomplete")

    def enable(self) -> None:
        """Re-enable the hook."""
        self.enabled = True
        logger.info("[SecurityAuditHook] Enabled")

    async def reset_circuit(self) -> None:
        """
        Reset circuit breaker to CLOSED state.

        Use for testing or administrative override.
        """
        await self.circuit_breaker.reset()
        logger.info("[SecurityAuditHook] Circuit breaker reset to CLOSED state")
