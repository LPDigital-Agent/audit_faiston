# =============================================================================
# Faiston Inventory Orchestrator Agent (ADR-002 Architecture)
# =============================================================================
# This is a STRANDS AGENT, not a Python wrapper of agents.
#
# ARCHITECTURE PRINCIPLES (per ADR-002):
# 1. Orchestrators ARE Agents - Full Strands Agent with hooks, session, output
# 2. Specialists at Same Level - All agents are peers, not parent-child
# 3. No Routing Tables in Prompts - LLM decides based on tool descriptions
# 4. AgentCoreMemorySessionManager - Persistent session state
#
# ROUTING:
# - LLM (Gemini Flash) decides which specialist to invoke based on intent
# - The invoke_specialist tool describes each agent's capabilities
# - No hardcoded ACTION_TO_SPECIALIST mapping (breaking change per ADR-002)
#
# MODES:
# 1. Health Check → System status
# 2. Infrastructure → Deterministic routing for pure infra ops (S3 URLs)
# 3. LLM-based Routing → Natural language + business data queries (100% Agentic)
#
# NOTE: Swarm integration was removed during cleanup for complete refactor.
#       Specialist agents (except debug) were also removed.
#
# Reference:
# - https://strandsagents.com/latest/
# - docs/adr/ADR-002-faiston-agent-ecosystem.md
# =============================================================================

import asyncio
import json
import logging
import os
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool, ToolContext

# Agent utilities
from agents.utils import create_gemini_model, AGENT_VERSION, extract_json

# Configuration - CONSOLIDATED: Use shared A2AClient (BUG-022 fix)
from shared.a2a_client import A2AClient, RUNTIME_IDS
from shared.data_contracts import ensure_dict

# Direct tool imports for Infrastructure Actions (bypass A2A for deterministic ops)
# NOTE: Import is done lazily in _handle_infrastructure_action() to avoid circular deps

# Hooks (Phase 1 ADR-002)
from shared.hooks.logging_hook import LoggingHook
from shared.hooks.metrics_hook import MetricsHook
from shared.hooks.guardrails_hook import GuardrailsHook
from shared.hooks.debug_hook import DebugHook

# AUDIT-003: Global error capture for Debug Agent enrichment
from shared.debug_utils import debug_error

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import OrchestratorResponse

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "inventory_management"
AGENT_NAME = "FaistonInventoryOrchestrator"
AGENT_DESCRIPTION = """
Intelligent orchestrator for Faiston Inventory Management (SGA).
Routes requests to specialist agents based on user intent.
Uses LLM reasoning to select the appropriate specialist.
"""

# =============================================================================
# System Prompt (No Routing Tables - LLM Decides from Tool Descriptions)
# =============================================================================

SYSTEM_PROMPT = """
# Faiston Inventory Management Orchestrator

You are the central intelligence for the SGA (Sistema de Gestao de Ativos).
Your role is to understand user requests and delegate to the appropriate specialist agent.

## Your Workflow

1. **Understand**: Analyze the user's intent from their message
2. **Select**: Choose the right specialist agent using the invoke_specialist tool
3. **Invoke**: Call the specialist with appropriate action and payload
4. **Return**: Provide the specialist's response to the user

## Decision Making

You have access to the debug specialist agent. Each invocation of invoke_specialist
requires you to specify:
- agent_id: Which specialist handles this domain
- action: What operation to perform
- payload: Parameters for the operation

The tool description tells you what each agent does. Trust your reasoning.

## Response Format

Always return structured JSON responses with:
- success: boolean
- specialist_agent: which agent handled the request
- response: the actual result data
- error: (if failed) error message

## Important

- Do NOT ask the user which agent to use - decide based on context
- Do NOT list agents to the user - just route to the right one
- Focus on UNDERSTANDING the request, not on explaining your routing

## Note

Currently only the debug agent is available. Other specialists were removed
during cleanup for complete refactor.
"""

