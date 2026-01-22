"""
Faiston SGA Specialist Agents - Smart Import Architecture

Phase 2+3+4+5 agents for the NEXO Smart Import flow:

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

Phase 5 - ObservationAgent:
- Proactive insights specialist (Nexo's Intuition)
- Pattern detection and health monitoring
- Port: 9012

Debug Agent:
- Error analysis and debugging support
- Port: 9014

NOTE: Carrier, expedition, reverse, reconciliacao agents belong to agentcore-carrier project.

IMPORTANT: This file uses LAZY IMPORTS to avoid cascading dependency issues.
Each specialist agent should be imported directly from its subpackage:
    from agents.specialists.observation.main import ...
    from agents.specialists.debug.main import ...
"""

# LAZY IMPORTS: Do NOT import all specialists here to avoid cascading dependencies.
# Each agent is deployed independently and may have different dependency sets.
# Import specialists directly from their subpackages when needed.

__all__ = [
    # Phase 2
    "inventory_analyst",
    # Phase 3
    "schema_mapper",
    # Phase 4
    "data_transformer",
    # Phase 5
    "observation",
    # Debug
    "debug",
]
