# =============================================================================
# Schema Mapper Agent - Phase 3: Semantic Column Mapping
# =============================================================================
# Specialist agent that proposes how file columns map to the PostgreSQL schema
# using semantic matching, prior learning, and dynamic schema introspection via MCP.
#
# ARCHITECTURE PRINCIPLES (per CLAUDE.md):
# 1. AI-FIRST / AGENTIC - Full Strands Agent with LLM reasoning
# 2. SANDWICH PATTERN - CODE → LLM → CODE
# 3. TOOL-FIRST - Deterministic tools handle MCP calls and memory
# 4. NO RAW DATA IN CONTEXT - Only column names and sample values (metadata)
# 5. HIL ALWAYS REQUIRED - Every mapping proposal requires human confirmation
#
# CAPABILITIES:
# 1. Schema Introspection via MCP Gateway (get_target_schema)
# 2. Semantic Matching (PT→EN dictionary, normalized names, similarity)
# 3. Transformation Detection (DATE_PARSE_PTBR, NUMBER_PARSE_PTBR, etc.)
# 4. Confidence Scoring (0.0-1.0 per mapping)
# 5. Memory Persistence (AgentCore Memory via AgentMemoryManager)
# 6. Smart Learning System (ask user when unsure, save training examples)
#
# RESPONSE LANGUAGE:
# - System prompt: English (as per CLAUDE.md)
# - User responses: Brazilian Portuguese (pt-BR)
#
# MEMORY:
# - STM for session context (via Strands Agent state)
# - LTM via AgentMemoryManager for learned mappings
#
# MODEL:
# - Gemini 2.5 Pro + Thinking (critical inventory agent per CLAUDE.md)
#
# VERSION: 2026-01-21T21:00:00Z (Phase 3 initial)
# =============================================================================

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill

# Agent utilities
from agents.utils import create_gemini_model, create_agent_skill, AGENT_VERSION

# Hooks (per ADR-002)
from shared.hooks.logging_hook import LoggingHook
from shared.hooks.metrics_hook import MetricsHook
from shared.hooks.debug_hook import DebugHook

# AUDIT-003: Global error capture for Debug Agent enrichment
from shared.debug_utils import debug_error

# AUDIT-028: Cognitive Error Handler for enriched error responses
from shared.cognitive_error_handler import cognitive_sync_handler, CognitiveError

# Schema introspection (uses MCP Gateway internally)
from tools.schema_provider import SchemaProvider, get_schema_provider

# Memory (AgentCore Memory SDK - per CLAUDE.md)
from shared.memory_manager import AgentMemoryManager, MemoryOriginType

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "schema_mapper"
AGENT_NAME = "FaistonSchemaMapper"
AGENT_DESCRIPTION = """
Senior Data Architect specialized in semantic column mapping.
Analyzes file columns and proposes mappings to PostgreSQL schema
using MCP introspection and AgentCore Memory for learning.
Phase 3 of the Smart Import architecture.
"""

# Port for local A2A server (see LOCAL_AGENTS in a2a_client.py)
AGENT_PORT = 9018

# Runtime ID for AgentCore deployment
RUNTIME_ID = "faiston_schema_mapper"

# =============================================================================
# Semantic Dictionary (PT → EN column name mappings)
# =============================================================================
# This dictionary provides initial semantic knowledge for column mapping.
# It's extended at runtime by learned mappings from AgentCore Memory.

