"""
Gateway PostgreSQL Adapter for SGA Inventory.

Implements DatabaseAdapter interface by routing database operations
through AgentCore Gateway MCP protocol to Lambda PostgreSQL tools.

Architecture:
    Agent → GatewayPostgresAdapter → MCPGatewayClient (SigV4) → AgentCore Gateway → Lambda → Aurora PostgreSQL

Tool Naming Convention (per AWS docs):
    Format: {TargetName}___{ToolName} (THREE underscores)
    Example: SGAPostgresTools___sga_get_balance

Authentication:
    Uses AWS IAM SigV4 signing (NOT Bearer tokens) per AWS Well-Architected Framework.
    The AgentCore Runtime's execution role provides credentials automatically.

Author: Faiston NEXO Team
Date: January 2026
Updated: January 2026 - Sync client with SigV4 auth
"""

import logging
import re
from typing import Any, Dict, List, Optional

from core_tools.database_adapter import (
    DatabaseAdapter,
    InventoryFilters,
    MovementFilters,
    MovementData,
)
from core_tools.mcp_gateway_client import MCPGatewayClient
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


# =============================================================================
# Input validation for schema evolution
# =============================================================================
# Security: Prevent SQL injection and unauthorized table/column creation

# Allowed tables for dynamic column creation (whitelist)
ALLOWED_TABLES_FOR_SCHEMA_EVOLUTION = frozenset({
    "pending_entry_items",
    "import_staging",
    "import_metadata",
})

# Allowed PostgreSQL column types (whitelist)
ALLOWED_COLUMN_TYPES = frozenset({
    "text",
    "varchar",
    "integer",
    "bigint",
    "numeric",
    "decimal",
    "boolean",
    "date",
    "timestamp",
    "timestamptz",
    "jsonb",
    "uuid",
})

# Column name format: alphanumeric + underscores, must start with letter
COLUMN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", re.IGNORECASE)
MAX_COLUMN_NAME_LENGTH = 63  # PostgreSQL limit


