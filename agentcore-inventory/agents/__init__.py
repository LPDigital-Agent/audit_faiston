# =============================================================================
# Faiston SGA Agent Ecosystem
# =============================================================================
# Structure: ADR-002 "Everything is an Agent" Architecture
#
# agents/
# ├── orchestrators/    # Domain orchestrators (full Strands Agents)
# │   └── estoque/      # Inventory management orchestrator
# └── specialists/      # Reusable specialist agents (15 total)
#
# IMPORTANT: AgentCore has a 30-second cold start limit.
# All agent imports must be LAZY (inside handler functions).
# Adding imports here will break the deployment.
# =============================================================================
