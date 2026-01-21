# =============================================================================
# Execute Import Tool
# =============================================================================
# Executes bulk import and creates inventory movements.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)

AGENT_ID = "data_import"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_execute_import")
async def execute_import_tool(
    import_id: str,
    s3_key: str,
    column_mappings: List[Dict[str, Any]],
    pn_overrides: Optional[Dict[str, str]] = None,
    project_id: Optional[str] = None,
    destination_location_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute bulk import and create movements.

    Args:
        import_id: Unique import batch ID
        s3_key: S3 key of the import file
        column_mappings: Validated column mappings
        pn_overrides: Manual PN overrides for unmatched rows
        project_id: Target project ID
        destination_location_id: Target location ID
        operator_id: User executing the import
        session_id: Optional session ID for audit

    Returns:
        Import result with statistics
    """
    audit.working(
        message=f"Executando importação {import_id}...",
        session_id=session_id,
    )

    try:
        # Build mapping lookup
        mapping_lookup = {}
        for m in column_mappings:
            source = m.get("source_column")
            target = m.get("target_field")
            if source and target:
                mapping_lookup[source] = target

        # Get column references
        pn_column = next(
            (m["source_column"] for m in column_mappings
             if m.get("target_field") == "part_number"),
            None
        )
        qty_column = next(
            (m["source_column"] for m in column_mappings
             if m.get("target_field") == "quantity"),
            None
        )
        serial_column = next(
            (m["source_column"] for m in column_mappings
             if m.get("target_field") == "serial_number"),
            None
        )
        location_column = next(
            (m["source_column"] for m in column_mappings
             if m.get("target_field") == "location"),
            None
        )

        # Download and parse file
        from agents.data_import.tools.preview_import import _download_file, _parse_csv, _parse_excel

        file_content, file_type = await _download_file(s3_key)
        if not file_content:
            return {
                "success": False,
                "error": f"Arquivo não encontrado: {s3_key}",
            }

        if file_type in ["xlsx", "xls"]:
            headers, rows = await _parse_excel(file_content, file_type)
        else:
            headers, rows = await _parse_csv(file_content)

        # Get part numbers for matching
        db_parts = await _get_part_numbers_map()

        # Process each row
        now = _now_iso()
        created_movements = []
        skipped_rows = []
        errors = []

        total_items = 0
        total_quantity = 0

        for row_idx, row in enumerate(rows, start=1):
            try:
                # Get part number (from column or override)
                raw_pn = row.get(pn_column) if pn_column else None
                part_number = None

                # Check override first
                if pn_overrides and raw_pn and str(raw_pn) in pn_overrides:
                    part_number = pn_overrides[str(raw_pn)]
                elif raw_pn:
                    # Look up in database
                    pn_normalized = str(raw_pn).strip().upper()
                    part_number = db_parts.get(pn_normalized)

                if not part_number:
                    skipped_rows.append({
                        "row": row_idx,
                        "reason": "PN não encontrado",
                        "raw_pn": raw_pn,
                    })
                    continue

                # BUG-022 v9 FIX (CRITICAL-A3): Quantity validation
                # NEVER silently default to 1 - this causes inventory discrepancies!
                quantity = None

                if qty_column and row.get(qty_column):
                    raw_qty = row[qty_column]
                    try:
                        quantity = float(raw_qty)
                    except (ValueError, TypeError):
                        logger.warning(
                            "[execute_import] Row %d: Cannot parse quantity '%s' - skipping row",
                            row_idx,
                            raw_qty,
                        )
                        skipped_rows.append({
                            "row": row_idx,
                            "reason": f"Quantidade inválida: '{raw_qty}'",
                            "raw_value": raw_qty,
                        })
                        continue

                # If no quantity column or value, log and skip (don't default to 1!)
                if quantity is None:
                    logger.warning(
                        "[execute_import] Row %d: No quantity value - skipping row "
                        "(qty_column=%s, has_value=%s)",
                        row_idx,
                        qty_column,
                        bool(qty_column and row.get(qty_column)),
                    )
                    skipped_rows.append({
                        "row": row_idx,
                        "reason": "Quantidade não informada",
                    })
                    continue

                if quantity == 0:
                    skipped_rows.append({
                        "row": row_idx,
                        "reason": "Quantidade zero",
                    })
                    continue

                # Get serial numbers
                serial_numbers = []
                if serial_column and row.get(serial_column):
                    raw_serial = str(row[serial_column])
                    # Split by common delimiters
                    for delim in [",", ";", "|", "\n"]:
                        if delim in raw_serial:
                            serial_numbers = [s.strip() for s in raw_serial.split(delim) if s.strip()]
                            break
                    else:
                        serial_numbers = [raw_serial.strip()] if raw_serial.strip() else []

                # Get location (from row or default)
                location_id = destination_location_id or "ESTOQUE_CENTRAL"
                if location_column and row.get(location_column):
                    location_id = str(row[location_column]).strip()

                # Determine movement type
                movement_type = "ENTRY" if quantity > 0 else "EXIT"

                # Create movement
                movement_id = _generate_id("MOV")
                movement_data = {
                    "movement_id": movement_id,
                    "movement_type": movement_type,
                    "part_number": part_number,
                    "quantity": abs(quantity),
                    "serial_numbers": serial_numbers,
                    "destination_location_id": location_id,
                    "project_id": project_id or "UNASSIGNED",
                    "import_id": import_id,
                    "import_row": row_idx,
                    "processed_by": operator_id or "system",
                    "created_at": now,
                }

                # Store movement
                await _store_movement(movement_data)
                created_movements.append(movement_id)

                # Update balance
                balance_delta = quantity if movement_type == "ENTRY" else -abs(quantity)
                await _update_balance(
                    part_number=part_number,
                    location_id=location_id,
                    project_id=project_id or "UNASSIGNED",
                    quantity_delta=balance_delta,
                )

                # Create assets for serialized items
                for serial in serial_numbers:
                    await _create_asset(
                        serial_number=serial,
                        part_number=part_number,
                        location_id=location_id,
                        project_id=project_id or "UNASSIGNED",
                        movement_id=movement_id,
                        import_id=import_id,
                    )

                total_items += 1
                total_quantity += abs(quantity)

                # Progress update every 100 rows
                if row_idx % 100 == 0:
                    audit.working(
                        message=f"Processando... {row_idx}/{len(rows)} linhas",
                        session_id=session_id,
                    )

            except Exception as e:
                errors.append({
                    "row": row_idx,
                    "error": str(e),
                })
                debug_error(e, "execute_import_row", {"row_idx": row_idx, "import_id": import_id})

        # Calculate final statistics
        match_rate = len(created_movements) / len(rows) if rows else 0

        # Store import record
        import_record = {
            "import_id": import_id,
            "s3_key": s3_key,
            "filename": s3_key.split("/")[-1],
            "total_rows": len(rows),
            "rows_imported": len(created_movements),
            "rows_skipped": len(skipped_rows),
            "rows_error": len(errors),
            "total_quantity": total_quantity,
            "match_rate": match_rate,
            "column_mappings_used": column_mappings,
            "project_id": project_id,
            "destination_location_id": destination_location_id,
            "executed_by": operator_id,
            "executed_at": now,
        }
        await _store_import_record(import_record)

        audit.completed(
            message=f"Importação concluída: {len(created_movements)}/{len(rows)} linhas",
            session_id=session_id,
            details={
                "imported": len(created_movements),
                "skipped": len(skipped_rows),
                "errors": len(errors),
            },
        )

        return {
            "success": True,
            "import_id": import_id,
            "filename": import_record["filename"],
            "message": f"Importação concluída. {len(created_movements)} de {len(rows)} linhas processadas.",
            "rows_imported": len(created_movements),
            "rows_skipped": len(skipped_rows),
            "rows_error": len(errors),
            "total_quantity": total_quantity,
            "match_rate": match_rate,
            "column_mappings_used": column_mappings,
            "movement_ids": created_movements,
            "skipped_details": skipped_rows[:20],  # First 20 for review
            "error_details": errors[:20],
        }

    except Exception as e:
        debug_error(e, "execute_import", {"import_id": import_id, "s3_key": s3_key})
        audit.error(
            message="Erro na importação",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "import_id": import_id,
            "error": str(e),
        }


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_part_numbers_map() -> Dict[str, str]:
    """Get part numbers as a lookup map (normalized → actual)."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        parts = await db.list_part_numbers()

        return {
            str(p.get("part_number", "")).strip().upper(): p.get("part_number")
            for p in parts
            if p.get("part_number")
        }
    except ImportError:
        logger.warning("[execute_import] DBClient not available")
        return {}
    except Exception as e:
        debug_error(e, "execute_import_get_part_numbers", {})
        return {}


async def _store_movement(movement_data: Dict[str, Any]) -> None:
    """
    Store movement record.

    BUG-022 v9 FIX (CRITICAL-A3): MUST raise on failure - movements are audit trail!
    """
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.put_movement(movement_data)
    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - movements are audit trail!
        debug_error(e, "execute_import_store_movement", {"movement_id": movement_data.get("movement_id", "unknown")})
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

    BUG-022 v9 FIX (CRITICAL-A3): MUST raise on failure - balance is inventory truth!
    """
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
    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - balance is inventory truth!
        debug_error(e, "execute_import_update_balance", {"part_number": part_number, "quantity_delta": quantity_delta})
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
    import_id: str,
) -> None:
    """
    Create asset record for serialized item.

    BUG-022 v9 FIX (CRITICAL-A3): MUST raise on failure - assets are serialized inventory!
    """
    try:
        from tools.db_client import DBClient
        db = DBClient()

        existing = await db.get_asset_by_serial(serial_number)
        now = _now_iso()

        if existing:
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
            asset_id = _generate_id("AST")
            await db.put_asset({
                "asset_id": asset_id,
                "serial_number": serial_number,
                "part_number": part_number,
                "location_id": location_id,
                "project_id": project_id,
                "status": "IN_STOCK",
                "acquisition_type": "BULK_IMPORT",
                "acquisition_ref": import_id,
                "last_movement_id": movement_id,
                "created_at": now,
                "updated_at": now,
            })
    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - assets are serialized inventory!
        debug_error(e, "execute_import_create_asset", {"serial_number": serial_number, "part_number": part_number})
        raise RuntimeError(
            f"Database client not available - asset {serial_number} creation failed. "
            "This is a critical infrastructure error."
        )


async def _store_import_record(import_record: Dict[str, Any]) -> None:
    """
    Store import batch record.

    BUG-022 v9 FIX (CRITICAL-A3): MUST raise on failure - import records are audit trail!
    """
    try:
        from tools.db_client import DBClient
        db = DBClient()
        await db.put_import_record(import_record)
    except ImportError as e:
        # BUG-022 v9 FIX: NEVER silently swallow - import records are audit trail!
        debug_error(e, "execute_import_store_record", {"import_id": import_record.get("import_id", "unknown")})
        raise RuntimeError(
            "Database client not available - import record cannot be stored. "
            "This is a critical infrastructure error."
        )


def _generate_id(prefix: str) -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
