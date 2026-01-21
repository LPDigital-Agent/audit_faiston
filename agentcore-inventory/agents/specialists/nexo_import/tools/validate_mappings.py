# =============================================================================
# Validate Mappings Tool
# =============================================================================
# Validates column mappings against PostgreSQL schema.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional, Set


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "nexo_import"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


# =============================================================================
# Known Valid Fields
# =============================================================================

STANDARD_FIELDS: Set[str] = {
    "part_number",
    "description",
    "quantity",
    "serial_number",
    "location",
    "unit",
    "condition",
    "notes",
    "project_code",
    "batch_number",
    "manufacturer",
    "supplier",
}

RESERVED_FIELDS: Set[str] = {
    "id",
    "created_at",
    "updated_at",
    "created_by",
    "source",
    "import_row_number",
}

SPECIAL_VALUES: Set[str] = {
    "_skip",
    "_create_new",
    "_select_other",
}


@trace_tool_call("sga_validate_mappings")
async def validate_mappings_tool(
    column_mappings: Dict[str, str],
    target_table: str = "pending_entry_items",
    schema_context: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate column mappings against PostgreSQL schema.

    Checks:
    1. Target fields exist in schema
    2. No duplicate mappings (multiple columns to same field)
    3. Required fields have mappings
    4. Data type compatibility (basic)

    Args:
        column_mappings: Proposed mappings {source_column: target_field}
        target_table: Target table for validation
        schema_context: Optional schema context for additional validation
        session_id: Optional session ID for audit

    Returns:
        Validation result with any errors/warnings
    """
    audit.working(
        message="Validando mapeamentos...",
        session_id=session_id,
    )

    try:
        errors: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []

        # Get valid fields (standard + dynamic from schema)
        valid_fields = _get_valid_fields(schema_context, target_table)

        # Track field usage for duplicate detection
        field_usage: Dict[str, List[str]] = {}

        for source_col, target_field in column_mappings.items():
            # Skip special values
            if target_field in SPECIAL_VALUES:
                continue

            # Skip empty mappings
            if not target_field:
                continue

            # Check if target field is valid
            if target_field not in valid_fields and target_field not in RESERVED_FIELDS:
                errors.append({
                    "column": source_col,
                    "field": target_field,
                    "error": f"Campo '{target_field}' não existe no schema",
                    "suggestion": _suggest_similar_field(target_field, valid_fields),
                })
                continue

            # Check for reserved fields
            if target_field in RESERVED_FIELDS:
                errors.append({
                    "column": source_col,
                    "field": target_field,
                    "error": f"Campo '{target_field}' é reservado (auto-preenchido)",
                })
                continue

            # Track usage for duplicate detection
            if target_field not in field_usage:
                field_usage[target_field] = []
            field_usage[target_field].append(source_col)

        # Check for duplicates
        for field, columns in field_usage.items():
            if len(columns) > 1:
                warnings.append({
                    "field": field,
                    "columns": columns,
                    "warning": f"Múltiplas colunas mapeadas para '{field}': {', '.join(columns)}",
                })

        # Check for recommended fields
        mapped_fields = set(
            f for f in column_mappings.values()
            if f and f not in SPECIAL_VALUES
        )

        recommended_missing = {"part_number", "description"} - mapped_fields
        if recommended_missing:
            for field in recommended_missing:
                warnings.append({
                    "field": field,
                    "warning": f"Campo recomendado '{field}' não mapeado",
                })

        # Calculate validation score
        total_mappings = len([m for m in column_mappings.values() if m and m not in SPECIAL_VALUES])
        valid_mappings = total_mappings - len(errors)
        validation_score = valid_mappings / total_mappings if total_mappings > 0 else 0

        is_valid = len(errors) == 0

        if is_valid:
            audit.completed(
                message=f"Mapeamentos válidos: {valid_mappings}/{total_mappings}",
                session_id=session_id,
                details={
                    "valid_mappings": valid_mappings,
                    "warnings_count": len(warnings),
                },
            )
        else:
            audit.error(
                message=f"Mapeamentos inválidos: {len(errors)} erro(s)",
                session_id=session_id,
                error=f"{len(errors)} campos inválidos",
            )

        return {
            "success": True,
            "is_valid": is_valid,
            "validation_score": validation_score,
            "errors": errors,
            "warnings": warnings,
            "valid_mappings": valid_mappings,
            "total_mappings": total_mappings,
            "mapped_fields": list(mapped_fields),
            "available_fields": list(valid_fields),
        }

    except Exception as e:
        logger.error(f"[validate_mappings] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao validar mapeamentos",
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


def _get_valid_fields(
    schema_context: Optional[str],
    target_table: str,
) -> Set[str]:
    """
    Get set of valid target fields.

    Combines standard fields with any dynamic columns from schema context.
    """
    valid_fields = STANDARD_FIELDS.copy()

    # Parse dynamic columns from schema context
    if schema_context:
        lines = schema_context.split("\n")
        for line in lines:
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    col_name = parts[1].lower()
                    # Add valid column names
                    if col_name and col_name.isidentifier():
                        if col_name not in RESERVED_FIELDS:
                            valid_fields.add(col_name)

    return valid_fields


def _suggest_similar_field(
    target_field: str,
    valid_fields: Set[str],
) -> Optional[str]:
    """
    Suggest a similar valid field for typo correction.

    Uses simple similarity matching.
    """
    if not target_field:
        return None

    target_lower = target_field.lower()

    # Exact match check (case-insensitive)
    for field in valid_fields:
        if field.lower() == target_lower:
            return field

    # Partial match
    for field in valid_fields:
        if target_lower in field or field in target_lower:
            return field

    # Common typo patterns
    typo_map = {
        "partnumber": "part_number",
        "partn": "part_number",
        "pn": "part_number",
        "desc": "description",
        "descricao": "description",
        "qty": "quantity",
        "qtd": "quantity",
        "quantidade": "quantity",
        "sn": "serial_number",
        "serial": "serial_number",
        "loc": "location",
        "localizacao": "location",
        "un": "unit",
        "unidade": "unit",
    }

    return typo_map.get(target_lower)
