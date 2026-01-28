"""
Inventory Hub Orchestrator - Central intelligence for SGA file ingestion.

Lazy import for AgentCore timeout compliance: All heavy imports are deferred
to first request, allowing module to load fast enough for AgentCore
Firecracker runtime (30-second initialization timeout).

A2A Protocol patterns: Changed from BedrockAgentCoreApp (HTTP, port 8080)
to A2AServer (A2A, port 9000). AgentCore expects A2A servers on port 9000
at root path (/).

Architecture:
- Module-level: Only json, logging, os (fast)
- First request: Lazy load all heavy dependencies (Strands, A2AServer, hooks, services, tools)
- Subsequent requests: Use cached imports (instant)
- Server: uvicorn on port 9000 with A2AServer (A2A protocol)
"""

import json
import logging
import os
from typing import Any

# =============================================================================
# Minimal module-level setup (FAST - must complete in <5s)
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# Lazy Import Cache (AgentCore timeout compliance + A2A Protocol patterns)
# =============================================================================
# All heavy imports are cached here on first request.
# This moves the ~20s import cost from module load to first request.

_lazy_loaded = False
_Agent = None
_A2AServer = None
_AgentSkill = None
_config = None
_prompts = None
_services = None
_tools = None
_utils = None
_intake_tools = None
_hooks = None
_shared = None


def _ensure_lazy_imports() -> None:
    """
    Load all heavy imports on first call, then cache for subsequent calls.

    Lazy import for AgentCore timeout compliance: By deferring imports to the
    first request, we allow the module to initialize quickly (<5s) so
    AgentCore doesn't kill the container before the server can start.

    A2A Protocol patterns: Also loads A2AServer for the protocol migration.
    """
    global _lazy_loaded, _Agent, _A2AServer, _AgentSkill
    global _config, _prompts, _services, _tools
    global _utils, _intake_tools, _hooks, _shared

    if _lazy_loaded:
        return

    logger.info("[InventoryHub] Loading lazy imports (first request)...")

    # Strands Agent (heavy - loads Google AI SDK)
    from strands import Agent as _AgentClass
    _Agent = _AgentClass

    # A2A Protocol patterns: Server for AgentCore A2A protocol
    from strands.multiagent.a2a import A2AServer as _A2AServerClass
    from a2a.types import AgentSkill as _AgentSkillClass
    _A2AServer = _A2AServerClass
    _AgentSkill = _AgentSkillClass

    # Config module: Agent identity and constants
    from agents.orchestrators.inventory_hub import config as _config_module
    _config = _config_module

    # Prompts module: SYSTEM_PROMPT and runtime injection
    from agents.orchestrators.inventory_hub import prompts as _prompts_module
    _prompts = _prompts_module

    # Services module: Business logic
    from agents.orchestrators.inventory_hub import services as _services_module
    _services = _services_module

    # Tools module: ALL_TOOLS for agent registration
    from agents.orchestrators.inventory_hub import tools as _tools_module
    _tools = _tools_module

    # External agent utilities
    from agents import utils as _utils_module
    _utils = _utils_module

    # Intake tools (presigned URLs, file verification)
    from agents.tools import intake_tools as _intake_tools_module
    _intake_tools = _intake_tools_module

    # Hooks (logging, metrics, debug, security audit)
    _hooks = {
        "LoggingHook": None,
        "MetricsHook": None,
        "DebugHook": None,
        "SecurityAuditHook": None,
    }
    from shared.hooks.logging_hook import LoggingHook
    from shared.hooks.metrics_hook import MetricsHook
    from shared.hooks.debug_hook import DebugHook
    from shared.hooks.security_audit_hook import SecurityAuditHook
    _hooks["LoggingHook"] = LoggingHook
    _hooks["MetricsHook"] = MetricsHook
    _hooks["DebugHook"] = DebugHook
    _hooks["SecurityAuditHook"] = SecurityAuditHook

    # Shared utilities
    _shared = {
        "debug_error": None,
        "extract_text_from_message": None,
        "CognitiveError": None,
    }
    from shared.debug_utils import debug_error
    from shared.message_utils import extract_text_from_message
    from shared.cognitive_error_handler import CognitiveError
    _shared["debug_error"] = debug_error
    _shared["extract_text_from_message"] = extract_text_from_message
    _shared["CognitiveError"] = CognitiveError

    _lazy_loaded = True
    logger.info("[InventoryHub] Lazy imports loaded successfully")


