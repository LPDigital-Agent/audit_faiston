"""
Faiston SGA Orchestrator Agents

Domain orchestrators that route requests to specialist agents.
Each orchestrator is a full Strands Agent (NOT a Python wrapper).

Orchestrators:
- estoque: Inventory management orchestrator (legacy, to be replaced by inventory_hub)
- inventory_hub: New secure file ingestion orchestrator (Phase 1)
- expedicao: Expedition orchestrator (future)
- reversa: Reverse logistics orchestrator (future)
- rastreabilidade: Traceability orchestrator (future)
"""
