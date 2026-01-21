# =============================================================================
# Faiston Inventory Management - AgentCore Entry Point
# =============================================================================
# This file is the deployment entry point for AgentCore Runtime.
# It re-exports the orchestrator from its proper location per ADR-002.
#
# ARCHITECTURE: ADR-002 "Everything is an Agent"
# LOCATION: agents/orchestrators/estoque/main.py (Full Strands Agent)
#
# AgentCore expects main.py in the module root, so this file:
# 1. Imports from the ADR-002 compliant location
# 2. Re-exports app and invoke for AgentCore
# 3. Provides deployment compatibility
#
# NOTE: Swarm utilities are in swarm/response_utils.py
# DO NOT re-export them here - import directly from that module.
#
# See: docs/adr/ADR-002-faiston-agent-ecosystem.md
# See: docs/ORCHESTRATOR_ARCHITECTURE.md
# =============================================================================

# Re-export from ADR-002 location
from agents.orchestrators.estoque.main import (
    app,
    invoke,
    create_orchestrator,
    AGENT_ID,
    AGENT_NAME,
)

# For AgentCore deployment ONLY - no utility re-exports
__all__ = [
    "app",
    "invoke",
    "create_orchestrator",
    "AGENT_ID",
    "AGENT_NAME",
]

# =============================================================================
# Legacy Migration Note (2026-01-14)
# =============================================================================
# The original 1,318-line orchestrator has been replaced with a full Strands
# Agent implementation (~790 lines) at agents/orchestrators/estoque/main.py.
#
# Key changes per ADR-002:
# - No routing tables in system prompt (LLM decides from tool descriptions)
# - No backward compatibility mapping (breaking change accepted)
# - Swarm integration embedded for NEXO imports
# - Hooks integration (logging, metrics, guardrails)
#
# File changes:
# - shared/a2a_client.py: KEPT (used by specialists for inter-agent calls)
# - shared/a2a_tool_provider.py: REMOVED (was orchestrator-only)
#
# Swarm Utilities (BUG-019):
# - Location: swarm/response_utils.py
# - Import directly: from swarm.response_utils import _extract_tool_output_from_swarm_result
# - NO re-exports here (per ADR-002 no legacy compatibility)
# =============================================================================

if __name__ == "__main__":
    app.run()
