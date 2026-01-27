# =============================================================================
# Faiston Inventory Management - AgentCore Entry Point
# =============================================================================
# Application factory pattern - uses create_app() for AgentCore compatibility.
# Based on OFFICIAL AgentCore A2A documentation pattern.
# Ref: https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/a2a.md
#
# ARCHITECTURE: ADR-002 "Everything is an Agent"
# LOCATION: agents/orchestrators/inventory_hub/main.py (Full Strands Agent)
#
# AgentCore expects main.py in the module root, so this file:
# 1. Imports from the ADR-002 compliant location
# 2. Re-exports create_app and invoke for AgentCore
# 3. Provides deployment compatibility via uvicorn
#
# See: docs/adr/ADR-002-faiston-agent-ecosystem.md
# See: docs/ORCHESTRATOR_ARCHITECTURE.md
# =============================================================================

import uvicorn

# Re-export from ADR-002 location (inventory_hub is the active orchestrator)
from agents.orchestrators.inventory_hub.main import (
    create_app,
    invoke,
    create_inventory_hub as create_orchestrator,
)
from agents.orchestrators.inventory_hub.config import AGENT_ID, AGENT_NAME

# For AgentCore deployment ONLY - no utility re-exports
__all__ = [
    "create_app",
    "invoke",
    "create_orchestrator",
    "AGENT_ID",
    "AGENT_NAME",
]

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=9000)
