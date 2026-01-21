# =============================================================================
# Create Column Tool
# =============================================================================
# Creates a new PostgreSQL column via MCP Gateway.
#
# CRITICAL: NO direct PostgreSQL connections - ALL access via MCP Gateway!
# =============================================================================

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

# Agent configuration
AGENT_ID = "schema_evolution"

# Audit emitter
audit = AgentAuditEmitter(agent_id=AGENT_ID)

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


# =============================================================================
# Result Type
# =============================================================================

@dataclass
class SchemaChangeResult:
    """Result of a schema change operation."""
    success: bool
    created: bool = False
    column_name: str = ""
    column_type: str = ""
    reason: str = ""
    use_metadata_fallback: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "created": self.created,
            "column_name": self.column_name,
            "column_type": self.column_type,
            "reason": self.reason,
            "use_metadata_fallback": self.use_metadata_fallback,
            "error": self.error,
        }


# =============================================================================
# Helper Functions
# =============================================================================

def _sanitize_column_name(raw_name: str) -> str:
    """Sanitize column name for PostgreSQL."""
    if not raw_name:
        return "unknown_field"

    name = raw_name.lower().strip()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')

    if name and name[0].isdigit():
        name = f"col_{name}"

    return name[:63] if name else "unknown_field"


def _infer_column_type(sample_values: List[str]) -> str:
    """Infer PostgreSQL type from sample data."""
    if not sample_values:
        return "TEXT"

    non_empty = [v.strip() for v in sample_values if v and v.strip()]
    if not non_empty:
        return "TEXT"

    # Check for integers
    def is_integer(v):
        try:
            cleaned = v.replace(",", "").replace(".", "").strip()
            int(cleaned)
            return "." not in v or v.count(".") == v.count(",")
        except (ValueError, AttributeError):
            return False

    if all(is_integer(v) for v in non_empty):
        try:
            max_val = max(abs(int(v.replace(",", "").replace(".", "")))
                         for v in non_empty)
            return "BIGINT" if max_val > 2147483647 else "INTEGER"
        except ValueError:
            return "INTEGER"

    # Check for decimals
    def is_decimal(v):
        try:
            cleaned = v.replace(" ", "")
            if "," in cleaned and "." in cleaned:
                if cleaned.index(",") > cleaned.index("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            float(cleaned)
            return True
        except (ValueError, AttributeError):
            return False

    if all(is_decimal(v) for v in non_empty):
        return "NUMERIC(12,2)"

    # Check for booleans
    bool_values = {'true', 'false', '1', '0', 'yes', 'no', 'sim', 'não', 'nao'}
    if all(v.lower() in bool_values for v in non_empty):
        return "BOOLEAN"

    # Check for dates
    date_patterns = [
        r'^\d{4}-\d{2}-\d{2}',
        r'^\d{2}/\d{2}/\d{4}',
        r'^\d{2}-\d{2}-\d{4}',
    ]

    def is_date(v):
        return any(re.match(p, v.strip()) for p in date_patterns)

    if all(is_date(v) for v in non_empty):
        return "TIMESTAMPTZ"

    # Default: Text with length consideration
    max_len = max(len(v) for v in non_empty)
    if max_len <= 100:
        return "VARCHAR(100)"
    elif max_len <= 255:
        return "VARCHAR(255)"
    elif max_len <= 500:
        return "VARCHAR(500)"
    return "TEXT"


def _validate_request(table_name: str, column_name: str, column_type: str) -> Dict[str, Any]:
    """Validate column creation request."""
    errors = []

    if table_name not in ALLOWED_TABLES:
        errors.append(
            f"Tabela '{table_name}' não permitida. "
            f"Permitidas: {', '.join(ALLOWED_TABLES)}"
        )

    if not column_name or len(column_name) < 2:
        errors.append("Nome da coluna muito curto")

    if column_type not in ALLOWED_TYPES:
        errors.append(f"Tipo '{column_type}' não permitido")

    # SQL injection check
    dangerous = ["drop", "delete", "insert", "update", "select", ";", "--"]
    if any(p in column_name.lower() for p in dangerous):
        errors.append("Nome contém padrão SQL perigoso")

    return {"valid": len(errors) == 0, "errors": errors}


# =============================================================================
# Gateway Adapter
# =============================================================================

_db_adapter = None


def _get_db_adapter():
    """Lazy-load MCP Gateway adapter."""
    global _db_adapter
    if _db_adapter is None:
        try:
            from tools.gateway_adapter import GatewayAdapterFactory
            _db_adapter = GatewayAdapterFactory.create_from_env()
            logger.info("[create_column] Gateway adapter initialized")
        except Exception as e:
            logger.error(f"[create_column] Gateway adapter init failed: {e}")
    return _db_adapter


# =============================================================================
# Tool Definition
# =============================================================================

@trace_tool_call("sga_create_column")
async def create_column_tool(
    table_name: str,
    column_name: str,
    column_type: str,
    requested_by: str,
    original_csv_column: Optional[str] = None,
    sample_values: Optional[List[str]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new PostgreSQL column via MCP Gateway.

    CRITICAL: No direct DB connections! All access via MCP Gateway.

    Workflow:
    1. Sanitize column name
    2. Infer type if not valid
    3. Validate against security rules
    4. Call MCP tool via Gateway Adapter
    5. Return result with fallback recommendation if needed

    Args:
        table_name: Target table (must be in ALLOWED_TABLES)
        column_name: Column name (will be sanitized)
        column_type: PostgreSQL type (will be validated/inferred)
        requested_by: User ID for audit trail
        original_csv_column: Original CSV header name
        sample_values: Sample values for type inference
        session_id: Optional session ID for audit

    Returns:
        SchemaChangeResult as dict
    """
    audit.started(
        message=f"Criando coluna: {column_name} em {table_name}",
        session_id=session_id,
    )

    try:
        # Step 1: Sanitize column name
        safe_column = _sanitize_column_name(column_name)

        # Step 2: Infer type if not valid
        if column_type not in ALLOWED_TYPES:
            column_type = _infer_column_type(sample_values or [])
            logger.info(f"[create_column] Inferred type: {column_type}")

        # Step 3: Validate request
        validation = _validate_request(table_name, safe_column, column_type)
        if not validation["valid"]:
            result = SchemaChangeResult(
                success=False,
                error="validation_failed",
                reason="; ".join(validation["errors"]),
                use_metadata_fallback=True,
            )
            audit.error(
                message=f"Validação falhou: {result.reason}",
                session_id=session_id,
            )
            return result.to_dict()

        # Step 4: Call MCP tool via Gateway
        db_adapter = _get_db_adapter()
        if not db_adapter:
            result = SchemaChangeResult(
                success=False,
                error="gateway_unavailable",
                reason="MCP Gateway não disponível",
                use_metadata_fallback=True,
            )
            audit.error(
                message="Gateway não disponível",
                session_id=session_id,
            )
            return result.to_dict()

        mcp_result = db_adapter.create_column_safe(
            table_name=table_name,
            column_name=safe_column,
            column_type=column_type,
            requested_by=requested_by,
            original_csv_column=original_csv_column,
            sample_values=sample_values[:5] if sample_values else None,
        )

        result = SchemaChangeResult(
            success=mcp_result.get("success", False),
            created=mcp_result.get("created", False),
            column_name=mcp_result.get("column_name", safe_column),
            column_type=mcp_result.get("column_type", column_type),
            reason=mcp_result.get("reason", ""),
            use_metadata_fallback=mcp_result.get("use_metadata_fallback", False),
            error=mcp_result.get("error"),
        )

        audit.completed(
            message=f"Coluna criada: {result.column_name}",
            session_id=session_id,
            details={"created": result.created},
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"[create_column] Error: {e}", exc_info=True)
        result = SchemaChangeResult(
            success=False,
            error="mcp_call_failed",
            reason=f"Erro ao chamar MCP Gateway: {str(e)[:200]}",
            use_metadata_fallback=True,
        )
        audit.error(
            message="Erro ao criar coluna",
            session_id=session_id,
            error=str(e),
        )
        return result.to_dict()
