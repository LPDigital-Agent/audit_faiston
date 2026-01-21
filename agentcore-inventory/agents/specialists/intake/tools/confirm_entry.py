# =============================================================================
# Confirm Entry Tool
# =============================================================================
# Confirms pending entry and creates inventory movements.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)

AGENT_ID = "intake"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_confirm_entry")
async def confirm_entry_tool(
    entry_id: str,
    confirmed_by: str,
    item_mappings: Optional[Dict[str, str]] = None,
    notes: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Confirm pending entry and create inventory movements.

    Args:
        entry_id: Entry ID to confirm
        confirmed_by: User confirming the entry
        item_mappings: Optional manual PN mappings for unmatched items
        notes: Additional notes
        session_id: Optional session ID for audit

    Returns:
        Confirmation result with created movements
    """
    audit.working(
        message=f"Confirmando entrada {entry_id}...",
        session_id=session_id,
    )

    try:
        # Get entry record
        entry = await _get_entry(entry_id)

        if not entry:
            return {
                "success": False,
                "error": f"Entrada {entry_id} não encontrada",
            }

        # Check status
        valid_statuses = ["PENDING_CONFIRMATION", "PENDING_APPROVAL"]
        if entry.get("status") not in valid_statuses:
            return {
                "success": False,
                "error": f"Entrada não pode ser confirmada. Status: {entry.get('status')}",
            }

        # Apply manual mappings if provided
        matched_items = entry.get("matched_items", [])
        unmatched_items = entry.get("unmatched_items", [])

        if item_mappings:
            for item in unmatched_items[:]:
                item_key = item.get("codigo") or item.get("descricao", "")[:20]
                if item_key in item_mappings:
                    item["matched_pn"] = item_mappings[item_key]
                    item["match_method"] = "manual"
                    # BUG-022 v9 FIX (TASK 11): Don't force 100% confidence on manual mappings.
                    # Manual mappings by operators are trusted but not infallible (e.g., typos).
                    # Use realistic 95% confidence to flag potential human errors in audit trails.
                    item["match_confidence"] = 0.95
                    matched_items.append(item)
                    unmatched_items.remove(item)

        # Check for remaining unmatched items
        if unmatched_items:
            return {
                "success": False,
                "error": f"Ainda existem {len(unmatched_items)} itens sem mapeamento",
                "items_pending": len(unmatched_items),
            }

        # Create movements for each item
        now = _now_iso()
        movement_ids = []
        total_items = 0

        for item in matched_items:
            movement_id = _generate_id("ENT")

            movement_data = {
                "movement_id": movement_id,
                "movement_type": "ENTRY",
                "part_number": item["matched_pn"],
                "quantity": item.get("quantidade", 1),
                "serial_numbers": item.get("seriais", []),
                "unit_value": item.get("valor_unitario", 0),
                "total_value": item.get("valor_total", 0),
                "destination_location_id": entry.get("destination_location_id", "ESTOQUE_CENTRAL"),
                "project_id": entry.get("project_id", ""),
                "nf_entry_id": entry_id,
                "nf_numero": entry.get("nf_numero"),
                "nf_item_codigo": item.get("codigo"),
                "processed_by": confirmed_by,
                "notes": notes,
                "created_at": now,
            }

            # Store movement
            await _store_movement(movement_data)
            movement_ids.append(movement_id)

            # Update balance
            await _update_balance(
                part_number=item["matched_pn"],
                location_id=entry.get("destination_location_id", "ESTOQUE_CENTRAL"),
                project_id=entry.get("project_id", ""),
                quantity_delta=item.get("quantidade", 1),
            )

            # Create assets for serialized items
            for serial in item.get("seriais", []):
                await _create_asset(
                    serial_number=serial,
                    part_number=item["matched_pn"],
                    location_id=entry.get("destination_location_id", "ESTOQUE_CENTRAL"),
                    project_id=entry.get("project_id", ""),
                    movement_id=movement_id,
                    entry_id=entry_id,
                )

            total_items += item.get("quantidade", 1)

        # Update entry status
        await _update_entry_status(
            entry_id=entry_id,
            status="COMPLETED",
            confirmed_by=confirmed_by,
            confirmed_at=now,
            notes=notes,
            movement_ids=movement_ids,
        )

        # Log to audit
        await _log_confirmation(
            entry_id=entry_id,
            confirmed_by=confirmed_by,
            movement_count=len(movement_ids),
            total_items=total_items,
        )

        audit.completed(
            message=f"Entrada confirmada: {total_items} itens em {len(movement_ids)} movimentações",
            session_id=session_id,
            details={
                "entry_id": entry_id,
                "movements": len(movement_ids),
                "items": total_items,
            },
        )

        return {
            "success": True,
            "entry_id": entry_id,
            "nf_id": entry.get("nf_id"),
            "message": f"Entrada confirmada. {total_items} itens processados em {len(movement_ids)} movimentações.",
            "movement_ids": movement_ids,
            "items_processed": total_items,
        }

    except Exception as e:
        debug_error(e, "confirm_entry", {"entry_id": entry_id, "confirmed_by": confirmed_by})
        audit.error(
            message="Erro ao confirmar entrada",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }


async def _get_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    """
    Get entry record from database.

    BUG-022 v9 FIX (CRITICAL-A4): NEVER return mock data!
    Mock data gets processed as real, creating fake movements/assets.
    """
    try:
        from tools.db_client import DBClient

        db = DBClient()
        return await db.get_entry(entry_id)

    except ImportError as e:
        # BUG-022 v9 FIX: NEVER return mock data - this creates fake records!
        debug_error(e, "confirm_entry_get_entry", {"entry_id": entry_id})
        raise RuntimeError(
            f"Database client not available - cannot retrieve entry {entry_id}. "
            "This is a critical infrastructure error."
        )

    except Exception as e:
        debug_error(e, "confirm_entry_get_entry", {"entry_id": entry_id})
        return None


async def _store_movement(movement_data: Dict[str, Any]) -> None:
    """
    Store movement record in database.

    BUG-022 v9 FIX: MUST raise on failure - movements are critical audit trail!
    """
    try:
        from tools.db_client import DBClient

        db = DBClient()
        await db.put_movement(movement_data)

    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - movements are audit trail!
        debug_error(e, "confirm_entry_store_movement", {"movement_id": movement_data.get("movement_id", "unknown")})
        raise RuntimeError(
            "Database client not available - movement cannot be stored. "
            "This is a critical infrastructure error."
        )


async def _update_balance(
    part_number: str,
    location_id: str,
    project_id: str,
    quantity_delta: float,
) -> None:
    """
    Update inventory balance.

    BUG-022 v9 FIX: MUST raise on failure - balance updates are critical!
    """
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

    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - balance is inventory truth!
        debug_error(e, "confirm_entry_update_balance", {"part_number": part_number, "quantity_delta": quantity_delta})
        raise RuntimeError(
            f"Database client not available - balance update for {part_number} failed. "
            "This is a critical infrastructure error."
        )


async def _create_asset(
    serial_number: str,
    part_number: str,
    location_id: str,
    project_id: str,
    movement_id: str,
    entry_id: str,
) -> None:
    """Create or update asset record for serialized item."""
    try:
        from tools.db_client import DBClient
        db = DBClient()

        # Check if asset exists
        existing = await db.get_asset_by_serial(serial_number)

        now = _now_iso()

        if existing:
            # Update existing
            await db.update_asset(
                asset_id=existing["asset_id"],
                updates={
                    "location_id": location_id,
                    "status": "IN_STOCK",
                    "last_movement_id": movement_id,
                    "updated_at": now,
                },
            )
        else:
            # Create new
            asset_id = _generate_id("AST")
            await db.put_asset({
                "asset_id": asset_id,
                "serial_number": serial_number,
                "part_number": part_number,
                "location_id": location_id,
                "project_id": project_id,
                "status": "IN_STOCK",
                "acquisition_type": "NF_ENTRY",
                "acquisition_ref": entry_id,
                "last_movement_id": movement_id,
                "created_at": now,
                "updated_at": now,
            })

    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - assets are serialized inventory!
        debug_error(e, "confirm_entry_create_asset", {"serial_number": serial_number, "part_number": part_number})
        raise RuntimeError(
            f"Database client not available - asset {serial_number} creation failed. "
            "This is a critical infrastructure error."
        )


async def _update_entry_status(
    entry_id: str,
    status: str,
    confirmed_by: str,
    confirmed_at: str,
    notes: Optional[str],
    movement_ids: List[str],
) -> None:
    """Update entry status to completed."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.update_entry(
            entry_id=entry_id,
            updates={
                "status": status,
                "confirmed_at": confirmed_at,
                "confirmed_by": confirmed_by,
                "confirmation_notes": notes,
                "movement_ids": movement_ids,
            },
        )

    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - status is workflow state!
        debug_error(e, "confirm_entry_update_status", {"entry_id": entry_id, "target_status": status})
        raise RuntimeError(
            f"Database client not available - entry {entry_id} status update failed. "
            "This is a critical infrastructure error."
        )


async def _log_confirmation(
    entry_id: str,
    confirmed_by: str,
    movement_count: int,
    total_items: int,
) -> None:
    """Log confirmation to audit trail."""
    try:
        from tools.audit_logger import SGAAuditLogger
        audit_logger = SGAAuditLogger()
        audit_logger.log_action(
            action="NF_ENTRY_CONFIRMED",
            entity_type="NF_ENTRY",
            entity_id=entry_id,
            actor=confirmed_by,
            details={
                "movements_created": movement_count,
                "total_items": total_items,
            },
        )
    except ImportError:
        logger.debug("[confirm_entry] Audit logger not available")


def _generate_id(prefix: str) -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
