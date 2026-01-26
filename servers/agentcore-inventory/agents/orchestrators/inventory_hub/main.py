"""
Inventory Hub Orchestrator - Central intelligence for SGA file ingestion.

This is the MINIMAL entrypoint after modular refactoring (Phase 4).
All implementation details extracted to:
- config.py: Agent identity, feature flags, singletons
- prompts.py: SYSTEM_PROMPT template and prepare_system_prompt()
- services/: Business logic (validation, intake, mapping, job, insight)
- tools/: @tool decorated functions (thin wrappers over services)

Architecture: God Object → SOTA Modular Package
- Before: 2,140 lines monolithic
- After: ~200 lines minimal entrypoint
"""

import json
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

# Config module: Agent identity and constants
from agents.orchestrators.inventory_hub.config import (
    AGENT_ID,
    AGENT_NAME,
    AGENT_DESCRIPTION,
    RUNTIME_ID,
    DIRECT_ACTIONS,
)

# Prompts module: SYSTEM_PROMPT and runtime injection
from agents.orchestrators.inventory_hub.prompts import (
    SYSTEM_PROMPT,
    prepare_system_prompt,
)

# Services module: Business logic
from agents.orchestrators.inventory_hub.services import (
    validate_payload,
    validate_llm_response,
    handle_direct_action,
    # Backward compatibility exports (BUG-045: tests depend on these)
    _merge_phase3_results,
    _convert_missing_fields_to_questions,
)

# Tools module: ALL_TOOLS for agent registration
from agents.orchestrators.inventory_hub.tools import (
    ALL_TOOLS,
    health_check,
)

# External dependencies
from agents.utils import create_gemini_model
from agents.tools.intake_tools import (
    request_file_upload_url,
    verify_file_availability,
)
from shared.hooks.logging_hook import LoggingHook
from shared.hooks.metrics_hook import MetricsHook
from shared.hooks.debug_hook import DebugHook
from shared.hooks.security_audit_hook import SecurityAuditHook
from shared.debug_utils import debug_error
from shared.message_utils import extract_text_from_message
from shared.cognitive_error_handler import CognitiveError

logger = logging.getLogger(__name__)


def create_inventory_hub(
    user_id: str = "anonymous",
    session_id: str = "default-session",
) -> Agent:
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
    hooks = [
        LoggingHook(log_level=logging.INFO),
        MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        DebugHook(timeout_seconds=30.0),
        SecurityAuditHook(enabled=True),  # FAIL-CLOSED audit trail
    ]

    # Inject runtime session variables into SYSTEM_PROMPT
    prepared_prompt = prepare_system_prompt(user_id, session_id)

    # Combine local tools (10) + imported tools (2) = 12 total
    all_agent_tools = ALL_TOOLS + [
        request_file_upload_url,
        verify_file_availability,
    ]

    agent = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model("inventory_hub"),  # Gemini Flash for speed
        tools=all_agent_tools,
        system_prompt=prepared_prompt,  # Uses runtime-injected variables
        hooks=hooks,
    )

    logger.info(
        f"[InventoryHub] Created {AGENT_NAME} with {len(hooks)} hooks, "
        f"{len(all_agent_tools)} tools, user={user_id}, session={session_id}"
    )
    return agent


