# =============================================================================
# Check Approval Status Tool
# =============================================================================

import logging
from typing import Dict, Any, Optional
from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)
AGENT_ID = "compliance"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_check_approval")
async def check_approval_status_tool(
    entity_type: str,
    entity_id: str,
    required_role: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Check if an entity has the required approval."""
    audit.working(message=f"Verificando aprovação para {entity_type} {entity_id}", session_id=session_id)

    try:
        from tools.hil_workflow import HILWorkflowManager
        manager = HILWorkflowManager()
        tasks = manager.get_tasks_for_entity(entity_type, entity_id)

        for task in tasks:
            if task.get("status") == "APPROVED":
                return {
                    "success": True,
                    "has_approval": True,
                    "approved_by": task.get("processed_by"),
                    "approved_at": task.get("processed_at"),
                    "task_id": task.get("task_id"),
                }

        pending = [t for t in tasks if t.get("status") == "PENDING"]
        if pending:
            return {
                "success": True,
                "has_approval": False,
                "status": "pending",
                "pending_task_id": pending[0].get("task_id"),
                "message": "Aprovação pendente",
            }

        return {
            "success": True,
            "has_approval": False,
            "status": "not_requested",
            "message": "Nenhuma aprovação solicitada",
        }

    except ImportError:
        logger.warning("[check_approval] HILWorkflowManager not available")
        return {"success": False, "has_approval": False, "status": "error", "message": "HIL manager not available"}
    except Exception as e:
        logger.error(f"[check_approval] Error: {e}", exc_info=True)
        return {"success": False, "has_approval": False, "status": "error", "message": str(e)}