class GatewayPostgresAdapter(DatabaseAdapter):
    """
    Adapter that routes database calls through AgentCore Gateway MCP.

    This adapter translates DatabaseAdapter method calls into MCP tool
    invocations via the Gateway. It handles:
    - Tool name prefixing with target name
    - Argument serialization
    - Response parsing
    - Error handling and logging

    Note: All methods are SYNCHRONOUS. The MCPGatewayClient uses SigV4
    signing and the requests library for HTTP calls.

    Attributes:
        TARGET_PREFIX: MCP target name for PostgreSQL tools
        _client: MCPGatewayClient instance for Gateway communication
    """

    TARGET_PREFIX = "SGAPostgresTools"

    def __init__(self, mcp_client: MCPGatewayClient):
        """
        Initialize Gateway PostgreSQL Adapter.

        Args:
            mcp_client: Configured MCPGatewayClient for Gateway communication
        """
        self._client = mcp_client

    def _tool_name(self, tool: str) -> str:
        """
        Build full tool name with target prefix.

        Per AWS MCP Gateway convention, tools are prefixed with:
        {TargetName}___{ToolName} (THREE underscores)

        Args:
            tool: Base tool name (e.g., "sga_get_balance")

        Returns:
            Full tool name (e.g., "SGAPostgresTools___sga_get_balance")
        """
        return f"{self.TARGET_PREFIX}___{tool}"

    def _clean_none_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove None values from dictionary for cleaner MCP calls.

        Args:
            data: Dictionary potentially containing None values

        Returns:
            Dictionary with None values removed
        """
        return {k: v for k, v in data.items() if v is not None}

    def list_inventory(
        self,
        filters: Optional[InventoryFilters] = None
    ) -> Dict[str, Any]:
        """
        List assets and balances with optional filters.

        Calls: SGAPostgresTools___sga_list_inventory
        """
        arguments = {}
        if filters:
            arguments = self._clean_none_values({
                "location_id": filters.location_id,
                "project_id": filters.project_id,
                "part_number": filters.part_number,
                "status": filters.status.value if filters.status else None,
                "limit": filters.limit,
                "offset": filters.offset,
            })

        logger.debug(f"list_inventory with filters: {arguments}")

        return self._client.call_tool(
            tool_name=self._tool_name("sga_list_inventory"),
            arguments=arguments
        )

    def get_balance(
        self,
        part_number: str,
        location_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get stock balance for a part number.

        Calls: SGAPostgresTools___sga_get_balance
        """
        arguments = self._clean_none_values({
            "part_number": part_number,
            "location_id": location_id,
            "project_id": project_id,
        })

        logger.debug(f"get_balance for: {part_number}")

        return self._client.call_tool(
            tool_name=self._tool_name("sga_get_balance"),
            arguments=arguments
        )

    def search_assets(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search assets by serial number, part number, or description.

        Calls: SGAPostgresTools___sga_search_assets
        """
        arguments = {
            "query": query,
            "search_type": search_type,
            "limit": limit,
        }

        logger.debug(f"search_assets: query='{query}', type={search_type}")

        result = self._client.call_tool(
            tool_name=self._tool_name("sga_search_assets"),
            arguments=arguments
        )

        # Return items list from result
        return result.get("items", []) if isinstance(result, dict) else result

    def get_asset_timeline(
        self,
        identifier: str,
        identifier_type: str = "serial_number",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get complete history of an asset (event sourcing).

        Calls: SGAPostgresTools___sga_get_asset_timeline
        """
        arguments = {
            "identifier": identifier,
            "identifier_type": identifier_type,
            "limit": limit,
        }

        logger.debug(f"get_asset_timeline: {identifier_type}={identifier}")

        result = self._client.call_tool(
            tool_name=self._tool_name("sga_get_asset_timeline"),
            arguments=arguments
        )

        return result.get("events", []) if isinstance(result, dict) else result

    def get_movements(
        self,
        filters: Optional[MovementFilters] = None
    ) -> List[Dict[str, Any]]:
        """
        List movements with filters.

        Calls: SGAPostgresTools___sga_get_movements
        """
        arguments = {}
        if filters:
            arguments = self._clean_none_values({
                "start_date": filters.start_date,
                "end_date": filters.end_date,
                "movement_type": filters.movement_type.value if filters.movement_type else None,
                "project_id": filters.project_id,
                "location_id": filters.location_id,
                "limit": filters.limit,
            })

        logger.debug(f"get_movements with filters: {arguments}")

        result = self._client.call_tool(
            tool_name=self._tool_name("sga_get_movements"),
            arguments=arguments
        )

        return result.get("movements", []) if isinstance(result, dict) else result

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List pending approval tasks (Human-in-the-Loop).

        Calls: SGAPostgresTools___sga_get_pending_tasks
        """
        arguments = self._clean_none_values({
            "task_type": task_type,
            "priority": priority,
            "assignee_id": assignee_id,
            "limit": limit,
        })

        logger.debug(f"get_pending_tasks: {arguments}")

        result = self._client.call_tool(
            tool_name=self._tool_name("sga_get_pending_tasks"),
            arguments=arguments
        )

        return result.get("tasks", []) if isinstance(result, dict) else result

    def create_movement(
        self,
        movement_data: MovementData
    ) -> Dict[str, Any]:
        """
        Create a new inventory movement.

        Calls: SGAPostgresTools___sga_create_movement
        """
        arguments = self._clean_none_values({
            "movement_type": movement_data.movement_type.value,
            "part_number": movement_data.part_number,
            "quantity": movement_data.quantity,
            "source_location_id": movement_data.source_location_id,
            "destination_location_id": movement_data.destination_location_id,
            "project_id": movement_data.project_id,
            "serial_numbers": movement_data.serial_numbers,
            "nf_number": movement_data.nf_number,
            "nf_date": movement_data.nf_date,
            "reason": movement_data.reason,
        })

        logger.info(
            f"create_movement: type={movement_data.movement_type}, "
            f"part={movement_data.part_number}, qty={movement_data.quantity}"
        )

        return self._client.call_tool(
            tool_name=self._tool_name("sga_create_movement"),
            arguments=arguments
        )

    def reconcile_with_sap(
        self,
        sap_data: List[Dict[str, Any]],
        include_serials: bool = False
    ) -> Dict[str, Any]:
        """
        Compare SGA inventory with SAP export data.

        Calls: SGAPostgresTools___sga_reconcile_sap
        """
        arguments = {
            "sap_data": sap_data,
            "include_serials": include_serials,
        }

        logger.info(f"reconcile_with_sap: {len(sap_data)} items")

        return self._client.call_tool(
            tool_name=self._tool_name("sga_reconcile_sap"),
            arguments=arguments
        )

    # =========================================================================
    # Schema Evolution Methods (Dynamic Column Creation)
    # =========================================================================

    def create_column_safe(
        self,
        table_name: str,
        column_name: str,
        column_type: str,
        requested_by: str,
        original_csv_column: Optional[str] = None,
        sample_values: Optional[List[str]] = None,
        lock_timeout_ms: int = 5000,
    ) -> Dict[str, Any]:
        """
        Create a new column in a database table with advisory locking.

        This method is called by the Schema Evolution Agent (SEA) when
        a user approves the creation of a new column during CSV import.

        Calls: SGAPostgresTools___sga_create_column

        Concurrency safety:
        - Uses pg_advisory_xact_lock() in Lambda for transaction-scoped locking
        - Double-checks column existence after acquiring lock
        - Returns success if column already exists (race condition handled)

        Security (Input validation for schema evolution):
        - table_name MUST be in ALLOWED_TABLES_FOR_SCHEMA_EVOLUTION whitelist
        - column_name MUST match COLUMN_NAME_PATTERN (alphanumeric + underscores)
        - column_type MUST be in ALLOWED_COLUMN_TYPES whitelist

        Args:
            table_name: Target table (must be in allowed list)
            column_name: Column name (will be sanitized)
            column_type: PostgreSQL data type (must be in allowed list)
            requested_by: User ID for audit trail
            original_csv_column: Original column name from CSV
            sample_values: Sample values (first 5, for debugging)
            lock_timeout_ms: Lock acquisition timeout (default 5000ms)

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
        # Input validation for schema evolution: validation BEFORE MCP call
        # Security: Prevent SQL injection and unauthorized table/column creation

        # 1. Validate table_name against whitelist
        if table_name not in ALLOWED_TABLES_FOR_SCHEMA_EVOLUTION:
            validation_error = ValueError(f"Table '{table_name}' is not allowed for schema evolution")
            debug_error(validation_error, "sea_validate_table_name", {"table_name": table_name, "allowed_tables": list(ALLOWED_TABLES_FOR_SCHEMA_EVOLUTION)})
            return {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": f"Table '{table_name}' is not allowed for schema evolution",
                "use_metadata_fallback": True,
            }

        # 2. Validate column_name format
        if not column_name or not COLUMN_NAME_PATTERN.match(column_name):
            validation_error = ValueError(f"Column name '{column_name}' has invalid format")
            debug_error(validation_error, "sea_validate_column_name_format", {"column_name": column_name})
            return {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": f"Column name '{column_name}' has invalid format",
                "use_metadata_fallback": True,
            }

        if len(column_name) > MAX_COLUMN_NAME_LENGTH:
            validation_error = ValueError(f"Column name too long ({len(column_name)} > {MAX_COLUMN_NAME_LENGTH})")
            debug_error(validation_error, "sea_validate_column_name_length", {"column_name": column_name, "length": len(column_name), "max_length": MAX_COLUMN_NAME_LENGTH})
            return {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": f"Column name too long ({len(column_name)} > {MAX_COLUMN_NAME_LENGTH})",
                "use_metadata_fallback": True,
            }

        # 3. Validate column_type against whitelist
        column_type_normalized = column_type.lower().split("(")[0].strip()  # Handle varchar(255)
        if column_type_normalized not in ALLOWED_COLUMN_TYPES:
            validation_error = ValueError(f"Column type '{column_type}' is not allowed")
            debug_error(validation_error, "sea_validate_column_type", {"column_type": column_type, "allowed_types": list(ALLOWED_COLUMN_TYPES)})
            return {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": f"Column type '{column_type}' is not allowed",
                "use_metadata_fallback": True,
            }

        # 4. Validate requested_by is not empty
        if not requested_by or not requested_by.strip():
            validation_error = ValueError("requested_by is required for audit trail")
            debug_error(validation_error, "sea_validate_requested_by", {"requested_by": requested_by})
            return {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "requested_by is required for audit trail",
            }

        # Validation passed - proceed with MCP call
        arguments = self._clean_none_values({
            "table_name": table_name,
            "column_name": column_name.lower(),  # Normalize to lowercase
            "column_type": column_type,
            "requested_by": requested_by.strip(),
            "original_csv_column": original_csv_column,
            "sample_values": sample_values[:5] if sample_values else None,  # Limit samples
            "lock_timeout_ms": lock_timeout_ms,
        })

        logger.info(
            "[SEA] create_column_safe: table=%s, column=%s, type=%s, user=%s",
            table_name, column_name, column_type, requested_by
        )

        return self._client.call_tool(
            tool_name=self._tool_name("sga_create_column"),
            arguments=arguments
        )


class GatewayAdapterFactory:
    """
    Factory for creating GatewayPostgresAdapter instances.

    Handles the setup of MCPGatewayClient and adapter creation,
    abstracting the complexity from agent code.

    Uses IAM-based authentication (SigV4) - no tokens required.
    The AgentCore Runtime's execution role provides credentials.
    """

    @staticmethod
    def create_from_env() -> GatewayPostgresAdapter:
        """
        Create adapter from environment variables.

        Uses IAM SigV4 authentication (not Bearer tokens).
        Credentials come from AgentCore Runtime's execution role.

        Environment Variables:
            AGENTCORE_GATEWAY_URL: Full MCP endpoint URL
            AGENTCORE_GATEWAY_ID: Gateway ID (alternative to full URL)
            AWS_REGION: AWS region for URL construction and SigV4 signing

        Returns:
            Configured GatewayPostgresAdapter

        Raises:
            ValueError: If required environment variables are missing
        """
        from core_tools.mcp_gateway_client import MCPGatewayClientFactory

        client = MCPGatewayClientFactory.create_from_env()
        logger.info("[GatewayAdapterFactory] Created adapter with IAM auth (SigV4)")

        return GatewayPostgresAdapter(client)

    @staticmethod
    def create_with_url(
        gateway_url: str,
        region: str = "us-east-2"
    ) -> GatewayPostgresAdapter:
        """
        Create adapter with explicit Gateway URL.

        Uses IAM SigV4 authentication (not Bearer tokens).

        Args:
            gateway_url: Full Gateway MCP endpoint URL
            region: AWS region for SigV4 signing

        Returns:
            Configured GatewayPostgresAdapter
        """
        from core_tools.mcp_gateway_client import MCPGatewayClient

        client = MCPGatewayClient(gateway_url=gateway_url, region=region)
        logger.info(f"[GatewayAdapterFactory] Created adapter for {gateway_url}")

        return GatewayPostgresAdapter(client)
