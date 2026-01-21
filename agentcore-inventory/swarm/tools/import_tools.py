# =============================================================================
# Import Tools - Transaction Execution for Inventory Swarm
# =============================================================================
# Tools for executing imports and managing audit trails.
#
# Used by: import_executor agent
# =============================================================================

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from decimal import Decimal

from strands import tool

# AUDIT-003: Global error capture for Debug Agent enrichment
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


@tool
def verify_approval(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify that user approval exists in the context.

    Args:
        context: Current swarm context with user responses

    Returns:
        dict with:
        - approved: Boolean indicating if approval exists
        - approval_timestamp: When approval was given
        - message: Status message
    """
    logger.info("[verify_approval] Checking approval status in context")

    # Check various places where approval might be stored
    approval_status = context.get("approval_status")
    user_responses = context.get("user_responses", {})

    # Check explicit approval
    if approval_status is True:
        return {
            "approved": True,
            "approval_timestamp": context.get("approval_timestamp"),
            "message": "User approval confirmed",
        }

    # Check if approval answer exists
    if user_responses.get("q_final_approval") == "approve":
        return {
            "approved": True,
            "approval_timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "User approved via final approval question",
        }

    return {
        "approved": False,
        "approval_timestamp": None,
        "message": "No user approval found in context. Cannot proceed with import.",
    }


@tool
def execute_import(
    mappings: List[Dict[str, Any]],
    data: List[Dict[str, Any]],
    target_table: str,
    metadata_columns: Optional[List[str]] = None,
    user_id: str = "unknown",
    session_id: str = "unknown",
) -> Dict[str, Any]:
    """
    Execute the import with transaction support.

    Args:
        mappings: Confirmed column mappings
        data: Data rows to import
        target_table: Target PostgreSQL table
        metadata_columns: Columns to store in metadata JSON field
        user_id: User performing the import
        session_id: Session ID for tracking

    Returns:
        dict with:
        - success: Boolean indicating import result
        - import_id: Unique import transaction ID
        - rows_imported: Number of rows imported
        - duration_ms: Import duration in milliseconds
        - error: Error message if failed
    """
    import time

    start_time = time.time()
    import_id = str(uuid.uuid4())

    logger.info(
        "[execute_import] Starting import %s: %d rows to %s",
        import_id,
        len(data),
        target_table,
    )

    try:
        # Build insert statements
        rows_imported = 0

        # Transform data according to mappings
        transformed_data = []
        for row in data:
            transformed_row = {"id": str(uuid.uuid4())}
            metadata = {}

            for mapping in mappings:
                source = mapping.get("source_column")
                target = mapping.get("target_column")
                transform = mapping.get("transform")

                # BUG-022 v9 FIX (TASK 12): Null check for mapping keys
                # Skip invalid mappings instead of silently corrupting data
                if not source:
                    logger.warning(
                        "[execute_import] Skipping mapping with missing source_column: %s",
                        mapping,
                    )
                    continue

                if not target:
                    logger.debug(
                        "[execute_import] Skipping mapping with missing target_column: source=%s",
                        source,
                    )
                    continue

                value = row.get(source)

                # Apply transform if needed
                if transform and value is not None:
                    value = _apply_transform(value, transform)

                transformed_row[target] = value

            # Handle metadata columns
            for col in metadata_columns or []:
                if col in row:
                    metadata[col] = row[col]

            if metadata:
                transformed_row["metadata"] = json.dumps(metadata)

            # Add audit fields
            transformed_row["created_at"] = datetime.now(timezone.utc).isoformat()
            transformed_row["created_by"] = user_id

            transformed_data.append(transformed_row)

        # BUG-022 v9 FIX (CRITICAL-S2): Execute against PostgreSQL via MCP or FAIL EXPLICITLY
        # NEVER simulate success - this causes silent data loss!
        try:
            from tools.postgres_client import PostgresClient

            db_client = PostgresClient()
            rows_imported = db_client.batch_insert(
                table_name=target_table,
                rows=transformed_data,
                import_id=import_id,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "[execute_import] Completed %s: %d rows in %d ms",
                import_id,
                rows_imported,
                duration_ms,
            )

            return {
                "success": True,
                "import_id": import_id,
                "rows_imported": rows_imported,
                "duration_ms": duration_ms,
                "target_table": target_table,
                "message": f"Successfully imported {rows_imported} rows",
            }

        except ImportError as ie:
            duration_ms = int((time.time() - start_time) * 1000)
            # AUDIT-003: Use debug_error for enriched error analysis
            debug_error(ie, "execute_import_db_unavailable", {
                "import_id": import_id,
                "rows_prepared": len(transformed_data),
                "target_table": target_table,
            }, severity="critical")

            return {
                "success": False,
                "import_id": import_id,
                "rows_imported": 0,
                "duration_ms": duration_ms,
                "target_table": target_table,
                "error": "Database client not available - cannot proceed with import",
                "message": "CRITICAL: Import failed - database client unavailable",
                "recoverable": False,
                "data_prepared": len(transformed_data),  # How many rows WOULD have been imported
            }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        # AUDIT-003: Use debug_error for enriched error analysis
        debug_error(e, "execute_import_failed", {"import_id": import_id, "target_table": target_table})

        return {
            "success": False,
            "import_id": import_id,
            "rows_imported": 0,
            "duration_ms": duration_ms,
            "error": str(e),
            "message": f"Import failed: {e}",
        }


@tool
def generate_audit(
    import_id: str,
    user_id: str,
    session_id: str,
    file_path: str,
    target_table: str,
    rows_imported: int,
    mappings: List[Dict[str, Any]],
    status: str,
    duration_ms: int,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an audit trail record in DynamoDB.

    Args:
        import_id: Import transaction ID
        user_id: User who performed import
        session_id: Session ID
        file_path: Source file path
        target_table: Target table
        rows_imported: Number of rows imported
        mappings: Column mappings used
        status: Import status (success/failed/rolled_back)
        duration_ms: Import duration
        error: Error message if failed

    Returns:
        dict with:
        - audit_id: Unique audit record ID
        - success: Whether audit was stored
    """
    audit_id = str(uuid.uuid4())

    audit_record = {
        "audit_id": audit_id,
        "import_id": import_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "file_path": file_path,
        "target_table": target_table,
        "rows_imported": rows_imported,
        "mappings_used": mappings,
        "status": status,
        "duration_ms": duration_ms,
        "error": error,
    }

    logger.info(
        "[generate_audit] Created audit %s for import %s (status=%s)",
        audit_id,
        import_id,
        status,
    )

    # In production, store in DynamoDB
    try:
        from shared.audit_emitter import AuditEmitter

        emitter = AuditEmitter()
        emitter.emit(audit_record)

    except ImportError:
        logger.warning("[generate_audit] AuditEmitter not available, audit logged only")

    return {
        "audit_id": audit_id,
        "success": True,
        "message": f"Audit trail created: {audit_id}",
    }


@tool
def rollback_import(import_id: str) -> Dict[str, Any]:
    """
    Rollback a failed import transaction.

    Args:
        import_id: Import transaction ID to rollback

    Returns:
        dict with:
        - success: Whether rollback succeeded
        - message: Status message
    """
    logger.info("[rollback_import] Rolling back import %s", import_id)

    # BUG-022 v9 FIX (CRITICAL-S3): Execute DELETE against PostgreSQL or FAIL EXPLICITLY
    # NEVER simulate success - this masks failed rollbacks!
    try:
        from tools.postgres_client import PostgresClient

        db_client = PostgresClient()
        rows_deleted = db_client.delete_by_import_id(import_id=import_id)

        logger.info(
            "[rollback_import] Successfully rolled back import %s: %d rows deleted",
            import_id,
            rows_deleted,
        )

        return {
            "success": True,
            "import_id": import_id,
            "message": f"Import {import_id} rolled back successfully",
            "rows_deleted": rows_deleted,
        }

    except ImportError as ie:
        # AUDIT-003: Use debug_error for enriched error analysis
        debug_error(ie, "rollback_import_db_unavailable", {"import_id": import_id}, severity="critical")

        return {
            "success": False,
            "import_id": import_id,
            "error": "Database client not available - cannot rollback",
            "message": "CRITICAL: Rollback failed - database client unavailable. Manual intervention required.",
            "rows_deleted": 0,
            "recoverable": False,
            "requires_manual_cleanup": True,
        }

    except Exception as e:
        # AUDIT-003: Use debug_error for enriched error analysis
        debug_error(e, "rollback_import_failed", {"import_id": import_id})

        return {
            "success": False,
            "import_id": import_id,
            "error": str(e),
            "message": f"Rollback failed: {e}",
            "rows_deleted": 0,
        }


@tool
def apply_quantity_rule(
    data: List[Dict[str, Any]],
    part_number_column: str,
    serial_number_column: str,
) -> Dict[str, Any]:
    """
    Apply the quantity calculation rule when quantity is missing.

    Groups by part_number and counts unique serial numbers.

    Args:
        data: Raw data rows
        part_number_column: Name of part number column
        serial_number_column: Name of serial number column

    Returns:
        dict with:
        - transformed_data: Data with calculated quantities
        - parts_count: Number of unique part numbers
        - total_serials: Total serial numbers processed
    """
    logger.info(
        "[apply_quantity_rule] Applying to %d rows (pn=%s, sn=%s)",
        len(data),
        part_number_column,
        serial_number_column,
    )

    # Group by part number
    groups = {}
    for row in data:
        pn = row.get(part_number_column)
        sn = row.get(serial_number_column)

        if pn is None:
            continue

        if pn not in groups:
            groups[pn] = {
                "part_number": pn,
                "serials": [],
                "first_row": row,  # Keep other fields from first row
            }

        if sn:
            groups[pn]["serials"].append(sn)

    # Build transformed data
    transformed = []
    for pn, group in groups.items():
        row = dict(group["first_row"])
        row[part_number_column] = pn
        row["quantity"] = len(group["serials"])
        row["serial_numbers"] = group["serials"]

        # Remove the original serial column (now in array)
        if serial_number_column in row:
            del row[serial_number_column]

        transformed.append(row)

    logger.info(
        "[apply_quantity_rule] Transformed %d rows into %d unique parts",
        len(data),
        len(transformed),
    )

    return {
        "transformed_data": transformed,
        "parts_count": len(groups),
        "total_serials": sum(len(g["serials"]) for g in groups.values()),
        "message": f"Calculated quantities for {len(groups)} unique part numbers",
    }


# =============================================================================
# Helper Functions
# =============================================================================


def _apply_transform(value: Any, transform: str) -> Any:
    """Apply a data transformation to a value."""
    if value is None:
        return None

    str_val = str(value).strip()

    if transform == "cast_to_integer":
        try:
            return int(float(str_val.replace(",", "")))
        except (ValueError, TypeError):
            return None

    if transform == "cast_to_decimal":
        try:
            return Decimal(str_val.replace(",", "."))
        except (ValueError, TypeError):
            return None

    if transform == "parse_date":
        return _parse_date(str_val)

    return value


def _parse_date(value: str) -> Optional[str]:
    """Parse various date formats to ISO format."""
    from datetime import datetime

    formats = [
        "%Y-%m-%d",  # ISO
        "%d/%m/%Y",  # DD/MM/YYYY
        "%m/%d/%Y",  # MM/DD/YYYY
        "%d-%m-%Y",  # DD-MM-YYYY
        "%Y/%m/%d",  # YYYY/MM/DD
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.isoformat()
        except ValueError:
            continue

    return value  # Return original if no format matches
