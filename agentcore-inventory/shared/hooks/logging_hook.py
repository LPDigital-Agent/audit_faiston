# =============================================================================
# Logging Hook for Strands Agents
# =============================================================================
# Implements structured logging for all agent lifecycle events.
#
# Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/
# =============================================================================

import logging
import json
from datetime import datetime
from typing import Any, Dict

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    BeforeInvocationEvent,
    AfterInvocationEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
    BeforeModelCallEvent,
    AfterModelCallEvent,
)

logger = logging.getLogger(__name__)


class LoggingHook(HookProvider):
    """
    Structured logging hook for Strands Agents.

    Logs all agent lifecycle events with consistent JSON format:
    - Agent invocation start/end
    - Tool calls (before/after)
    - Model calls (before/after)

    Usage:
        agent = Agent(hooks=[LoggingHook()])
    """

    def __init__(self, log_level: int = logging.INFO, include_payloads: bool = False):
        """
        Initialize LoggingHook.

        Args:
            log_level: Logging level (default: INFO)
            include_payloads: Whether to log full payloads (default: False for security)
        """
        self.log_level = log_level
        self.include_payloads = include_payloads

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register callbacks for all lifecycle events."""
        registry.add_callback(BeforeInvocationEvent, self._on_invocation_start)
        registry.add_callback(AfterInvocationEvent, self._on_invocation_end)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_start)
        registry.add_callback(AfterToolCallEvent, self._on_tool_end)
        registry.add_callback(BeforeModelCallEvent, self._on_model_start)
        registry.add_callback(AfterModelCallEvent, self._on_model_end)

    def _log(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit structured log entry."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **data,
        }
        logger.log(self.log_level, json.dumps(log_entry))

    def _on_invocation_start(self, event: BeforeInvocationEvent) -> None:
        """Log agent invocation start."""
        self._log("AGENT_INVOCATION_START", {
            "agent_name": getattr(event.agent, "name", "unknown"),
            "message_count": len(getattr(event.agent, "messages", [])),
        })

    def _on_invocation_end(self, event: AfterInvocationEvent) -> None:
        """Log agent invocation end."""
        self._log("AGENT_INVOCATION_END", {
            "agent_name": getattr(event.agent, "name", "unknown"),
            "stop_reason": getattr(event, "stop_reason", "unknown"),
        })

    def _on_tool_start(self, event: BeforeToolCallEvent) -> None:
        """Log tool call start."""
        data = {
            "tool_name": getattr(event, "tool_name", "unknown"),
        }
        if self.include_payloads:
            data["tool_input"] = getattr(event, "tool_input", {})
        self._log("TOOL_CALL_START", data)

    def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        """Log tool call end."""
        data = {
            "tool_name": getattr(event, "tool_name", "unknown"),
            "success": not getattr(event, "error", None),
        }
        if getattr(event, "error", None):
            data["error"] = str(event.error)
        self._log("TOOL_CALL_END", data)

    def _on_model_start(self, event: BeforeModelCallEvent) -> None:
        """Log model call start."""
        self._log("MODEL_CALL_START", {
            "message_count": len(getattr(event, "messages", [])),
        })

    def _on_model_end(self, event: AfterModelCallEvent) -> None:
        """Log model call end."""
        self._log("MODEL_CALL_END", {
            "stop_reason": getattr(event, "stop_reason", "unknown"),
            "usage": getattr(event, "usage", {}),
        })
