# =============================================================================
# Transfer Tool
# =============================================================================
# Create transfers between inventory locations.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "estoque_control"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_create_transfer")
async def create_transfer_tool(
    part_number: str,
    quantity: int,
    source_location_id: str,
    destination_location_id: str,
    project_id: str,
    serial_numbers: Optional[List[str]] = None,
    requested_by: str = "system",
    notes: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a transfer between locations.

    Args:
        part_number: Part number to transfer
        quantity: Quantity to transfer
        source_location_id: Source location
        destination_location_id: Destination location
        project_id: Project context
        serial_numbers: Specific serials to transfer
        requested_by: User requesting
        notes: Additional notes
        session_id: Optional session ID for audit

    Returns:
        Transfer result with movement details
    """
    audit.working(
        message=f"Criando transferência: {quantity}x {part_number}",
        session_id=session_id,
    )

    try:
        # 1. Check source balance
        source_balance = await _get_balance(
            part_number=part_number,
            location_id=source_location_id,
            project_id=project_id,
        )

        if source_balance.get("available", 0) < quantity:
            return {
                "success": False,
                "message": f"Saldo insuficiente na origem. Disponível: {source_balance.get('available', 0)}",
                "data": {"source_balance": source_balance},
            }

        # 2. Check if destination is restricted
        dest_location = await _get_location(destination_location_id)
        is_restricted = dest_location and dest_location.get("restricted", False)

        # 3. Determine if HIL required
        requires_hil = is_restricted

        # 4. Create transfer movement
        movement_id = _generate_id("TRF")
        now = _now_iso()

        movement_data = {
            "movement_id": movement_id,
            "movement_type": "TRANSFER",
            "part_number": part_number,
            "quantity": quantity,
            "serial_numbers": serial_numbers or [],
            "source_location_id": source_location_id,
            "destination_location_id": destination_location_id,
            "project_id": project_id,
            "status": "PENDING_APPROVAL" if requires_hil else "COMPLETED",
            "requested_by": requested_by,
            "notes": notes,
            "created_at": now,
        }

        # 5. If HIL required, create task
        hil_task_id = None
        if requires_hil:
            hil_task_id = await _create_hil_task(
                task_type="APPROVAL_TRANSFER",
                title=f"Aprovar transferência para local restrito: {part_number}",
                entity_type="MOVEMENT",
                entity_id=movement_id,
                requested_by=requested_by,
                details={
                    "part_number": part_number,
                    "quantity": quantity,
                    "source": source_location_id,
                    "destination": destination_location_id,
                    "restricted": is_restricted,
                },
            )
            movement_data["hil_task_id"] = hil_task_id

        # 6. Save movement
        await _store_movement(movement_data)

        # 7. If not HIL, execute transfer
        if not requires_hil:
            await _execute_transfer(
                movement_id=movement_id,
                part_number=part_number,
                quantity=quantity,
                serial_numbers=serial_numbers,
                source_location_id=source_location_id,
                destination_location_id=destination_location_id,
                project_id=project_id,
            )

        audit.completed(
            message=f"Transferência {'executada' if not requires_hil else 'aguardando aprovação'}: {movement_id}",
            session_id=session_id,
            details={
                "movement_id": movement_id,
                "requires_hil": requires_hil,
            },
        )

        return {
            "success": True,
            "movement_id": movement_id,
            "message": "Transferência executada" if not requires_hil else "Transferência aguardando aprovação",
            "requires_hil": requires_hil,
            "hil_task_id": hil_task_id,
            "data": {
                "movement_id": movement_id,
                "movement_type": "TRANSFER",
                "source": source_location_id,
                "destination": destination_location_id,
            },
        }

    except Exception as e:
        logger.error(f"[create_transfer] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao criar transferência",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "message": f"Erro ao criar transferência: {str(e)}",
        }


async def _execute_transfer(
    movement_id: str,
    part_number: str,
    quantity: int,
    serial_numbers: Optional[List[str]],
    source_location_id: str,
    destination_location_id: str,
    project_id: str,
) -> None:
    """
    Execute the balance updates for a transfer.

    Called after approval (or immediately if no HIL).
    """
    # Decrement source balance
    await _update_balance(
        part_number=part_number,
        location_id=source_location_id,
        project_id=project_id,
        quantity_delta=-quantity,
    )

    # Increment destination balance
    await _update_balance(
        part_number=part_number,
        location_id=destination_location_id,
        project_id=project_id,
        quantity_delta=quantity,
    )

    # Update asset locations if serial numbers
    for serial in (serial_numbers or []):
        await _update_asset_status(
            serial_number=serial,
            new_status="IN_STOCK",
            location_id=destination_location_id,
            movement_id=movement_id,
        )


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


async def _get_location(location_id: str) -> Optional[Dict[str, Any]]:
    """Get location from database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        return await db.get_location(location_id)
    except ImportError:
        return None


async def _store_movement(movement_data: Dict[str, Any]) -> None:
    """Store movement in database."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.put_movement(movement_data)
    except ImportError:
        logger.warning("[transfer] DBClient not available")


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
        logger.warning("[transfer] DBClient not available")


async def _update_asset_status(
    serial_number: str,
    new_status: str,
    location_id: str,
    movement_id: str,
) -> None:
    """Update asset status after movement."""
    try:
        from tools.db_client import DBClient
        db = DBClient()

        asset = await db.get_asset_by_serial(serial_number)
        if not asset:
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
        logger.warning("[transfer] DBClient not available")


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
        logger.warning("[transfer] HILWorkflowManager not available")
        return None


def _generate_id(prefix: str) -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
