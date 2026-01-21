# =============================================================================
# Validate Operation Tool
# =============================================================================

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)
AGENT_ID = "compliance"
audit = AgentAuditEmitter(agent_id=AGENT_ID)

# Constants
HIGH_VALUE_THRESHOLD = 5000.0
BULK_QUANTITY_THRESHOLD = 50
BUSINESS_HOURS_START = 8
BUSINESS_HOURS_END = 18
MAX_MOVEMENTS_PER_HOUR = 10

RESTRICTED_LOCATIONS = {"COFRE", "QUARENTENA", "DESCARTE"}


@trace_tool_call("sga_validate_operation")
async def validate_operation_tool(
    operation_type: str,
    part_number: str,
    quantity: int,
    source_location: Optional[str] = None,
    destination_location: Optional[str] = None,
    source_project: Optional[str] = None,
    destination_project: Optional[str] = None,
    total_value: Optional[float] = None,
    user_id: str = "system",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate an operation against compliance policies."""
    audit.working(message=f"Validando operação: {operation_type}", session_id=session_id)

    violations = []
    required_approvals = []
    recommendations = []
    risk_level = "LOW"

    try:
        # 1. Check restricted locations
        if source_location in RESTRICTED_LOCATIONS:
            required_approvals.append({
                "role": "INVENTORY_MANAGER",
                "reason": f"Saída de local {source_location} requer aprovação",
                "type": "restricted_location",
            })

        if destination_location in RESTRICTED_LOCATIONS:
            if destination_location == "DESCARTE":
                required_approvals.append({
                    "role": "DIRECTOR",
                    "reason": "Descarte requer aprovação de Diretor",
                    "type": "discard",
                })
            else:
                required_approvals.append({
                    "role": "INVENTORY_MANAGER",
                    "reason": f"Entrada em local {destination_location} requer aprovação",
                    "type": "restricted_location",
                })

        # 2. Check cross-project restrictions
        if source_project and destination_project and source_project != destination_project:
            required_approvals.append({
                "role": "INVENTORY_MANAGER",
                "reason": "Operação cross-project requer aprovação",
                "type": "cross_project",
            })
            risk_level = "MEDIUM"

        # 3. Check value thresholds
        if total_value and total_value >= HIGH_VALUE_THRESHOLD:
            required_approvals.append({
                "role": "INVENTORY_MANAGER",
                "reason": f"Valor alto (R$ {total_value:,.2f})",
                "type": "high_value",
            })
            risk_level = "HIGH"

        # 4. Check quantity thresholds
        if quantity >= BULK_QUANTITY_THRESHOLD:
            recommendations.append(f"Quantidade elevada ({quantity} unidades). Considere dividir em múltiplas operações.")
            risk_level = max(risk_level, "MEDIUM")

        # 5. Check time restrictions
        now = datetime.utcnow()
        if now.weekday() >= 5:
            recommendations.append("Movimentação em final de semana. Operação será auditada.")
            risk_level = "MEDIUM"
        elif now.hour < BUSINESS_HOURS_START or now.hour >= BUSINESS_HOURS_END:
            recommendations.append(f"Movimentação fora do horário comercial ({BUSINESS_HOURS_START}h-{BUSINESS_HOURS_END}h).")
            risk_level = "MEDIUM"

        # 6. Check operation-specific rules
        if operation_type == "ADJUSTMENT":
            required_approvals.append({
                "role": "INVENTORY_MANAGER",
                "reason": "Ajustes de inventário SEMPRE requerem aprovação",
                "type": "adjustment",
            })

        if operation_type in ["DISCARD", "LOSS"]:
            required_approvals.append({
                "role": "DIRECTOR",
                "reason": f"{operation_type} SEMPRE requer aprovação de Diretor",
                "type": operation_type.lower(),
            })

        # Determine final status
        if violations:
            status = "non_compliant"
            is_compliant = False
            message = f"Operação NÃO conforme: {len(violations)} violação(es)"
        elif required_approvals:
            status = "warning"
            is_compliant = True
            message = f"Operação requer {len(required_approvals)} aprovação(es)"
        else:
            status = "compliant"
            is_compliant = True
            message = "Operação conforme com todas as políticas"

        audit.completed(message=f"Validação: {status}", session_id=session_id)

        return {
            "success": True,
            "is_compliant": is_compliant,
            "status": status,
            "message": message,
            "violations": violations,
            "required_approvals": required_approvals,
            "recommendations": recommendations,
            "risk_level": risk_level,
        }

    except Exception as e:
        logger.error(f"[validate_operation] Error: {e}", exc_info=True)
        audit.error(message="Erro na validação", session_id=session_id, error=str(e))
        return {"success": False, "is_compliant": False, "status": "error", "message": str(e)}
