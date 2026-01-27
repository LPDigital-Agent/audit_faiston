"""Configuration module for InventoryHub orchestrator.

This module centralizes all configuration constants, environment variables,
and singleton patterns used by the InventoryHub agent. Extracted from main.py
to improve maintainability and reduce file size.

Architecture Note:
    InventoryHub is the central orchestrator for SGA file ingestion.
    It coordinates Phase 1-5 of the NEXO Cognitive Import Pipeline.

Environment Variables:
    ENABLE_AUTO_SCHEMA_MAPPING: Enable automatic Phase 3 triggering (default: "true")

Lazy import for AgentCore timeout compliance:
    MCPGatewayClientFactory is imported INSIDE get_mcp_file_analyzer() to:
    1. Avoid circular imports at module load time
    2. Allow sys.path modification before import
    3. Resolve namespace collision between agents/tools/ and root tools/
"""

import logging
import os

logger = logging.getLogger(__name__)

# =============================================================================
# Agent Identity Constants
# =============================================================================

AGENT_ID: str = "inventory_hub"
"""Unique identifier for the InventoryHub agent used in A2A communication."""

AGENT_NAME: str = "FaistonInventoryHub"
"""Human-readable name for the agent displayed in logs and monitoring."""

AGENT_DESCRIPTION: str = (
    "Central orchestrator for NEXO Cognitive Import Pipeline. "
    "Coordinates Phases 1-5: File Ingestion, Structure Analysis, "
    "Schema Mapping (A2A), Data Transformation (A2A), and Insights."
)
"""Full description of the agent's capabilities for A2A discovery."""

RUNTIME_ID: str = "faiston_sga_inventory_hub"
"""AgentCore Runtime identifier for deployment and routing."""

# =============================================================================
# Feature Flags
# =============================================================================

ENABLE_AUTO_SCHEMA_MAPPING: bool = os.getenv(
    "ENABLE_AUTO_SCHEMA_MAPPING", "true"
).lower() == "true"
"""
Enable automatic Phase 3 (SchemaMapper) triggering after Phase 2 analysis.

When True (default), file analysis automatically invokes SchemaMapper
to propose column mappings. When False, Phase 3 must be triggered manually.
"""

# =============================================================================
# Direct Action Routing
# =============================================================================

DIRECT_ACTIONS: frozenset[str] = frozenset({
    "get_nf_upload_url",
    "verify_file",
    "nexo_analyze_file",
})
"""
Actions that bypass LLM invocation for deterministic execution.

These actions are handled by Mode 2.5 routing in the invoke() entrypoint:
- get_nf_upload_url: Generate presigned S3 upload URL (Lambda via LambdaInvoker)
- verify_file: Verify file availability in S3 (Lambda via LambdaInvoker)
- nexo_analyze_file: Analyze file structure (direct tool call, no LLM)

Note:
    Using frozenset for immutability and O(1) membership testing.
"""

# =============================================================================
# MCP Gateway Singleton
# =============================================================================

_mcp_file_analyzer = None  # Type annotation removed to avoid forward reference issues


def get_mcp_file_analyzer():
    """Get or create MCP Gateway client for file analyzer Lambda.

    This singleton pattern ensures a single MCPGatewayClientFactory instance
    is reused across all file analysis operations, reducing connection overhead.

    The client is lazily initialized on first call using environment variables:
    - MCP_GATEWAY_URL: AgentCore MCP Gateway endpoint
    - MCP_GATEWAY_API_KEY: API key for authentication (if required)

    Lazy import for AgentCore timeout compliance:
    1. Avoid circular imports at module load time
    2. Modify sys.path to include project root before importing
    3. Resolve namespace collision between agents/tools/ and root tools/

    Returns:
        MCPGatewayClientFactory: Configured client for invoking
            SGAFileAnalyzer Lambda via MCP protocol.

    Example:
        >>> client = get_mcp_file_analyzer()
        >>> result = client.call_tool(
        ...     tool_name="SGAFileAnalyzer___analyze_file_structure",
        ...     arguments={"s3_key": "uploads/user123/file.csv"}
        ... )
    """
    global _mcp_file_analyzer
    if _mcp_file_analyzer is None:
        import sys

        # Compute project root from this file's location
        # File: /var/task/agents/orchestrators/inventory_hub/config.py
        # Root: /var/task (up 4 levels: config.py → inventory_hub → orchestrators → agents → root)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../../../.."))

        # Ensure project root is first in sys.path to resolve tools/ correctly
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        try:
            # Now import from root tools/ (not agents/tools/)
            from core_tools.mcp_gateway_client import MCPGatewayClientFactory

            logger.debug("[config] Initializing MCP Gateway client for file analyzer")
            _mcp_file_analyzer = MCPGatewayClientFactory.create_from_env()
        except ImportError as e:
            logger.error(f"[config] Failed to import core_tools.mcp_gateway_client: {e}")
            raise

    return _mcp_file_analyzer


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Agent Identity
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_DESCRIPTION",
    "RUNTIME_ID",
    # Feature Flags
    "ENABLE_AUTO_SCHEMA_MAPPING",
    # Direct Actions
    "DIRECT_ACTIONS",
    # Singletons
    "get_mcp_file_analyzer",
]
