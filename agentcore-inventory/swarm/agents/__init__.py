# =============================================================================
# Swarm Agents - Faiston Inventory Management
# =============================================================================
# This module contains the 5 autonomous agents that form the Inventory Swarm.
#
# Agents:
# - file_analyst: Entry point, analyzes uploaded files
# - schema_validator: Validates data against PostgreSQL schema
# - memory_agent: Manages episodic memory for learned patterns
# - hil_agent: Handles human-in-the-loop clarification
# - import_executor: Executes validated imports
#
# Each agent can:
# 1. Perform its specialized task
# 2. Hand off to other agents via handoff_to_agent()
# 3. Create new tools via Meta-Tooling (load_tool, editor, shell)
# =============================================================================

from swarm.agents.file_analyst import create_file_analyst
from swarm.agents.schema_validator import create_schema_validator
from swarm.agents.memory_agent import create_memory_agent
from swarm.agents.hil_agent import create_hil_agent
from swarm.agents.import_executor import create_import_executor

__all__ = [
    "create_file_analyst",
    "create_schema_validator",
    "create_memory_agent",
    "create_hil_agent",
    "create_import_executor",
]
