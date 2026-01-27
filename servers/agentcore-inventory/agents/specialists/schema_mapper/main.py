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
# RUNTIME:
# - AWS Bedrock AgentCore with A2A protocol on port 9000
# - Uses uvicorn + A2AServer (NOT BedrockAgentCoreApp)
#
# BUG-034 FIX: Lazy imports pattern for AgentCore 30s initialization timeout
# - Only import what's needed at module level (json, logging, os)
# - All heavy imports (strands, hooks, validators, etc.) deferred to first request
#
# BUG-035 FIX: A2A Protocol Migration
# - Changed from BedrockAgentCoreApp (HTTP, port 8080) to A2AServer (A2A, port 9000)
# - AgentCore expects A2A servers on port 9000 at root path (/)
#
# VERSION: 2026-01-27T05:30:00Z (BUG-035 A2A migration)
# =============================================================================

# =============================================================================
# BUG-033 FIX: sys.path fix for AgentCore Runtime
# =============================================================================
# MUST be at the very top, BEFORE any shared.* or tools.* imports.
# AgentCore deploys to /var/task but nested package imports can fail.
#
# File location: /var/task/agents/specialists/schema_mapper/main.py
# Project root: /var/task (4 levels up: main.py → schema_mapper → specialists → agents → root)
# =============================================================================
import sys
import os

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "../../../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# =============================================================================

# =============================================================================
# MINIMAL MODULE-LEVEL IMPORTS (BUG-034 + BUG-035)
# =============================================================================
# Only import what's absolutely required for fast initialization:
# 1. Logging (lightweight, standard library)
# 2. JSON serialization (lightweight, standard library)
# 3. OS for environment variable access
# 4. Type hints (typing module is lazy-loaded by Python)
#
# ALL heavy imports (strands, A2AServer, hooks, validators, memory, etc.)
# are deferred to _ensure_lazy_imports() which runs on first request.
# =============================================================================

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# LAZY IMPORT CACHE (BUG-034)
# =============================================================================
# Heavy imports are loaded ONCE on first invoke() and cached globally.
# This reduces module initialization time from >30s to <1s.
# =============================================================================

_lazy_loaded = False
_Agent = None
_tool = None
_A2AServer = None
_AgentSkill = None
_create_gemini_model = None
_AGENT_VERSION = None
_LoggingHook = None
_MetricsHook = None
_DebugHook = None
_SecurityAuditHook = None
_ResultValidationHook = None
_AGENT_VALIDATORS = None
_debug_error = None
_SchemaMappingResponse = None
_get_schema_provider = None
_AgentMemoryManager = None