# =============================================================================
# Infrastructure Actions (Deterministic Routing - No LLM Needed)
# =============================================================================
#
# IMPORTANT: Only INFRASTRUCTURE operations go here!
# ALL business data queries MUST use LLM → A2A → MCP Gateway → DB
# This maintains the 100% Agentic AI principle for business logic.
#
# Infrastructure ops are pure technical operations (S3 URLs, health checks)
# that don't require LLM reasoning but DO need specialist agent execution.
#
INFRASTRUCTURE_ACTIONS = {
    # BUG-027: Debug analytics (pure logging, no LLM needed)
    "record_debug_action": ("debug", "record_action"),
}

def _handle_infrastructure_action(action: str, payload: dict) -> dict:
    """
    Handle infrastructure actions directly without A2A protocol.

    BUG-017 FIX: A2A calls pass through the specialist's LLM which wraps
    the tool result in conversational text. For infrastructure operations
    like S3 presigned URLs, we need raw JSON responses.

    This function imports and calls the tool functions directly, bypassing
    the A2A protocol entirely for deterministic infrastructure operations.

    Args:
        action: Infrastructure action name (from INFRASTRUCTURE_ACTIONS)
        payload: Action parameters (filename, content_type, etc.)

    Returns:
        Raw JSON response dict (not LLM-wrapped)
    """
    try:
        if action == "record_debug_action":
            # BUG-027: Record debug action analytics (pure logging, no LLM)
            from shared.debug_analytics import record_debug_action as _record_debug_action

            debug_action = payload.get("debug_action")
            error_signature = payload.get("error_signature", "unknown")
            error_type = payload.get("error_type", "unknown")
            suggested_action = payload.get("suggested_action", "retry")
            debug_analysis = payload.get("debug_analysis")
            user_id = payload.get("user_id", "unknown")
            session_id = payload.get("session_id", "unknown")

            if not debug_action:
                return {
                    "success": False,
                    "error": "Missing 'debug_action' parameter",
                }

            # Record via debug_analytics module (CloudWatch + DynamoDB)
            _record_debug_action(
                action=debug_action,
                error_signature=error_signature,
                error_type=error_type,
                suggested_action=suggested_action,
                user_id=user_id,
                session_id=session_id,
                debug_analysis=debug_analysis,
            )

            logger.info(
                f"[Infrastructure] Recorded debug action: {debug_action} "
                f"(error_type={error_type}, user={user_id})"
            )
            return {
                "success": True,
                "specialist_agent": "debug",
                "response": {
                    "message": "Debug action recorded successfully",
                    "action": debug_action,
                    "error_signature": error_signature,
                },
            }

        else:
            # Unknown infrastructure action (shouldn't happen)
            return {
                "success": False,
                "error": f"Unknown infrastructure action: {action}",
            }

    except Exception as e:
        # AUDIT-003: Use debug_error for enriched error analysis
        debug_error(e, f"infrastructure_{action}", {"action": action, "payload_keys": list(payload.keys()) if payload else []})
        # Sandwich Pattern: Provide error context for potential LLM recovery decision
        return {
            "success": False,
            "error": str(e),
            "action": action,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": f"infrastructure_{action}",
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_permissions", "escalate"],
        }


# =============================================================================
# Specialist Invocation Tool
# =============================================================================


def _build_agent_runtime_arn(agent_id: str) -> Optional[str]:
    """Build AgentCore runtime ARN from agent ID."""
    runtime_id = RUNTIME_IDS.get(agent_id)
    if not runtime_id:
        return None

    region = os.environ.get("AWS_REGION", "us-east-2")
    account_id = os.environ.get("AWS_ACCOUNT_ID", "377311924364")
    return f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{runtime_id}"


