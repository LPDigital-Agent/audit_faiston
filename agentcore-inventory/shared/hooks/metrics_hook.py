# =============================================================================
# Metrics Hook for Strands Agents
# =============================================================================
# Emits CloudWatch metrics for agent performance monitoring.
#
# Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/
# =============================================================================

import logging
import time
from typing import Dict, Optional

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    BeforeInvocationEvent,
    AfterInvocationEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
)

logger = logging.getLogger(__name__)


class MetricsHook(HookProvider):
    """
    CloudWatch metrics hook for Strands Agents.

    Emits metrics:
    - agent_invocation_count
    - agent_invocation_duration_ms
    - tool_call_count
    - tool_call_duration_ms
    - tool_call_errors

    Usage:
        agent = Agent(hooks=[MetricsHook(namespace="FaistonSGA")])
    """

    def __init__(
        self,
        namespace: str = "FaistonSGA",
        emit_to_cloudwatch: bool = True,
    ):
        """
        Initialize MetricsHook.

        Args:
            namespace: CloudWatch namespace for metrics
            emit_to_cloudwatch: Whether to emit to CloudWatch (False for local dev)
        """
        self.namespace = namespace
        self.emit_to_cloudwatch = emit_to_cloudwatch
        self._invocation_start: Optional[float] = None
        self._tool_starts: Dict[str, float] = {}
        self._cloudwatch_client = None

    def _get_cloudwatch_client(self):
        """Lazy load CloudWatch client."""
        if self._cloudwatch_client is None and self.emit_to_cloudwatch:
            try:
                import boto3
                self._cloudwatch_client = boto3.client("cloudwatch", region_name="us-east-2")
            except Exception as e:
                logger.warning(f"[MetricsHook] Failed to create CloudWatch client: {e}")
        return self._cloudwatch_client

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register callbacks for metrics collection."""
        registry.add_callback(BeforeInvocationEvent, self._on_invocation_start)
        registry.add_callback(AfterInvocationEvent, self._on_invocation_end)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_start)
        registry.add_callback(AfterToolCallEvent, self._on_tool_end)

    def _emit_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[Dict[str, str]] = None,
    ) -> None:
        """Emit a metric to CloudWatch."""
        client = self._get_cloudwatch_client()
        if not client:
            logger.debug(f"[MetricsHook] {metric_name}={value} {unit}")
            return

        try:
            metric_data = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
            }
            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in dimensions.items()
                ]

            client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data],
            )
        except Exception as e:
            logger.warning(f"[MetricsHook] Failed to emit metric {metric_name}: {e}")

    def _on_invocation_start(self, event: BeforeInvocationEvent) -> None:
        """Record invocation start time."""
        self._invocation_start = time.time()
        agent_name = getattr(event.agent, "name", "unknown")
        self._emit_metric(
            "agent_invocation_count",
            1,
            "Count",
            {"AgentName": agent_name},
        )

    def _on_invocation_end(self, event: AfterInvocationEvent) -> None:
        """Emit invocation duration metric."""
        if self._invocation_start:
            duration_ms = (time.time() - self._invocation_start) * 1000
            agent_name = getattr(event.agent, "name", "unknown")
            self._emit_metric(
                "agent_invocation_duration_ms",
                duration_ms,
                "Milliseconds",
                {"AgentName": agent_name},
            )
            self._invocation_start = None

    def _on_tool_start(self, event: BeforeToolCallEvent) -> None:
        """Record tool call start time."""
        tool_name = getattr(event, "tool_name", "unknown")
        self._tool_starts[tool_name] = time.time()
        self._emit_metric(
            "tool_call_count",
            1,
            "Count",
            {"ToolName": tool_name},
        )

    def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        """Emit tool call duration and error metrics."""
        tool_name = getattr(event, "tool_name", "unknown")

        # Duration metric
        if tool_name in self._tool_starts:
            duration_ms = (time.time() - self._tool_starts[tool_name]) * 1000
            self._emit_metric(
                "tool_call_duration_ms",
                duration_ms,
                "Milliseconds",
                {"ToolName": tool_name},
            )
            del self._tool_starts[tool_name]

        # Error metric
        if getattr(event, "error", None):
            self._emit_metric(
                "tool_call_errors",
                1,
                "Count",
                {"ToolName": tool_name},
            )
