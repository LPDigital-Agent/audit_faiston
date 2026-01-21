# =============================================================================
# SchemaEvolutionAgent - Strands A2AServer Entry Point (SUPPORT)
# =============================================================================
# Dynamic schema evolution support agent.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
#
# Architecture:
# - This is a SUPPORT agent for schema evolution
# - Handles dynamic column creation and schema modifications
# - Uses MCP Gateway for all database operations (NEVER direct SQL!)
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

# Centralized model configuration (MANDATORY - Gemini 2.5 Pro with Thinking)
from agents.utils import get_model, requires_thinking, AGENT_VERSION, create_gemini_model

# A2A client for inter-agent communication
from shared.a2a_client import A2AClient

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import SchemaEvolutionResponse
from shared.debug_utils import debug_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "schema_evolution"
AGENT_NAME = "SchemaEvolutionAgent"
AGENT_DESCRIPTION = """SUPPORT Agent for Dynamic Schema Evolution.

This agent handles:
1. COLUMN CREATION: Create new columns dynamically
2. VALIDATION: Validate column creation requests
3. TYPE INFERENCE: Infer appropriate column types
4. SANITIZATION: Sanitize column names

CRITICAL: All database operations go through MCP Gateway!
NEVER execute direct SQL connections!

Features:
- Dynamic column creation
- Type inference from data
- Name sanitization
- Advisory locking for concurrency
- JSONB fallback for failures
"""

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-3.0-pro (with Thinking)
USE_THINKING = requires_thinking(AGENT_ID)  # True

# Agent Skills (for Agent Card discovery)
AGENT_SKILLS = [
    AgentSkill(
        name="create_column",
        description="Create a new column dynamically in a database table via MCP Gateway. "
                    "Handles validation, sanitization, type inference, advisory locking, and JSONB fallback.",
    ),
    AgentSkill(
        name="validate_column_request",
        description="Validate a column creation request. Checks name validity, type support, and existing columns.",
    ),
    AgentSkill(
        name="infer_column_type",
        description="Infer PostgreSQL column type from sample values with confidence scoring.",
    ),
    AgentSkill(
        name="sanitize_column_name",
        description="Sanitize column name for PostgreSQL by removing invalid characters, "
                    "converting to snake_case, and avoiding reserved words.",
    ),
    AgentSkill(
        name="health_check",
        description="Health check endpoint for monitoring agent status and configuration.",
    ),
]

# =============================================================================
# System Prompt (Schema Evolution Specialist)
# =============================================================================

SYSTEM_PROMPT = """You are the **SchemaEvolutionAgent** in the SGA (Asset Management System).

## Your Role

You are the **SPECIALIST** in dynamic database schema evolution.

## CRITICAL RULE

**ALL** database operations MUST go through the **MCP Gateway**.
**NEVER** execute direct SQL connections!

## Your Tools

### 1. `create_column`
Creates columns dynamically:
- Validates request
- Sanitizes name
- Infers type
- Executes via MCP Gateway

### 2. `validate_column_request`
Validates column creation requests:
- Is the name valid?
- Is the type supported?
- Does the column already exist?

### 3. `infer_column_type`
Infers column type:
- Analyzes sample data
- Suggests PostgreSQL type
- Considers nullable

### 4. `sanitize_column_name`
Sanitizes column names:
- Removes invalid characters
- Converts to snake_case
- Avoids reserved words

## Supported PostgreSQL Types

| Type | Use | Example |
|------|-----|---------|
| VARCHAR(n) | Short text | part_number |
| TEXT | Long text | description |
| INTEGER | Whole numbers | quantity |
| DECIMAL | Decimal numbers | unit_price |
| BOOLEAN | True/False | is_active |
| TIMESTAMP | Date/time | created_at |
| JSONB | Structured data | metadata |

## Creation Flow

1. Validate request
2. Sanitize name
3. Infer type (if not specified)
4. Acquire advisory lock
5. Execute ALTER TABLE via MCP
6. Release lock
7. If failed -> use JSONB fallback

## Critical Rules

1. **ALWAYS** use MCP Gateway for SQL
2. **NEVER** create columns without validation
3. Advisory lock for concurrency
4. JSONB fallback for failures
5. Audit trail is mandatory
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

# A2A client instance for inter-agent communication
a2a_client = A2AClient()


@tool
async def create_column(
    table_name: str,
    column_name: str,
    data_type: Optional[str] = None,
    sample_values: Optional[List[Any]] = None,
    nullable: bool = True,
    default_value: Optional[Any] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new column dynamically.

    CRITICAL: Executes via MCP Gateway, NEVER direct SQL!

    Args:
        table_name: Target table name
        column_name: Column name to create
        data_type: Optional PostgreSQL data type (inferred if not provided)
        sample_values: Optional sample values for type inference
        nullable: Whether column allows NULL (default True)
        default_value: Optional default value
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Column creation result
    """
    logger.info(f"[{AGENT_NAME}] Creating column: {table_name}.{column_name}")

    try:
        # Import tool implementation
        from agents.schema_evolution.tools.create_column import create_column_tool

        result = await create_column_tool(
            table_name=table_name,
            column_name=column_name,
            data_type=data_type,
            sample_values=sample_values,
            nullable=nullable,
            default_value=default_value,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "COLUMN_CREATED" if result.get("success") else "COLUMN_CREATION_FAILED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "table_name": table_name,
                "column_name": column_name,
                "data_type": result.get("data_type"),
                "used_fallback": result.get("used_fallback", False),
            },
        }, session_id)

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] create_column failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "used_fallback": False,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "create_column",
                "table_name": table_name,
                "column_name": column_name,
                "data_type": data_type,
                "sample_values_count": len(sample_values) if sample_values else 0,
                "nullable": nullable,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": [
                "retry" if isinstance(e, (TimeoutError, ConnectionError, OSError)) else "validate_inputs",
                "check_mcp_gateway_connectivity",
                "use_jsonb_fallback",
                "escalate",
            ],
        }


