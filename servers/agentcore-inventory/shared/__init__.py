# =============================================================================
# Shared Module - Common Utilities for All SGA Agents
# =============================================================================
# This module provides shared infrastructure for the 100% Agentic architecture:
#
# - audit_emitter: Agent Room real-time visibility (DynamoDB audit trail)
# - a2a_client: A2A protocol client (JSON-RPC 2.0)
# - xray_tracer: X-Ray distributed tracing
#
# Usage:
#   from shared.audit_emitter import AgentAuditEmitter, AgentStatus
#   from shared.a2a_client import A2AClient, delegate_to_learning
#   from shared.xray_tracer import trace_a2a_call, init_xray_tracing
#
# Architecture: AWS Strands Agents + AWS Bedrock AgentCore (100% Agentic)
# =============================================================================

# Audit Emitter exports
from shared.audit_emitter import (
    AgentAuditEmitter,
    AgentStatus,
    AuditEvent,
    emit_agent_event,
)

# A2A Client exports
from shared.a2a_client import (
    A2AClient,
    A2AMessage,
    A2AResponse,
    delegate_to_learning,
    delegate_to_validation,
    delegate_to_schema_evolution,
)

# X-Ray Tracer exports
from shared.xray_tracer import (
    init_xray_tracing,
    trace_a2a_call,
    trace_memory_operation,
    trace_tool_call,
    trace_subsegment,
    add_trace_annotation,
    add_trace_metadata,
)

# Genesis Kernel exports (NEXO Mind DNA)
from shared.genesis_kernel import (
    GeneticLaw,
    UserRole,
    get_role_priority,
    MemoryOriginType,
    MemorySourceType,
    LawAlignment,
    check_command_safety,
    validate_tutor_action,
    check_autopoiesis_approval,
    is_consolidation_period,
    get_system_prompt_core,
    get_reflection_prompt,
    NexoMemoryMetadata,
    interpret_hebbian_weight,
    should_forget,
)

# Memory Manager exports (NEXO Mind Hippocampus)
from shared.memory_manager import (
    AgentMemoryManager,
    observe_patterns,
    learn_pattern,
)

# Debug Utils exports (ADR-004: Global Error Capture)
from shared.debug_utils import (
    debug_error,
    debug_error_async,
    debug_json_error,
    debug_http_error,
    debug_aws_error,
)

# Message Utils exports (BUG-039: Strands Message Extraction)
from shared.message_utils import (
    extract_text_from_message,
    safe_message_lower,
)

__all__ = [
    # Audit Emitter
    "AgentAuditEmitter",
    "AgentStatus",
    "AuditEvent",
    "emit_agent_event",
    # A2A Client
    "A2AClient",
    "A2AMessage",
    "A2AResponse",
    "delegate_to_learning",
    "delegate_to_validation",
    "delegate_to_schema_evolution",
    # X-Ray Tracer
    "init_xray_tracing",
    "trace_a2a_call",
    "trace_memory_operation",
    "trace_tool_call",
    "trace_subsegment",
    "add_trace_annotation",
    "add_trace_metadata",
    # Genesis Kernel (NEXO Mind DNA)
    "GeneticLaw",
    "UserRole",
    "get_role_priority",
    "MemoryOriginType",
    "MemorySourceType",
    "LawAlignment",
    "check_command_safety",
    "validate_tutor_action",
    "check_autopoiesis_approval",
    "is_consolidation_period",
    "get_system_prompt_core",
    "get_reflection_prompt",
    "NexoMemoryMetadata",
    "interpret_hebbian_weight",
    "should_forget",
    # Memory Manager (NEXO Mind Hippocampus)
    "AgentMemoryManager",
    "observe_patterns",
    "learn_pattern",
    # Debug Utils (ADR-004: Global Error Capture)
    "debug_error",
    "debug_error_async",
    "debug_json_error",
    "debug_http_error",
    "debug_aws_error",
    # Message Utils (BUG-039: Strands Message Extraction)
    "extract_text_from_message",
    "safe_message_lower",
]
