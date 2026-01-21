# =============================================================================
# DebugAgent - Module Exports
# =============================================================================
# Intelligent error analysis agent for Faiston SGA system.
#
# Architecture: AWS Strands Agents + AWS Bedrock AgentCore
# Protocol: A2A (JSON-RPC 2.0)
# Memory: AgentCore Memory for error pattern storage
#
# Usage:
#   # From other agents via DebugHook (automatic):
#   # Hook intercepts errors and enriches them via A2A
#
#   # From other agents via A2A protocol (manual):
#   from shared.a2a_client import delegate_to_debug
#   result = await delegate_to_debug({
#       "action": "analyze_error",
#       "error_type": "ValidationError",
#       "message": "Missing required field: part_number",
#       "operation": "import_csv",
#   })
#
#   # Entry Point: main.py with Strands A2AServer
# =============================================================================

from agents.specialists.debug.main import create_agent, AGENT_ID, AGENT_NAME

__all__ = [
    "create_agent",
    "AGENT_ID",
    "AGENT_NAME",
]
