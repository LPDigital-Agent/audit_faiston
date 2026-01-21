"""
Faiston Inventory Orchestrator Agent (ADR-002)

This is a FULL STRANDS AGENT that orchestrates inventory operations.
It routes requests to specialist agents via A2A protocol.

Architecture per ADR-002:
- No routing tables in system prompt (LLM decides from tool descriptions)
- invocation_state for hidden context (user_id, session_id)
- HookProvider implementations (logging, metrics, guardrails)
- Swarm integration for NEXO imports
- Direct boto3 SDK for A2A invocation
"""
from .main import (
    app,
    invoke,
    create_orchestrator,
    AGENT_ID,
    AGENT_NAME,
)

__all__ = ["app", "invoke", "create_orchestrator", "AGENT_ID", "AGENT_NAME"]
