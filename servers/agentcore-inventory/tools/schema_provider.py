"""
Schema Provider for SGA Inventory.

Centralized schema knowledge base that provides PostgreSQL schema metadata
to NEXO agents. Implements caching to minimize database round trips.

Philosophy: Agents should LEARN the schema BEFORE analyzing import files.
This enables schema-aware reasoning and validation.

Architecture:
    SchemaProvider (Singleton)
        ├─ get_table_schema() → Table column metadata
        ├─ get_enum_values() → ENUM valid values
        ├─ get_schema_for_prompt() → Markdown for Gemini prompts
        └─ validate_column_exists() → Column existence check

Cache TTL: 5 minutes (schema rarely changes during import sessions)

Author: Faiston NEXO Team
Date: January 2026
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)

# Feature flag: Use MCP Gateway for schema queries (required when running in AgentCore)
USE_POSTGRES_MCP = os.environ.get("USE_POSTGRES_MCP", "true").lower() == "true"


# =============================================================================
# Data Classes for Schema Metadata
# =============================================================================


@dataclass
class ColumnInfo:
    """
    Column metadata from PostgreSQL information_schema.

    Used by agents to understand target table structure
    and validate column mappings.
    """
    name: str                           # Column name (e.g., "part_number")
    data_type: str                      # PostgreSQL type (e.g., "character varying")
    max_length: Optional[int] = None    # For VARCHAR(n)
    is_nullable: bool = True            # Can be NULL?
    default_value: Optional[str] = None # Default value
    is_primary_key: bool = False        # Is PK?
    is_foreign_key: bool = False        # Is FK?
    fk_reference: Optional[str] = None  # FK target (e.g., "sga.part_numbers.part_number_id")
    udt_name: Optional[str] = None      # User-defined type (for ENUMs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "max_length": self.max_length,
            "is_nullable": self.is_nullable,
            "default_value": self.default_value,
            "is_primary_key": self.is_primary_key,
            "is_foreign_key": self.is_foreign_key,
            "fk_reference": self.fk_reference,
            "udt_name": self.udt_name,
        }


@dataclass
class TableSchema:
    """
    Complete schema for a PostgreSQL table.

    Includes columns, primary keys, and foreign key relationships.
    """
    table_name: str                     # Table name (e.g., "pending_entry_items")
    schema_name: str = "sga"            # PostgreSQL schema
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = field(default_factory=list)
    required_columns: List[str] = field(default_factory=list)  # NOT NULL without default

    def get_column(self, name: str) -> Optional[ColumnInfo]:
        """Get a column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_column_names(self) -> List[str]:
        """Get list of all column names."""
        return [col.name for col in self.columns]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "table_name": self.table_name,
            "schema_name": self.schema_name,
            "columns": [col.to_dict() for col in self.columns],
            "primary_key": self.primary_key,
            "foreign_keys": self.foreign_keys,
            "required_columns": self.required_columns,
        }


# =============================================================================
# Schema Provider (Singleton)
# =============================================================================