async def _invoke_agent_via_a2a(
    agent_id: str,
    action: str,
    payload: dict,
    session_id: str,
    user_id: str,
) -> dict:
    """
    Invoke a specialist agent via A2A Protocol using shared A2AClient.

    ARCHITECTURE CONSOLIDATION (BUG-022 FIX):
    This function now delegates to shared/a2a_client.py which contains:
    - Comprehensive response parsing (message parts, artifacts, tool_results)
    - BUG-022 fix: No double-encoding of JSON responses
    - BUG-012 fix: Artifact extraction per A2A Protocol spec
    - Environment-aware RUNTIME_IDS (dev/prod switching)
    - AWS adaptive retry with exponential backoff

    Args:
        agent_id: Target specialist agent ID
        action: Action to perform
        payload: Action parameters
        session_id: Session ID for context
        user_id: User ID for context propagation

    Returns:
        Response dict from specialist with keys:
        - success: bool
        - specialist_agent: str
        - response: dict (parsed response data)
        - error: str (if success=False)
    """
    # Validate agent exists in RUNTIME_IDS
    if agent_id not in RUNTIME_IDS:
        return {
            "success": False,
            "error": f"Unknown agent: {agent_id}",
            "available_agents": list(RUNTIME_IDS.keys()),
        }

    # Build payload with action and user context
    full_payload = {
        "action": action,
        "user_id": user_id,
        **payload,
    }

    logger.info(f"[Orchestrator] Invoking {agent_id} via shared A2AClient: action={action}")

    try:
        # Use shared A2AClient (SINGLE SOURCE OF TRUTH)
        client = A2AClient()
        result = await client.invoke_agent(
            agent_id=agent_id,
            payload=full_payload,
            session_id=session_id,
            timeout=300.0,  # 5 minutes for Gemini with Thinking mode
        )

        if result.success:
            # Parse response - the shared client already handles BUG-022 unwrapping
            response_data = result.response

            # Try to parse as JSON if it's a string
            if isinstance(response_data, str) and response_data.strip():
                try:
                    # Strip markdown code blocks before parsing
                    clean_text = extract_json(response_data)
                    parsed = json.loads(clean_text)
                    response_data = parsed
                except (json.JSONDecodeError, TypeError):
                    # Keep as string wrapped in dict if not valid JSON
                    response_data = {"message": response_data}

            return {
                "success": True,
                "specialist_agent": agent_id,
                "response": response_data if isinstance(response_data, dict) else {"message": str(response_data)},
            }
        else:
            return {
                "success": False,
                "specialist_agent": agent_id,
                "error": result.error or "Unknown error from specialist",
            }

    except Exception as e:
        # AUDIT-003: Use debug_error for enriched error analysis
        debug_error(e, "orchestrator_a2a_invocation", {"agent_id": agent_id, "payload_keys": list(payload.keys()) if payload else []})
        return {
            "success": False,
            "specialist_agent": agent_id,
            "error": str(e),
        }


@tool(context=True)
async def invoke_specialist(
    agent_id: str,
    action: str,
    payload: dict,
    tool_context: ToolContext,
) -> dict:
    """
    Invoke a specialist agent to handle a specific task.

    This is the primary routing mechanism. Select the appropriate agent
    based on the user's request and the agent capabilities below.

    ## Available Specialist Agents:

    ### debug
    Error analysis and debugging: Deep error analysis with root cause identification,
    documentation search, pattern matching from historical errors, resolution storage.
    Actions: analyze_error, search_documentation, query_memory_patterns, store_resolution,
    search_stackoverflow, search_github_issues

    NOTE: Other specialist agents were removed during cleanup for complete refactor.
    Only debug agent is currently available.

    Args:
        agent_id: ID of the specialist agent to invoke
        action: Action to perform on the specialist
        payload: Parameters for the action (varies by agent)
        tool_context: Strands ToolContext (injected automatically)

    Returns:
        Dict with success status, specialist_agent, and response data
    """
    # Extract context from invocation_state (hidden from LLM)
    user_id = tool_context.invocation_state.get("user_id", "unknown")
    session_id = tool_context.invocation_state.get("session_id", "default-session")
    request_id = tool_context.tool_use.get("toolUseId", "unknown")

    logger.info(
        f"[Orchestrator] Routing: agent={agent_id}, action={action}, "
        f"user={user_id}, session={session_id}, request={request_id}"
    )

    result = await _invoke_agent_via_a2a(
        agent_id=agent_id,
        action=action,
        payload=payload,
        session_id=session_id,
        user_id=user_id,
    )

    result["request_id"] = request_id
    return result


