"""
Faiston SGA Specialist Agents

Reusable agent capabilities that can be invoked by ANY orchestrator.
Each specialist implements a specific domain capability via A2A protocol.

Specialists:
- compliance: Policy validation and approval workflows
- data_import: Generic data import operations
- enrichment: Data enrichment and enhancement
- estoque_control: Inventory movements and balance queries
- file_analyzer: CSV/XLSX file analysis (BUG-025 - Strands structured output)
- intake: Document intake (NF PDF/XML processing)
- learning: Memory and pattern learning (AgentCore Memory)
- nexo_import: Smart AI-powered file analysis and import
- observation: Audit logging and analysis
- schema_evolution: Column type inference and schema changes
- validation: Data and schema validation
- vision_analyzer: Vision document analysis (BUG-025 - Strands structured output)

NOTE: equipment_research was removed (AUDIT-004/2) - replaced by enrichment agent.

NOTE: carrier, expedition, reverse, reconciliacao agents belong to agentcore-carrier project.
"""
