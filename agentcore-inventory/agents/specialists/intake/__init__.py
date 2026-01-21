# =============================================================================
# IntakeAgent - NF Processing Specialist
# =============================================================================
# Processes incoming materials via NF (Nota Fiscal Eletrônica).
#
# Features:
# - NF XML/PDF parsing with AI extraction
# - Vision AI for scanned documents (DANFE)
# - Automatic part number matching
# - Serial number detection
# - HIL routing for low-confidence items
#
# Architecture:
# - Runtime: Dedicated AgentCore Runtime (1 runtime = 1 agent)
# - Protocol: A2A (JSON-RPC 2.0) for inter-agent communication
# - Entry Point: main.py with Strands A2AServer
# =============================================================================

from agents.intake.main import create_agent, AGENT_ID, AGENT_NAME

__all__ = [
    "create_agent",
    "AGENT_ID",
    "AGENT_NAME",
]