def create_inventory_hub(
    user_id: str = "anonymous",
    session_id: str = "default-session",
) -> Any:
    """
    Create the Inventory Hub orchestrator as a full Strands Agent.

    This agent handles the NEXO Cognitive Import Pipeline with:
    - File upload URL generation (presigned POST)
    - Upload verification with retry logic
    - File type validation
    - Schema mapping with HIL interview
    - STM + LTM memory for learning

    The system prompt is dynamically prepared with runtime session variables
    (user_id, session_id, current_date) for context-aware operation.

    Args:
        user_id: The authenticated user's ID from Cognito (default: "anonymous").
        session_id: The active import session ID (default: "default-session").

    Returns:
        Strands Agent configured for inventory file ingestion with injected context.
    """
    _ensure_lazy_imports()

    hooks = [
        _hooks["LoggingHook"](log_level=logging.DEBUG, include_payloads=True),
        _hooks["MetricsHook"](namespace="FaistonSGA", emit_to_cloudwatch=True),
        _hooks["DebugHook"](timeout_seconds=30.0),
        _hooks["SecurityAuditHook"](enabled=True),  # FAIL-CLOSED audit trail
    ]

    # Inject runtime session variables into SYSTEM_PROMPT
    prepared_prompt = _prompts.prepare_system_prompt(user_id, session_id)

    # Combine local tools (10) + imported tools (2) = 12 total
    all_agent_tools = _tools.ALL_TOOLS + [
        _intake_tools.request_file_upload_url,
        _intake_tools.verify_file_availability,
    ]

    agent = _Agent(
        name=_config.AGENT_NAME,
        description=_config.AGENT_DESCRIPTION,
        model=_utils.create_gemini_model("inventory_hub"),  # Gemini Flash for speed
        tools=all_agent_tools,
        system_prompt=prepared_prompt,  # Uses runtime-injected variables
        hooks=hooks,
    )

    logger.info(
        f"[InventoryHub] Created {_config.AGENT_NAME} with {len(hooks)} hooks, "
        f"{len(all_agent_tools)} tools, user={user_id}, session={session_id}"
    )
    return agent


