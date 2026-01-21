# =============================================================================
# Validate Data Tool
# =============================================================================
# Validates data rows against schema constraints.
# =============================================================================

import logging
import re
from typing import Dict, Any, List, Optional
from decimal import Decimal, InvalidOperation


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "validation"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


# =============================================================================
# Validation Rules
# =============================================================================

FIELD_VALIDATORS = {
    "part_number": {
        "max_length": 100,
        "pattern": r"^[A-Za-z0-9\-_./]+$",
        "pattern_desc": "Alfanumérico com hífens, underscores, pontos e barras",
    },
    "quantity": {
        "type": "decimal",
        "min_value": 0,
        "max_value": 999999999,
    },
    "serial_number": {
        "max_length": 100,
    },
    "location": {
        "max_length": 255,
    },
    "unit": {
        "max_length": 20,
        "allowed_values": ["UN", "PC", "KG", "L", "M", "M2", "M3", "CX", "PCT", "KIT"],
    },
    "condition": {
        "max_length": 50,
        "allowed_values": ["NEW", "USED", "REFURBISHED", "DAMAGED", "NOVO", "USADO"],
    },
    "project_code": {
        "max_length": 50,
    },
    "batch_number": {
        "max_length": 100,
    },
}


@trace_tool_call("sga_validate_data")
async def validate_data_tool(
    rows: List[Dict[str, Any]],
    column_mappings: Dict[str, str],
    target_table: str = "pending_entry_items",
    max_errors: int = 100,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate data rows against schema constraints.

    Checks:
    1. Data types are correct (numeric, string, etc.)
    2. Values within allowed ranges/lengths
    3. Required fields have non-empty values
    4. Format patterns are respected

    Args:
        rows: Data rows to validate
        column_mappings: Column to field mappings
        target_table: Target table for context
        max_errors: Maximum errors to return (for performance)
        session_id: Optional session ID for audit

    Returns:
        Validation result with row-level errors
    """
    audit.working(
        message=f"Validando {len(rows)} linhas de dados...",
        session_id=session_id,
    )

    try:
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        valid_rows = 0
        invalid_rows = 0

        # Build reverse mapping (target_field -> source_column)
        field_to_source = {v: k for k, v in column_mappings.items() if v}

        for row_idx, row in enumerate(rows):
            row_errors = _validate_row(
                row=row,
                row_number=row_idx + 1,
                column_mappings=column_mappings,
                field_to_source=field_to_source,
            )

            if row_errors:
                invalid_rows += 1
                if len(errors) < max_errors:
                    errors.extend(row_errors)
            else:
                valid_rows += 1

        # Check for empty/null dominant columns
        column_warnings = _check_column_quality(rows, column_mappings)
        warnings.extend(column_warnings)

        # Calculate validation score
        total_rows = len(rows)
        validation_score = valid_rows / total_rows if total_rows > 0 else 0

        is_valid = invalid_rows == 0

        status_msg = "válidas" if is_valid else "com problemas"
        audit.completed(
            message=f"Linhas {status_msg}: {valid_rows}/{total_rows}",
            session_id=session_id,
            details={
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "errors_count": len(errors),
            },
        )

        return {
            "success": True,
            "is_valid": is_valid,
            "validation_score": validation_score,
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "total_rows": total_rows,
            "errors": errors,
            "warnings": warnings,
            "errors_truncated": len(errors) >= max_errors,
        }

    except Exception as e:
        logger.error(f"[validate_data] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao validar dados",
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


def _validate_row(
    row: Dict[str, Any],
    row_number: int,
    column_mappings: Dict[str, str],
    field_to_source: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Validate a single row against field constraints.
    """
    errors = []

    for source_col, target_field in column_mappings.items():
        if not target_field or target_field.startswith("_"):
            continue

        value = row.get(source_col)

        # Get validator for field
        validator = FIELD_VALIDATORS.get(target_field, {})

        # Validate value
        field_errors = _validate_value(
            value=value,
            field=target_field,
            validator=validator,
            row_number=row_number,
            source_col=source_col,
        )

        errors.extend(field_errors)

    return errors


def _validate_value(
    value: Any,
    field: str,
    validator: Dict[str, Any],
    row_number: int,
    source_col: str,
) -> List[Dict[str, Any]]:
    """
    Validate a single value against field constraints.
    """
    errors = []

    # Skip null/empty values (not required check - that's separate)
    if value is None or value == "":
        return errors

    # Convert to string for length checks
    str_value = str(value).strip()

    # Max length check
    max_length = validator.get("max_length")
    if max_length and len(str_value) > max_length:
        errors.append({
            "row": row_number,
            "column": source_col,
            "field": field,
            "value": str_value[:50] + "..." if len(str_value) > 50 else str_value,
            "error": f"Valor excede tamanho máximo ({len(str_value)} > {max_length})",
        })

    # Type check (decimal)
    if validator.get("type") == "decimal":
        try:
            num_value = _parse_decimal(value)
            min_val = validator.get("min_value")
            max_val = validator.get("max_value")

            if min_val is not None and num_value < min_val:
                errors.append({
                    "row": row_number,
                    "column": source_col,
                    "field": field,
                    "value": str(value),
                    "error": f"Valor abaixo do mínimo ({num_value} < {min_val})",
                })

            if max_val is not None and num_value > max_val:
                errors.append({
                    "row": row_number,
                    "column": source_col,
                    "field": field,
                    "value": str(value),
                    "error": f"Valor acima do máximo ({num_value} > {max_val})",
                })

        except (ValueError, InvalidOperation):
            errors.append({
                "row": row_number,
                "column": source_col,
                "field": field,
                "value": str(value),
                "error": "Valor não é numérico válido",
            })

    # Pattern check
    pattern = validator.get("pattern")
    if pattern and not re.match(pattern, str_value):
        errors.append({
            "row": row_number,
            "column": source_col,
            "field": field,
            "value": str_value[:50],
            "error": f"Formato inválido: {validator.get('pattern_desc', 'padrão não atendido')}",
        })

    # Allowed values check
    allowed_values = validator.get("allowed_values")
    if allowed_values:
        upper_value = str_value.upper()
        if upper_value not in [v.upper() for v in allowed_values]:
            errors.append({
                "row": row_number,
                "column": source_col,
                "field": field,
                "value": str_value,
                "error": f"Valor não permitido. Permitidos: {', '.join(allowed_values)}",
            })

    return errors


def _parse_decimal(value: Any) -> Decimal:
    """
    Parse value to decimal, handling Brazilian format.
    """
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    str_value = str(value).strip()

    # Handle Brazilian format (1.000,50 -> 1000.50)
    if "," in str_value:
        str_value = str_value.replace(".", "").replace(",", ".")

    return Decimal(str_value)


def _check_column_quality(
    rows: List[Dict[str, Any]],
    column_mappings: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Check column data quality (empty rates, etc.)
    """
    warnings = []
    total_rows = len(rows)

    if total_rows == 0:
        return warnings

    for source_col, target_field in column_mappings.items():
        if not target_field or target_field.startswith("_"):
            continue

        # Count empty values
        empty_count = sum(
            1 for row in rows
            if row.get(source_col) is None or str(row.get(source_col, "")).strip() == ""
        )

        empty_rate = empty_count / total_rows

        # Warn if more than 80% empty
        if empty_rate > 0.8:
            warnings.append({
                "column": source_col,
                "field": target_field,
                "warning": f"Coluna '{source_col}' tem {empty_rate:.0%} de valores vazios",
                "empty_count": empty_count,
                "total_rows": total_rows,
            })

    return warnings
