# =============================================================================
# Faiston Inventory Swarm - 100% Autonomous Multi-Agent Architecture
# =============================================================================
# This module implements the Strands Swarm pattern for intelligent,
# autonomous inventory import processing with Meta-Tooling capabilities.
#
# Architecture: 5 autonomous agents with handoff-based collaboration
# - file_analyst: Entry point, file analysis
# - schema_validator: Schema validation and mapping
# - memory_agent: Episodic memory for learned patterns
# - hil_agent: Human-in-the-loop clarification
# - import_executor: Transaction execution
#
# Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/
# =============================================================================

from swarm.config import create_inventory_swarm, SwarmConfig

__all__ = ["create_inventory_swarm", "SwarmConfig"]