def _ensure_lazy_imports() -> None:
    """
    Load all heavy imports on first invoke() call.

    BUG-034 FIX: AgentCore Firecracker has a 30-second initialization timeout.
    By deferring heavy imports to first invoke(), we:
    1. Allow app.run() to start the listener quickly (<1s)
    2. Load heavy dependencies only when actually needed
    3. Cache imports globally so subsequent calls are fast
    """
    global _lazy_loaded
    global _Agent, _tool, _A2AServer, _AgentSkill
    global _create_gemini_model, _AGENT_VERSION
    global _LoggingHook, _MetricsHook, _DebugHook, _SecurityAuditHook, _ResultValidationHook
    global _AGENT_VALIDATORS, _debug_error, _SchemaMappingResponse
    global _get_schema_provider, _AgentMemoryManager

    if _lazy_loaded:
        return

    logger.info("[SchemaMapper] Loading lazy imports (first invoke)...")

    # Strands framework
    from strands import Agent as AgentClass
    from strands import tool as tool_decorator
    from strands.multiagent.a2a import A2AServer as A2AServerClass
    from a2a.types import AgentSkill as AgentSkillClass

    _Agent = AgentClass
    _tool = tool_decorator
    _A2AServer = A2AServerClass
    _AgentSkill = AgentSkillClass

    # Agent utilities
    from agents.utils import create_gemini_model as _cgm, AGENT_VERSION as _av

    _create_gemini_model = _cgm
    _AGENT_VERSION = _av

    # Hooks (per ADR-002)
    from shared.hooks.logging_hook import LoggingHook
    from shared.hooks.metrics_hook import MetricsHook
    from shared.hooks.debug_hook import DebugHook
    from shared.hooks.security_audit_hook import SecurityAuditHook
    from shared.hooks.result_validation_hook import ResultValidationHook

    _LoggingHook = LoggingHook
    _MetricsHook = MetricsHook
    _DebugHook = DebugHook
    _SecurityAuditHook = SecurityAuditHook
    _ResultValidationHook = ResultValidationHook

    # Validators for Self-Validating Agent Pattern
    from shared.validators import AGENT_VALIDATORS

    _AGENT_VALIDATORS = AGENT_VALIDATORS

    # Debug utilities
    from shared.debug_utils import debug_error

    _debug_error = debug_error

    # Structured output schema
    from shared.agent_schemas import SchemaMappingResponse

    _SchemaMappingResponse = SchemaMappingResponse

    # Schema introspection
    from core_tools.schema_provider import get_schema_provider

    _get_schema_provider = get_schema_provider

    # Memory manager
    from shared.memory_manager import AgentMemoryManager

    _AgentMemoryManager = AgentMemoryManager

    _lazy_loaded = True
    logger.info("[SchemaMapper] Lazy imports loaded successfully")

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "schema_mapper"
AGENT_NAME = "FaistonSchemaMapper"
RUNTIME_ID = "faiston_schema_mapper-7fxI9bFHzd"  # From a2a_client.py PROD_RUNTIME_IDS
AGENT_DESCRIPTION = """
Senior Data Architect specialized in semantic column mapping.
Analyzes file columns and proposes mappings to PostgreSQL schema
using MCP introspection and AgentCore Memory for learning.
Phase 3 of the Smart Import architecture.
"""

# Port for local A2A server (see LOCAL_AGENTS in a2a_client.py)
AGENT_PORT = 9018

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

## Intelligent Question Generation (BUG-045 FIX)
When generating questions for disambiguation, use the sample_data provided to create
CONTEXT-AWARE questions. DO NOT use generic templates.

**Question Generation Rules:**
1. Analyze sample values to identify patterns (codes, dates, numbers, text)
2. Include 2-3 sample values in the question to help the user recognize the data
3. Write questions in **pt-BR** (user-facing) with a helpful, conversational tone
4. Add a `hint` field explaining your reasoning based on the observed patterns
5. Add a `context` field explaining why this mapping matters for the import

**Example - BEFORE (generic, unhelpful):**
"Qual coluna representa o código do material?"

