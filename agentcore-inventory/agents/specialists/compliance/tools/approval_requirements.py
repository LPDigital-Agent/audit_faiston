# =============================================================================
# Approval Requirements Tool
# =============================================================================

import logging
from typing import Dict, Any, Optional
from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)
AGENT_ID = "compliance"
audit = AgentAuditEmitter(agent_id=AGENT_ID)

# Approval role hierarchy
APPROVAL_REQUIREMENTS = {
    "ENTRY": {
        "default": "INVENTORY_OPERATOR",
        "high_value": "INVENTORY_MANAGER",
        "threshold": 5000.0,
    },
    "EXIT": {
        "default": "INVENTORY_OPERATOR",
        "restricted_location": "INVENTORY_MANAGER",
    },
    "TRANSFER": {
        "default": "INVENTORY_OPERATOR",
        "cross_project": "INVENTORY_MANAGER",
        "restricted_location": "INVENTORY_MANAGER",
    },
    "ADJUSTMENT": {
        "default": "INVENTORY_MANAGER",
        "always_required": True,
    },
    "DISCARD": {
        "default": "DIRECTOR",
        "always_required": True,
    },
    "LOSS": {
        "default": "DIRECTOR",
        "always_required": True,
    },
    "RESERVATION": {
        "default": "INVENTORY_OPERATOR",
        "cross_project": "INVENTORY_MANAGER",
    },
}


@trace_tool_call("sga_get_approval_requirements")
async def get_approval_requirements_tool(
    operation_type: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get approval requirements for an operation type."""
    audit.working(message=f"Consultando requisitos: {operation_type}", session_id=session_id)

    try:
        requirements = APPROVAL_REQUIREMENTS.get(
            operation_type.upper(),
            {"default": "INVENTORY_OPERATOR"},
        )

        audit.completed(message=f"Requisitos consultados: {operation_type}", session_id=session_id)

        return {
            "success": True,
            "operation_type": operation_type,
            "requirements": requirements,
        }

    except Exception as e:
        logger.error(f"[get_approval_requirements] Error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