def invoke(payload: dict, context=None) -> dict:
    """
    Legacy handler for direct invocation (backward compatibility).

    NOTE: With A2A migration, this function is NO LONGER the entrypoint.
    The A2AServer routes JSON-RPC messages directly to the Strands Agent.
    This function is kept for:
    - Backward compatibility with tests
    - Direct programmatic invocation
    - Reference implementation of the mode-based routing

    Handles three modes:
    1. Mode 1 (health_check): Direct response, no LLM
    2. Mode 2.5 (DIRECT_ACTIONS): Deterministic routing, no LLM
    3. Mode 2 (LLM): Natural language processing via Strands Agent

    Args:
        payload: Request with either:
            - action: "health_check" for system status
            - action: One of DIRECT_ACTIONS for deterministic execution
            - prompt: Natural language request for file operations
        context: Optional context object with session_id, identity (legacy).

    Returns:
        Response dict with operation results.
    """
    # Load lazy imports on first call (AgentCore timeout compliance)
    _ensure_lazy_imports()

    try:
        # Extract context
        session_id = getattr(context, "session_id", "default-session")
        user_id = getattr(context, "user_id", None) or payload.get("user_id", "anonymous")
        action = payload.get("action")
        prompt = payload.get("prompt", payload.get("message", ""))

        logger.info(
            f"[InventoryHub] Invoke: action={action}, session={session_id}, "
            f"user={user_id}, prompt_len={len(prompt)}"
        )

        # Mode 1: Health check (direct response, no LLM)
        if action == "health_check":
            return json.loads(_tools.health_check())

        # Mode 2.5: Direct action routing (deterministic, no LLM)
        if action in _config.DIRECT_ACTIONS:
            logger.info(
                f"[InventoryHub] Mode 2.5 direct action: action={action}, "
                f"user={user_id}, session={session_id}"
            )
            try:
                return _services.handle_direct_action(action, payload, user_id, session_id)
            except _shared["CognitiveError"] as e:
                logger.warning(f"[InventoryHub] CognitiveError in Mode 2.5: {e.technical_message}")
                return {
                    "success": False,
                    "error": e.human_explanation,
                    "technical_error": e.technical_message,
                    "suggested_fix": e.suggested_fix,
                    "specialist_agent": "intake",
                    "agent_id": _config.AGENT_ID,
                }

        # Mode 2: Natural language processing via LLM
        try:
            prompt = _services.validate_payload(payload)
        except _shared["CognitiveError"] as e:
            logger.warning(f"[InventoryHub] CognitiveError in payload validation: {e.technical_message}")
            return {
                "success": False,
                "error": e.human_explanation,
                "technical_error": e.technical_message,
                "suggested_fix": e.suggested_fix,
                "usage": {
                    "prompt": "Natural language request (e.g., 'Quero fazer upload de um arquivo CSV')",
                    "action": f"Action name (health_check, {', '.join(_config.DIRECT_ACTIONS)})",
                },
                "agent_id": _config.AGENT_ID,
            }

        # Create fresh agent instance with injected runtime context (concurrency fix)
        agent = create_inventory_hub(user_id=user_id, session_id=session_id)

        # Invoke agent with prompt
        result = agent(
            prompt,
            user_id=user_id,
            session_id=session_id,
        )

        # Extract response
        if hasattr(result, "message"):
            message = result.message
            # Try to parse as JSON if structured
            if isinstance(message, str) and message.strip().startswith("{"):
                try:
                    parsed = json.loads(message)
                    action = payload.get("action", "")
                    validated = _services.validate_llm_response(parsed, action)
                    return {
                        "success": True,
                        "specialist_agent": "llm",
                        "response": validated,
                        "agent_id": _config.AGENT_ID,
                    }
                except json.JSONDecodeError:
                    pass
                except ValueError:
                    raise

            # Detect tool failure in LLM text responses
            failure_indicators = [
                "não consegui",
                "não foi possível",
                "houve um problema",
                "houve um erro",
                "falhou",
                "failed",
                "error occurred",
                "A2A call failed",
            ]
            message_text = _shared["extract_text_from_message"](message)
            message_lower = message_text.lower()
            is_failure_message = any(indicator in message_lower for indicator in failure_indicators)

            if is_failure_message:
                logger.warning(f"[InventoryHub] LLM text indicates tool failure: {message_text[:200]}")
                return {
                    "success": False,
                    "error": message_text,
                    "error_type": "TOOL_FAILURE",
                    "specialist_agent": "llm",
                    "agent_id": _config.AGENT_ID,
                }

            return {
                "success": True,
                "specialist_agent": "llm",
                "response": message_text,
                "agent_id": _config.AGENT_ID,
            }

        return {
            "success": True,
            "specialist_agent": "llm",
            "response": str(result),
            "agent_id": _config.AGENT_ID,
        }

    except Exception as e:
        # Check if it's a CognitiveError (lazy loaded)
        CognitiveError = _shared.get("CognitiveError") if _shared else None
        if CognitiveError and isinstance(e, CognitiveError):
            logger.warning(
                f"[InventoryHub] CognitiveError in invoke: "
                f"type={e.error_type}, recoverable={e.recoverable}, "
                f"message={e.technical_message[:100]}"
            )
            # Get AGENT_ID safely
            agent_id = _config.AGENT_ID if _config else "inventory-hub"
            return {
                "success": False,
                "error": e.human_explanation,
                "technical_error": e.technical_message,
                "suggested_fix": e.suggested_fix,
                "specialist_agent": "inventory_hub",
                "agent_id": agent_id,
                "debug_analysis": {
                    "error_signature": f"inventory_hub_{e.error_type}",
                    "error_type": e.error_type,
                    "technical_explanation": e.technical_message,
                    "root_causes": [],
                    "debugging_steps": [e.suggested_fix] if e.suggested_fix else [],
                    "documentation_links": [],
                    "similar_patterns": [],
                    "recoverable": e.recoverable,
                    "suggested_action": "retry" if e.recoverable else "escalate",
                    "llm_powered": True,
                },
                "error_context": {
                    "error_type": e.error_type,
                    "operation": "inventory_hub_invoke",
                    "recoverable": e.recoverable,
                },
            }

        # Generic exception handling
        debug_error_fn = _shared.get("debug_error") if _shared else None
        agent_id = _config.AGENT_ID if _config else "inventory-hub"

        if debug_error_fn:
            enrichment = debug_error_fn(e, "inventory_hub_invoke", {
                "action": payload.get("action"),
                "prompt_len": len(payload.get("prompt", "")),
            })
            analysis = enrichment.get("analysis", {}) if enrichment.get("enriched") else {}
        else:
            enrichment = {"enriched": False}
            analysis = {}

        error_type = type(e).__name__
        is_recoverable = isinstance(e, (ValueError, TimeoutError, ConnectionError, OSError))
        return {
            "success": False,
            "error": str(e),
            "technical_error": str(e),
            "agent_id": agent_id,
            "debug_analysis": {
                "error_signature": f"inventory_hub_{error_type}",
                "error_type": error_type,
                "technical_explanation": analysis.get("technical_explanation", str(e)),
                "human_explanation": analysis.get("human_explanation", ""),
                "root_causes": analysis.get("root_causes", []),
                "debugging_steps": analysis.get("debugging_steps", []),
                "documentation_links": analysis.get("documentation_links", []),
                "similar_patterns": analysis.get("similar_patterns", []),
                "recoverable": analysis.get("recoverable", is_recoverable),
                "suggested_action": analysis.get("suggested_action", "retry" if is_recoverable else "escalate"),
                "llm_powered": enrichment.get("enriched", False),
            },
            "error_context": {
                "error_type": error_type,
                "operation": "inventory_hub_invoke",
                "recoverable": is_recoverable,
            },
        }