**Example - AFTER (intelligent, context-aware):**
"Identificamos valores como 'PN-12345', 'ABC-789' na coluna 'COD_PROD'. Isso é o código do produto (Part Number)?"

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
    "partial_mappings": [...],
    "questions": [
        {
            "id": "q_part_number_abc123",
            "question": "Identificamos valores como 'PN-12345', 'ABC-789' na coluna 'COD_PROD'. Isso é o código do produto (Part Number)?",
            "context": "O campo part_number é obrigatório para importação no sistema de inventário.",
            "hint": "Baseado nos valores observados, esta coluna parece conter códigos alfanuméricos no formato de Part Number.",
            "importance": "critical",
            "topic": "column_mapping",
            "target_column": "part_number",
            "options": [
                {"value": "COD_PROD", "label": "COD_PROD", "recommended": true},
                {"value": "SKU", "label": "SKU", "recommended": false},
                {"value": "_none_", "label": "Nenhuma dessas colunas", "warning": true}
            ]
        }
    ],
    "overall_confidence": 0.65
}
"""


# =============================================================================
# Tools (Created dynamically inside invoke() with lazy imports)
# =============================================================================
# NOTE: Tools are created inside _create_tools() which is called after
# _ensure_lazy_imports(). This allows using lazy-loaded decorators and utilities.
# =============================================================================


def _create_tools():
    """
    Create tool functions with @tool decorator after lazy imports are loaded.

    BUG-034 FIX: We can't use @tool decorator at module level because
    strands isn't imported until _ensure_lazy_imports() runs. Instead,
    we create the tools dynamically here.

    Returns:
        List of tool-decorated functions for the Strands Agent.
    """
    _ensure_lazy_imports()

    @_tool
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
            provider = _get_schema_provider()
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
            _debug_error(e, "get_target_schema", {"table_name": table_name})
            return json.dumps({
                "success": False,
                "error": f"Schema fetch failed: {str(e)}"
            })

    @_tool
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
            memory = _AgentMemoryManager(
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
            _debug_error(e, "observe_prior_patterns", {"session_id": session_id})
            return json.dumps({
                "success": False,
                "error": f"Memory observation failed: {str(e)}"
            })

    @_tool
    def save_mapping_proposal(
        session_id: str,
        mappings: list,
        unmapped_columns: list,
        missing_required: list,
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
        import asyncio

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
            memory = _AgentMemoryManager(
                agent_id=AGENT_ID,
                actor_id=session_id,
            )

            # Save as INFERENCE (agent-suggested, awaiting HIL)
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
            _debug_error(e, "save_mapping_proposal", {
                "session_id": session_id,
                "mappings_count": len(mappings) if mappings else 0,
            })
            return json.dumps({
                "success": False,
                "error": f"Failed to save proposal: {str(e)}"
            })

    @_tool
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
            "version": _AGENT_VERSION,
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

    return [get_target_schema, observe_prior_patterns, save_mapping_proposal, health_check]


# Health check function for direct access (no LLM needed)
def _health_check_direct() -> dict:
    """Direct health check without lazy imports (for Mode 1)."""
    return {
        "success": True,
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": "2026-01-27T03:00:00Z",  # Hardcoded to avoid lazy import
        "runtime_id": RUNTIME_ID,
        "lazy_imports": "enabled",
    }


# =============================================================================
# Agent Skills (Created dynamically with lazy imports)
# =============================================================================


def _create_agent_skills() -> list:
    """
    Create agent skills after lazy imports are loaded.

    BUG-034 FIX: AgentSkill class requires a2a.types import which is deferred.
    """
    _ensure_lazy_imports()
    return [
        _AgentSkill(
            id="get_target_schema",
            name="Get Target Schema",
            description="Fetch PostgreSQL table schema via MCP Gateway for mapping decisions",
            tags=["schema", "mcp", "introspection"],
        ),
        _AgentSkill(
            id="observe_prior_patterns",
            name="Observe Prior Patterns",
            description="Retrieve learned column mapping patterns from AgentCore Memory",
            tags=["memory", "learning", "patterns"],
        ),
        _AgentSkill(
            id="save_mapping_proposal",
            name="Save Mapping Proposal",
            description="Persist column mapping proposal to AgentCore Memory for HIL approval",
            tags=["memory", "proposal", "hil"],
        ),
        _AgentSkill(
            id="health_check",
            name="Health Check",
            description="Check agent health status and capabilities",
            tags=["health", "monitoring"],
        ),
    ]


# =============================================================================
# Agent Factory (Uses lazy imports)
# =============================================================================


def create_agent():
    """
    Create the SchemaMapper as a full Strands Agent.

    This agent handles Phase 3 semantic column mapping with:
    - MCP schema introspection (via SchemaProvider)
    - Semantic matching (dictionary + similarity)
    - Transformation detection (dates, numbers, currency)
    - Memory persistence (AgentCore Memory)
    - Gemini 2.5 Pro + Thinking (per CLAUDE.md)

    BUG-034 FIX: Uses lazy-loaded classes and decorators.

    Returns:
        Strands Agent configured for semantic column mapping.
    """
    _ensure_lazy_imports()

    # Create tools dynamically (they use @_tool decorator)
    tools = _create_tools()

    hooks = [
        _LoggingHook(log_level=logging.INFO),
        _MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        _DebugHook(timeout_seconds=30.0),
        _SecurityAuditHook(enabled=True),  # FAIL-CLOSED audit trail
        # Self-Validating Agent Pattern (FEAT-self-validating-agents.md)
        # Runs deterministic validators on structured_output, triggers self-correction if needed
        _ResultValidationHook(
            validators=_AGENT_VALIDATORS.get(AGENT_ID, []),  # schema_mapper validators
            max_retries=3,
            enabled=True,
        ),
    ]

    agent = _Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=_create_gemini_model(AGENT_ID),  # Gemini 2.5 Pro + Thinking
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
        # BUG-023 FIX: Enforce structured JSON output matching Pydantic model
        structured_output_model=_SchemaMappingResponse,
    )

    logger.info(f"[SchemaMapper] Created {AGENT_NAME} with {len(hooks)} hooks")
    return agent


def create_a2a_server(agent):
    """
    Create A2A server for agent-to-agent communication.

    The A2AServer wraps the Strands Agent and provides:
    - JSON-RPC 2.0 endpoint at /
    - Agent Card discovery at /.well-known/agent.json
    - Health check at /health

    BUG-034 FIX: Uses lazy-loaded A2AServer class.
    BUG-035 FIX: Uses port 9000 and serve_at_root=True for AgentCore.

    Args:
        agent: The Strands Agent to wrap.

    Returns:
        A2AServer instance ready to mount on FastAPI.
    """
    _ensure_lazy_imports()
    skills = _create_agent_skills()

    # Get runtime URL for A2A self-registration
    runtime_url = os.environ.get("AGENTCORE_RUNTIME_URL", "http://127.0.0.1:9000/")

    server = _A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,  # BUG-035: AgentCore expects port 9000
        http_url=runtime_url,
        version=_AGENT_VERSION,
        skills=skills,
        serve_at_root=True,  # BUG-035: Required for AgentCore
    )

    logger.info(
        f"[SchemaMapper] Created A2A server on port 9000 "
        f"with {len(skills)} skills"
    )
    return server


# =============================================================================
# Legacy Invoke Handler (Backward Compatibility)
# =============================================================================
# NOTE: With BUG-035 A2A migration, this function is NO LONGER the entrypoint.
# The A2AServer routes JSON-RPC messages directly to the Strands Agent.
# This function is kept for backward compatibility with tests and direct calls.
# =============================================================================


def invoke(payload: dict, context=None) -> dict:
    """
    Legacy handler for direct invocation (backward compatibility).

    NOTE: With BUG-035 A2A migration, this function is NO LONGER the entrypoint.
    The A2AServer routes JSON-RPC messages directly to the Strands Agent.
    This function is kept for:
    - Backward compatibility with tests
    - Direct programmatic invocation
    - Reference implementation

    Args:
        payload: Request payload containing:
            - action: "health_check" for system status
            - source_columns: List of column names from the uploaded file
            - sample_data: Sample values for each column (for inference)
            - session_id: Import session identifier
        context: Optional context object (legacy, not used in A2A).

    Returns:
        Response dict with mapping proposal or health status.
    """
    try:
        # Handle health check (Mode 1: no LLM, no lazy imports)
        action = payload.get("action", "")
        if action == "health_check":
            logger.info("[SchemaMapper] Health check requested (direct, no lazy imports)")
            return _health_check_direct()

        # Extract context
        session_id = payload.get("session_id", "unknown")
        logger.info(f"[SchemaMapper] Invoked with keys: {list(payload.keys())}, session={session_id}")

        # BUG-034: Lazy imports are loaded here on first LLM call
        _ensure_lazy_imports()

        # Initialize Strands Agent (uses lazy-loaded classes)
        agent = create_agent()

        # Invoke agent with the full payload (Mode 2: LLM reasoning)
        # The agent will use get_target_schema, observe_prior_patterns, etc.
        response = agent(payload)

        # Extract response from Strands Agent result
        if hasattr(response, "message"):
            return {"success": True, "response": response.message}
        elif isinstance(response, dict):
            return response
        else:
            return {"success": True, "response": str(response)}

    except Exception as e:
        # Log full stack trace for debugging
        logger.error(f"[SchemaMapper] Error in invoke: {str(e)}", exc_info=True)
        # Re-raise so caller can handle
        raise


# =============================================================================
# A2A SERVER FACTORY (BUG-035 FIX)
# =============================================================================
# Creates FastAPI app with A2AServer mounted for AgentCore A2A protocol.
# Port 9000, serve_at_root=True per AgentCore A2A requirements.
# =============================================================================


def create_app():
    """
    Factory function to create FastAPI app with A2AServer.

    BUG-035 FIX: Migrates from BedrockAgentCoreApp (HTTP, port 8080) to
    A2AServer (A2A protocol, port 9000).

    This function:
    1. Loads lazy imports (first call triggers heavy imports)
    2. Creates the Strands Agent with tools and hooks
    3. Wraps agent in A2AServer for JSON-RPC protocol
    4. Returns FastAPI app with health check endpoint

    Returns:
        FastAPI application ready for uvicorn.
    """
    _ensure_lazy_imports()

    from fastapi import FastAPI

    # Create Strands Agent with tools
    agent = create_agent()

    # Create A2AServer wrapping the agent
    a2a_server = create_a2a_server(agent)

    # Create FastAPI app with health check endpoint
    app = FastAPI(
        title="SchemaMapper A2A Server",
        description="Senior Data Architect for semantic column mapping",
    )

    @app.get("/ping")
    def ping():
        """Health check endpoint for AgentCore."""
        return {
            "status": "healthy",
            "agent_id": AGENT_ID,
            "protocol": "A2A",
            "port": 9000,
        }

    # Mount A2AServer at root (AgentCore expects A2A at /)
    app.mount("/", a2a_server.to_fastapi_app())

    logger.info(f"[SchemaMapper] Created A2A app with agent {AGENT_ID}")
    return app


def _start_server():
    """
    Start the A2A server with uvicorn.

    BUG-035 FIX: Uses uvicorn on port 9000 for A2A protocol.

    This function is called:
    - When module is run directly: `python -m agents.specialists.schema_mapper.main`
    - When module is imported in AgentCore: Detected via AWS_EXECUTION_ENV
    """
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("[SchemaMapper] Starting A2A Server on port 9000...")
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=9000)


# =============================================================================
# MODULE-LEVEL EXECUTION (BUG-035 FIX)
# =============================================================================
# A2A servers must start uvicorn on port 9000. The server is started when:
# 1. Module is run directly: __name__ == "__main__"
# 2. Module is imported in AgentCore: AWS_EXECUTION_ENV is set
#
# CRITICAL (User Feedback A): We use AWS_EXECUTION_ENV check instead of bare
# `else` block to avoid side-effects on import. This allows:
# - Unit tests to import without blocking
# - Local development with explicit `python main.py`
# - AgentCore deployment to auto-start server
# =============================================================================

if __name__ == "__main__":
    # Local development: python -m agents.specialists.schema_mapper.main
    _start_server()
# REMOVED (BUG-036): AWS_EXECUTION_ENV check was redundant.
# AgentCore A2A pattern uses `if __name__ == "__main__"` only.
# Ref: https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/a2a.md


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_PORT",
    "create_agent",
    "create_a2a_server",
    "create_app",  # BUG-035: FastAPI factory for A2AServer
    "_start_server",  # BUG-035: Server startup function
    "invoke",  # Legacy handler for backward compatibility
]
