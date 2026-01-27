# =============================================================================
# ObservationAgent - Phase 5: Proactive Insights Specialist
# =============================================================================
# The Nexo's Intuition - Analyzes historical data from AgentCore Memory and
# database to find patterns, recurrent errors, and optimization opportunities.
#
# ARCHITECTURE PRINCIPLES (per CLAUDE.md):
# 1. AI-FIRST / AGENTIC - Full Strands Agent with LLM reasoning
# 2. OBSERVE → THINK → LEARN → ACT loop (Proactive instead of Reactive)
# 3. TOOL-FIRST - Deterministic tools handle queries, LLM synthesizes insights
# 4. NO RAW DATA IN CONTEXT - Query summaries only
# 5. ACTOR-SCOPED - ALL queries enforce WHERE owner_id = :actor_id
# 6. COGNITIVE MIDDLEWARE - ALL errors enriched by DebugAgent
#
# CAPABILITIES:
# 1. Scan Memory activity (facts, episodes, sessions) with configurable windows
# 2. Detect patterns (error patterns, mapping opportunities, behavior insights)
# 3. Generate InsightReports with confidence scoring and deduplication
# 4. Check inventory database health for anomalies
# 5. Provide one-click fixes via ActionPayload
#
# TRIGGER MODES:
# 1. Post-Import (Event): DataTransformer fires A2A call after job completion
# 2. On-Demand (User): Orchestrator calls for "Global Health Check"
#
# RESPONSE LANGUAGE:
# - System prompt: English (as per CLAUDE.md)
# - User responses: Brazilian Portuguese (pt-BR)
#
# MODEL:
# - Gemini 2.5 Flash (non-critical, read-heavy agent per CLAUDE.md)
#
# VERSION: 2026-01-22T00:00:00Z (Phase 5 initial)
# =============================================================================

import json
import logging
import os
import sys
from typing import Any, Dict, List

# Add parent directory to path for imports (required by AgentCore runtime)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill

# Agent utilities
from agents.utils import create_gemini_model, AGENT_VERSION

# Hooks (per ADR-002)
from shared.hooks.logging_hook import LoggingHook
from shared.hooks.metrics_hook import MetricsHook
from shared.hooks.debug_hook import DebugHook
from shared.hooks.security_audit_hook import SecurityAuditHook

# Cognitive error handler (Nexo Immune System)
from shared.cognitive_error_handler import cognitive_error_handler, cognitive_sync_handler

# Structured output schemas
from shared.agent_schemas import ObservationResponse, InsightReport