# =============================================================================
# Module Exports (Backward Compatibility)
# =============================================================================
# Note: These are lazy-loaded, so they'll be None until _ensure_lazy_imports()
# is called. Tests and external code should import from the submodules directly.


def _get_agent_id():
    """Lazy accessor for AGENT_ID."""
    _ensure_lazy_imports()
    return _config.AGENT_ID


def _get_agent_name():
    """Lazy accessor for AGENT_NAME."""
    _ensure_lazy_imports()
    return _config.AGENT_NAME


def _get_runtime_id():
    """Lazy accessor for RUNTIME_ID."""
    _ensure_lazy_imports()
    return _config.RUNTIME_ID


def _get_system_prompt():
    """Lazy accessor for SYSTEM_PROMPT."""
    _ensure_lazy_imports()
    return _prompts.SYSTEM_PROMPT


def _get_prepare_system_prompt():
    """Lazy accessor for prepare_system_prompt."""
    _ensure_lazy_imports()
    return _prompts.prepare_system_prompt


def _get_direct_actions():
    """Lazy accessor for DIRECT_ACTIONS."""
    _ensure_lazy_imports()
    return _config.DIRECT_ACTIONS


def _get_merge_phase3_results():
    """Lazy accessor for _merge_phase3_results (backward compatibility)."""
    _ensure_lazy_imports()
    return _services._merge_phase3_results


def _get_convert_missing_fields_to_questions():
    """Lazy accessor for _convert_missing_fields_to_questions (backward compatibility)."""
    _ensure_lazy_imports()
    return _services._convert_missing_fields_to_questions


# NOTE: For backward compatibility, use these getter functions or import from submodules:
#   from agents.orchestrators.inventory_hub.config import AGENT_ID, AGENT_NAME, RUNTIME_ID
#   from agents.orchestrators.inventory_hub.prompts import SYSTEM_PROMPT, prepare_system_prompt
#   from agents.orchestrators.inventory_hub.services import _merge_phase3_results