app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """
    Main entrypoint for AgentCore Runtime.

    Handles three modes:
    1. Mode 1 (health_check): Direct response, no LLM
    2. Mode 2.5 (DIRECT_ACTIONS): Deterministic routing, no LLM
    3. Mode 2 (LLM): Natural language processing via Strands Agent

    Args:
        payload: Request with either:
            - action: "health_check" for system status
            - action: One of DIRECT_ACTIONS for deterministic execution
            - prompt: Natural language request for file operations
        context: AgentCore context with session_id, identity

    Returns:
        Response dict with operation results
    """
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
            return json.loads(health_check())

        # Mode 2.5: Direct action routing (deterministic, no LLM)
        if action in DIRECT_ACTIONS:
            logger.info(
                f"[InventoryHub] Mode 2.5 direct action: action={action}, "
                f"user={user_id}, session={session_id}"
            )
            try:
                return handle_direct_action(action, payload, user_id, session_id)
            except CognitiveError as e:
                logger.warning(f"[InventoryHub] CognitiveError in Mode 2.5: {e.technical_message}")
                return {
                    "success": False,
                    "error": e.human_explanation,
                    "technical_error": e.technical_message,
                    "suggested_fix": e.suggested_fix,
                    "specialist_agent": "intake",
                    "agent_id": AGENT_ID,
                }

        # Mode 2: Natural language processing via LLM
        try:
            prompt = validate_payload(payload)
        except CognitiveError as e:
            logger.warning(f"[InventoryHub] CognitiveError in payload validation: {e.technical_message}")
            return {
                "success": False,
                "error": e.human_explanation,
                "technical_error": e.technical_message,
                "suggested_fix": e.suggested_fix,
                "usage": {
                    "prompt": "Natural language request (e.g., 'Quero fazer upload de um arquivo CSV')",
                    "action": f"Action name (health_check, {', '.join(DIRECT_ACTIONS)})",
                },
                "agent_id": AGENT_ID,
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
                    validated = validate_llm_response(parsed, action)
                    return {
                        "success": True,
                        "specialist_agent": "llm",
                        "response": validated,
                        "agent_id": AGENT_ID,
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
            message_text = extract_text_from_message(message)
            message_lower = message_text.lower()
            is_failure_message = any(indicator in message_lower for indicator in failure_indicators)

            if is_failure_message:
                logger.warning(f"[InventoryHub] LLM text indicates tool failure: {message_text[:200]}")
                return {
                    "success": False,
                    "error": message_text,
                    "error_type": "TOOL_FAILURE",
                    "specialist_agent": "llm",
                    "agent_id": AGENT_ID,
                }

            return {
                "success": True,
                "specialist_agent": "llm",
                "response": message_text,
                "agent_id": AGENT_ID,
            }

        return {
            "success": True,
            "specialist_agent": "llm",
            "response": str(result),
            "agent_id": AGENT_ID,
        }

    except CognitiveError as e:
        logger.warning(
            f"[InventoryHub] CognitiveError in invoke: "
            f"type={e.error_type}, recoverable={e.recoverable}, "
            f"message={e.technical_message[:100]}"
        )
        return {
            "success": False,
            "error": e.human_explanation,
            "technical_error": e.technical_message,
            "suggested_fix": e.suggested_fix,
            "specialist_agent": "inventory_hub",
            "agent_id": AGENT_ID,
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

    except Exception as e:
        enrichment = debug_error(e, "inventory_hub_invoke", {
            "action": payload.get("action"),
            "prompt_len": len(payload.get("prompt", "")),
        })

        analysis = enrichment.get("analysis", {}) if enrichment.get("enriched") else {}

        error_type = type(e).__name__
        is_recoverable = isinstance(e, (ValueError, TimeoutError, ConnectionError, OSError))
        return {
            "success": False,
            "error": str(e),
            "technical_error": str(e),
            "agent_id": AGENT_ID,
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

__all__ = [
    # Core entrypoints
    "app",
    "create_inventory_hub",
    "invoke",
    # Agent identity (re-exported from config.py)
    "AGENT_ID",
    "AGENT_NAME",
    "RUNTIME_ID",
    # Prompt (re-exported from prompts.py)
    "SYSTEM_PROMPT",
    "prepare_system_prompt",
    # Constants (re-exported from config.py)
    "DIRECT_ACTIONS",
    # Backward compatibility (BUG-045: tests import from main.py)
    "_merge_phase3_results",
    "_convert_missing_fields_to_questions",
]


if __name__ == "__main__":
    app.run()
