# =============================================================================
# Expedition Tool
# =============================================================================
# Process outgoing shipments from inventory.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "estoque_control"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_process_expedition")
async def process_expedition_tool(
    reservation_id: Optional[str] = None,
    part_number: Optional[str] = None,
    quantity: int = 1,
    serial_numbers: Optional[List[str]] = None,
    source_location_id: str = "ESTOQUE_CENTRAL",
    destination: str = "",
    project_id: Optional[str] = None,
    chamado_id: Optional[str] = None,
    recipient_name: str = "",
    recipient_contact: str = "",
    shipping_method: str = "HAND_DELIVERY",
    processed_by: str = "system",
    notes: Optional[str] = None,
    evidence_keys: Optional[List[str]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process an expedition (outgoing shipment).

    Can be based on a reservation or ad-hoc.

    Args:
        reservation_id: Optional reservation to fulfill
        part_number: Part number (required if no reservation)
        quantity: Quantity to ship
        serial_numbers: Specific serials to ship
        source_location_id: Location shipping from
        destination: Destination address/description
        project_id: Project/client
        chamado_id: Ticket ID
        recipient_name: Who will receive
        recipient_contact: Contact info
        shipping_method: How it will be shipped
        processed_by: User processing
        notes: Additional notes
        evidence_keys: S3 keys for evidence documents
        session_id: Optional session ID for audit

    Returns:
        Expedition result with movement details
    """
    audit.working(
        message="Processando expedição...",
        session_id=session_id,
    )

    try:
        # 1. If reservation, load it
        reservation = None
        if reservation_id:
            reservation = await _get_reservation(reservation_id)
            if not reservation:
                return {
                    "success": False,
                    "message": f"Reserva {reservation_id} não encontrada",
                }
            if reservation.get("status") != "ACTIVE":
                return {
                    "success": False,
                    "message": f"Reserva não está ativa. Status: {reservation.get('status')}",
                }

            # Use reservation data
            part_number = reservation["part_number"]
            quantity = reservation["quantity"]
            project_id = reservation["project_id"]
            serial_numbers = reservation.get("serial_numbers") or serial_numbers
            source_location_id = reservation["source_location_id"]
            chamado_id = reservation.get("chamado_id") or chamado_id

        # 2. Validate required fields
        if not part_number:
            return {
                "success": False,
                "message": "part_number é obrigatório",
            }

        # 3. Check balance
        balance = await _get_balance(
            part_number=part_number,
            location_id=source_location_id,
            project_id=project_id,
        )

        # Check available (for non-reservation) or total (for reservation)
        check_field = "available" if not reservation_id else "total"
        if balance.get(check_field, 0) < quantity:
            return {
                "success": False,
                "message": f"Saldo insuficiente. {check_field.title()}: {balance.get(check_field, 0)}, Solicitado: {quantity}",
                "data": {"balance": balance},
            }

        # 4. Create movement record
        movement_id = _generate_id("EXP")
        now = _now_iso()

        movement_data = {
            "movement_id": movement_id,
            "movement_type": "EXIT",
            "part_number": part_number,
            "quantity": -quantity,  # Negative for outgoing
            "serial_numbers": serial_numbers or [],
            "source_location_id": source_location_id,
            "destination": destination,
            "project_id": project_id,
            "chamado_id": chamado_id,
            "reservation_id": reservation_id,
            "recipient_name": recipient_name,
            "recipient_contact": recipient_contact,
            "shipping_method": shipping_method,
            "processed_by": processed_by,
            "notes": notes,
            "evidence_keys": evidence_keys or [],
            "created_at": now,
        }

        # 5. Save movement
        await _store_movement(movement_data)

        # 6. Update balances
        # Decrement total balance
        await _update_balance(
            part_number=part_number,
            location_id=source_location_id,
            project_id=project_id,
            quantity_delta=-quantity,
        )

        # If from reservation, also decrement reserved
        if reservation_id:
            await _update_reserved_balance(
                part_number=part_number,
                location_id=source_location_id,
                project_id=project_id,
                quantity_delta=-quantity,
            )

            # Mark reservation as fulfilled
            await _update_reservation_status(
                reservation_id=reservation_id,
                status="FULFILLED",
                fulfilled_at=now,
                fulfilled_by_movement=movement_id,
            )

        # 7. Update asset status if serial numbers
        for serial in (serial_numbers or []):
            await _update_asset_status(
                serial_number=serial,
                new_status="IN_TRANSIT",
                location_id=None,  # No longer in stock
                movement_id=movement_id,
            )

        audit.completed(
            message=f"Expedição processada: {quantity}x {part_number}",
            session_id=session_id,
            details={
                "movement_id": movement_id,
                "quantity": quantity,
                "destination": destination,
            },
        )

        return {
            "success": True,
            "movement_id": movement_id,
            "message": f"Expedição processada com sucesso. {quantity}x {part_number} enviado.",
            "data": {
                "movement_id": movement_id,
                "movement_type": "EXIT",
                "quantity": quantity,
                "destination": destination,
                "shipping_method": shipping_method,
                "reservation_fulfilled": reservation_id,
            },
        }

    except Exception as e:
        logger.error(f"[process_expedition] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao processar expedição",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "message": f"Erro ao processar expedição: {str(e)}",
        }


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_reservation(reservation_id: str) -> Optional[Dict[str, Any]]:
    """Get reservation from database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        return await db.get_reservation(reservation_id)
    except ImportError:
        return None


async def _get_balance(
    part_number: str,
    location_id: str,
    project_id: Optional[str],
) -> Dict[str, Any]:
    """Get balance from database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        return await db.get_balance(
            part_number=part_number,
            location_id=location_id,
            project_id=project_id or "ALL",
        ) or {"total": 0, "reserved": 0, "available": 0}
    except ImportError:
        return {"total": 0, "reserved": 0, "available": 0}


async def _store_movement(movement_data: Dict[str, Any]) -> None:
    """Store movement in database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.put_movement(movement_data)
    except ImportError:
        logger.warning("[expedition] DBClient not available")


async def _update_balance(
    part_number: str,
    location_id: str,
    project_id: Optional[str],
    quantity_delta: int,
) -> None:
    """Update total balance."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.update_balance(
            part_number=part_number,
            location_id=location_id,
            project_id=project_id or "UNASSIGNED",
            quantity_delta=quantity_delta,
            reserved_delta=0,
        )
    except ImportError:
        logger.warning("[expedition] DBClient not available")


async def _update_reserved_balance(
    part_number: str,
    location_id: str,
    project_id: Optional[str],
    quantity_delta: int,
) -> None:
    """Update reserved balance."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.update_balance(
            part_number=part_number,
            location_id=location_id,
            project_id=project_id or "UNASSIGNED",
            quantity_delta=0,
            reserved_delta=quantity_delta,
        )
    except ImportError:
        logger.warning("[expedition] DBClient not available")


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
        logger.warning("[expedition] DBClient not available")


async def _update_asset_status(
    serial_number: str,
    new_status: str,
    location_id: Optional[str],
    movement_id: str,
) -> None:
    """Update asset status after movement."""
    try:
        from tools.db_client import DBClient
        db = DBClient()

        asset = await db.get_asset_by_serial(serial_number)
        if not asset:
            return

        updates = {
            "status": new_status,
            "last_movement_id": movement_id,
            "updated_at": _now_iso(),
        }

        if location_id:
            updates["location_id"] = location_id

        await db.update_asset(
            asset_id=asset["asset_id"],
            updates=updates,
        )
    except ImportError:
        logger.warning("[expedition] DBClient not available")


def _generate_id(prefix: str) -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
