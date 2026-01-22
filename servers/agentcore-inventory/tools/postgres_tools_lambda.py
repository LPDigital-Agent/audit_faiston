"""
PostgreSQL MCP Tools Lambda Handler.

This Lambda function handles tool invocations from AgentCore Gateway.
Per AWS documentation (gateway-add-target-lambda.html):
- Event object: Contains ONLY the tool arguments (properties from inputSchema)
- Context object: Contains bedrockAgentCoreToolName in client_context.custom

Architecture:
    AgentCore Gateway -> Lambda (this) -> RDS Proxy -> Aurora PostgreSQL

Tool Naming Convention (context.client_context.custom['bedrockAgentCoreToolName']):
    Format: {TargetName}___{ToolName} (THREE underscores)
    Example: SGAPostgresTools___sga_list_inventory
    Handler strips prefix and routes to appropriate function.

Author: Faiston NEXO Team
Date: January 2026
Updated: January 2026 - Fix to read tool name from context, not event (per AWS docs)
"""

import json
import logging
import os
from typing import Any, Dict
from datetime import datetime, date

from shared.debug_utils import debug_error

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# Target prefix for tool naming
TARGET_PREFIX = "SGAPostgresTools"


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for AgentCore Gateway tool invocation.

    Per AWS documentation (gateway-add-target-lambda.html):
    - Event object: Contains ONLY the tool arguments (not tool name!)
    - Context object: Contains bedrockAgentCoreToolName in client_context.custom

    Args:
        event: Tool arguments (properties from inputSchema)
        context: Lambda context with client_context.custom metadata

    Returns:
        Tool execution result or error
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Extract tool name from context (per AWS MCP Gateway documentation)
        # The tool name is in context.client_context.custom['bedrockAgentCoreToolName']
        # Format: {TargetName}___{ToolName} (THREE underscores)
        tool_name = ""

        # Try to get tool name from context (MCP Gateway invocation)
        if hasattr(context, 'client_context') and context.client_context:
            custom = getattr(context.client_context, 'custom', None)
            if custom and isinstance(custom, dict):
                tool_name = custom.get('bedrockAgentCoreToolName', '')
                logger.info(f"Tool name from context: {tool_name}")

        # Fallback: Try to get from event (direct invocation for testing)
        if not tool_name:
            tool_name = event.get("name", "")
            if tool_name:
                logger.info(f"Tool name from event (direct invocation): {tool_name}")

        # For MCP Gateway: event IS the arguments (not nested under 'arguments')
        # For direct invocation: arguments may be nested under 'arguments'
        if "arguments" in event and isinstance(event.get("arguments"), dict):
            arguments = event["arguments"]  # Direct invocation format
        else:
            arguments = event  # MCP Gateway format - event IS the arguments

        # Strip target prefix (SGAPostgresTools___)
        # AWS MCP Gateway convention uses THREE underscores: {TargetName}___{ToolName}
        delimiter = "___"
        if delimiter in tool_name:
            actual_tool = tool_name.split(delimiter, 1)[-1]
        else:
            actual_tool = tool_name

        logger.info(f"Executing tool: {actual_tool} with args: {json.dumps(arguments)}")

        # Route to appropriate handler
        handlers = {
            # Data operations
            "sga_list_inventory": handle_list_inventory,
            "sga_get_balance": handle_get_balance,
            "sga_search_assets": handle_search_assets,
            "sga_get_asset_timeline": handle_get_asset_timeline,
            "sga_get_movements": handle_get_movements,
            "sga_get_pending_tasks": handle_get_pending_tasks,
            "sga_create_movement": handle_create_movement,
            "sga_reconcile_sap": handle_reconcile_sap,
            # Schema introspection (for NEXO Import schema-aware validation)
            "sga_get_schema_metadata": handle_get_schema_metadata,
            "sga_get_table_columns": handle_get_table_columns,
            "sga_get_enum_values": handle_get_enum_values,
            # Schema evolution (dynamic column creation)
            "sga_create_column": handle_create_column,
            # Batch operations (Phase 4 - DataTransformer ETL)
            "sga_insert_pending_items_batch": handle_insert_pending_items_batch,
        }

        if actual_tool not in handlers:
            unknown_tool_error = ValueError(f"Unknown tool: {actual_tool}")
            debug_error(unknown_tool_error, "postgres_tools_handler", {"tool_name": actual_tool, "available_tools": list(handlers.keys())})
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"Unknown tool: {actual_tool}"})
                    }
                ],
                "isError": True
            }

        # Execute the tool handler
        result = handlers[actual_tool](arguments)

        logger.info(f"Tool result: {result}")

        # Return MCP-formatted response
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, default=json_serializer)
                }
            ],
            "isError": False
        }

    except Exception as e:
        debug_error(e, "postgres_tools_execute_tool", {"tool_name": actual_tool if 'actual_tool' in dir() else None})
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"error": str(e)})
                }
            ],
            "isError": True
        }


