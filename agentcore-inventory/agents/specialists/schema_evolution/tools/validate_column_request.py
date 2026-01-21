# =============================================================================
# Validate Column Request Tool
# =============================================================================
# Validates column creation request against security rules.
# =============================================================================

from typing import Dict, Any

from shared.xray_tracer import trace_tool_call

# Whitelists
ALLOWED_TABLES = frozenset({
    "pending_entry_items",
    "pending_entries",
})

ALLOWED_TYPES = frozenset({
    "TEXT",
    "VARCHAR(100)",
    "VARCHAR(255)",
    "VARCHAR(500)",
    "INTEGER",
    "BIGINT",
    "NUMERIC(12,2)",
    "BOOLEAN",
    "TIMESTAMPTZ",
    "DATE",
    "JSONB",
    "TEXT[]",
})


@trace_tool_call("sga_validate_column_request")
async def validate_column_request_tool(
    table_name: str,
    column_name: str,
    column_type: str,
) -> Dict[str, Any]:
    """
    Validate column creation request before sending to MCP.

    Performs security checks:
    - Table whitelist validation
    - Type whitelist validation
    - Column name format validation
    - SQL injection pattern detection

    Args:
        table_name: Target table for column creation
        column_name: Sanitized column name
        column_type: PostgreSQL data type

    Returns:
        Dictionary with:
        - valid: bool - Whether request passed all checks
        - errors: List[str] - List of validation errors
    """
    errors = []

    # Table whitelist check
    if table_name not in ALLOWED_TABLES:
        errors.append(
            f"Tabela '{table_name}' não permitida para colunas dinâmicas. "
            f"Tabelas permitidas: {', '.join(ALLOWED_TABLES)}"
        )

    # Column name validation
    if not column_name or len(column_name) < 2:
        errors.append("Nome da coluna muito curto (mínimo 2 caracteres)")

    if len(column_name) > 63:
        errors.append("Nome da coluna excede limite do PostgreSQL (63 chars)")

    # Type whitelist check
    if column_type not in ALLOWED_TYPES:
        errors.append(
            f"Tipo '{column_type}' não permitido. "
            f"Tipos permitidos: {', '.join(sorted(ALLOWED_TYPES))}"
        )

    # SQL injection pattern detection
    dangerous_patterns = [
        "drop", "delete", "insert", "update", "select", "truncate",
        "alter", "create", "grant", "revoke", ";", "--", "/*", "*/",
    ]
    name_lower = column_name.lower()
    for pattern in dangerous_patterns:
        if pattern in name_lower:
            errors.append(f"Nome da coluna contém padrão SQL perigoso: '{pattern}'")
            break

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "table_name": table_name,
        "column_name": column_name,
        "column_type": column_type,
    }
