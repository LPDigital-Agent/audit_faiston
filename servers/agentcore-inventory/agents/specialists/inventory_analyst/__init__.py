"""
InventoryAnalyst specialist agent package.

This agent is responsible for analyzing uploaded inventory file structures
(CSV/Excel) without loading full content into memory. It uses the FileInspector
library for efficient file parsing.

Protocol: A2A (JSON-RPC 2.0)
Agent ID: faiston_inventory_analyst
Port: 9001
Memory: STM_ONLY

Persona: Technical Data Engineer - extracts metadata only, no business interpretation.
"""

from agents.specialists.inventory_analyst.main import (
    AGENT_DESCRIPTION,
    AGENT_ID,
    AGENT_NAME,
    AGENT_PORT,
    AGENT_SKILLS,
    create_agent,
    main,
)

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_PORT",
    "AGENT_DESCRIPTION",
    "AGENT_SKILLS",
    "create_agent",
    "main",
]
