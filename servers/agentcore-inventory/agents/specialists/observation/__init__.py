# =============================================================================
# ObservationAgent - Phase 5: Proactive Insights Specialist
# =============================================================================
# The Nexo's Intuition - Analyzes historical data from AgentCore Memory and
# database to find patterns, recurrent errors, and optimization opportunities.
#
# ARCHITECTURE PRINCIPLES (per CLAUDE.md):
# 1. AI-FIRST / AGENTIC - Full Strands Agent with LLM reasoning
# 2. OBSERVE → THINK → LEARN → ACT loop
# 3. TOOL-FIRST - Deterministic tools handle analysis, LLM synthesizes insights
# 4. NO RAW DATA IN CONTEXT - Query summaries only
# 5. ACTOR-SCOPED - ALL queries enforce WHERE owner_id = :actor_id
#
# CAPABILITIES:
# 1. Scan recent Memory activity (facts, episodes, sessions)
# 2. Detect patterns in historical data (errors, mappings, behavior)
# 3. Generate actionable InsightReports with confidence scores
# 4. Check inventory database health for anomalies
# 5. Provide one-click fixes via ActionPayload
#
# VERSION: 2026-01-22T00:00:00Z (Phase 5 initial)
# =============================================================================

from .main import (
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