# Tools (absolute imports for AgentCore runtime compatibility)
from agents.specialists.observation.tools import (
    scan_recent_activity,
    analyze_patterns,
    generate_insight,
    dismiss_insight,
    check_inventory_health,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "observation"
AGENT_NAME = "FaistonObservationAgent"
AGENT_DESCRIPTION = """
The Nexo's Intuition - Proactive insights specialist.
Analyzes historical data from AgentCore Memory and database to find patterns,
recurrent errors, and optimization opportunities.
Phase 5 of the Smart Import architecture.
"""

# Port for local A2A server (see LOCAL_AGENTS in a2a_client.py:1455)
AGENT_PORT = 9012

# Runtime ID for AgentCore deployment (January 2026 update)
RUNTIME_ID = "faiston_sga_observation-tgaIiC6AtX"


# =============================================================================
# System Prompt (English per CLAUDE.md)
# =============================================================================

SYSTEM_PROMPT = """You are **The Nexo's Intuition** - a proactive insights specialist.

## Your Role
Make the system PROACTIVE instead of just REACTIVE. Analyze historical data from
AgentCore Memory and the inventory database to find patterns, recurrent errors,
and optimization opportunities BEFORE the user asks.

## Core Loop: OBSERVE → THINK → LEARN → ACT
1. **OBSERVE**: Scan recent Memory activity (facts, episodes, sessions)
2. **THINK**: Detect patterns using statistical and semantic analysis
3. **LEARN**: Use prior insights and dismissals to improve recommendations
4. **ACT**: Generate actionable InsightReports with confidence scores

## Capabilities

1. **Scan Recent Activity**
   - Use `scan_recent_activity` to read from AgentCore Memory
   - Configurable time windows: 24h (tactical), 7d (operational), 30d (strategic)
   - Actor-scoped: ALL data belongs to the requesting user only

2. **Analyze Patterns**
   - Use `analyze_patterns` to detect error patterns, mapping opportunities, behavior insights
   - Error pattern types: SchemaMismatch, DataIntegrity, BusinessLogic, Formatting
   - Mapping detection uses Triangulation: (Frequency * 0.3) + (Semantic * 0.4) + (History * 0.3)

3. **Generate Insights**
   - Use `generate_insight` to create InsightReports
   - Deduplication: Hash + 7-day cooldown prevents spam
   - Confidence thresholds per category (automation: 0.9, health: 0.85, workflow: 0.7, pattern: 0.6)

4. **Check Database Health**
   - Use `check_inventory_health` to query for anomalies
   - Detects: zero stock items, duplicate part numbers, missing required fields, price anomalies, stale sessions

5. **Handle Dismissals**
   - Use `dismiss_insight` when user rejects a recommendation
   - Track dismissal_count and severity_at_dismissal for learning
   - Resurface if current_severity > stored_severity * 1.5

## Severity Levels (Traffic Light System)

- **CRITICAL** 🔴: Data integrity or financial risk. Requires immediate action.
  Examples: Duplicate inventory entries, negative stock values, data corruption
  Display: Show only 1 insight (crisis mode)

- **WARNING** ⚠️: Process friction or recurring errors. Add to backlog.
  Examples: Repeated mapping errors, slow performance patterns, stale data
  Display: Show up to 3 insights (routine mode)

- **INFO** ℹ️: Optimization opportunities or trends. FYI only.
  Examples: Usage patterns, automation opportunities, efficiency suggestions

## Learning Mode Thresholds
- Require minimum 3 sessions before detecting patterns (avoid false positives)
- Require minimum 50 rows of data before statistical insights
- CRITICAL insights bypass thresholds (immediate alerting)

## Response Format
Return structured ObservationResponse with:
- insights: List of InsightReport objects
- total_pending: Total pending insights (may be more than displayed)
- displayed_count: Number shown (1 if critical, up to 3 otherwise)
- health_score: Overall inventory health (0.0 - 1.0) when health check performed
- human_message: Summary in pt-BR

## Example Workflow: Post-Import Analysis

When triggered after a DataTransformer job completes:
1. Call `scan_recent_activity(actor_id, time_window_hours=24)` for recent session
2. Call `analyze_patterns(activity_json, pattern_type="all")` to detect issues
3. For each significant pattern, call `generate_insight(pattern_json, category)`
4. Return insights sorted by severity (critical first)

## Example Workflow: Global Health Check

When user asks "Como está minha operação?":
1. Call `check_inventory_health(actor_id)` for database anomalies
2. Call `scan_recent_activity(actor_id, time_window_hours=168)` for weekly trends
3. Call `analyze_patterns(activity_json, pattern_type="all")` for pattern detection
4. Synthesize findings into actionable insights
5. Return with health_score and prioritized recommendations

## Response Language
Always respond to users in Brazilian Portuguese (pt-BR).
"""


# =============================================================================
# Health Check Tool
# =============================================================================


@cognitive_sync_handler(AGENT_ID)
@tool
def health_check() -> str:
    """
    Check the health status of the ObservationAgent.

    Returns system information useful for debugging and monitoring.

    Returns:
        JSON string with health status, version, and capabilities.
    """
    return json.dumps({
        "success": True,
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "runtime_id": RUNTIME_ID,
        "architecture": "phase5-proactive-insights",
        "capabilities": [
            "scan_recent_activity",
            "analyze_patterns",
            "generate_insight",
            "dismiss_insight",
            "check_inventory_health",
        ],
        "model": "gemini-2.5-flash",
        "thinking_enabled": False,  # Non-critical agent
        "features": [
            "memory-read",
            "pattern-detection",
            "confidence-scoring",
            "deduplication",
            "one-click-fixes",
            "cognitive-middleware",
        ],
    })


# =============================================================================
# Agent Skills (A2A Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="scan_activity",
        name="Scan Activity",
        description="Scan recent Memory activity for patterns and anomalies",
        tags=["memory", "analysis", "patterns"],
    ),
    AgentSkill(
        id="analyze_patterns",
        name="Analyze Patterns",
        description="Detect error patterns, mapping opportunities, and behavior insights",
        tags=["patterns", "errors", "mappings"],
    ),
    AgentSkill(
        id="generate_insights",
        name="Generate Insights",
        description="Create actionable InsightReports with confidence scoring",
        tags=["insights", "recommendations", "actions"],
    ),
    AgentSkill(
        id="check_health",
        name="Check Health",
        description="Check inventory database health for anomalies",
        tags=["health", "database", "anomalies"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Check agent health status and capabilities",
        tags=["health", "monitoring"],
    ),
]


