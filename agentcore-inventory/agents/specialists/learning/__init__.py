# =============================================================================
# LearningAgent - Module Exports
# =============================================================================
# Episodic memory agent for import intelligence.
#
# Architecture: AWS Strands Agents + AWS Bedrock AgentCore
# Protocol: A2A (JSON-RPC 2.0)
# Memory: AgentCore Memory with GLOBAL namespace
#
# Usage:
#   # From other agents via A2A protocol:
#   from shared.a2a_client import delegate_to_learning
#   result = await delegate_to_learning({
#       "action": "retrieve_prior_knowledge",
#       "filename": "EXPEDIÇÃO_JAN_2026.csv",
#       "file_analysis": {...}
#   })
#
#   # Entry Point: main.py with Strands A2AServer
# =============================================================================

from agents.learning.main import create_agent, AGENT_ID, AGENT_NAME

__all__ = [
    "create_agent",
    "AGENT_ID",
    "AGENT_NAME",
]
