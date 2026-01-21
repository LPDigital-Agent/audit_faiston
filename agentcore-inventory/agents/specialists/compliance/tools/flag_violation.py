# =============================================================================
# Flag Violation Tool
# =============================================================================

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)
AGENT_ID = "compliance"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_flag_violation")
async def flag_violation_tool(
    entity_type: str,
    entity_id: str,
    violation_type: str,
    description: str,
    severity: str = "MEDIUM",
    flagged_by: str = "system",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Flag a compliance violation for review."""
    audit.working(message=f"Registrando violação: {violation_type}", session_id=session_id)

    try:
        import uuid
        flag_id = f"FLAG_{uuid.uuid4().hex[:12].upper()}"
        now = datetime.utcnow().isoformat() + "Z"

        flag_data = {
            "flag_id": flag_id,
            "related_entity_type": entity_type,
            "related_entity_id": entity_id,
            "violation_type": violation_type,
            "description": description,
            "severity": severity,
            "status": "OPEN",
            "flagged_by": flagged_by,
            "created_at": now,
        }

        # Store flag
        try:
            from tools.db_client import DBClient
            db = DBClient()
            await db.put_compliance_flag(flag_data)
        except ImportError:
            logger.warning("[flag_violation] DBClient not available")

        # Create HIL task for severe violations
        hil_task_id = None
        if severity in ["HIGH", "CRITICAL"]:
            try:
                from tools.hil_workflow import HILWorkflowManager
                hil_manager = HILWorkflowManager()
                task = await hil_manager.create_task(
                    task_type="ESCALATION",
                    title=f"Violação de Compliance: {violation_type}",
                    entity_type="COMPLIANCE_FLAG",
                    entity_id=flag_id,
                    requested_by=flagged_by,
                    priority="URGENT" if severity == "CRITICAL" else "HIGH",
                )
                hil_task_id = task.get("task_id")
            except ImportError:
                logger.warning("[flag_violation] HILWorkflowManager not available")

        audit.completed(
            message=f"Violação registrada: {flag_id} ({severity})",
            session_id=session_id,
            details={"flag_id": flag_id, "severity": severity},
        )

        return {
            "success": True,
            "flag_id": flag_id,
            "severity": severity,
            "hil_task_id": hil_task_id,
            "message": f"Violação registrada com severidade {severity}",
        }

    except Exception as e:
        logger.error(f"[flag_violation] Error: {e}", exc_info=True)
        audit.error(message="Erro ao registrar violação", session_id=session_id, error=str(e))
        return {"success": False, "error": str(e)}
