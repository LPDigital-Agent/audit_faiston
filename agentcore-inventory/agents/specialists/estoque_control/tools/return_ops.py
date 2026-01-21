# =============================================================================
# Return Operations Tool
# =============================================================================
# Process returns (reversas) to inventory.
# Note: File named return_ops.py because 'return' is a Python keyword.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "estoque_control"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_process_return")
async def process_return_tool(
    part_number: str,
    quantity: int,
    serial_numbers: Optional[List[str]] = None,
    destination_location_id: str = "ESTOQUE_CENTRAL",
    project_id: str = "",
    chamado_id: Optional[str] = None,
    original_expedition_id: Optional[str] = None,
    return_reason: str = "",
    condition: str = "GOOD",  # GOOD, DAMAGED, DEFECTIVE
    processed_by: str = "system",
    notes: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a return (reversa).

    Args:
        part_number: Part number being returned
        quantity: Quantity returned
        serial_numbers: Serial numbers returned
        destination_location_id: Where to receive
        project_id: Project context
        chamado_id: Related ticket
        original_expedition_id: Original outgoing movement
        return_reason: Why returned
        condition: Item condition (GOOD, DAMAGED, DEFECTIVE)
        processed_by: User processing
        notes: Additional notes
        session_id: Optional session ID for audit

    Returns:
        Return result with movement details
    """
    audit.working(
        message=f"Processando reversa: {quantity}x {part_number}",
        session_id=session_id,
    )

    try:
        # 1. Validate condition
        valid_conditions = ["GOOD", "DAMAGED", "DEFECTIVE"]
        if condition not in valid_conditions:
            condition = "GOOD"

        # 2. Create movement record
        movement_id = _generate_id("RET")
        now = _now_iso()

        movement_data = {
            "movement_id": movement_id,
            "movement_type": "RETURN",
            "part_number": part_number,
            "quantity": quantity,  # Positive for incoming
            "serial_numbers": serial_numbers or [],
            "destination_location_id": destination_location_id,
            "project_id": project_id,
            "chamado_id": chamado_id,
            "original_expedition_id": original_expedition_id,
            "return_reason": return_reason,
            "condition": condition,
            "processed_by": processed_by,
            "notes": notes,
            "created_at": now,
        }

        # 3. Save movement
        await _store_movement(movement_data)

        # 4. Update balance
        await _update_balance(
            part_number=part_number,
            location_id=destination_location_id,
            project_id=project_id or "UNASSIGNED",
            quantity_delta=quantity,
        )

        # 5. Update asset status if serial numbers
        status_map = {
            "GOOD": "IN_STOCK",
            "DAMAGED": "DAMAGED",
            "DEFECTIVE": "DEFECTIVE",
        }
        new_status = status_map.get(condition, "IN_STOCK")

        for serial in (serial_numbers or []):
            await _update_asset_status(
                serial_number=serial,
                new_status=new_status,
                location_id=destination_location_id,
                movement_id=movement_id,
            )

        audit.completed(
            message=f"Reversa processada: {quantity}x {part_number} ({condition})",
            session_id=session_id,
            details={
                "movement_id": movement_id,
                "condition": condition,
            },
        )

        return {
            "success": True,
            "movement_id": movement_id,
            "message": f"Reversa processada com sucesso. {quantity}x {part_number} recebido.",
            "data": {
                "movement_id": movement_id,
                "movement_type": "RETURN",
                "quantity": quantity,
                "condition": condition,
                "destination": destination_location_id,
            },
        }

    except Exception as e:
        logger.error(f"[process_return] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao processar reversa",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "message": f"Erro ao processar reversa: {str(e)}",
        }


# =============================================================================
# Helper Functions
# =============================================================================

async def _store_movement(movement_data: Dict[str, Any]) -> None:
    """Store movement in database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.put_movement(movement_data)
    except ImportError:
        logger.warning("[return_ops] DBClient not available")


async def _update_balance(
    part_number: str,
    location_id: str,
    project_id: str,
    quantity_delta: int,
) -> None:
    """Update total balance."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.update_balance(
            part_number=part_number,
            location_id=location_id,
            project_id=project_id,
            quantity_delta=quantity_delta,
            reserved_delta=0,
        )
    except ImportError:
        logger.warning("[return_ops] DBClient not available")


async def _update_asset_status(
    serial_number: str,
    new_status: str,
    location_id: str,
    movement_id: str,
) -> None:
    """Update asset status after return."""
    try:
        from tools.db_client import DBClient
        db = DBClient()

        asset = await db.get_asset_by_serial(serial_number)
        if not asset:
            # Create new asset if not found
            asset_id = _generate_id("AST")
            await db.put_asset({
                "asset_id": asset_id,
                "serial_number": serial_number,
                "status": new_status,
                "location_id": location_id,
                "last_movement_id": movement_id,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            })
            return

        await db.update_asset(
            asset_id=asset["asset_id"],
            updates={
                "status": new_status,
                "location_id": location_id,
                "last_movement_id": movement_id,
                "updated_at": _now_iso(),
            },
        )
    except ImportError:
        logger.warning("[return_ops] DBClient not available")


def _generate_id(prefix: str) -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