@tool
def health_check() -> dict:
    """
    Check orchestrator health status.

    Returns system information including version, architecture type,
    and available specialist agents.
    """
    return {
        "success": True,
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "git_commit": os.environ.get("GIT_COMMIT_SHA", "unknown"),
        "deployed_at": os.environ.get("DEPLOYED_AT", "unknown"),
        "architecture": "adr-002-strands-orchestrator",
        "features": {
            "hooks_enabled": True,
        },
        "specialists": list(RUNTIME_IDS.keys()),
        "note": "Specialist agents removed during cleanup. Only debug available.",
    }


# =============================================================================
# Orchestrator Factory
# =============================================================================


def create_orchestrator() -> Agent:
    """
    Create the Inventory Orchestrator as a full Strands Agent.

    This is NOT a Python wrapper - it's a proper Strands Agent with:
    - AgentCoreMemorySessionManager (future)
    - HookProvider implementations for logging, metrics, guardrails
    - Structured output capability
    - LLM-based routing (no hardcoded tables)
    """
    # Feature: Guardrails in shadow mode
    guardrail_id = os.environ.get("GUARDRAIL_ID")

    hooks = [
        LoggingHook(log_level=logging.INFO),
        MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        DebugHook(timeout_seconds=30.0),  # TIMEOUT-FIX: Maximum for Gemini Pro
    ]

    if guardrail_id:
        hooks.append(GuardrailsHook(guardrail_id=guardrail_id, shadow_mode=True))

    orchestrator = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model("orchestrator"),  # Gemini Flash for speed
        tools=[invoke_specialist, health_check],
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
        structured_output_model=OrchestratorResponse,  # AUDIT-001: Strands structured output
    )

    logger.info(f"[Orchestrator] Created {AGENT_NAME} with {len(hooks)} hooks")
    return orchestrator


# =============================================================================
# BedrockAgentCoreApp Entrypoint
# =============================================================================

app = BedrockAgentCoreApp()

