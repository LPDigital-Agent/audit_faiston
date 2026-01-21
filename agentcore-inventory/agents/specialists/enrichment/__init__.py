# =============================================================================
# EnrichmentAgent - Equipment Data Enrichment Agent
# =============================================================================
# Orchestrates equipment enrichment using Tavily AI search via AgentCore Gateway.
#
# Module: Gestao de Ativos -> Enrichment
# Protocol: A2A (Agent-to-Agent) on port 9000
# Model: Gemini 2.5 Pro with Thinking (CRITICAL AGENT)
#
# Reference:
# - PRD: product-development/current-feature/PRD-tavily-enrichment.md
# - Architecture: Gateway-first pattern (Tavily via AgentCore Gateway)
# =============================================================================

from agents.enrichment.main import (
    AGENT_ID,
    AGENT_NAME,
    AGENT_DESCRIPTION,
    AGENT_SKILLS,
    create_agent,
    main,
)

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_DESCRIPTION",
    "AGENT_SKILLS",
    "create_agent",
    "main",
]
