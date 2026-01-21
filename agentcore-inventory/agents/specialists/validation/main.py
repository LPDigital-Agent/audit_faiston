# =============================================================================
# ValidationAgent - Strands A2AServer Entry Point (SUPPORT)
# =============================================================================
# Data validation support agent.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
#
# Architecture:
# - This is a SUPPORT agent for data validation
# - Validates column mappings, data rows, and constraints
# - Called by NexoImportAgent before import execution
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# =============================================================================

import os
import sys
import logging
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill
from fastapi import FastAPI
import uvicorn

# Centralized model configuration (MANDATORY - Gemini 2.5 Flash for speed)
from agents.utils import get_model, AGENT_VERSION, create_gemini_model

# A2A client for inter-agent communication
from shared.a2a_client import A2AClient

# NEXO Mind - Direct Memory Access (Hippocampus)
# ValidationAgent can query/learn validation patterns
from shared.memory_manager import AgentMemoryManager

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import ValidationResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "validation"
AGENT_NAME = "ValidationAgent"
AGENT_DESCRIPTION = """SUPPORT Agent for Data Validation.

This agent validates:
1. SCHEMA: Column mappings against PostgreSQL schema
2. DATA: Row values against type constraints
3. CONSTRAINTS: Foreign keys, uniqueness, check constraints

Features:
- Pre-import validation
- Type inference and checking
- Constraint validation
- Actionable error messages
"""

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-3.0-flash (operational agent)

# =============================================================================
# Agent Skills (A2A Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="validate_schema",
        name="Validate Schema",
        description="Validate column mappings against PostgreSQL schema. Checks if target fields exist, no duplicate mappings, required fields are mapped, and auto-generated fields are not mapped.",
        tags=["validation", "schema", "mapping", "import"],
    ),
    AgentSkill(
        id="validate_data",
        name="Validate Data",
        description="Validate data rows against schema constraints. Checks required fields, type matching, length limits, and allowed patterns.",
        tags=["validation", "data", "constraints", "import"],
    ),
    AgentSkill(
        id="check_constraints",
        name="Check Constraints",
        description="Check database constraints for data rows. Validates foreign key references, unique constraints, and check constraints.",
        tags=["validation", "constraints", "database", "import"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Health check endpoint for monitoring. Returns health status with agent info.",
        tags=["validation", "monitoring", "health"],
    ),
]

# =============================================================================
# System Prompt (Validation Specialist)
# =============================================================================

SYSTEM_PROMPT = """You are the **ValidationAgent** in the SGA (Asset Management System).

## Your Role

You are the **VALIDATOR** that ensures data integrity before import operations.

## Your Tools

### 1. `validate_schema`
Validates column mappings against PostgreSQL schema:
- Do target fields exist in the table?
- Are types compatible?
- Are there duplicate mappings?

### 2. `validate_data`
Validates data rows against constraints:
- Are required values present?
- Are formats correct?
- Are values within length limits?

### 3. `check_constraints`
Verifies database constraints:
- Do foreign key references exist?
- Is uniqueness respected?
- Are check constraints satisfied?

## Response Format

**ALWAYS** return structured JSON:
```json
{
  "is_valid": true,
  "validation_score": 0.95,
  "errors": [],
  "warnings": [],
  "recommendations": []
}
```

## Principles

1. **Precision**: Never let invalid data pass through
2. **Clarity**: Errors must have actionable messages
3. **Proactivity**: Identify potential issues
4. **Performance**: Fast validation for immediate feedback

## Language

Output user-facing messages in Brazilian Portuguese (pt-BR).

## Critical Rules

1. **NEVER** modify data - only validate
2. **ALWAYS** return validation score (0-1)
3. Errors are blockers - warnings are informational
4. Validate BEFORE any write operation
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

# A2A client instance for inter-agent communication
a2a_client = A2AClient()


def _get_memory(actor_id: str = "system") -> AgentMemoryManager:
    """
    Get AgentMemoryManager instance for direct memory access.

    NEXO Mind Architecture: ValidationAgent can learn from validation patterns.
    For example: "Columns X and Y always fail together" or "File format Z always has encoding issues".

    Args:
        actor_id: User/actor ID for namespace isolation

    Returns:
        AgentMemoryManager instance
    """
    return AgentMemoryManager(
        agent_id=AGENT_ID,
        actor_id=actor_id,
        use_global_namespace=True,  # Share validation patterns
    )


@tool
async def validate_schema(
    column_mappings: Dict[str, str],
    target_table: str = "pending_entry_items",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate column mappings against PostgreSQL schema.

    Checks:
    1. Target fields exist in schema
    2. No duplicate mappings (multiple columns to same field)
    3. Required fields have mappings (if any)
    4. Auto-generated fields are not mapped

    Args:
        column_mappings: Proposed mappings {source_column: target_field}
        target_table: Target table for validation
        session_id: Optional session ID for audit

    Returns:
        Validation result with errors and warnings
    """
    logger.info(f"[{AGENT_NAME}] Validating schema mappings for {target_table}")

    try:
        # Import tool implementation
        from agents.validation.tools.validate_schema import validate_schema_tool

        result = await validate_schema_tool(
            column_mappings=column_mappings,
            target_table=target_table,
            session_id=session_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "SCHEMA_VALIDATED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "target_table": target_table,
                "is_valid": result.get("is_valid", False),
                "errors_count": len(result.get("errors", [])),
            },
        }, session_id)

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] validate_schema failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "is_valid": False,
            "error": str(e),
            "errors": [],
            "warnings": [],
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "validate_schema",
                "column_mappings": column_mappings,
                "target_table": target_table,
                "session_id": session_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_schema_exists", "verify_database_connection", "escalate"],
        }