__all__ = [
    # Core functions
    "create_inventory_hub",
    "create_app",
    "_start_server",
    "invoke",  # Legacy handler for backward compatibility
    # Lazy accessors (for backward compatibility - prefer direct submodule imports)
    "_get_agent_id",
    "_get_agent_name",
    "_get_runtime_id",
    "_get_system_prompt",
    "_get_prepare_system_prompt",
    "_get_direct_actions",
    "_get_merge_phase3_results",
    "_get_convert_missing_fields_to_questions",
    # Re-export lazy import loader for testing
    "_ensure_lazy_imports",
]


# =============================================================================
# A2A SERVER FACTORY (A2A Protocol patterns)
# =============================================================================
# Creates FastAPI app with A2AServer mounted for AgentCore A2A protocol.
# Port 9000, serve_at_root=True per AgentCore A2A requirements.
# =============================================================================


def create_app():
    """
    Factory function to create FastAPI app with A2AServer.

    A2A Protocol patterns: Migrates from BedrockAgentCoreApp (HTTP, port 8080)
    to A2AServer (A2A protocol, port 9000).

    This function:
    1. Loads lazy imports (first call triggers heavy imports)
    2. Creates the Strands Agent with tools and hooks
    3. Wraps agent in A2AServer for JSON-RPC protocol
    4. Returns FastAPI app with health check endpoint

    Returns:
        FastAPI application ready for uvicorn.
    """
    _ensure_lazy_imports()

    from fastapi import FastAPI

    # Get AGENT_ID for logging
    agent_id = _config.AGENT_ID if _config else "inventory_hub"

    # Create Strands Agent with tools
    agent = create_inventory_hub()

    # Get runtime URL for A2A self-registration
    runtime_url = os.environ.get("AGENTCORE_RUNTIME_URL", "http://127.0.0.1:9000/")

    # Create A2AServer wrapping the agent
    a2a_server = _A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        http_url=runtime_url,
        serve_at_root=True,  # Required for AgentCore
    )

    # Create FastAPI app with health check endpoint
    app = FastAPI(
        title="InventoryHub A2A Server",
        description="Central intelligence for SGA file ingestion",
    )

    @app.get("/ping")
    def ping():
        """Health check endpoint for AgentCore."""
        return {
            "status": "healthy",
            "agent_id": agent_id,
            "protocol": "A2A",
            "port": 9000,
        }

    # Mount A2AServer at root (AgentCore expects A2A at /)
    app.mount("/", a2a_server.to_fastapi_app())

    logger.info(f"[InventoryHub] Created A2A app with agent {agent_id}")
    return app


def _start_server():
    """
    Start the A2A server with uvicorn.

    A2A Protocol patterns: Uses uvicorn on port 9000 for A2A protocol.

    This function is called:
    - When module is run directly: `python -m agents.orchestrators.inventory_hub.main`
    - When module is imported in AgentCore: Detected via AWS_EXECUTION_ENV
    """
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("[InventoryHub] Starting A2A Server on port 9000...")
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=9000)


# =============================================================================
# MODULE-LEVEL EXECUTION (A2A Protocol patterns)
# =============================================================================
# A2A servers must start uvicorn on port 9000. The server is started when:
# 1. Module is run directly: __name__ == "__main__"
# 2. Module is imported in AgentCore: AWS_EXECUTION_ENV is set
#
# CRITICAL (User Feedback A): We use AWS_EXECUTION_ENV check instead of bare
# `else` block to avoid side-effects on import. This allows:
# - Unit tests to import without blocking
# - Local development with explicit `python main.py`
# - AgentCore deployment to auto-start server
# =============================================================================

if __name__ == "__main__":
    # Local development: python -m agents.orchestrators.inventory_hub.main
    _start_server()
# Response format standardization: AWS_EXECUTION_ENV check was redundant.
# AgentCore A2A pattern uses `if __name__ == "__main__"` only.
# Ref: https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/a2a.md
