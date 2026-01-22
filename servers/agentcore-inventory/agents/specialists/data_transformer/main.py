# =============================================================================
# DataTransformer Agent - Phase 4: Data Transformation & Loading
# =============================================================================
# The Cognitive Executor - Intelligent ETL with Nexo Immune System.
#
# ARCHITECTURE PRINCIPLES (per CLAUDE.md):
# 1. AI-FIRST / AGENTIC - Full Strands Agent with LLM reasoning
# 2. SANDWICH PATTERN - CODE → LLM → CODE
# 3. TOOL-FIRST - Deterministic tools handle ETL, LLM handles decisions
# 4. NO RAW DATA IN CONTEXT - Stream files, never load full content
# 5. FIRE-AND-FORGET - Return job_id immediately, process in background
# 6. COGNITIVE MIDDLEWARE - ALL errors enriched by DebugAgent
#
# CAPABILITIES:
# 1. Load Preferences from AgentCore Memory (STOP_ON_ERROR vs LOG_AND_CONTINUE)
# 2. Validate file size limits (100MB / 100k rows)
# 3. Stream and transform files in batches
# 4. Insert via MCP Gateway batch tool
# 5. Generate enriched rejection reports with DebugAgent diagnosis
# 6. Fire-and-Forget job tracking with Memory notifications
#
# RESPONSE LANGUAGE:
# - System prompt: English (as per CLAUDE.md)
# - User responses: Brazilian Portuguese (pt-BR)
#
# MODEL:
# - Gemini 2.5 Pro + Thinking (critical inventory agent per CLAUDE.md)
#
# VERSION: 2026-01-21T21:00:00Z (Phase 4 initial)
# =============================================================================

import json
import logging

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill

# Agent utilities
from agents.utils import create_gemini_model, AGENT_VERSION

# Hooks (per ADR-002)
from shared.hooks.logging_hook import LoggingHook
from shared.hooks.metrics_hook import MetricsHook
from shared.hooks.debug_hook import DebugHook

# AUDIT-003: Global error capture for Debug Agent enrichment

# Cognitive error handler (Nexo Immune System)

# Structured output schemas