# =============================================================================
# CONCURRENCY FIX: No cached orchestrator instance
# =============================================================================
# Strands Agents are STATEFUL and do NOT support concurrent invocations.
# The SDK raises ConcurrencyException if the same Agent instance is invoked
# while already processing a request.
#
# AgentCore Runtime may send concurrent requests to the same container,
# so we MUST create a NEW Agent instance per request.
#
# Reference: Strands SDK AWS Lambda deployment pattern
# https://strandsagents.com/latest/user-guide/deploy/deploy_to_aws_lambda/
#
# Trade-off: ~100-200ms overhead per request for Agent instantiation
# vs. guaranteed thread-safety and no ConcurrencyException errors.
# =============================================================================


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """
    Main entrypoint for AgentCore Runtime.

    Routing Modes:
    1. Health check → Direct response
    2. Infrastructure actions → Deterministic routing for pure infra (S3 URLs)
    3. Natural language or action → LLM-based routing (100% Agentic)

    IMPORTANT: Business data queries (query_balance, query_asset_location, etc.)
    MUST go through Mode 3 (LLM) to maintain 100% Agentic AI principle.
    Only pure infrastructure ops (S3 URLs) bypass LLM via Mode 2.

    Args:
        payload: Request with either:
            - prompt: Natural language request
            - action: Direct action name (for Infrastructure)
        context: AgentCore context with session_id, identity

    Returns:
        Response from orchestrator or specialist
    """
    action = payload.get("action")
    prompt = payload.get("prompt") or payload.get("message")
    session_id = getattr(context, "session_id", None) or payload.get("session_id", "default-session")

    # Extract user identity
    try:
        from shared.identity_utils import extract_user_identity

        user = extract_user_identity(context, payload)
        user_id = user.user_id
    except Exception as e:
        logger.warning(f"[Orchestrator] Identity extraction failed: {e}")
        user_id = payload.get("user_id", "unknown")

    logger.info(
        f"[Orchestrator] Request: action={action}, prompt={prompt[:50] if prompt else None}, "
        f"user={user_id}, session={session_id}"
    )

    try:
        # Mode 1: Health Check
        if action in ("health_check", "health"):
            return health_check()

        # Mode 2: Infrastructure Actions (DIRECT TOOL CALL - No A2A)
        # BUG-017 FIX: A2A calls pass through specialist's LLM which wraps
        # responses in conversational text. For infrastructure ops like S3
        # presigned URLs, we call the tool functions directly for raw JSON.
        #
        # NOTE: Only S3/infrastructure ops - business data MUST go through LLM
        # This preserves the 100% Agentic AI principle for all business logic.
        if action and action in INFRASTRUCTURE_ACTIONS:
            logger.info(f"[Orchestrator] Infrastructure direct call: {action}")
            return _handle_infrastructure_action(action=action, payload=payload)

        # Mode 3: LLM-based Routing (Natural Language or Direct Action)
        # CONCURRENCY FIX: Create NEW Agent per request (not cached singleton)
        # This prevents ConcurrencyException when AgentCore sends concurrent requests
        orchestrator = create_orchestrator()

        # Build the prompt for the LLM
        if prompt:
            llm_prompt = prompt
        elif action:
            # Convert action to natural language for LLM routing
            llm_prompt = f"Execute the '{action}' operation with these parameters: {json.dumps(payload)}"
        else:
            # Sandwich Pattern: Input validation error with guidance
            return {
                "success": False,
                "error": "Missing 'action' or 'prompt' in request",
                "usage": {
                    "prompt": "Natural language request",
                    "action": "Action name (health_check, etc.)",
                },
                "error_context": {
                    "error_type": "missing_required_parameter",
                    "operation": "orchestrator_invoke",
                    "received_params": list(payload.keys()) if payload else [],
                },
                "suggested_actions": ["provide_action_name", "provide_natural_language_prompt"],
            }

        logger.info(f"[Orchestrator] LLM routing: {llm_prompt[:100]}...")

        # Invoke orchestrator with context in invocation_state
        result = orchestrator(
            llm_prompt,
            user_id=user_id,  # Hidden from LLM, available to tools
            session_id=session_id,  # Hidden from LLM, available to tools
        )

        # Extract response
        if hasattr(result, "message"):
            try:
                # Handle both dict (already parsed) and string (needs parsing)
                if isinstance(result.message, dict):
                    return result.message
                # Strip markdown code blocks before parsing (LLM may wrap JSON)
                clean_message = extract_json(result.message)
                parsed = json.loads(clean_message)

                # BUG-022 FIX: If we got a string back, it was double-encoded
                # json.loads on '"success"' returns the string "success", not a dict
                # We need to unwrap again to get the actual dict
                if isinstance(parsed, str):
                    logger.warning("[BUG-022] Double-encoded response detected, unwrapping")
                    try:
                        parsed = json.loads(parsed)
                    except json.JSONDecodeError:
                        # If second parse fails, return as wrapped string
                        return {
                            "success": True,
                            "response": parsed,
                            "agent_id": AGENT_ID,
                        }

                return parsed
            except (json.JSONDecodeError, TypeError):
                return {
                    "success": True,
                    "response": result.message,
                    "agent_id": AGENT_ID,
                }

        return {
            "success": True,
            "response": str(result),
            "agent_id": AGENT_ID,
        }

    except Exception as e:
        # AUDIT-003: Use debug_error for enriched error analysis
        debug_error(e, f"orchestrator_{action or 'llm_routing'}", {"action": action, "agent_id": AGENT_ID})
        # Sandwich Pattern: Provide error context for potential LLM recovery decision
        return {
            "success": False,
            "error": str(e),
            "agent_id": AGENT_ID,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": f"orchestrator_{action or 'llm_routing'}",
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_agent_health", "escalate"],
        }


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "app",
    "create_orchestrator",
    "invoke",
    "AGENT_ID",
    "AGENT_NAME",
]


# =============================================================================
# Main (for local testing)
# =============================================================================

if __name__ == "__main__":
    app.run()