SEMANTIC_DICTIONARY = {
    # Part Number variants
    "codigo": "part_number",
    "code": "part_number",
    "cod": "part_number",
    "sku": "part_number",
    "pn": "part_number",
    "partnumber": "part_number",
    "part_number": "part_number",
    "material": "part_number",
    "item": "part_number",
    "ref": "part_number",
    "referencia": "part_number",

    # Description variants
    "descricao": "description",
    "desc": "description",
    "descr": "description",
    "description": "description",
    "nome": "description",
    "name": "description",
    "produto": "description",
    "product": "description",

    # Quantity variants
    "quantidade": "quantity",
    "qtd": "quantity",
    "qty": "quantity",
    "quant": "quantity",
    "quantity": "quantity",

    # Location variants
    "localizacao": "location_code",
    "loc": "location_code",
    "local": "location_code",
    "location": "location_code",
    "endereco": "location_code",
    "address": "location_code",
    "posicao": "location_code",

    # Supplier variants
    "fornecedor": "supplier_name",
    "supplier": "supplier_name",
    "vendor": "supplier_name",
    "fabricante": "supplier_name",

    # Date variants
    "data_entrada": "entry_date",
    "dt_entrada": "entry_date",
    "data": "entry_date",
    "date": "entry_date",
    "entrada": "entry_date",

    # NF variants
    "numero_nf": "nf_number",
    "nf": "nf_number",
    "nota": "nf_number",
    "nota_fiscal": "nf_number",
    "nf_number": "nf_number",

    # Price/Value variants
    "valor_unitario": "unit_price",
    "vlr_unit": "unit_price",
    "preco": "unit_price",
    "price": "unit_price",
    "valor": "unit_price",
    "unit_price": "unit_price",
    "preco_unitario": "unit_price",

    # Total value variants
    "valor_total": "total_value",
    "vlr_total": "total_value",
    "total": "total_value",
    "total_value": "total_value",

    # Serial number variants
    "serial": "serial_number",
    "serie": "serial_number",
    "ns": "serial_number",
    "serial_number": "serial_number",
    "numero_serie": "serial_number",
}

# =============================================================================
# Transformation Detection Patterns
# =============================================================================

TRANSFORM_PATTERNS = {
    # Brazilian date format: DD/MM/YYYY → YYYY-MM-DD
    "DATE_PARSE_PTBR": r"^\d{2}/\d{2}/\d{4}$",

    # Brazilian number format: 1.234,56 → 1234.56
    "NUMBER_PARSE_PTBR": r"^\d{1,3}(\.\d{3})*(,\d{2})?$",

    # Brazilian currency: R$ 15,50 → 15.50
    "CURRENCY_CLEAN_PTBR": r"^R\$\s*\d",

    # Whitespace needs trimming
    "TRIM": r"^\s+|\s+$",

    # Case normalization
    "UPPERCASE": r"^[a-z]+$",  # All lowercase → needs uppercase
}


# =============================================================================
# System Prompt (English per CLAUDE.md)
# =============================================================================

SYSTEM_PROMPT = """You are a **Senior Data Architect** specialized in semantic column mapping.

## Your Role
Analyze file columns extracted by InventoryAnalyst and propose mappings to the target PostgreSQL schema.
You read schemas via MCP. You save proposals to AgentCore Memory. You NEVER assume mappings without evidence.

## Capabilities
1. **Schema Introspection**: Use `get_target_schema` to fetch target table structure via MCP.
2. **Semantic Matching**: Compare source columns with target columns using:
   - Exact match (codigo → codigo)
   - Normalized match (CODIGO → codigo, remove accents)
   - Semantic similarity (qtd → quantity, desc → description)
   - Portuguese-English equivalents (quantidade → quantity)
3. **Transformation Inference**: Identify required transformations:
   - `TRIM` - Whitespace removal
   - `UPPERCASE` / `LOWERCASE` - Case normalization
   - `DATE_PARSE_PTBR` - DD/MM/YYYY → YYYY-MM-DD (ISO)
   - `NUMBER_PARSE_PTBR` - 1.234,56 → 1234.56 (decimal)
   - `CURRENCY_CLEAN_PTBR` - R$ 15,50 → 15.50 (remove symbol + parse)
4. **Confidence Scoring**: Assign confidence (0.0-1.0) based on match quality.
5. **Memory Persistence**: Use `save_mapping_proposal` to store to AgentCore Memory.

## Critical Rules
- **DB SEPARATION**: Read schema from MCP. Write proposals to AgentCore Memory.
- **NO RAW DATA**: Work only with column names and sample values (metadata only).
- **HIL ALWAYS REQUIRED**: ALL proposals require human confirmation (requires_confirmation=true).
- **UNMAPPED COLUMNS**: List source columns that don't map to any target.
- **MISSING REQUIRED**: When required target columns have no source match, return status="needs_input".

## Smart Learning System
When you cannot confidently map a REQUIRED column:
1. Return status="needs_input" with the missing_required_fields list
2. Include available_sources (file columns that could potentially match)
3. The orchestrator will ask the user and save the answer as a Training Example
4. On subsequent imports, you'll find this pattern in memory via observe_prior_patterns

## Semantic Dictionary (PT → EN)
- codigo, code, cod, sku, pn → part_number
- descricao, desc, descr, nome → description
- quantidade, qtd, qty → quantity
- localizacao, loc, local → location_code
- fornecedor, supplier → supplier_name
- data_entrada, dt_entrada → entry_date
- numero_nf, nota, nf → nf_number
- valor_unitario, vlr_unit, preco → unit_price
- valor_total, vlr_total → total_value
- serial, serie, ns → serial_number

## Response Format
For successful mapping, return:
{
    "status": "success",
    "session_id": "from-payload",
    "target_table": "pending_entry_items",
    "mappings": [
        {
            "source_column": "codigo",
            "target_column": "part_number",
            "transform": "TRIM|UPPERCASE",
            "confidence": 0.95,
            "reason": "Exact semantic match + common PT abbreviation"
        }
    ],
    "unmapped_source_columns": ["observacao", "custom_field"],
    "missing_required_columns": [],
    "overall_confidence": 0.87,
    "requires_confirmation": true
}

When you need user input for missing required columns:
{
    "status": "needs_input",
    "missing_required_fields": [
        {
            "target_column": "part_number",
            "description": "Código do material/SKU",
            "suggested_source": null,
            "available_sources": ["COD", "SKU", "ITEM", "REF"]
        }
    ],
    "partial_mappings": [...]
}
"""


