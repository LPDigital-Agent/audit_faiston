"""
Faiston SGA Specialist Agents - Smart Import Architecture

Phase 2+3+4 agents for the NEXO Smart Import flow:

Phase 2 - InventoryAnalyst:
- Analyzes file structure without loading full content
- Detects file type, columns, and data patterns
- Port: 9017

Phase 3 - SchemaMapper:
- Semantic column mapping with MCP schema introspection
- Learns from prior imports via AgentCore Memory
- Port: 9018

Phase 4 - DataTransformer:
- Cognitive ETL with error enrichment (Nexo Immune System)
- Fire-and-Forget background processing
- Port: 9019

Debug Agent:
- Error analysis and debugging support
- Port: 9014

NOTE: carrier, expedition, reverse, reconciliacao agents belong to agentcore-carrier project.
"""

# Phase 2: Inventory Analyst
from .inventory_analyst import (
    AGENT_ID as INVENTORY_ANALYST_ID,
    AGENT_PORT as INVENTORY_ANALYST_PORT,
    create_agent as create_inventory_analyst,
)

# Phase 3: Schema Mapper
from .schema_mapper import (
    AGENT_ID as SCHEMA_MAPPER_ID,
    AGENT_PORT as SCHEMA_MAPPER_PORT,
    create_agent as create_schema_mapper,
)

# Phase 4: Data Transformer
from .data_transformer import (
    AGENT_ID as DATA_TRANSFORMER_ID,
    AGENT_PORT as DATA_TRANSFORMER_PORT,
    create_agent as create_data_transformer,
)

# Debug Agent
from .debug import (
    AGENT_ID as DEBUG_AGENT_ID,
)

__all__ = [
    # Phase 2
    "INVENTORY_ANALYST_ID",
    "INVENTORY_ANALYST_PORT",
    "create_inventory_analyst",
    # Phase 3
    "SCHEMA_MAPPER_ID",
    "SCHEMA_MAPPER_PORT",
    "create_schema_mapper",
    # Phase 4
    "DATA_TRANSFORMER_ID",
    "DATA_TRANSFORMER_PORT",
    "create_data_transformer",
    # Debug
    "DEBUG_AGENT_ID",
]
