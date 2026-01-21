# =============================================================================
# EstoqueControlAgent - Core Inventory Control
# =============================================================================
# Core agent for inventory movements (+/-). Handles:
# - Reservations for chamados/projetos
# - Expeditions (outgoing shipments)
# - Transfers between locations
# - Returns (reversas)
# - Balance queries
#
# Human-in-the-Loop Matrix:
# - Reservation same project: AUTONOMOUS
# - Reservation cross-project: HIL
# - Transfer same project: AUTONOMOUS
# - Transfer to restricted location: HIL
# - Adjustment: ALWAYS HIL
# - Discard/Loss: ALWAYS HIL
#
# Architecture:
# - Runtime: Dedicated AgentCore Runtime (1 runtime = 1 agent)
# - Protocol: A2A (JSON-RPC 2.0) for inter-agent communication
# - Entry Point: main.py with Strands A2AServer
# =============================================================================

from agents.estoque_control.main import create_agent, AGENT_ID, AGENT_NAME

__all__ = [
    "create_agent",
    "AGENT_ID",
    "AGENT_NAME",
]
