# =============================================================================
# ValidationAgent - Data Validation Specialist
# =============================================================================
# Validates data and mappings against PostgreSQL schema.
#
# Called by:
# - NexoImportAgent: Before import execution
# - SchemaEvolutionAgent: Before column creation
#
# Architecture:
# - Runtime: Dedicated AgentCore Runtime (1 runtime = 1 agent)
# - Protocol: A2A (JSON-RPC 2.0) for inter-agent communication
# - Entry Point: main.py with Strands A2AServer
# =============================================================================

from agents.validation.main import create_agent, AGENT_ID, AGENT_NAME

__all__ = [
    "create_agent",
    "AGENT_ID",
    "AGENT_NAME",
]