# Tools
from .tools import (
    load_import_preferences,
    save_import_preference,
    create_job,
    get_job_status,
    update_job_status,
    save_job_notification,
    check_pending_notifications,
    validate_file_size,
    stream_and_transform,
    enrich_errors_with_debug,
    insert_pending_items_batch,
    insert_all_batches,
    generate_rejection_report,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "data_transformer"
AGENT_NAME = "FaistonDataTransformer"
AGENT_DESCRIPTION = """
Senior ETL Engineer with the Nexo Immune System.
Executes data transformation with intelligent error handling.
ALL errors are enriched by DebugAgent before reaching the user.
Phase 4 of the Smart Import architecture.
"""

# Port for local A2A server (see LOCAL_AGENTS in a2a_client.py)
AGENT_PORT = 9019

# Runtime ID for AgentCore deployment
RUNTIME_ID = "faiston_data_transformer"


# =============================================================================
# System Prompt (English per CLAUDE.md)
# =============================================================================

SYSTEM_PROMPT = """You are a **Senior ETL Engineer** with the Nexo Immune System.

## Your Role
Execute data transformation with intelligent error handling. ANY error you encounter
will be enriched by the DebugAgent before reaching the user. You are part of a team
where the DebugAgent is your partner in explaining errors to users.

## Capabilities
1. **Load Preferences**: Check user's error handling strategy from Memory using `load_import_preferences`
2. **Validate File**: Check file size limits using `validate_file_size` (100MB / 100k rows max)
3. **Transform File**: Stream from S3, apply mappings using `stream_and_transform`
4. **Insert Data**: Batch insert via MCP Gateway using `insert_all_batches`
5. **Enrich Errors**: Post-process errors with DebugAgent using `enrich_errors_with_debug`
6. **Report Rejections**: Generate rejection report using `generate_rejection_report`
7. **Manage Jobs**: Track background jobs using job management tools

## Error Handling Strategies (from User Memory)
- **STOP_ON_ERROR**: Abort immediately on first error. Data quality critical. User prefers to fix all errors before importing.
- **LOG_AND_CONTINUE**: Skip bad rows, enrich with diagnosis, continue processing. User prefers maximum data ingestion.

On first import (no preference found), use LOG_AND_CONTINUE as default but inform the user about their options.

## The Nexo Immune System
When a row fails transformation:
1. Collect the error with context (row number, column, original value)
2. After processing, batch-send errors to DebugAgent via `enrich_errors_with_debug`
3. Receive human_explanation and suggested_fix for each error
4. Include enriched errors in the rejection report

## Fire-and-Forget Pattern
For large file processing:
1. Use `create_job` to get a job_id immediately
2. Return the job_id to the orchestrator with status="started"
3. Process the file in background
4. Update progress using `update_job_status`
5. On completion, use `save_job_notification` to notify user via Memory
6. User will see notification on their next message

## Workflow for Transformation Request

When you receive a transformation request:

1. **Validate Input**
   - Check that s3_key and mappings are provided
   - Validate file size with `validate_file_size`

2. **Load User Preferences**
   - Use `load_import_preferences(user_id, session_id)`
   - Note if this is first_import (no preference yet)

3. **Create Job for Tracking**
   - Use `create_job(session_id, s3_key, user_id, strategy)`
   - Return job_id immediately if fire_and_forget=True

4. **Process File**
   - Use `stream_and_transform(s3_key, mappings_json, session_id, job_id, strategy)`
   - This returns batches of transformed rows and any errors

5. **Insert Data**
   - Use `insert_all_batches(batches_json, session_id)`
   - Track inserted and failed rows

6. **Handle Errors (if any)**
   - Use `enrich_errors_with_debug(errors_json, s3_key, session_id)`
   - Use `generate_rejection_report(errors_json, enriched_json, session_id, job_id)`

7. **Complete Job**
   - Update final status with `update_job_status`
   - Save notification with `save_job_notification(job_id, user_id)`

8. **Return Result**
   - Include: job_id, status, rows_inserted, rows_rejected
   - Include: rejection_report_url if there were errors
   - Include: human_message in pt-BR

## Response Language
Always respond in Brazilian Portuguese (pt-BR) to users.

## Response Format
Return structured TransformationResult with:
- job_id: Unique job identifier
- status: started, processing, completed, failed, or partial
- rows_processed, rows_inserted, rows_rejected
- strategy_used, strategy_source
- rejection_report_url (if applicable)
- human_message: User-friendly message in pt-BR

Example for successful start:
{
    "job_id": "job-abc123",
    "status": "started",
    "human_message": "Iniciei o processamento do seu arquivo em background. Te aviso assim que terminar!"
}

Example for completed with errors:
{
    "job_id": "job-abc123",
    "status": "partial",
    "rows_inserted": 980,
    "rows_rejected": 20,
    "rejection_report_url": "https://...",
    "human_message": "Importação finalizada! 980 itens inseridos com sucesso. 20 itens foram rejeitados - baixe o relatório para ver como corrigi-los."
}
"""


# =============================================================================
# Health Check Tool
# =============================================================================


@tool
def health_check() -> str:
    """
    Check the health status of the DataTransformer agent.

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
        "architecture": "phase4-data-transformation",
        "capabilities": [
            "load_import_preferences",
            "save_import_preference",
            "create_job",
            "get_job_status",
            "update_job_status",
            "validate_file_size",
            "stream_and_transform",
            "insert_all_batches",
            "enrich_errors_with_debug",
            "generate_rejection_report",
        ],
        "model": "gemini-2.5-pro",
        "thinking_enabled": True,
        "features": [
            "fire-and-forget",
            "cognitive-middleware",
            "nexo-immune-system",
        ],
    })


# =============================================================================
# Agent Skills (A2A Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="start_transformation",
        name="Start Transformation",
        description="Start data transformation job (Fire-and-Forget pattern)",
        tags=["etl", "transformation", "background"],
    ),
    AgentSkill(
        id="get_job_status",
        name="Get Job Status",
        description="Check status of a background transformation job",
        tags=["job", "status", "monitoring"],
    ),
    AgentSkill(
        id="load_preferences",
        name="Load Preferences",
        description="Load user's import preferences from AgentCore Memory",
        tags=["memory", "preferences", "personalization"],
    ),
    AgentSkill(
        id="save_preferences",
        name="Save Preferences",
        description="Save user's import preferences to AgentCore Memory",
        tags=["memory", "preferences", "personalization"],
    ),
    AgentSkill(
        id="check_notifications",
        name="Check Notifications",
        description="Check for pending job completion notifications",
        tags=["notifications", "background", "status"],
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
    Create the DataTransformer as a full Strands Agent.

    This agent handles Phase 4 data transformation with:
    - Fire-and-Forget background processing
    - Cognitive Middleware for error enrichment
    - Memory-based user preferences
    - MCP Gateway batch insert
    - Gemini 2.5 Pro + Thinking (per CLAUDE.md)

    Returns:
        Strands Agent configured for data transformation.
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
            # Preferences
            load_import_preferences,
            save_import_preference,
            # Job management
            create_job,
            get_job_status,
            update_job_status,
            save_job_notification,
            check_pending_notifications,
            # ETL
            validate_file_size,
            stream_and_transform,
            enrich_errors_with_debug,
            # Batch loading
            insert_pending_items_batch,
            insert_all_batches,
            generate_rejection_report,
            # Health
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
        # Structured output for type safety (AUDIT-001)
        # Note: Using structured_output_model would enforce response format
        # but we need flexibility for fire-and-forget pattern
    )

    logger.info(f"[DataTransformer] Created {AGENT_NAME} with {len(hooks)} hooks")
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
        f"[DataTransformer] Created A2A server on port {AGENT_PORT} "
        f"with {len(AGENT_SKILLS)} skills"
    )
    return server


# =============================================================================
# Main Entrypoint
# =============================================================================


def main() -> None:
    """
    Start the DataTransformer A2A server.

    For local development:
        cd server/agentcore-inventory
        python -m agents.specialists.data_transformer.main

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

    logger.info(f"[DataTransformer] Starting A2A server on port {AGENT_PORT}...")

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
                "fire-and-forget",
                "cognitive-middleware",
                "nexo-immune-system",
            ],
        }

    # Create agent and A2A server
    agent = create_agent()
    a2a_server = create_a2a_server(agent)

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[DataTransformer] Starting uvicorn server on 0.0.0.0:{AGENT_PORT}")
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