class SchemaProvider:
    """
    Singleton that provides schema metadata to NEXO agents.

    Implements caching with 5-minute TTL to minimize database round trips.
    Schema is retrieved once and reused across multiple agent invocations.

    Usage:
        provider = SchemaProvider()  # Uses postgres_client internally
        schema = provider.get_table_schema("pending_entry_items")
        prompt_context = provider.get_schema_for_prompt("movements")
    """

    # Cache TTL in seconds (5 minutes)
    CACHE_TTL_SECONDS = 300

    # Singleton instance
    _instance: Optional["SchemaProvider"] = None
    _initialized: bool = False

    def __new__(cls):
        """Singleton pattern - ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the schema provider (only once)."""
        if SchemaProvider._initialized:
            return

        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: float = 0.0
        self._postgres_client = None  # Lazy initialization (direct connection)
        self._mcp_client = None       # Lazy initialization (MCP Gateway)
        self._use_mcp = USE_POSTGRES_MCP

        SchemaProvider._initialized = True
        logger.info(f"[SchemaProvider] Initialized (singleton, use_mcp={self._use_mcp})")

    def _get_mcp_client(self):
        """
        Get or create MCP Gateway client (lazy initialization).

        Uses IAM SigV4 authentication (not Bearer tokens) per AWS Well-Architected
        Framework best practices. Credentials come from AgentCore Runtime's
        execution role automatically.
        """
        if self._mcp_client is None:
            try:
                from tools.mcp_gateway_client import MCPGatewayClientFactory

                # No token provider needed - uses IAM credentials via SigV4
                self._mcp_client = MCPGatewayClientFactory.create_from_env()
                logger.info("[SchemaProvider] MCP Gateway client initialized (IAM auth)")
            except Exception as e:
                debug_error(e, "schema_provider_create_mcp_client", {})
                raise
        return self._mcp_client

    def _get_client(self):
        """Get or create PostgreSQL client (lazy initialization)."""
        if self._postgres_client is None:
            # Lazy import to avoid cold start impact
            from tools.postgres_client import SGAPostgresClient
            self._postgres_client = SGAPostgresClient()
            logger.info("[SchemaProvider] PostgreSQL client initialized")
        return self._postgres_client

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._cache:
            return False
        age = time.time() - self._cache_timestamp
        return age < self.CACHE_TTL_SECONDS

    def _refresh_cache(self) -> None:
        """
        Refresh schema cache from database.

        Uses MCP Gateway if USE_POSTGRES_MCP=true (required for AgentCore),
        otherwise connects directly to PostgreSQL.
        """
        try:
            if self._use_mcp:
                # Use MCP Gateway to query schema (AgentCore path)
                metadata = self._refresh_via_mcp()
            else:
                # Direct PostgreSQL connection (Lambda path)
                client = self._get_client()
                metadata = client.get_schema_metadata()

            self._cache = metadata
            self._cache_timestamp = time.time()
            logger.info(
                f"[SchemaProvider] Cache refreshed via {'MCP' if self._use_mcp else 'direct'}: "
                f"{len(metadata.get('tables', {}))} tables, "
                f"{len(metadata.get('enums', {}))} enums"
            )
        except Exception as e:
            debug_error(e, "schema_provider_refresh_cache", {"use_mcp": self._use_mcp})
            # Keep stale cache if refresh fails
            if not self._cache:
                raise

    def _refresh_via_mcp(self) -> Dict[str, Any]:
        """
        Fetch schema metadata via MCP Gateway.

        Calls the sga_get_schema_metadata tool through the Gateway.
        Uses synchronous MCPGatewayClient with SigV4 signing.

        Returns:
            Schema metadata dictionary
        """
        try:
            mcp_client = self._get_mcp_client()

            # Synchronous call - no async/await needed
            # Tool name format: {TargetName}___{tool_name} (THREE underscores per AWS MCP Gateway convention)
            result = mcp_client.call_tool(
                tool_name="SGAPostgresTools___sga_get_schema_metadata",
                arguments={}
            )

            if not result:
                raise ValueError("Empty response from MCP Gateway")

            # Result is already parsed by mcp_gateway_client.call_tool()
            if isinstance(result, dict):
                if "error" in result:
                    raise ValueError(f"MCP tool error: {result['error']}")
                if "tables" in result:
                    return result

            raise ValueError(f"Unexpected MCP response format: {type(result)}")

        except Exception as e:
            debug_error(e, "schema_provider_mcp_refresh", {})
            raise

    def _ensure_cache(self) -> None:
        """Ensure cache is populated and valid."""
        if not self._is_cache_valid():
            self._refresh_cache()

    def get_table_schema(self, table_name: str) -> Optional[TableSchema]:
        """
        Get schema for a specific table.

        Args:
            table_name: Name of the table (e.g., "pending_entry_items")

        Returns:
            TableSchema object or None if table not found
        """
        self._ensure_cache()

        tables = self._cache.get("tables", {})
        foreign_keys = self._cache.get("foreign_keys", {})
        required_columns = self._cache.get("required_columns", {})

        if table_name not in tables:
            logger.warning(f"[SchemaProvider] Table not found: {table_name}")
            return None

        columns_data = tables[table_name]
        fks = foreign_keys.get(table_name, [])
        required = required_columns.get(table_name, [])

        # Build FK lookup for quick reference
        fk_lookup = {fk["column_name"]: fk for fk in fks}

        # Convert to ColumnInfo objects
        columns = []
        primary_keys = []

        for col_data in columns_data:
            col_name = col_data["name"]
            fk_info = fk_lookup.get(col_name)

            col = ColumnInfo(
                name=col_name,
                data_type=col_data.get("data_type", "unknown"),
                max_length=col_data.get("character_maximum_length"),
                is_nullable=col_data.get("is_nullable") == "YES",
                default_value=col_data.get("column_default"),
                is_primary_key=col_data.get("is_primary_key", False),
                is_foreign_key=fk_info is not None,
                fk_reference=(
                    f"{fk_info['foreign_table_schema']}.{fk_info['foreign_table_name']}.{fk_info['foreign_column_name']}"
                    if fk_info else None
                ),
                udt_name=col_data.get("udt_name"),
            )
            columns.append(col)

            if col.is_primary_key:
                primary_keys.append(col_name)

        return TableSchema(
            table_name=table_name,
            schema_name="sga",
            columns=columns,
            primary_key=primary_keys,
            foreign_keys=fks,
            required_columns=required,
        )

    def get_enum_values(self, enum_name: str) -> List[str]:
        """
        Get valid values for a PostgreSQL ENUM type.

        Args:
            enum_name: Name of the ENUM (e.g., "movement_type")

        Returns:
            List of valid enum values
        """
        self._ensure_cache()
        enums = self._cache.get("enums", {})
        return enums.get(enum_name, [])

    def get_all_enums(self) -> Dict[str, List[str]]:
        """
        Get all ENUM types and their values.

        Returns:
            Dictionary mapping enum name to list of values
        """
        self._ensure_cache()
        return self._cache.get("enums", {})

    def get_all_target_tables(self) -> List[str]:
        """
        Get list of all import-relevant tables.

        Returns:
            List of table names
        """
        self._ensure_cache()
        return self._cache.get("table_list", [])

    def validate_column_exists(self, table_name: str, column_name: str) -> bool:
        """
        Check if a column exists in a table.

        Args:
            table_name: Table name
            column_name: Column name to check

        Returns:
            True if column exists, False otherwise
        """
        schema = self.get_table_schema(table_name)
        if not schema:
            return False
        return column_name in schema.get_column_names()

    def get_required_columns(self, table_name: str) -> List[str]:
        """
        Get required columns (NOT NULL without default) for a table.

        Args:
            table_name: Table name

        Returns:
            List of required column names
        """
        schema = self.get_table_schema(table_name)
        if not schema:
            return []
        return schema.required_columns

    def get_schema_version(self) -> str:
        """
        Get a hash representing the current schema version.

        Used by LearningAgent to track schema changes and
        invalidate stale learned mappings.

        Returns:
            MD5 hash of schema structure
        """
        self._ensure_cache()

        # Create hash from table structure
        tables = self._cache.get("tables", {})
        schema_str = str(sorted(tables.items()))
        return hashlib.md5(schema_str.encode()).hexdigest()[:16]

    def get_schema_for_prompt(self, table_name: str) -> str:
        """
        Format table schema as markdown for Gemini prompt injection.

        This method produces human-readable schema documentation
        that helps Gemini understand target table structure.

        Args:
            table_name: Table name to document

        Returns:
            Markdown-formatted schema documentation
        """
        schema = self.get_table_schema(table_name)
        if not schema:
            return f"⚠️ Tabela '{table_name}' não encontrada no schema."

        lines = [
            f"### Tabela: sga.{table_name}",
            "",
            "| Coluna | Tipo | Obrigatório | FK | Descrição |",
            "|--------|------|-------------|----|-----------| ",
        ]

        for col in schema.columns:
            # Format type with length
            data_type = col.data_type
            if col.max_length:
                data_type = f"{data_type}({col.max_length})"

            # Check if it's an ENUM
            if col.udt_name and col.udt_name in self.get_all_enums():
                enum_values = self.get_enum_values(col.udt_name)
                data_type = f"ENUM: {', '.join(enum_values[:5])}"
                if len(enum_values) > 5:
                    data_type += f" (+{len(enum_values) - 5})"

            # Required indicator
            required = "SIM" if col.name in schema.required_columns else "não"
            if col.is_primary_key:
                required = "PK (auto)"

            # FK indicator
            fk = ""
            if col.fk_reference:
                fk = f"→ {col.fk_reference.split('.')[-2]}"

            # Description (basic inference)
            desc = self._infer_column_description(col.name)

            lines.append(f"| `{col.name}` | {data_type} | {required} | {fk} | {desc} |")

        # Add ENUMs section if table uses them
        enum_cols = [col for col in schema.columns if col.udt_name in self.get_all_enums()]
        if enum_cols:
            lines.append("")
            lines.append("#### ENUMs Utilizados")
            for col in enum_cols:
                values = self.get_enum_values(col.udt_name)
                lines.append(f"- **{col.udt_name}**: `{', '.join(values)}`")

        return "\n".join(lines)

    def get_full_schema_for_prompt(self, tables: Optional[List[str]] = None) -> str:
        """
        Get schema documentation for multiple tables.

        Args:
            tables: List of table names (default: main import tables)

        Returns:
            Markdown-formatted schema documentation
        """
        if tables is None:
            tables = ["pending_entry_items", "movements", "part_numbers", "locations"]

        sections = []
        for table in tables:
            sections.append(self.get_schema_for_prompt(table))

        # Add global ENUMs section
        all_enums = self.get_all_enums()
        if all_enums:
            sections.append("")
            sections.append("### ENUMs Globais")
            for enum_name, values in all_enums.items():
                sections.append(f"- **{enum_name}**: `{', '.join(values)}`")

        return "\n\n".join(sections)

    def _infer_column_description(self, column_name: str) -> str:
        """
        Infer a basic description from column name.

        This is a helper for documentation - not definitive.
        """
        descriptions = {
            "part_number": "Código do material/SKU",
            "description": "Descrição do item",
            "quantity": "Quantidade (inteiro)",
            "serial_number": "Número de série",
            "serial_numbers": "Lista de números de série",
            "location_id": "ID da localização",
            "location_code": "Código da localização",
            "project_id": "ID do projeto/cliente",
            "project_code": "Código do projeto",
            "movement_type": "Tipo de movimento",
            "movement_date": "Data do movimento",
            "source_location_id": "Origem (para saída/transferência)",
            "destination_location_id": "Destino (para entrada/transferência)",
            "nf_number": "Número da NF",
            "nf_date": "Data da NF",
            "nf_key": "Chave da NF eletrônica",
            "supplier_name": "Nome do fornecedor",
            "supplier_cnpj": "CNPJ do fornecedor",
            "status": "Status atual",
            "created_at": "Data de criação (auto)",
            "updated_at": "Data de atualização (auto)",
            "created_by": "Usuário que criou",
            "is_active": "Registro ativo?",
            "metadata": "Campos customizados (JSON)",
        }
        return descriptions.get(column_name, "-")

    def clear_cache(self) -> None:
        """Force cache refresh on next access."""
        self._cache = {}
        self._cache_timestamp = 0.0
        logger.info("[SchemaProvider] Cache cleared")


# =============================================================================
# Helper Functions
# =============================================================================


def get_schema_provider() -> SchemaProvider:
    """
    Get the singleton SchemaProvider instance.

    Returns:
        SchemaProvider instance
    """
    return SchemaProvider()