# =============================================================================
# Tools
# =============================================================================


@tool
def get_target_schema(table_name: str = "pending_entry_items") -> str:
    """
    Fetch target table schema via MCP Gateway.

    Uses SchemaProvider singleton (already handles MCP calls via
    SGAPostgresTools___sga_get_schema_metadata).

    Returns simplified schema for LLM reasoning.

    Args:
        table_name: Target PostgreSQL table (default: pending_entry_items)

    Returns:
        JSON with columns, data types, required columns, and enums.
    """
    try:
        provider = get_schema_provider()
        schema = provider.get_table_schema(table_name)

        if not schema:
            return json.dumps({
                "success": False,
                "error": f"Table {table_name} not found in schema cache"
            })

        # Simplify for LLM context (reduce tokens)
        return json.dumps({
            "success": True,
            "table_name": schema.table_name,
            "columns": [
                {
                    "name": c.name,
                    "type": c.data_type,
                    "required": c.name in schema.required_columns,
                    "is_enum": c.udt_name is not None,
                }
                for c in schema.columns
            ],
            "required_columns": schema.required_columns,
            "enums": provider.get_all_enums(),
        })

    except Exception as e:
        debug_error(e, "get_target_schema", {"table_name": table_name})
        return json.dumps({
            "success": False,
            "error": f"Schema fetch failed: {str(e)}"
        })


@tool
def observe_prior_patterns(session_id: str = "") -> str:
    """
    Retrieve prior column mapping patterns from AgentCore Memory.

    This enables learning from previous imports. Patterns are stored
    when users confirm mappings (learn_fact with use_global=True).

    Args:
        session_id: Current session ID for context.

    Returns:
        JSON with learned patterns (column mappings that worked before).
    """
    try:
        # Initialize memory manager
        memory = AgentMemoryManager(
            agent_id=AGENT_ID,
            actor_id=session_id or "system",
        )

        # Observe global patterns (confirmed mappings from all users)
        patterns = memory.observe_global(
            query="column mapping patterns confirmed",
            limit=20,
        )

        if not patterns:
            return json.dumps({
                "success": True,
                "patterns": [],
                "message": "No prior patterns found. This may be the first import."
            })

        return json.dumps({
            "success": True,
            "patterns": patterns,
            "count": len(patterns),
        })

    except Exception as e:
        debug_error(e, "observe_prior_patterns", {"session_id": session_id})
        return json.dumps({
            "success": False,
            "error": f"Memory observation failed: {str(e)}"
        })


