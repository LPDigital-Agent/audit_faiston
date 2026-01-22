# =============================================================================
# Faiston Inventory Management - AgentCore Entry Point
# =============================================================================
# This file is the deployment entry point for AgentCore Runtime.
# It re-exports the orchestrator from its proper location per ADR-002.
#
# ARCHITECTURE: ADR-002 "Everything is an Agent"
# LOCATION: agents/orchestrators/inventory_hub/main.py (Full Strands Agent)
#
# AgentCore expects main.py in the module root, so this file:
# 1. Imports from the ADR-002 compliant location
# 2. Re-exports app and invoke for AgentCore
# 3. Provides deployment compatibility
#
# See: docs/adr/ADR-002-faiston-agent-ecosystem.md
# See: docs/ORCHESTRATOR_ARCHITECTURE.md
# =============================================================================

# Re-export from ADR-002 location (inventory_hub is the active orchestrator)
from agents.orchestrators.inventory_hub.main import (
    app,
    invoke,
    create_inventory_hub as create_orchestrator,
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

if __name__ == "__main__":
    app.run()
