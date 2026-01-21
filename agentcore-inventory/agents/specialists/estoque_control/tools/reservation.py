# =============================================================================
# Reservation Tools
# =============================================================================
# Create and cancel inventory reservations.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "estoque_control"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_create_reservation")
async def create_reservation_tool(
    part_number: str,
    quantity: int,
    project_id: str,
    chamado_id: Optional[str] = None,
    serial_numbers: Optional[List[str]] = None,
    source_location_id: str = "ESTOQUE_CENTRAL",
    destination_location_id: Optional[str] = None,
    requested_by: str = "system",
    notes: Optional[str] = None,
    ttl_hours: int = 72,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a reservation for assets.

    Args:
        part_number: Part number to reserve
        quantity: Quantity to reserve
        project_id: Project/client this reservation is for
        chamado_id: Optional ticket/chamado ID
        serial_numbers: Optional specific serials to reserve
        source_location_id: Location to reserve from
        destination_location_id: Optional final destination
        requested_by: User who requested the reservation
        notes: Optional notes
        ttl_hours: TTL for reservation (default 72h)
        session_id: Optional session ID for audit

    Returns:
        Reservation result with details
    """
    audit.working(
        message=f"Criando reserva: {quantity}x {part_number}",
        session_id=session_id,
    )

    try:
        # 1. Check available balance
        balance = await _get_balance(
            part_number=part_number,
            location_id=source_location_id,
            project_id=project_id,
        )

        if balance.get("available", 0) < quantity:
            return {
                "success": False,
                "message": f"Saldo insuficiente. Disponível: {balance.get('available', 0)}, Solicitado: {quantity}",
                "data": {"balance": balance},
            }

        # 2. Check if cross-project (different project owns the stock)
        is_cross_project = balance.get("owner_project_id") and balance.get("owner_project_id") != project_id
        requires_hil = is_cross_project

        # 3. Generate reservation ID
        reservation_id = _generate_id("RES")
        now = _now_iso()
        ttl_timestamp = int(datetime.utcnow().timestamp()) + (ttl_hours * 3600)

        # 4. Create reservation record
        reservation_data = {
            "reservation_id": reservation_id,
            "part_number": part_number,
            "quantity": quantity,
            "project_id": project_id,
            "chamado_id": chamado_id,
            "serial_numbers": serial_numbers or [],
            "source_location_id": source_location_id,
            "destination_location_id": destination_location_id,
            "status": "PENDING_APPROVAL" if requires_hil else "ACTIVE",
            "requested_by": requested_by,
            "notes": notes,
            "created_at": now,
            "ttl": ttl_timestamp,
        }

        # 5. If HIL required, create approval task
        hil_task_id = None
        if requires_hil:
            hil_task_id = await _create_hil_task(
                task_type="APPROVAL_RESERVATION",
                title=f"Aprovar reserva cross-project: {part_number}",
                entity_type="RESERVATION",
                entity_id=reservation_id,
                requested_by=requested_by,
                details={
                    "part_number": part_number,
                    "quantity": quantity,
                    "project_id": project_id,
                    "source_project": balance.get("owner_project_id", "N/A"),
                },
            )
            reservation_data["hil_task_id"] = hil_task_id

        # 6. Save reservation
        await _store_reservation(reservation_data)

        # 7. If not HIL, update reserved balance
        if not requires_hil:
            await _update_reserved_balance(
                part_number=part_number,
                location_id=source_location_id,
                project_id=project_id,
                quantity_delta=quantity,
            )

        audit.completed(
            message=f"Reserva {'criada' if not requires_hil else 'aguardando aprovação'}: {reservation_id}",
            session_id=session_id,
            details={"reservation_id": reservation_id, "requires_hil": requires_hil},
        )

        return {
            "success": True,
            "reservation_id": reservation_id,
            "message": "Reserva criada com sucesso" if not requires_hil else "Reserva aguardando aprovação",
            "requires_hil": requires_hil,
            "hil_task_id": hil_task_id,
            "data": {
                "reservation_id": reservation_id,
                "status": reservation_data["status"],
                "ttl_hours": ttl_hours,
            },
        }

    except Exception as e:
        logger.error(f"[create_reservation] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao criar reserva",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "message": f"Erro ao criar reserva: {str(e)}",
        }


@trace_tool_call("sga_cancel_reservation")
async def cancel_reservation_tool(
    reservation_id: str,
    cancelled_by: str = "system",
    reason: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel an active reservation.

    Args:
        reservation_id: Reservation ID to cancel
        cancelled_by: User cancelling
        reason: Cancellation reason
        session_id: Optional session ID for audit

    Returns:
        Cancellation result
    """
    audit.working(
        message=f"Cancelando reserva: {reservation_id}",
        session_id=session_id,
    )

    try:
        # Get reservation
        reservation = await _get_reservation(reservation_id)

        if not reservation:
            return {
                "success": False,
                "message": f"Reserva {reservation_id} não encontrada",
            }

        if reservation.get("status") not in ["ACTIVE", "PENDING_APPROVAL"]:
            return {
                "success": False,
                "message": f"Reserva não pode ser cancelada. Status: {reservation.get('status')}",
            }

        # Update status
        now = _now_iso()
        await _update_reservation_status(
            reservation_id=reservation_id,
            status="CANCELLED",
            cancelled_by=cancelled_by,
            cancelled_at=now,
            cancellation_reason=reason,
        )

        # Release reserved balance (if was active)
        if reservation.get("status") == "ACTIVE":
            await _update_reserved_balance(
                part_number=reservation["part_number"],
                location_id=reservation["source_location_id"],
                project_id=reservation["project_id"],
                quantity_delta=-reservation["quantity"],
            )

        audit.completed(
            message=f"Reserva cancelada: {reservation_id}",
            session_id=session_id,
        )

        return {
            "success": True,
            "reservation_id": reservation_id,
            "message": "Reserva cancelada com sucesso",
            "data": {
                "reservation_id": reservation_id,
                "previous_status": reservation.get("status"),
                "cancelled_at": now,
            },
        }

    except Exception as e:
        logger.error(f"[cancel_reservation] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao cancelar reserva",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "message": f"Erro ao cancelar reserva: {str(e)}",
        }


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_balance(
    part_number: str,
    location_id: str,
    project_id: str,
) -> Dict[str, Any]:
    """Get balance from database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        return await db.get_balance(
            part_number=part_number,
            location_id=location_id,
            project_id=project_id,
        ) or {"total": 0, "reserved": 0, "available": 0}
    except ImportError:
        return {"total": 0, "reserved": 0, "available": 0}


async def _store_reservation(reservation_data: Dict[str, Any]) -> None:
    """Store reservation in database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.put_reservation(reservation_data)
    except ImportError:
        logger.warning("[reservation] DBClient not available")


async def _get_reservation(reservation_id: str) -> Optional[Dict[str, Any]]:
    """Get reservation from database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        return await db.get_reservation(reservation_id)
    except ImportError:
        return None


async def _update_reservation_status(
    reservation_id: str,
    status: str,
    **kwargs,
) -> None:
    """Update reservation status."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.update_reservation(
            reservation_id=reservation_id,
            updates={"status": status, **kwargs},
        )
    except ImportError:
        logger.warning("[reservation] DBClient not available")


async def _update_reserved_balance(
    part_number: str,
    location_id: str,
    project_id: str,
    quantity_delta: int,
) -> None:
    """Update reserved balance."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.update_balance(
            part_number=part_number,
            location_id=location_id,
            project_id=project_id,
            quantity_delta=0,
            reserved_delta=quantity_delta,
        )
    except ImportError:
        logger.warning("[reservation] DBClient not available")


async def _create_hil_task(
    task_type: str,
    title: str,
    entity_type: str,
    entity_id: str,
    requested_by: str,
    details: Dict[str, Any],
) -> Optional[str]:
    """Create HIL approval task."""
    try:
        from tools.hil_workflow import HILWorkflowManager
        hil_manager = HILWorkflowManager()
        task = await hil_manager.create_task(
            task_type=task_type,
            title=title,
            entity_type=entity_type,
            entity_id=entity_id,
            requested_by=requested_by,
            payload=details,
        )
        return task.get("task_id")
    except ImportError:
        logger.warning("[reservation] HILWorkflowManager not available")
        return None


def _generate_id(prefix: str) -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
