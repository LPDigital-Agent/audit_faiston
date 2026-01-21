# =============================================================================
# Get Schema Context Tool
# =============================================================================
# Obtains PostgreSQL schema context for intelligent mapping prompts.
# =============================================================================

import logging
from typing import Dict, Any, Optional


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "nexo_import"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


# =============================================================================
# Default Schema Context (Fallback)
# =============================================================================

DEFAULT_SCHEMA_CONTEXT = """
## PostgreSQL Schema: pending_entry_items

### Core Fields (Standard)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key (auto-generated) |
| part_number | VARCHAR(100) | Part/Equipment number (PN, P/N, Equipamento) |
| description | TEXT | Item description |
| quantity | DECIMAL(10,2) | Quantity (default: 1) |
| serial_number | VARCHAR(100) | Serial number (SN) |
| location | VARCHAR(255) | Storage location |
| unit | VARCHAR(20) | Unit of measure (UN, PC, KG, etc.) |
| condition | VARCHAR(50) | Item condition (NEW, USED, REFURB) |
| notes | TEXT | Additional notes |

### Metadata Fields

| Column | Type | Description |
|--------|------|-------------|
| project_code | VARCHAR(50) | Project/Contract code |
| batch_number | VARCHAR(100) | Lot/Batch number |
| manufacturer | VARCHAR(255) | Manufacturer name |
| supplier | VARCHAR(255) | Supplier name |

### Audit Fields (Auto-populated)

| Column | Type | Description |
|--------|------|-------------|
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |
| created_by | VARCHAR(100) | User who created |
| source | VARCHAR(50) | Data source (import, manual, nf) |

### Dynamic Columns (Schema Evolution)

The schema supports dynamic columns created by SchemaEvolutionAgent.
These columns are created on-demand when new data patterns are detected.

### Common Mapping Patterns

| Source Column Pattern | Target Field |
|-----------------------|--------------|
| PN, P/N, PARTNUMBER, EQUIPAMENTO | part_number |
| QTY, QTD, QUANTIDADE | quantity |
| DESC, DESCRICAO, NOME | description |
| SN, SERIAL | serial_number |
| LOC, LOCALIZACAO | location |
| UN, UNIDADE | unit |
"""


@trace_tool_call("sga_get_schema_context")
async def get_schema_context_tool(
    target_table: str = "pending_entry_items",
    include_dynamic_columns: bool = True,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get PostgreSQL schema context for mapping prompts.

    Retrieves the current schema including:
    - Standard columns with types and descriptions
    - Dynamic columns created by SchemaEvolutionAgent
    - Common mapping patterns from prior knowledge

    Args:
        target_table: Table to get schema for (default: pending_entry_items)
        include_dynamic_columns: Whether to include dynamic columns
        session_id: Optional session ID for audit

    Returns:
        Schema context formatted for LLM prompts
    """
    audit.working(
        message="Obtendo contexto do schema...",
        session_id=session_id,
    )

    try:
        # Try to get live schema from database
        schema_context = await _get_live_schema(target_table, include_dynamic_columns)

        if not schema_context:
            # Use default schema context as fallback
            schema_context = DEFAULT_SCHEMA_CONTEXT
            logger.info("[get_schema_context] Using default schema context")

        # Parse column list from context
        columns = _extract_columns(schema_context)

        audit.completed(
            message=f"Schema obtido: {len(columns)} colunas",
            session_id=session_id,
            details={"column_count": len(columns)},
        )

        return {
            "success": True,
            "schema_context": schema_context,
            "target_table": target_table,
            "columns": columns,
            "column_count": len(columns),
        }

    except Exception as e:
        logger.error(f"[get_schema_context] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao obter schema",
            session_id=session_id,
            error=str(e),
        )

        # Return default context on error
        return {
            "success": True,  # Still success with fallback
            "schema_context": DEFAULT_SCHEMA_CONTEXT,
            "target_table": target_table,
            "columns": _extract_columns(DEFAULT_SCHEMA_CONTEXT),
            "fallback": True,
        }


async def _get_live_schema(
    target_table: str,
    include_dynamic_columns: bool,
) -> Optional[str]:
    """
    Get live schema from PostgreSQL via MCP Gateway.

    Returns schema formatted as markdown for LLM context.
    """
    try:
        from tools.db_client import DBClient

        db = DBClient()

        # Query information_schema for columns
        query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """

        result = await db.execute(query, [target_table])

        if not result or not result.get("rows"):
            return None

        # Build markdown schema
        lines = [
            f"## PostgreSQL Schema: {target_table}",
            "",
            "| Column | Type | Nullable | Description |",
            "|--------|------|----------|-------------|",
        ]

        for row in result["rows"]:
            col_name = row.get("column_name", "")
            data_type = row.get("data_type", "")
            nullable = "Yes" if row.get("is_nullable") == "YES" else "No"
            max_len = row.get("character_maximum_length")

            # Add length info for varchar
            if max_len:
                data_type = f"{data_type}({max_len})"

            # Generate description from column name
            description = _generate_column_description(col_name)

            lines.append(f"| {col_name} | {data_type} | {nullable} | {description} |")

        # Add common mapping patterns
        lines.extend([
            "",
            "### Common Mapping Patterns",
            "",
            "| Source Column Pattern | Target Field |",
            "|-----------------------|--------------|",
            "| PN, P/N, PARTNUMBER, EQUIPAMENTO | part_number |",
            "| QTY, QTD, QUANTIDADE | quantity |",
            "| DESC, DESCRICAO, NOME | description |",
            "| SN, SERIAL | serial_number |",
            "| LOC, LOCALIZACAO | location |",
            "| UN, UNIDADE | unit |",
        ])

        return "\n".join(lines)

    except ImportError:
        logger.info("[get_schema_context] DBClient not available")
        return None

    except Exception as e:
        logger.error(f"[get_schema_context] Live schema error: {e}")
        return None


def _extract_columns(schema_context: str) -> list:
    """
    Extract column names from schema context markdown.
    """
    columns = []
    lines = schema_context.split("\n")

    for line in lines:
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                col_name = parts[1]
                # Skip header rows and separators
                if col_name and col_name != "Column" and not col_name.startswith("-"):
                    if col_name.isidentifier() or "_" in col_name:
                        columns.append(col_name)

    return list(set(columns))  # Deduplicate


def _generate_column_description(col_name: str) -> str:
    """
    Generate human-readable description from column name.
    """
    descriptions = {
        "id": "Primary key",
        "part_number": "Part/Equipment number",
        "description": "Item description",
        "quantity": "Quantity",
        "serial_number": "Serial number",
        "location": "Storage location",
        "unit": "Unit of measure",
        "condition": "Item condition",
        "notes": "Additional notes",
        "project_code": "Project code",
        "batch_number": "Batch/Lot number",
        "manufacturer": "Manufacturer",
        "supplier": "Supplier",
        "created_at": "Creation timestamp",
        "updated_at": "Last update",
        "created_by": "Created by user",
        "source": "Data source",
    }

    return descriptions.get(col_name, col_name.replace("_", " ").title())
