"""
DataTransformer Agent - Phase 4: Data Transformation & Loading.

This agent executes data transformation with intelligent error handling.
Part of the Nexo Immune System - ALL errors enriched by DebugAgent.

Protocol: A2A (JSON-RPC 2.0)
Agent ID: faiston_data_transformer
Port: 9019
Memory: STM + LTM via AgentMemoryManager
Model: Gemini 2.5 Pro + Thinking (critical inventory agent per CLAUDE.md)

Key Features:
- Fire-and-Forget pattern (return job_id immediately, process in background)
- Cognitive Middleware (errors enriched by DebugAgent)
- Memory-based preferences (STOP_ON_ERROR vs LOG_AND_CONTINUE)
- Batch insert via MCP Gateway for performance
- Enriched rejection reports with human-readable fix suggestions

Author: Faiston NEXO Team
Date: January 2026
"""

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
