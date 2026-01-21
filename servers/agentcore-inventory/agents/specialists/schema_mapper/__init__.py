"""
SchemaMapper Agent - Phase 3: Semantic Column Mapping.

This agent proposes how file columns map to the PostgreSQL database schema
using semantic matching, prior learning, and dynamic schema introspection via MCP.

Protocol: A2A (JSON-RPC 2.0)
Agent ID: faiston_schema_mapper
Port: 9002
Memory: STM + LTM via AgentMemoryManager
Model: Gemini 2.5 Pro + Thinking (critical inventory agent per CLAUDE.md)

Author: Faiston NEXO Team
Date: January 2026
"""

from .main import (
    AGENT_ID,
    AGENT_NAME,
    AGENT_PORT,
    create_agent,
    create_a2a_server,
    main,
)

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_PORT",
    "create_agent",
    "create_a2a_server",
    "main",
]
