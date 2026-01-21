# =============================================================================
# Validate Schema Tool
# =============================================================================
# Validates column mappings against PostgreSQL schema.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional, Set


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "validation"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


# =============================================================================
# Known Schema Definitions
# =============================================================================

PENDING_ENTRY_ITEMS_SCHEMA: Dict[str, Dict[str, Any]] = {
    # Core fields
    "id": {"type": "uuid", "required": False, "auto": True},
    "part_number": {"type": "varchar", "max_length": 100, "required": False},
    "description": {"type": "text", "required": False},
    "quantity": {"type": "decimal", "required": False, "default": 1},
    "serial_number": {"type": "varchar", "max_length": 100, "required": False},
    "location": {"type": "varchar", "max_length": 255, "required": False},
    "unit": {"type": "varchar", "max_length": 20, "required": False},
    "condition": {"type": "varchar", "max_length": 50, "required": False},
    "notes": {"type": "text", "required": False},

    # Metadata fields
    "project_code": {"type": "varchar", "max_length": 50, "required": False},
    "batch_number": {"type": "varchar", "max_length": 100, "required": False},
    "manufacturer": {"type": "varchar", "max_length": 255, "required": False},
    "supplier": {"type": "varchar", "max_length": 255, "required": False},

    # Audit fields (auto-populated)
    "created_at": {"type": "timestamp", "required": False, "auto": True},
    "updated_at": {"type": "timestamp", "required": False, "auto": True},
    "created_by": {"type": "varchar", "max_length": 100, "required": False},
    "source": {"type": "varchar", "max_length": 50, "required": False},
}

AUTO_FIELDS: Set[str] = {"id", "created_at", "updated_at"}
SPECIAL_VALUES: Set[str] = {"_skip", "_create_new", "_select_other"}


@trace_tool_call("sga_validate_schema")
async def validate_schema_tool(
    column_mappings: Dict[str, str],
    target_table: str = "pending_entry_items",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate column mappings against PostgreSQL schema.

    Checks:
    1. Target fields exist in schema
    2. No duplicate mappings (multiple columns to same field)
    3. Required fields have mappings (if any)
    4. Auto-generated fields are not mapped

    Args:
        column_mappings: Proposed mappings {source_column: target_field}
        target_table: Target table for validation
        session_id: Optional session ID for audit

    Returns:
        Validation result with errors and warnings
    """
    audit.working(
        message="Validando mapeamentos contra schema...",
        session_id=session_id,
    )

    try:
        errors: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []

        # Get schema for target table
        schema = await _get_table_schema(target_table)

        # Track field usage for duplicate detection
        field_usage: Dict[str, List[str]] = {}

        for source_col, target_field in column_mappings.items():
            # Skip special values
            if target_field in SPECIAL_VALUES or not target_field:
                continue

            # Check if field exists
            if target_field not in schema:
                errors.append({
                    "type": "invalid_field",
                    "column": source_col,
                    "field": target_field,
                    "message": f"Campo '{target_field}' não existe na tabela '{target_table}'",
                    "suggestion": _find_similar_field(target_field, schema),
                })
                continue

            # Check if field is auto-generated
            field_def = schema.get(target_field, {})
            if field_def.get("auto"):
                errors.append({
                    "type": "auto_field",
                    "column": source_col,
                    "field": target_field,
                    "message": f"Campo '{target_field}' é auto-gerado e não pode ser mapeado",
                })
                continue

            # Track for duplicate detection
            if target_field not in field_usage:
                field_usage[target_field] = []
            field_usage[target_field].append(source_col)

        # Check for duplicate mappings
        for field, columns in field_usage.items():
            if len(columns) > 1:
                warnings.append({
                    "type": "duplicate_mapping",
                    "field": field,
                    "columns": columns,
                    "message": f"Múltiplas colunas mapeadas para '{field}': {', '.join(columns)}",
                })

        # Check for recommended fields
        mapped_fields = set(field_usage.keys())
        recommended = {"part_number", "description"}
        missing_recommended = recommended - mapped_fields

        for field in missing_recommended:
            warnings.append({
                "type": "missing_recommended",
                "field": field,
                "message": f"Campo recomendado '{field}' não está mapeado",
            })

        # Calculate validation score
        total_mappings = len([m for m in column_mappings.values() if m and m not in SPECIAL_VALUES])
        valid_mappings = total_mappings - len([e for e in errors if e["type"] != "auto_field"])
        validation_score = valid_mappings / total_mappings if total_mappings > 0 else 0

        is_valid = len(errors) == 0

        status_msg = "válidos" if is_valid else "inválidos"
        audit.completed(
            message=f"Mapeamentos {status_msg}: {valid_mappings}/{total_mappings}",
            session_id=session_id,
            details={
                "is_valid": is_valid,
                "errors_count": len(errors),
                "warnings_count": len(warnings),
            },
        )

        return {
            "success": True,
            "is_valid": is_valid,
            "validation_score": validation_score,
            "errors": errors,
            "warnings": warnings,
            "valid_mappings": valid_mappings,
            "total_mappings": total_mappings,
            "schema_fields": list(schema.keys()),
        }

    except Exception as e:
        logger.error(f"[validate_schema] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao validar schema",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "is_valid": False,
            "error": str(e),
            "errors": [],
            "warnings": [],
        }


async def _get_table_schema(table_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Get schema for a table.

    First tries to query the database, then falls back to known schemas.
    """
    # Try live schema from database
    try:
        from tools.db_client import DBClient

        db = DBClient()
        query = """
        SELECT column_name, data_type, is_nullable,
               character_maximum_length, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        """
        result = await db.execute(query, [table_name])

        if result and result.get("rows"):
            schema = {}
            for row in result["rows"]:
                col_name = row["column_name"]
                schema[col_name] = {
                    "type": row["data_type"],
                    "required": row["is_nullable"] == "NO",
                    "max_length": row.get("character_maximum_length"),
                    "auto": row.get("column_default", "").startswith("nextval")
                            or col_name in AUTO_FIELDS,
                }
            return schema

    except Exception as e:
        logger.debug(f"[validate_schema] Live schema query failed: {e}")

    # Fallback to known schemas
    if table_name == "pending_entry_items":
        return PENDING_ENTRY_ITEMS_SCHEMA

    # Return minimal schema for unknown tables
    return {}


def _find_similar_field(target_field: str, schema: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """
    Find a similar field name for typo suggestions.
    """
    target_lower = target_field.lower()

    # Exact match (case-insensitive)
    for field in schema:
        if field.lower() == target_lower:
            return field

    # Partial match
    for field in schema:
        if target_lower in field or field in target_lower:
            return field

    # Common aliases
    aliases = {
        "pn": "part_number",
        "partnumber": "part_number",
        "desc": "description",
        "qty": "quantity",
        "qtd": "quantity",
        "sn": "serial_number",
        "loc": "location",
    }

    return aliases.get(target_lower)