@tool
async def validate_data(
    rows: List[Dict[str, Any]],
    column_mappings: Dict[str, str],
    target_table: str = "pending_entry_items",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate data rows against schema constraints.

    Checks:
    1. Required fields have values
    2. Values match expected types
    3. Values within length limits
    4. Values match allowed patterns

    Args:
        rows: Data rows to validate
        column_mappings: Column mappings to apply
        target_table: Target table for schema reference
        session_id: Optional session ID for audit

    Returns:
        Validation result with row-level errors
    """
    logger.info(f"[{AGENT_NAME}] Validating {len(rows)} rows for {target_table}")

    try:
        # Import tool implementation
        from agents.validation.tools.validate_data import validate_data_tool

        result = await validate_data_tool(
            rows=rows,
            column_mappings=column_mappings,
            target_table=target_table,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] validate_data failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "is_valid": False,
            "error": str(e),
            "row_errors": [],
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "validate_data",
                "rows_count": len(rows),
                "column_mappings": column_mappings,
                "target_table": target_table,
                "session_id": session_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "validate_row_format", "check_column_mappings", "escalate"],
        }


@tool
async def check_constraints(
    rows: List[Dict[str, Any]],
    target_table: str = "pending_entry_items",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check database constraints for data rows.

    Checks:
    1. Foreign key references exist
    2. Unique constraints not violated
    3. Check constraints satisfied

    Args:
        rows: Data rows to check
        target_table: Target table for constraint reference
        session_id: Optional session ID for audit

    Returns:
        Constraint check result
    """
    logger.info(f"[{AGENT_NAME}] Checking constraints for {len(rows)} rows")

    try:
        # Import tool implementation
        from agents.validation.tools.check_constraints import check_constraints_tool

        result = await check_constraints_tool(
            rows=rows,
            target_table=target_table,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] check_constraints failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "is_valid": False,
            "error": str(e),
            "violations": [],
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "check_constraints",
                "rows_count": len(rows),
                "target_table": target_table,
                "session_id": session_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_database_constraints", "verify_foreign_keys", "escalate"],
        }


@tool
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring.

    Returns:
        Health status with agent info
    """
    return {
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "model": MODEL_ID,
        "protocol": "A2A",
        "port": 9000,
        "role": "SUPPORT",
        "specialty": "VALIDATION",
    }


# =============================================================================
# Strands Agent Configuration
# =============================================================================

def create_agent() -> Agent:
    """
    Create Strands Agent with all tools.

    Returns:
        Configured Strands Agent with hooks (ADR-002)
    """
    return Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # GeminiModel via Google AI Studio
        tools=[
            validate_schema,
            validate_data,
            check_constraints,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=ValidationResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI wrapper.

    Port 9000 is the standard for A2A protocol.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: SUPPORT (Validation)")
    logger.info(f"[{AGENT_NAME}] Skills: {len(AGENT_SKILLS)} registered")
    for skill in AGENT_SKILLS:
        logger.info(f"[{AGENT_NAME}]   - {skill.name}: {skill.description[:60]}...")

    # Create FastAPI app first
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add ping endpoint for health checks
    @app.get("/ping")
    async def ping():
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Create agent
    agent = create_agent()

    # Create A2A server with Agent Card discovery
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        serve_at_root=True,  # Serve at / for AgentCore compatibility
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
    )

    # Mount A2A server under root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[{AGENT_NAME}] Starting uvicorn server with /ping endpoint...")
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