def json_serializer(obj):
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# =============================================================================
# Tool Handlers
# =============================================================================

def handle_list_inventory(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    List assets and balances with optional filters.

    Args:
        location_id: Filter by location
        project_id: Filter by project
        part_number: Filter by part number
        status: Filter by asset status
        limit: Max results (default 100)
        offset: Pagination offset
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    filters = {
        "location_id": arguments.get("location_id"),
        "project_id": arguments.get("project_id"),
        "part_number": arguments.get("part_number"),
        "status": arguments.get("status"),
    }
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    limit = arguments.get("limit", 100)
    offset = arguments.get("offset", 0)

    return client.list_inventory(filters=filters, limit=limit, offset=offset)


def handle_get_balance(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock balance for a part number.

    Args:
        part_number: Part number to query (required)
        location_id: Filter by location (optional)
        project_id: Filter by project (optional)
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    part_number = arguments.get("part_number")
    if not part_number:
        return {"error": "part_number is required"}

    return client.get_balance(
        part_number=part_number,
        location_id=arguments.get("location_id"),
        project_id=arguments.get("project_id")
    )


def handle_search_assets(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search assets by serial number, part number, or description.

    Args:
        query: Search term (required)
        search_type: Type of search (serial, part_number, description, all)
        limit: Max results
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    query = arguments.get("query")
    if not query:
        return {"error": "query is required"}

    return client.search_assets(
        query=query,
        search_type=arguments.get("search_type", "all"),
        limit=arguments.get("limit", 50)
    )


def handle_get_asset_timeline(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get complete history of an asset (event sourcing).

    Args:
        identifier: Asset ID or serial number (required)
        identifier_type: Type of identifier (asset_id, serial_number)
        limit: Max results
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    identifier = arguments.get("identifier")
    if not identifier:
        return {"error": "identifier is required"}

    return client.get_asset_timeline(
        identifier=identifier,
        identifier_type=arguments.get("identifier_type", "serial_number"),
        limit=arguments.get("limit", 100)
    )


def handle_get_movements(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    List movements with filters.

    Args:
        start_date: Start date filter
        end_date: End date filter
        movement_type: Type of movement
        project_id: Filter by project
        location_id: Filter by location
        limit: Max results
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    filters = {
        "start_date": arguments.get("start_date"),
        "end_date": arguments.get("end_date"),
        "movement_type": arguments.get("movement_type"),
        "project_id": arguments.get("project_id"),
        "location_id": arguments.get("location_id"),
    }
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return client.get_movements(
        filters=filters,
        limit=arguments.get("limit", 100)
    )


def handle_get_pending_tasks(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    List pending approval tasks (HIL).

    Args:
        task_type: Type of task
        priority: Task priority
        assignee_id: Filter by assignee
        limit: Max results
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    filters = {
        "task_type": arguments.get("task_type"),
        "priority": arguments.get("priority"),
        "assignee_id": arguments.get("assignee_id"),
    }
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return client.get_pending_tasks(
        filters=filters,
        limit=arguments.get("limit", 50)
    )


def handle_create_movement(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new inventory movement.

    Args:
        movement_type: Type of movement (required)
        part_number: Part number (required)
        quantity: Quantity (required)
        source_location_id: Source location (for exit/transfer)
        destination_location_id: Destination location (for entry/transfer)
        project_id: Project
        serial_numbers: List of serial numbers
        nf_number: NF number
        nf_date: NF date
        reason: Reason for movement
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    # Validate required fields
    required = ["movement_type", "part_number", "quantity"]
    for field in required:
        if field not in arguments:
            return {"error": f"{field} is required"}

    return client.create_movement(
        movement_type=arguments["movement_type"],
        part_number=arguments["part_number"],
        quantity=arguments["quantity"],
        source_location_id=arguments.get("source_location_id"),
        destination_location_id=arguments.get("destination_location_id"),
        project_id=arguments.get("project_id"),
        serial_numbers=arguments.get("serial_numbers", []),
        nf_number=arguments.get("nf_number"),
        nf_date=arguments.get("nf_date"),
        reason=arguments.get("reason")
    )


def handle_reconcile_sap(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare SGA inventory with SAP export data.

    Args:
        sap_data: List of SAP items to compare (required)
        include_serials: Include serial number comparison
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    sap_data = arguments.get("sap_data")
    if not sap_data:
        return {"error": "sap_data is required"}

    return client.reconcile_with_sap(
        sap_data=sap_data,
        include_serials=arguments.get("include_serials", False)
    )


# =============================================================================
# Schema Introspection Handlers (for NEXO Import schema-aware validation)
# =============================================================================
# These tools enable AgentCore agents to query PostgreSQL schema metadata
# via MCP Gateway. Required because AgentCore runs outside VPC and cannot
# directly connect to RDS Proxy.
# =============================================================================


def handle_get_schema_metadata(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get complete schema metadata for all SGA import-related tables.

    This is the main entry point for SchemaProvider to fetch all schema
    knowledge in a single call.

    Returns:
        Dictionary with:
        - tables: Dict[table_name, List[column_info]]
        - enums: Dict[enum_name, List[values]]
        - foreign_keys: Dict[table_name, List[fk_info]]
        - required_columns: Dict[table_name, List[required_column_names]]
        - table_list: List of available table names
        - timestamp: ISO timestamp of retrieval
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    try:
        metadata = client.get_schema_metadata()
        logger.info(
            f"Schema metadata retrieved: {len(metadata.get('tables', {}))} tables, "
            f"{len(metadata.get('enums', {}))} enums"
        )
        return metadata
    except Exception as e:
        debug_error(e, "postgres_tools_get_schema_metadata", {})
        return {"error": str(e)}


def handle_get_table_columns(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get column metadata for a specific table.

    Args:
        table_name: Name of the table (required)
        schema_name: PostgreSQL schema (default: "sga")

    Returns:
        List of column metadata dictionaries with:
        - name: Column name
        - data_type: PostgreSQL data type
        - character_maximum_length: Max length for VARCHAR
        - is_nullable: YES/NO
        - column_default: Default value
        - udt_name: User-defined type name (for ENUMs)
        - is_primary_key: Boolean
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    table_name = arguments.get("table_name")
    if not table_name:
        return {"error": "table_name is required"}

    schema_name = arguments.get("schema_name", "sga")

    try:
        columns = client.get_table_columns(table_name, schema_name)
        logger.info(f"Retrieved {len(columns)} columns for {schema_name}.{table_name}")
        return {"columns": columns, "table_name": table_name, "schema_name": schema_name}
    except Exception as e:
        debug_error(e, "postgres_tools_get_table_columns", {"table_name": table_name, "schema_name": schema_name})
        return {"error": str(e)}


def handle_get_enum_values(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get valid values for a PostgreSQL ENUM type.

    Args:
        enum_name: Name of the ENUM type (required)

    Returns:
        Dictionary with:
        - enum_name: The ENUM type name
        - values: List of valid enum values
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    enum_name = arguments.get("enum_name")
    if not enum_name:
        return {"error": "enum_name is required"}

    try:
        values = client.get_enum_values(enum_name)
        logger.info(f"Retrieved {len(values)} values for enum {enum_name}")
        return {"enum_name": enum_name, "values": values}
    except Exception as e:
        debug_error(e, "postgres_tools_get_enum_values", {"enum_name": enum_name})
        return {"error": str(e)}


# =============================================================================
# Schema Evolution Handler (Dynamic Column Creation)
# =============================================================================
# This tool enables the Schema Evolution Agent (SEA) to dynamically create
# new columns in PostgreSQL when users import CSV files with unknown fields.
#
# Security measures:
# - Table whitelist (only pending_entry_items, pending_entries)
# - Type whitelist (only safe PostgreSQL types)
# - Column name sanitization (SQL injection prevention)
# - Advisory locking (prevents race conditions)
# - Audit logging (all changes logged to schema_evolution_log)
# =============================================================================


def handle_create_column(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new column in a database table with advisory locking.

    This tool is called by the Schema Evolution Agent (SEA) when a user
    approves the creation of a new column during CSV import.

    Concurrency safety:
    - Uses pg_advisory_xact_lock() for transaction-scoped locking
    - Double-checks column existence after acquiring lock
    - Returns success if column already exists (race condition handled)

    Args:
        column_name: Name of the column to create (required)
        table_name: Target table (default: "pending_entry_items")
        column_type: PostgreSQL data type (default: "TEXT")
        requested_by: User ID for audit trail
        original_csv_column: Original column name from CSV
        sample_values: Sample values for type inference debugging
        lock_timeout_ms: Lock acquisition timeout (default: 5000ms)

    Returns:
        Dictionary with:
        - success: bool
        - created: bool (True if new column, False if already existed)
        - column_name: sanitized column name
        - column_type: validated column type
        - reason: explanation string
        - use_metadata_fallback: bool (True if should use JSONB)
        - error: error type string (if failed)
        - message: error message (if failed)
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    # Validate required field
    column_name = arguments.get("column_name")
    if not column_name:
        return {
            "success": False,
            "error": "validation_failed",
            "message": "column_name is required",
            "use_metadata_fallback": True,
        }

    try:
        result = client.create_column_safe(
            table_name=arguments.get("table_name", "pending_entry_items"),
            column_name=column_name,
            column_type=arguments.get("column_type", "TEXT"),
            requested_by=arguments.get("requested_by", "system"),
            original_csv_column=arguments.get("original_csv_column"),
            sample_values=arguments.get("sample_values"),
            lock_timeout_ms=arguments.get("lock_timeout_ms", 5000),
        )

        logger.info(
            f"[SEA] create_column result: success={result.get('success')}, "
            f"created={result.get('created')}, column={result.get('column_name')}"
        )

        return result

    except Exception as e:
        debug_error(e, "postgres_tools_create_column", {"table_name": table_name, "column_name": column_name, "column_type": column_type})
        return {
            "success": False,
            "error": "unexpected_error",
            "message": str(e),
            "use_metadata_fallback": True,
        }


# =============================================================================
# Batch Insert Handler (Phase 4 - DataTransformer ETL)
# =============================================================================

def handle_insert_pending_items_batch(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Batch insert rows into pending_entry_items table.

    Called by DataTransformer agent during Phase 4 ETL.
    session_id from agent = entry_id in database (FK to pending_entries).

    Args:
        rows: List of dicts with column names as keys (required)
              Each row should have: line_number, part_number, description,
              quantity, unit_value, total_value, serial_numbers, etc.
        session_id: Import session ID = entry_id UUID (required)
                    Must exist in pending_entries table (FK enforced)

    Returns:
        {
            "success": bool,
            "inserted_count": int,
            "errors": list of row-level errors with row_index, error, row_data
        }
    """
    from postgres_client import SGAPostgresClient

    client = SGAPostgresClient()

    rows = arguments.get("rows")
    session_id = arguments.get("session_id")  # This is entry_id in DB

    if not rows:
        return {
            "success": False,
            "error": "rows is required",
            "inserted_count": 0,
            "errors": [],
        }
    if not session_id:
        return {
            "success": False,
            "error": "session_id is required",
            "inserted_count": 0,
            "errors": [],
        }
    if not isinstance(rows, list):
        return {
            "success": False,
            "error": "rows must be a list",
            "inserted_count": 0,
            "errors": [],
        }

    try:
        logger.info(
            f"[BatchInsert] Inserting {len(rows)} rows for session_id={session_id}"
        )

        result = client.insert_pending_items_batch(rows=rows, entry_id=session_id)

        logger.info(
            f"[BatchInsert] Result: success={result.get('success')}, "
            f"inserted={result.get('inserted_count')}, errors={len(result.get('errors', []))}"
        )

        return result

    except Exception as e:
        debug_error(
            e, "postgres_tools_insert_batch",
            {"session_id": session_id, "row_count": len(rows) if rows else 0}
        )
        return {
            "success": False,
            "error": str(e),
            "inserted_count": 0,
            "errors": [{"row_index": -1, "error": str(e), "row_data": None}],
        }