@tool
def save_mapping_proposal(
    session_id: str,
    mappings: List[Dict[str, Any]],
    unmapped_columns: List[str],
    missing_required: List[str],
    overall_confidence: float,
    target_table: str = "pending_entry_items",
) -> str:
    """
    Save mapping proposal to AgentCore Memory as INFERENCE.

    The proposal awaits HIL (Human-in-the-Loop) confirmation before
    being promoted to FACT. This enables the learning loop.

    Args:
        session_id: Import session identifier.
        mappings: List of column mappings with source, target, transform, confidence.
        unmapped_columns: Source columns that don't map to any target.
        missing_required: Required target columns without source match.
        overall_confidence: Overall mapping confidence (0.0-1.0).
        target_table: Target PostgreSQL table name.

    Returns:
        JSON confirmation of saved proposal.
    """
    try:
        # Build proposal structure
        proposal = {
            "session_id": session_id,
            "target_table": target_table,
            "mappings": mappings,
            "unmapped_source_columns": unmapped_columns,
            "missing_required_columns": missing_required,
            "overall_confidence": overall_confidence,
            "requires_confirmation": True,  # HIL ALWAYS required
        }

        # Initialize memory manager
        memory = AgentMemoryManager(
            agent_id=AGENT_ID,
            actor_id=session_id,
        )

        # Save as INFERENCE (agent-suggested, awaiting HIL)
        # Using synchronous version since Strands tools are sync
        import asyncio

        async def _save():
            await memory.learn_inference(
                inference=json.dumps(proposal),
                category="column_mapping_proposal",
                confidence=overall_confidence,
                session_id=session_id,
                use_global=False,  # User-specific until confirmed
                source_columns=[m.get("source_column") for m in mappings],
                target_table=target_table,
            )

        asyncio.run(_save())

        logger.info(
            f"[SchemaMapper] Saved proposal for session {session_id}: "
            f"{len(mappings)} mappings, confidence={overall_confidence:.2f}"
        )

        return json.dumps({
            "success": True,
            "message": "Mapping proposal saved to memory",
            "session_id": session_id,
            "mappings_count": len(mappings),
            "requires_hil": True,
        })

    except Exception as e:
        debug_error(e, "save_mapping_proposal", {
            "session_id": session_id,
            "mappings_count": len(mappings) if mappings else 0,
        })
        return json.dumps({
            "success": False,
            "error": f"Failed to save proposal: {str(e)}"
        })


@tool
def health_check() -> str:
    """
    Check the health status of the SchemaMapper agent.

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
        "architecture": "phase3-semantic-mapping",
        "capabilities": [
            "get_target_schema",
            "observe_prior_patterns",
            "save_mapping_proposal",
        ],
        "model": "gemini-2.5-pro",
        "thinking_enabled": True,
    })


# =============================================================================
# Agent Skills (A2A Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="get_target_schema",
        name="Get Target Schema",
        description="Fetch PostgreSQL table schema via MCP Gateway for mapping decisions",
        tags=["schema", "mcp", "introspection"],
    ),
    AgentSkill(
        id="observe_prior_patterns",
        name="Observe Prior Patterns",
        description="Retrieve learned column mapping patterns from AgentCore Memory",
        tags=["memory", "learning", "patterns"],
    ),
    AgentSkill(
        id="save_mapping_proposal",
        name="Save Mapping Proposal",
        description="Persist column mapping proposal to AgentCore Memory for HIL approval",
        tags=["memory", "proposal", "hil"],
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
    Create the SchemaMapper as a full Strands Agent.

    This agent handles Phase 3 semantic column mapping with:
    - MCP schema introspection (via SchemaProvider)
    - Semantic matching (dictionary + similarity)
    - Transformation detection (dates, numbers, currency)
    - Memory persistence (AgentCore Memory)
    - Gemini 2.5 Pro + Thinking (per CLAUDE.md)

    Returns:
        Strands Agent configured for semantic column mapping.
    """
    hooks = [
        LoggingHook(log_level=logging.INFO),
        MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        DebugHook(timeout_seconds=30.0),
    ]

    agent = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # Gemini 2.5 Pro + Thinking
        tools=[
            get_target_schema,
            observe_prior_patterns,
            save_mapping_proposal,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
    )

    logger.info(f"[SchemaMapper] Created {AGENT_NAME} with {len(hooks)} hooks")
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
        f"[SchemaMapper] Created A2A server on port {AGENT_PORT} "
        f"with {len(AGENT_SKILLS)} skills"
    )
    return server


# =============================================================================
# Main Entrypoint
# =============================================================================


def main() -> None:
    """
    Start the SchemaMapper A2A server.

    For local development:
        cd server/agentcore-inventory
        python -m agents.specialists.schema_mapper.main

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

    logger.info(f"[SchemaMapper] Starting A2A server on port {AGENT_PORT}...")

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

    # Create agent and A2A server
    agent = create_agent()
    a2a_server = create_a2a_server(agent)

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[SchemaMapper] Starting uvicorn server on 0.0.0.0:{AGENT_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_PORT",
    "create_agent",
    "create_a2a_server",
    "main",
]


if __name__ == "__main__":
    main()