# =============================================================================
# Agent Factory
# =============================================================================


def create_agent() -> Agent:
    """
    Create the ObservationAgent as a full Strands Agent.

    This agent handles Phase 5 proactive insights with:
    - Memory scanning for patterns and anomalies
    - Confidence-based insight generation
    - Deduplication and learning from dismissals
    - Cognitive Middleware for error enrichment
    - Gemini 2.5 Flash (per CLAUDE.md for non-critical agents)

    Returns:
        Strands Agent configured for proactive insights.
    """
    hooks = [
        LoggingHook(log_level=logging.INFO),
        MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        DebugHook(timeout_seconds=30.0),
        SecurityAuditHook(enabled=True),  # FAIL-CLOSED audit trail
    ]

    agent = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # Gemini 2.5 Flash
        tools=[
            # Memory scanning
            scan_recent_activity,
            # Pattern analysis
            analyze_patterns,
            # Insight generation
            generate_insight,
            dismiss_insight,
            # Database health
            check_inventory_health,
            # System
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
        # Structured output for type safety (AUDIT-001)
        # Note: Using structured_output_model would enforce response format
        # but we need flexibility for different trigger modes
    )

    logger.info(f"[ObservationAgent] Created {AGENT_NAME} with {len(hooks)} hooks")
    return agent


def create_a2a_server(agent: Agent) -> A2AServer:
    """
    Create A2A server for agent-to-agent communication.

    The A2AServer wraps the Strands Agent and provides:
    - JSON-RPC 2.0 endpoint at /
    - Agent Card discovery at /.well-known/agent-card.json
    - Health check at /health

    Args:
        agent: The Strands Agent to wrap.

    Returns:
        A2AServer instance ready to mount on FastAPI.
    """
    server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=AGENT_PORT,
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
        serve_at_root=False,  # Mount at root below
    )

    logger.info(
        f"[ObservationAgent] Created A2A server on port {AGENT_PORT} "
        f"with {len(AGENT_SKILLS)} skills"
    )
    return server


# =============================================================================
# Main Entrypoint
# =============================================================================


def main() -> None:
    """
    Start the ObservationAgent A2A server.

    For local development:
        cd server/agentcore-inventory
        python -m agents.specialists.observation.main

    For AgentCore deployment:
        agentcore deploy --profile faiston-aio
    """
    # Import FastAPI and uvicorn here to avoid circular imports
    from fastapi import FastAPI
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info(f"[ObservationAgent] Starting A2A server on port {AGENT_PORT}...")

    # Create FastAPI app
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping health endpoint for AWS ALB
    @app.get("/ping")
    async def ping():
        """Health check endpoint for AWS Application Load Balancer."""
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Add /health endpoint
    @app.get("/health")
    async def health():
        """Detailed health check endpoint."""
        return {
            "status": "healthy",
            "agent_id": AGENT_ID,
            "agent_name": AGENT_NAME,
            "version": AGENT_VERSION,
            "port": AGENT_PORT,
            "runtime_id": RUNTIME_ID,
            "features": [
                "memory-read",
                "pattern-detection",
                "confidence-scoring",
                "deduplication",
                "one-click-fixes",
                "cognitive-middleware",
            ],
        }

    # Create agent and A2A server
    agent = create_agent()
    a2a_server = create_a2a_server(agent)

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[ObservationAgent] Starting uvicorn server on 0.0.0.0:{AGENT_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_PORT",
    "RUNTIME_ID",
    "create_agent",
    "create_a2a_server",
    "main",
]


if __name__ == "__main__":
    main()
