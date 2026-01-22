"""
Faiston SGA Agent Hooks

HookProvider implementations for Strands Agents:
- LoggingHook: Structured logging for all agent events
- MetricsHook: CloudWatch metrics emission
- GuardrailsHook: Shadow mode content moderation
- DebugHook: Intelligent error analysis via Debug Agent (ADR-003)
- SecurityAuditHook: FAIL-CLOSED security validation for agent responses (ADR-003)

Usage:
    from shared.hooks import LoggingHook, MetricsHook, DebugHook, SecurityAuditHook

    agent = Agent(
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=5.0), SecurityAuditHook()]
    )
"""
from .logging_hook import LoggingHook
from .metrics_hook import MetricsHook
from .guardrails_hook import GuardrailsHook
from .debug_hook import DebugHook
from .security_audit_hook import SecurityAuditHook

__all__ = ["LoggingHook", "MetricsHook", "GuardrailsHook", "DebugHook", "SecurityAuditHook"]