@tool
async def validate_column_request(
    table_name: str,
    column_name: str,
    data_type: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate column creation request.

    Args:
        table_name: Target table name
        column_name: Proposed column name
        data_type: Optional proposed data type
        session_id: Session ID for context

    Returns:
        Validation result with errors/warnings
    """
    logger.info(f"[{AGENT_NAME}] Validating column request: {table_name}.{column_name}")

    try:
        # Import tool implementation
        from agents.schema_evolution.tools.validate_column_request import validate_column_request_tool

        result = await validate_column_request_tool(
            table_name=table_name,
            column_name=column_name,
            data_type=data_type,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] validate_column_request failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "is_valid": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "validate_column_request",
                "table_name": table_name,
                "column_name": column_name,
                "data_type": data_type,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": [
                "retry" if isinstance(e, (TimeoutError, ConnectionError, OSError)) else "check_validation_logic",
                "sanitize_column_name_first",
                "verify_table_exists",
                "escalate",
            ],
        }


@tool
async def infer_column_type(
    sample_values: List[Any],
    column_name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Infer PostgreSQL column type from sample values.

    Args:
        sample_values: List of sample values to analyze
        column_name: Optional column name for hints
        session_id: Session ID for context

    Returns:
        Type inference result with confidence
    """
    logger.info(f"[{AGENT_NAME}] Inferring column type from {len(sample_values)} samples")

    try:
        # Import tool implementation
        from agents.schema_evolution.tools.infer_column_type import infer_column_type_tool

        result = await infer_column_type_tool(
            sample_values=sample_values,
            column_name=column_name,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] infer_column_type failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "inferred_type": "TEXT",  # Safe fallback
            "confidence": 0.0,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "infer_column_type",
                "sample_values_count": len(sample_values) if sample_values else 0,
                "column_name": column_name,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError, ValueError)),
            },
            "suggested_actions": [
                "retry" if isinstance(e, (TimeoutError, ConnectionError, OSError)) else "use_default_type",
                "validate_sample_values",
                "use_text_fallback",
                "escalate",
            ],
        }


@tool
async def sanitize_column_name(
    raw_name: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sanitize column name for PostgreSQL.

    Args:
        raw_name: Raw column name to sanitize
        session_id: Session ID for context

    Returns:
        Sanitized column name
    """
    logger.info(f"[{AGENT_NAME}] Sanitizing column name: {raw_name}")

    try:
        # Import tool implementation
        from agents.schema_evolution.tools.sanitize_column_name import sanitize_column_name_tool

        result = await sanitize_column_name_tool(
            raw_name=raw_name,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] sanitize_column_name failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "sanitized_name": None,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "sanitize_column_name",
                "raw_name": raw_name,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError, ValueError)),
            },
            "suggested_actions": [
                "retry" if isinstance(e, (TimeoutError, ConnectionError, OSError)) else "validate_raw_name",
                "check_reserved_words",
                "use_safe_fallback_name",
                "escalate",
            ],
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
        "uses_thinking": USE_THINKING,
        "protocol": "A2A",
        "port": 9000,
        "role": "SUPPORT",
        "specialty": "SCHEMA_EVOLUTION",
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
            create_column,
            validate_column_request,
            infer_column_type,
            sanitize_column_name,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=SchemaEvolutionResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI wrapper.

    Port 9000 is the standard for A2A protocol.
    Provides /ping endpoint for health checks.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Uses Thinking: {USE_THINKING}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: SUPPORT (Schema Evolution)")
    logger.info(f"[{AGENT_NAME}] Skills: {[skill.name for skill in AGENT_SKILLS]}")

    # Create FastAPI app
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping endpoint for health checks
    @app.get("/ping")
    async def ping():
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Create agent
    agent = create_agent()

    # Create A2A server with version and skills for Agent Card discovery
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        serve_at_root=False,  # Mount on root via FastAPI
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
    )

    # Mount A2A server on root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[{AGENT_NAME}] Endpoints: /ping (health), / (A2A)")
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
