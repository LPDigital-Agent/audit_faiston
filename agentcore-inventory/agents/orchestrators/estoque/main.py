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
# 2. Swarm (nexo_*) → Autonomous 5-agent Swarm for imports
# 2.5. Infrastructure → Deterministic routing for pure infra ops (S3 URLs)
# 3. LLM-based Routing → Natural language + business data queries (100% Agentic)
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

# Swarm response extraction (BUG-020)
# BUG-020 v5: Use _process_swarm_result() for 100% Strands-compliant extraction
from swarm.response_utils import _process_swarm_result

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

You have access to 15+ specialist agents. Each invocation of invoke_specialist
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
"""

# =============================================================================
# Swarm Configuration (Phase 8)
# =============================================================================

USE_SWARM_IMPORT = os.environ.get("USE_SWARM_IMPORT", "true").lower() == "true"

# Actions routed to Swarm when USE_SWARM_IMPORT=true
SWARM_ACTIONS = {
    "nexo_analyze_file",
    "nexo_get_questions",
    "nexo_submit_answers",
    "nexo_execute_import",
    "nexo_learn_from_import",
    "nexo_prepare_processing",
    "nexo_get_prior_knowledge",
    "nexo_get_adaptive_threshold",
}

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
    # S3 presigned URLs (pure infrastructure, no business logic)
    "get_nf_upload_url": ("intake", "get_upload_url"),
    "get_presigned_download_url": ("intake", "get_download_url"),
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
    # Lazy import to avoid circular dependencies
    from tools.s3_client import SGAS3Client

    try:
        if action == "get_nf_upload_url":
            # Generate presigned upload URL for NF document
            filename = payload.get("filename", "document")
            content_type = payload.get("content_type", "application/octet-stream")

            s3 = SGAS3Client()
            key = s3.get_temp_path(filename)
            url_info = s3.generate_upload_url(
                key=key, content_type=content_type, expires_in=3600
            )

            # Rename 'key' to 's3_key' for API consistency (as intake agent does)
            url_info["s3_key"] = url_info.pop("key", key)

            logger.info(
                f"[Infrastructure] Generated upload URL for {filename}: {key}"
            )
            return {
                "success": True,
                "specialist_agent": "intake",
                "response": url_info,
            }

        elif action == "get_presigned_download_url":
            # Generate presigned download URL for existing S3 object
            s3_key = payload.get("s3_key") or payload.get("key")
            if not s3_key:
                return {
                    "success": False,
                    "error": "Missing 's3_key' parameter",
                }

            s3 = SGAS3Client()
            url_info = s3.generate_download_url(key=s3_key, expires_in=3600)

            logger.info(f"[Infrastructure] Generated download URL for {s3_key}")
            return {
                "success": True,
                "specialist_agent": "intake",
                "response": url_info,
            }

        elif action == "record_debug_action":
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
            "suggested_actions": ["retry", "check_s3_permissions", "escalate"],
        }


# =============================================================================
# CONCURRENCY FIX: No cached Swarm instance
# =============================================================================
# Like Strands Agents, Swarms contain multiple internal Agent instances.
# Each Swarm invocation uses these internal agents, which are NOT thread-safe.
#
# To prevent ConcurrencyException on concurrent NEXO import requests,
# we create a NEW Swarm instance per invocation.
#
# The session state dictionary (_swarm_sessions) IS safe to cache because
# it only stores Python dicts, not Agent instances.
# =============================================================================
_swarm_sessions = {}  # session_id -> session state (safe to cache)


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

    ### estoque_control
    Inventory control operations: stock movements, reservations, expeditions,
    transfers, returns, balance queries, asset location tracking.
    Actions: query_balance, create_reservation, cancel_reservation, create_movement,
    process_expedition, create_transfer, query_asset_location

    ### intake
    Document intake and processing: NF (Nota Fiscal) PDF/XML extraction,
    OCR scanning, invoice validation, entry confirmation.
    Actions: process_nf, validate_extraction, confirm_entry, parse_nf_image, get_upload_url

    ### nexo_import
    Smart file import with AI analysis: CSV, XLSX, PDF file analysis,
    column mapping, schema inference, iterative HIL dialogue.
    Actions: analyze_file, get_questions, submit_answers, execute_import

    ### learning
    Memory and pattern learning: prior knowledge retrieval, import pattern
    storage, adaptive thresholds, historical analysis.
    Actions: retrieve_prior_knowledge, store_pattern, get_adaptive_threshold

    ### validation
    Data validation: schema validation, type checking, constraint verification,
    business rule validation.
    Actions: validate_data, validate_schema, check_constraints

    ### reconciliacao
    Inventory reconciliation: counting campaigns, divergence analysis,
    adjustment proposals, physical vs system comparison.
    Actions: start_campaign, submit_count, analyze_divergences, propose_adjustment

    ### compliance
    Policy and approval workflows: HIL approvals, policy validation,
    audit trail, authorization checks.
    Actions: request_approval, validate_policy, check_authorization

    ### carrier
    Shipping and logistics: carrier quotes, recommendations, shipment tracking,
    delivery scheduling.
    Actions: get_quotes, recommend_carrier, track_shipment

    ### expedition
    Outbound logistics: expedition processing, stock verification,
    separation confirmation, SAP export.
    Actions: process_expedition_request, verify_stock, confirm_separation, complete_expedition

    ### reverse
    Reverse logistics: return processing, condition evaluation,
    origin validation, restocking decisions.
    Actions: process_return, validate_origin, evaluate_condition

    ### observation
    Audit and observations: import observations, audit logging,
    analysis notes, traceability records.
    Actions: generate_observations, log_audit_event

    ### schema_evolution
    Schema management: column type inference, schema changes,
    migration planning, compatibility checks.
    Actions: infer_column_types, propose_schema_change

    ### equipment_research (REMOVED - AUDIT-004/2)
    DEPRECATED: Use enrichment agent instead for equipment lookups.
    Equipment research functionality was replaced by enrichment agent
    which provides web search capability via Tavily AI.

    ### data_import
    Generic data import: bulk imports, SAP imports, preview mode,
    mapping validation.
    Actions: preview_import, execute_import, execute_sap_import

    ### enrichment
    Data enrichment: equipment specs via Tavily AI search,
    part number validation, knowledge base sync.
    Actions: enrich_equipment, enrich_batch, validate_part_number, sync_knowledge_base

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
    available specialist agents, and Swarm status.
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
            "swarm_import": USE_SWARM_IMPORT,
            "hooks_enabled": True,
        },
        "swarm": {
            "enabled": USE_SWARM_IMPORT,
            "agents": [
                "file_analyst",
                "schema_validator",
                "memory_agent",
                "hil_agent",
                "import_executor",
            ],
            "active_sessions": len(_swarm_sessions),
        },
        "specialists": list(RUNTIME_IDS.keys()),
    }


# =============================================================================
# Swarm Integration (Phase 8 - Kept from original)
# =============================================================================


def _create_inventory_swarm():
    """
    Create a NEW Inventory Swarm instance.

    CONCURRENCY FIX: Returns a fresh Swarm instance per invocation.
    Unlike the previous _get_inventory_swarm() which cached a singleton,
    this function creates new internal Agent instances each time.

    This prevents ConcurrencyException when multiple NEXO import requests
    are processed concurrently in the same AgentCore container.
    """
    from swarm.config import create_inventory_swarm, SwarmConfig

    config = SwarmConfig(
        max_handoffs=30,
        max_iterations=50,
        execution_timeout=1800.0,
        node_timeout=300.0,
        enable_meta_tooling=True,
    )
    swarm = create_inventory_swarm(config)
    logger.info("[Orchestrator] Created NEW Inventory Swarm instance")

    return swarm


def _get_swarm_session(session_id: str) -> dict:
    """Get or create session state for Swarm execution."""
    if session_id not in _swarm_sessions:
        _swarm_sessions[session_id] = {
            "context": {},
            "awaiting_response": False,
            "questions": [],
            "import_id": None,
            "round_count": 0,
        }
    return _swarm_sessions[session_id]


def _restore_session_from_payload(session: dict, payload: dict) -> None:
    """
    Restore session context from frontend's session_state payload.

    STATELESS ARCHITECTURE: Frontend stores full state, backend restores.
    This ensures Round 2+ works even if container restarted.

    BUG-020 v15 FIX: Called at start of _invoke_swarm() for non-init actions.
    The frontend passes the full session_state including s3_key, filename,
    and accumulated answers. Without this restoration, a new container
    would have empty session context and fail with S3 NoSuchKey errors.

    Args:
        session: The in-memory session dict to restore into
        payload: The request payload containing session_state from frontend
    """
    frontend_state = payload.get("session_state", {})
    if not frontend_state:
        logger.debug("[v15] No session_state in payload, skipping restoration")
        return

    # Log restoration for debugging
    s3_key_preview = frontend_state.get("s3_key", "")[:50] if frontend_state.get("s3_key") else "None"
    logger.info(
        "[v15] Restoring session from frontend state: s3_key=%s, stage=%s",
        s3_key_preview,
        frontend_state.get("stage", "unknown"),
    )

    # Restore critical context fields for file re-analysis
    if "s3_key" in frontend_state:
        session["context"]["s3_key"] = frontend_state["s3_key"]
    if "filename" in frontend_state:
        session["context"]["filename"] = frontend_state["filename"]

    # Restore file_analysis if present (used by re-analysis)
    file_analysis = frontend_state.get("file_analysis") or {}
    if file_analysis:
        session["context"]["file_analysis"] = file_analysis

    # Restore user responses (accumulated from previous rounds)
    if "answers" in frontend_state:
        session["context"]["user_responses"] = {
            **session["context"].get("user_responses", {}),
            **frontend_state["answers"],
        }

    # Restore column mappings (for validation in later rounds)
    if "column_mappings" in frontend_state:
        session["context"]["column_mappings"] = frontend_state["column_mappings"]

    # Mark session as having pending questions (for Round 2+)
    # This prevents the "No pending questions" error when container restarts
    if frontend_state.get("stage") == "questioning" or frontend_state.get("questions"):
        session["awaiting_response"] = True
        logger.debug("[v15] Set awaiting_response=True from frontend stage/questions")


async def _invoke_swarm(
    action: str,
    payload: dict,
    user_id: str,
    session_id: str,
) -> dict:
    """
    Invoke the Inventory Swarm for NEXO import operations.

    The Swarm handles autonomous multi-agent processing with HIL support.
    """
    # CONCURRENCY FIX: Create NEW Swarm per invocation (not cached singleton)
    swarm = _create_inventory_swarm()
    session = _get_swarm_session(session_id)

    # =========================================================================
    # BUG-020 v15 FIX: Restore session context from frontend's session_state
    # =========================================================================
    # STATELESS ARCHITECTURE: Frontend stores full state between rounds.
    # AgentCore containers are ephemeral - _swarm_sessions may be empty.
    # This restoration ensures Round 2+ works even after container restart.
    # =========================================================================
    _restore_session_from_payload(session, payload)

    # =========================================================================
    # BUG-020 v16 FIX: Ensure s3_key is available for ALL Swarm actions
    # =========================================================================
    # Pre-analysis actions (prior_knowledge, adaptive_threshold) may be called
    # before nexo_analyze_file sets s3_key in context. This ensures s3_key
    # propagates to session context for any action that has it in payload.
    # =========================================================================
    incoming_s3_key = (
        payload.get("s3_key") or
        payload.get("file_path") or
        payload.get("key", "")
    )
    if incoming_s3_key and not session["context"].get("s3_key"):
        session["context"]["s3_key"] = incoming_s3_key
        logger.info("[v16] Propagated s3_key to session: %s", incoming_s3_key[:50])

    logger.info(
        f"[Swarm] Invocation: action={action}, session={session_id}, "
        f"round={session['round_count']}, s3_key={session['context'].get('s3_key', 'NONE')[:30] if session['context'].get('s3_key') else 'NONE'}"
    )

    # Build Swarm context
    swarm_context = {
        "user_id": user_id,
        "session_id": session_id,
        "action": action,
        **session["context"],
    }

    # Build prompt based on action
    if action == "nexo_analyze_file":
        s3_key = payload.get("s3_key") or payload.get("file_path") or payload.get("key", "")
        filename = payload.get("filename", "")

        session["context"] = {
            "s3_key": s3_key,
            "filename": filename,
            "target_table": payload.get("target_table", "inventory_movements"),
            "tenant_id": payload.get("tenant_id", "default"),
        }
        session["round_count"] = 0

        prompt = f"""
        Analyze this file for inventory import using the unified_analyze_file tool.
        - s3_key: "{s3_key}"
        - filename: "{filename}"
        - session_id: "{session_id}"
        Return the tool's response directly as JSON.
        """

    elif action == "nexo_submit_answers":
        if not session["awaiting_response"]:
            # Sandwich Pattern: Include session state for debugging/recovery
            return {
                "success": False,
                "error": "No pending questions for this session",
                "session_id": session_id,
                "error_context": {
                    "error_type": "invalid_session_state",
                    "operation": "nexo_submit_answers",
                    "session_state": {
                        "awaiting_response": session.get("awaiting_response", False),
                        "round_count": session.get("round_count", 0),
                        "has_questions": bool(session.get("questions")),
                    },
                },
                "suggested_actions": ["restart_analysis", "check_session_id", "escalate"],
            }

        user_responses = payload.get("answers", {})
        session["context"]["user_responses"] = {
            **session["context"].get("user_responses", {}),
            **user_responses,
        }
        session["awaiting_response"] = False

        s3_key = session["context"].get("s3_key", "")
        analysis_round = session.get("round_count", 1) + 1

        prompt = f"""
        User provided answers. Re-analyze with:
        - s3_key: "{s3_key}"
        - session_id: "{session_id}"
        - user_responses: {json.dumps(user_responses)}
        - analysis_round: {analysis_round}
        """

    elif action == "nexo_execute_import":
        if not session["context"].get("approval_status"):
            # Sandwich Pattern: Include session state for debugging/recovery
            return {
                "success": False,
                "error": "Import not approved. User approval required.",
                "session_id": session_id,
                "error_context": {
                    "error_type": "approval_required",
                    "operation": "nexo_execute_import",
                    "session_state": {
                        "approval_status": session["context"].get("approval_status"),
                        "round_count": session.get("round_count", 0),
                        "has_mappings": "column_mappings" in session.get("context", {}),
                    },
                },
                "suggested_actions": ["complete_analysis_first", "submit_approval", "review_mappings"],
            }

        prompt = "Execute the approved import and generate audit trail."

    else:
        prompt = f"Execute NEXO action: {action}\nPayload: {json.dumps(payload)}"

    # Invoke Swarm
    session["round_count"] += 1

    try:
        result = swarm(prompt, **swarm_context)

        # BUG-020 v3: Log Swarm result structure for debugging
        logger.info(
            "[Swarm] Result structure: results_keys=%s, status=%s, has_message=%s",
            list(result.results.keys()) if hasattr(result, "results") and result.results else "None",
            getattr(result, "status", "N/A"),
            bool(getattr(result, "message", None)),
        )

        # =====================================================================
        # BUG-020 v8 FIX: 100% Strands-Compliant Response Extraction
        # =====================================================================
        # Uses _process_swarm_result() which extracts from:
        # - result.results["agent_name"].result.message (v8 - CORRECT!)
        # - result.results["agent_name"].result as dict (fallback)
        # - result.entry_point.messages (fallback for tool_result blocks)
        #
        # NOTE: AgentResult.message IS a valid Strands attribute per official SDK!
        # Reference: https://github.com/strands-agents/sdk-python AgentResult dataclass
        # =====================================================================
        response = _process_swarm_result(
            swarm_result=result,
            session=session,
            action="nexo_analyze_file"
        )

        logger.debug(
            "[Swarm] Processed response: success=%s, has_analysis=%s",
            response.get("success"),
            "analysis" in response,
        )

        # =====================================================================
        # BUG-020 v18: SANDWICH PATTERN - Technical vs Business Separation
        # =====================================================================
        # TECHNICAL check: Did Swarm runtime crash? (Code decides)
        # BUSINESS check: success=False with data? (LLM decided, we preserve)
        #
        # The Sandwich Pattern: Code (Technical) → LLM (Business) → Code (Validate)
        # - HTTP requests, JSON parsing, structure validation = Code (deterministic)
        # - Error recovery decisions, retry logic, HIL questions = LLM (reasoning)
        #
        # When LLM returns success=False + valid data, that's a BUSINESS decision
        # (e.g., "I need more info from user before proceeding"). We MUST NOT
        # override it with a hardcoded error response.
        # =====================================================================

        # TECHNICAL: Check if Swarm runtime had an error (infrastructure failure)
        swarm_runtime_error = getattr(result, "status", None) == "error"

        # TECHNICAL: Check if extraction produced ANY valid structure
        # These are the fields that indicate meaningful LLM processing occurred
        has_valid_structure = (
            ("analysis" in response and isinstance(response.get("analysis"), dict))
            or ("questions" in response and isinstance(response.get("questions"), list) and len(response.get("questions", [])) > 0)
            or ("column_mappings" in response and isinstance(response.get("column_mappings"), list))
        )

        # Only trigger CODE error when TECHNICAL failure (runtime crashed, no data)
        # This is a TECHNICAL decision - infrastructure failed, nothing to show user
        if swarm_runtime_error and not has_valid_structure:
            # AUDIT-003: Use debug_error for enriched error analysis
            swarm_technical_error = RuntimeError(f"Swarm TECHNICAL failure: runtime_error={getattr(result, 'status', 'unknown')}, no valid structure extracted")
            debug_error(swarm_technical_error, "swarm_technical_failure", {
                "runtime_status": getattr(result, "status", "unknown"),
                "has_valid_structure": has_valid_structure,
                "session_id": session_id,
                "action": action,
            })
            # Return structured error context - let caller/agent decide recovery
            return {
                "success": False,
                "session_id": session_id,
                "round": session["round_count"],
                "error": "Swarm runtime error - no valid data extracted",
                "error_context": {
                    "error_type": "swarm_runtime_error",
                    "swarm_status": getattr(result, "status", "unknown"),
                    "has_analysis": "analysis" in response,
                    "has_questions": "questions" in response,
                    "recoverable": True,
                },
                "questions": [{
                    "id": "swarm_technical_error",
                    "question": "Ocorreu um erro técnico ao processar o arquivo. Por favor, tente novamente.",
                    "type": "error"
                }],
                "analysis": {
                    "sheets": [],
                    "sheet_count": 0,
                    "total_rows": 0,
                    "recommended_strategy": "manual_review"
                },
                "suggested_actions": ["retry", "check_swarm_logs", "escalate"],
            }

        # BUSINESS: LLM returned success=False with valid data (HIL pause)
        # This is a VALID intermediate state - LLM is asking for user input
        # We MUST preserve the LLM's decision, not override it!
        if not response.get("success") and has_valid_structure:
            logger.info(
                "[Swarm] HIL pause: LLM returned success=False with valid data "
                "(questions=%d, has_analysis=%s, has_mappings=%s) - preserving LLM decision",
                len(response.get("questions", [])),
                "analysis" in response,
                "column_mappings" in response,
            )
            # Fall through - response will be returned as-is below
            # The LLM made a business decision (needs user input), we respect it

        # =====================================================================
        # BUG-021 FIX: SCENARIO 3 - Extraction failed completely
        # =====================================================================
        # When success=False AND no valid structure AND no error field, the
        # extraction failed silently (e.g., Gemini timeout, parsing failure).
        # This is NOT a business decision - it's a technical failure that needs
        # a user-friendly error message.
        # =====================================================================
        if not response.get("success") and not has_valid_structure and not response.get("error"):
            logger.warning(
                "[Swarm] BUG-021 Scenario 3: Extraction failed with no error field. "
                "success=%s, has_valid_structure=%s, response_keys=%s",
                response.get("success"),
                has_valid_structure,
                list(response.keys()),
            )
            response["error"] = (
                "Erro na análise do arquivo. Possíveis causas: "
                "timeout na API de IA, arquivo muito grande, ou formato não suportado. "
                "Tente novamente com um arquivo menor ou em formato diferente."
            )
            response["error_context"] = {
                "error_type": "extraction_failure",
                "operation": action,
                "recoverable": True,
                "suggested_actions": ["retry_with_smaller_file", "try_different_format", "check_cloudwatch_logs"],
            }

        # Check for HIL pause (from _process_swarm_result context update)
        if response.get("stop_action") or session.get("awaiting_response"):
            session["awaiting_response"] = True
            session["questions"] = response.get("questions", [])

        # Check approval status
        if response.get("approval_status") is not None:
            session["context"]["approval_status"] = response["approval_status"]

        # Check completion
        if response.get("import_id"):
            session["import_id"] = response["import_id"]

        # Add session metadata to the processed response
        response["session_id"] = session_id
        response["round"] = session["round_count"]

        return response

    except Exception as e:
        # AUDIT-003: Use debug_error for enriched error analysis
        debug_error(e, f"swarm_{action}", {"session_id": session_id, "action": action, "round": session["round_count"]})
        # Sandwich Pattern: Provide error context for potential LLM recovery decision
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id,
            "round": session["round_count"],
            "error_context": {
                "error_type": type(e).__name__,
                "operation": f"swarm_{action}",
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
                "session_state": {
                    "awaiting_response": session.get("awaiting_response", False),
                    "has_context": bool(session.get("context")),
                },
            },
            "suggested_actions": ["retry", "reset_session", "escalate"],
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
    2. NEXO Swarm actions → Autonomous 5-agent Swarm
    2.5. Infrastructure actions → Deterministic routing for pure infra (S3 URLs)
    3. Natural language or action → LLM-based routing (100% Agentic)

    IMPORTANT: Business data queries (query_balance, query_asset_location, etc.)
    MUST go through Mode 3 (LLM) to maintain 100% Agentic AI principle.
    Only pure infrastructure ops (S3 URLs) bypass LLM via Mode 2.5.

    Args:
        payload: Request with either:
            - prompt: Natural language request
            - action: Direct action name (for Swarm/Infrastructure)
        context: AgentCore context with session_id, identity

    Returns:
        Response from orchestrator, specialist, or Swarm
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

        # Mode 2: Swarm Routing (NEXO imports)
        if action and USE_SWARM_IMPORT and action in SWARM_ACTIONS:
            logger.info(f"[Orchestrator] Swarm routing: {action}")
            return asyncio.run(
                _invoke_swarm(
                    action=action,
                    payload=payload,
                    user_id=user_id,
                    session_id=session_id,
                )
            )

        # Mode 2.5: Infrastructure Actions (DIRECT TOOL CALL - No A2A)
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
                    "action": "Action name (nexo_analyze_file, etc.)",
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
