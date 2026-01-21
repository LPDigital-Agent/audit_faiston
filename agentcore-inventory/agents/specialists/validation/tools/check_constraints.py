# =============================================================================
# Check Constraints Tool
# =============================================================================
# Checks database constraints for import data.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional, Set


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "validation"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_check_constraints")
async def check_constraints_tool(
    rows: List[Dict[str, Any]],
    target_table: str = "pending_entry_items",
    check_uniqueness: bool = True,
    check_foreign_keys: bool = True,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check database constraints for import data.

    Checks:
    1. Unique constraints (duplicates within import)
    2. Foreign key references (if applicable)
    3. Check constraints (value restrictions)

    Args:
        rows: Data rows to check
        target_table: Target table for constraint lookup
        check_uniqueness: Whether to check unique constraints
        check_foreign_keys: Whether to check foreign key references
        session_id: Optional session ID for audit

    Returns:
        Constraint check result with violations
    """
    audit.working(
        message=f"Verificando restrições para {len(rows)} linhas...",
        session_id=session_id,
    )

    try:
        violations: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        # Check uniqueness within import batch
        if check_uniqueness:
            uniqueness_violations = _check_internal_uniqueness(rows, target_table)
            violations.extend(uniqueness_violations)

        # Check foreign keys (if enabled and applicable)
        if check_foreign_keys:
            fk_violations = await _check_foreign_keys(rows, target_table)
            violations.extend(fk_violations)

        # Check for duplicates in existing database
        db_duplicates = await _check_existing_duplicates(rows, target_table)
        warnings.extend(db_duplicates)

        is_valid = len(violations) == 0

        status_msg = "OK" if is_valid else f"{len(violations)} violação(ões)"
        audit.completed(
            message=f"Restrições: {status_msg}",
            session_id=session_id,
            details={
                "violations_count": len(violations),
                "warnings_count": len(warnings),
            },
        )

        return {
            "success": True,
            "is_valid": is_valid,
            "violations": violations,
            "warnings": warnings,
            "total_rows": len(rows),
        }

    except Exception as e:
        logger.error(f"[check_constraints] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao verificar restrições",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "is_valid": False,
            "error": str(e),
            "violations": [],
            "warnings": [],
        }


def _check_internal_uniqueness(
    rows: List[Dict[str, Any]],
    target_table: str,
) -> List[Dict[str, Any]]:
    """
    Check for uniqueness violations within the import batch.

    For pending_entry_items:
    - part_number + serial_number should be unique
    """
    violations = []

    # Define unique key combinations per table
    unique_keys = {
        "pending_entry_items": [
            ("part_number", "serial_number"),  # Composite unique
        ],
    }

    key_combinations = unique_keys.get(target_table, [])

    for key_fields in key_combinations:
        seen_values: Dict[tuple, List[int]] = {}

        for idx, row in enumerate(rows):
            # Extract key values
            key_value = tuple(
                str(row.get(field, "")).strip().upper()
                for field in key_fields
            )

            # Skip if all key fields are empty
            if all(v == "" for v in key_value):
                continue

            # Check for duplicate
            if key_value in seen_values:
                seen_values[key_value].append(idx + 1)
            else:
                seen_values[key_value] = [idx + 1]

        # Report duplicates
        for key_value, row_numbers in seen_values.items():
            if len(row_numbers) > 1:
                violations.append({
                    "type": "duplicate_key",
                    "key_fields": key_fields,
                    "key_value": key_value,
                    "rows": row_numbers,
                    "message": f"Valores duplicados nas linhas {row_numbers}: {key_fields}={key_value}",
                })

    return violations


async def _check_foreign_keys(
    rows: List[Dict[str, Any]],
    target_table: str,
) -> List[Dict[str, Any]]:
    """
    Check foreign key references exist in database.

    For pending_entry_items:
    - project_code should exist in projects table (if provided)
    - location should exist in locations table (if provided)
    """
    violations = []

    # Define FK relationships
    foreign_keys = {
        "pending_entry_items": [
            # (field, referenced_table, referenced_column, optional)
            ("project_code", "projects", "code", True),
            ("location", "locations", "name", True),
        ],
    }

    fk_definitions = foreign_keys.get(target_table, [])

    if not fk_definitions:
        return violations

    try:
        from tools.db_client import DBClient
        db = DBClient()

        for field, ref_table, ref_column, optional in fk_definitions:
            # Collect unique values to check
            values_to_check: Set[str] = set()

            for row in rows:
                value = row.get(field)
                if value and str(value).strip():
                    values_to_check.add(str(value).strip())

            if not values_to_check:
                continue

            # Check which values exist
            existing = await _get_existing_values(db, ref_table, ref_column, values_to_check)

            # Report missing references
            missing = values_to_check - existing

            if missing and not optional:
                violations.append({
                    "type": "foreign_key",
                    "field": field,
                    "referenced_table": ref_table,
                    "missing_values": list(missing)[:10],  # Limit for readability
                    "message": f"Valores de '{field}' não encontrados em '{ref_table}': {list(missing)[:5]}",
                })

    except ImportError:
        logger.debug("[check_constraints] DBClient not available, skipping FK check")
    except Exception as e:
        logger.warning(f"[check_constraints] FK check failed: {e}")

    return violations


async def _get_existing_values(
    db,
    table: str,
    column: str,
    values: Set[str],
) -> Set[str]:
    """
    Query database for existing values.
    """
    try:
        # Build parameterized query
        placeholders = ", ".join(["%s"] * len(values))
        query = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IN ({placeholders})"

        result = await db.execute(query, list(values))

        if result and result.get("rows"):
            return {row[column] for row in result["rows"]}

    except Exception as e:
        logger.warning(f"[check_constraints] Query failed: {e}")

    return set()


async def _check_existing_duplicates(
    rows: List[Dict[str, Any]],
    target_table: str,
) -> List[Dict[str, Any]]:
    """
    Check if records already exist in the database.

    Returns warnings (not violations) since duplicates might be intentional.
    """
    warnings = []

    # Collect part_numbers to check
    part_numbers: Set[str] = set()
    serial_numbers: Set[str] = set()

    for row in rows:
        pn = row.get("part_number")
        sn = row.get("serial_number")

        if pn:
            part_numbers.add(str(pn).strip().upper())
        if sn:
            serial_numbers.add(str(sn).strip().upper())

    if not part_numbers:
        return warnings

    try:
        from tools.db_client import DBClient
        db = DBClient()

        # Check for existing items with same part_number + serial_number
        if serial_numbers:
            existing = await _find_existing_items(
                db,
                target_table,
                part_numbers,
                serial_numbers,
            )

            if existing:
                warnings.append({
                    "type": "existing_records",
                    "count": len(existing),
                    "examples": existing[:5],
                    "message": f"{len(existing)} registro(s) podem já existir no banco",
                })

    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[check_constraints] Duplicate check failed: {e}")

    return warnings


async def _find_existing_items(
    db,
    table: str,
    part_numbers: Set[str],
    serial_numbers: Set[str],
) -> List[Dict[str, str]]:
    """
    Find existing items with matching part_number and serial_number.
    """
    try:
        pn_placeholders = ", ".join(["%s"] * len(part_numbers))
        sn_placeholders = ", ".join(["%s"] * len(serial_numbers))

        query = f"""
        SELECT part_number, serial_number
        FROM {table}
        WHERE UPPER(part_number) IN ({pn_placeholders})
          AND UPPER(serial_number) IN ({sn_placeholders})
        LIMIT 10
        """

        result = await db.execute(query, list(part_numbers) + list(serial_numbers))

        if result and result.get("rows"):
            return [
                {"part_number": row["part_number"], "serial_number": row["serial_number"]}
                for row in result["rows"]
            ]

    except Exception as e:
        logger.warning(f"[check_constraints] Existing items query failed: {e}")

    return []
