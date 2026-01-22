# =============================================================================
# RepairAgent Module
# =============================================================================
# The Software Surgeon - Automated code repair specialist.
#
# This module provides the RepairAgent implementation for Faiston NEXO,
# triggered by DebugAgent when suggested_action == "repair".
# =============================================================================

from agents.specialists.repair.main import (
    AGENT_ID,
    AGENT_NAME,
    AGENT_PORT,
    RUNTIME_ID,
    create_agent,
    create_a2a_server,
    main,
)

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_PORT",
    "RUNTIME_ID",
    "create_agent",
    "create_a2a_server",
    "main",
]
