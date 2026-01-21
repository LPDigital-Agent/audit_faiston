# =============================================================================
# ImportAgent - Bulk CSV/Excel Importer
# =============================================================================
# Processes bulk imports from CSV and Excel files for inventory management.
#
# Features:
# - Auto-detect file format (CSV, XLSX, XLS)
# - Column mapping with pattern recognition
# - Part number matching (exact + fuzzy)
# - Batch movement creation
# - Learning episode storage via A2A
#
# Architecture:
# - Runtime: Dedicated AgentCore Runtime (1 runtime = 1 agent)
# - Protocol: A2A (JSON-RPC 2.0) for inter-agent communication
# - Entry Point: main.py with Strands A2AServer
# =============================================================================

from agents.data_import.main import create_agent, AGENT_ID, AGENT_NAME

__all__ = [
    "create_agent",
    "AGENT_ID",
    "AGENT_NAME",
]
