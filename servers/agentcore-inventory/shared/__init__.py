# =============================================================================
# Shared Module - Common Utilities for All SGA Agents
# =============================================================================
# This module provides shared infrastructure for the 100% Agentic architecture:
#
# - audit_emitter: Agent activity logging (DynamoDB audit trail)
# - a2a_client: A2A protocol client (JSON-RPC 2.0)
# - xray_tracer: X-Ray distributed tracing
#
# Usage:
#   from shared.audit_emitter import AgentAuditEmitter, AgentStatus
#   from shared.strands_a2a_client import StrandsA2AClient, A2AResponse
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

# A2A Client exports (Strands Framework - CLAUDE.md IMMUTABLE)
from shared.strands_a2a_client import (
    StrandsA2AClient,
    A2AClient,  # Alias for StrandsA2AClient
    LocalA2AClient,  # Legacy alias for backward compatibility
    A2AResponse,
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

# Prompt Templates exports (AI Agent Best Practices - Pillar 5)
from shared.prompt_templates import (
    render_prompt,
    render_prompt_safe,
    sanitize_input,
    sanitize_dict,
    wrap_user_input,
    build_context_block,
    INSTRUCTION_HIERARCHY_BLOCK,
    REFUSAL_PATTERN_BLOCK,
)

__all__ = [
    # Audit Emitter
    "AgentAuditEmitter",
    "AgentStatus",
    "AuditEvent",
    "emit_agent_event",
    # A2A Client (Strands Framework)
    "StrandsA2AClient",
    "A2AClient",
    "LocalA2AClient",
    "A2AResponse",
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
    # Prompt Templates (AI Agent Best Practices - Pillar 5)
    "render_prompt",
    "render_prompt_safe",
    "sanitize_input",
    "sanitize_dict",
    "wrap_user_input",
    "build_context_block",
    "INSTRUCTION_HIERARCHY_BLOCK",
    "REFUSAL_PATTERN_BLOCK",
]
