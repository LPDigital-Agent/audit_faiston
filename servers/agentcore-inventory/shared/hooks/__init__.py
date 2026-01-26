"""
Faiston SGA Agent Hooks

HookProvider implementations for Strands Agents:
- LoggingHook: Structured logging for all agent events
- MetricsHook: CloudWatch metrics emission
- GuardrailsHook: Shadow mode content moderation
- DebugHook: Intelligent error analysis via Debug Agent (ADR-003)
- ResultValidationHook: Self-validating agent pattern with auto-correction

Usage:
    from shared.hooks import LoggingHook, MetricsHook, DebugHook, ResultValidationHook
    from shared.validators import AGENT_VALIDATORS

    validators = AGENT_VALIDATORS.get("schema_mapper", [])
    agent = Agent(
        hooks=[
            LoggingHook(),
            MetricsHook(),
            DebugHook(timeout_seconds=5.0),
            ResultValidationHook(validators=validators, max_retries=3),
        ]
    )
"""
from .logging_hook import LoggingHook
from .metrics_hook import MetricsHook
from .guardrails_hook import GuardrailsHook
from .debug_hook import DebugHook
from .result_validation_hook import ResultValidationHook

__all__ = [
    "LoggingHook",
    "MetricsHook",
    "GuardrailsHook",
    "DebugHook",
    "ResultValidationHook",
]
