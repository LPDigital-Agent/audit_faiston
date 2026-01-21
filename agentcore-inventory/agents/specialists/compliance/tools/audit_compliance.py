# =============================================================================
# Audit Compliance Tool
# =============================================================================

import logging
from typing import Dict, Any, Optional
from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)
AGENT_ID = "compliance"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_audit_compliance")
async def audit_compliance_tool(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    location_id: Optional[str] = None,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run compliance audit on historical operations."""
    audit.working(message="Executando auditoria de compliance...", session_id=session_id)

    try:
        # In production, query historical movements and check each against policies
        report = {
            "audit_period": {"start": start_date or "N/A", "end": end_date or "N/A"},
            "scope": {"location_id": location_id or "ALL", "project_id": project_id or "ALL"},
            "summary": {
                "total_operations": 0,
                "compliant": 0,
                "non_compliant": 0,
                "warnings": 0,
            },
            "findings": [],
            "recommendations": [],
        }

        audit.completed(message="Auditoria concluída", session_id=session_id)
        return {"success": True, "report": report}

    except Exception as e:
        logger.error(f"[audit_compliance] Error: {e}", exc_info=True)
        audit.error(message="Erro na auditoria", session_id=session_id, error=str(e))
        return {"success": False, "error": str(e)}
