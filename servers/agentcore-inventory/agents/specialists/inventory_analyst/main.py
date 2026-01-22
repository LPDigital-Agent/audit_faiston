"""
InventoryAnalyst - File Structure Analysis Specialist Agent.

This agent inspects uploaded CSV/Excel files to extract their structure
(columns, sample data, format, encoding) without loading full content.

Protocol: A2A (JSON-RPC 2.0)
Agent ID: faiston_inventory_analyst
Port: 9001
Memory: STM_ONLY
Model: Gemini 2.5 Flash

Persona: Technical Data Engineer
    - Extracts metadata ONLY
    - Does NOT interpret business meaning
    - Does NOT suggest column mappings
    - Returns raw technical facts
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from strands import Agent, tool
from shared.hooks import DebugHook, LoggingHook, MetricsHook, SecurityAuditHook
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from agents.tools.analysis_tools import get_file_structure, validate_file_columns
from agents.utils import create_gemini_model

# AUDIT-028: Cognitive Error Handler for enriched error responses
from shared.cognitive_error_handler import cognitive_sync_handler, CognitiveError
from shared.debug_utils import debug_error

# Note: FileAnalystResponse exists in shared.agent_schemas but not used here
# because this agent returns raw tool JSON output (Technical Data Engineer persona)
# The schema is available for downstream processing if needed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

AGENT_ID = "faiston_inventory_analyst"
AGENT_NAME = "InventoryAnalyst"
RUNTIME_ID = "faiston_inventory_analyst-0uGg1W8ITM"  # From a2a_client.py PROD_RUNTIME_IDS
AGENT_DESCRIPTION = """
Technical Data Engineer specialized in file parsing and metadata extraction.
Inspects CSV/Excel file structures without loading full content.
Extracts column names, sample data, formats, and encodings.
Does NOT interpret business meaning - returns raw technical facts only.
"""

AGENT_PORT = 9001

# System prompt for the agent
SYSTEM_PROMPT = """You are a **Technical Data Engineer** specialized in file parsing and metadata extraction.
Your ONLY role is to inspect the raw structure of CSV/Excel files and report technical facts.

## Capabilities

1. Extract column names exactly as they appear (preserving accents/symbols).
2. Detect technical formats (CSV vs Excel) and delimiters (semicolon vs comma vs tab).
3. Report sample rows without modification.
4. Estimate row counts based on file size.
5. Detect encoding (UTF-8 or Latin-1).
6. Detect whether the file has a header row.

## Rules (CRITICAL)

- DO NOT interpret what the data means (e.g., do not infer that "qtd" is "physical quantity").
- DO NOT attempt to validate business rules.
- DO NOT suggest column mappings or business interpretations.
- DO NOT make assumptions about data quality or correctness.
- Output MUST be valid JSON structure from the tools.
- NEVER load full file contents - only use the provided tools.
- ONLY use the `get_file_structure` and `validate_file_columns` tools.

## Response Format

When analyzing a file, return ONLY the technical metadata from the tool output.
Format your response as a structured summary:

```
File Analysis Results:
- Format: [detected_format]
- Encoding: [encoding]
- Has Header: [yes/no]
- Columns: [list of column names]
- Estimated Rows: [row_count_estimate]
- Sample Data: [first 3 rows]
```

If analysis fails, return the error structure from the tool with no interpretation.

## Error Handling (CRITICAL - BUG-040 FIX)

When ANY tool returns an error (success=false), you MUST:
- Return the EXACT JSON from the tool as your response
- DO NOT generate apologies or conversational language
- DO NOT use phrases like: "Desculpe", "não consegui", "infelizmente", "houve um erro"
- DO NOT explain or interpret the error

Example - Tool returns error:
```
Tool output: {"success": false, "error": "File not found: s3://bucket/key", "error_type": "FILE_NOT_FOUND"}

Your response MUST be:
{"success": false, "error": "File not found: s3://bucket/key", "error_type": "FILE_NOT_FOUND"}

Your response MUST NOT be:
"Desculpe, não consegui obter a estrutura do arquivo. O sistema encontrou dificuldades técnicas..."
```

## Example Interaction

User: "Analyze the file at temp/uploads/abc123_inventory.csv"

You should:
1. Call get_file_structure with s3_key="temp/uploads/abc123_inventory.csv"
2. Return the technical results without interpretation

NEVER say things like "This appears to be an inventory file" or "The 'codigo' column likely represents product codes".
Just report what you see, factually.
"""

# Agent skills for A2A discovery
AGENT_SKILLS: List[AgentSkill] = [
    AgentSkill(
        id="analyze_file_structure",
        name="Analisar Estrutura de Arquivo",
        description=(
            "Inspect uploaded CSV/Excel file structure without loading full content. "
            "Returns columns, sample data, format, encoding, and estimated row count."
        ),
        tags=["inventory", "file", "analysis", "csv", "excel", "parsing"],
    ),
    AgentSkill(
        id="validate_columns",
        name="Validar Colunas do Arquivo",
        description=(
            "Validate that a file contains required columns for inventory processing. "
            "Uses case-insensitive matching."
        ),
        tags=["inventory", "validation", "columns", "schema"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Monitor agent health and configuration.",
        tags=["monitoring", "health", "status"],
    ),
]


# =============================================================================
# HEALTH CHECK TOOL
# =============================================================================

@tool
def health_check() -> str:
    """
    Check agent health and return status information.

    Returns:
        JSON string with health status:
        {
            "status": "healthy",
            "agent_id": "faiston_inventory_analyst",
            "agent_name": "InventoryAnalyst",
            "version": "2026-01-21",
            "capabilities": ["file_structure_analysis", "column_validation"]
        }
    """
    return json.dumps(
        {
            "status": "healthy",
            "agent_id": AGENT_ID,
            "agent_name": AGENT_NAME,
            "version": "2026-01-21",
            "phase": "2-smart-parsing",
            "capabilities": [
                "file_structure_analysis",
                "column_validation",
                "csv_parsing",
                "excel_parsing",
                "encoding_detection",
                "header_detection",
            ],
            "supported_formats": ["csv", "csv_semicolon", "csv_tab", "xlsx", "xls"],
            "max_file_size_mb": 500,
        }
    )


# =============================================================================
# AGENT CREATION
# =============================================================================

def create_agent() -> Agent:
    """
    Create and configure the InventoryAnalyst agent.

    Returns:
        Configured Strands Agent instance with:
        - Gemini 2.5 Flash model
        - File analysis tools
        - Logging, metrics, and debug hooks
        - Technical Data Engineer persona
    """
    logger.info(f"Creating {AGENT_NAME} agent with ID: {AGENT_ID}")

    # Create model (Gemini 2.5 Flash for speed)
    model = create_gemini_model(AGENT_ID)

    # Define tools
    tools = [
        get_file_structure,
        validate_file_columns,
        health_check,
    ]

    # Create agent with hooks
    agent = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        hooks=[
            LoggingHook(),
            MetricsHook(),
            DebugHook(timeout_seconds=30.0),  # 30s timeout for file analysis (standardized)
            SecurityAuditHook(enabled=True),  # FAIL-CLOSED audit trail
        ],
    )

    logger.info(f"{AGENT_NAME} agent created successfully")
    return agent


# =============================================================================
# A2A SERVER
# =============================================================================

def create_a2a_server(agent: Agent) -> A2AServer:
    """
    Create A2A server for agent-to-agent communication.

    Args:
        agent: The Strands Agent to wrap.

    Returns:
        Configured A2AServer instance with:
        - Agent card for discovery
        - Skills metadata
        - Health endpoint
    """
    server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=AGENT_PORT,
        version="2026-01-21",
        skills=AGENT_SKILLS,
        serve_at_root=False,  # Mount at root below
    )

    logger.info(f"A2A server created for {AGENT_NAME} on port {AGENT_PORT}")
    return server


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    """
    Main entry point for the InventoryAnalyst agent.

    Starts the A2A server and listens for requests.
    Used by AgentCore runtime for deployment.
    """
    # Import FastAPI and uvicorn here to avoid circular imports
    from fastapi import FastAPI
    import uvicorn

    logger.info(f"Starting {AGENT_NAME} agent...")
    logger.info(f"Agent ID: {AGENT_ID}")
    logger.info(f"Port: {AGENT_PORT}")
    logger.info(f"Memory Mode: STM_ONLY")

    # Log environment
    logger.info(f"AWS_REGION: {os.environ.get('AWS_REGION', 'not set')}")
    logger.info(f"DOCUMENTS_BUCKET: {os.environ.get('DOCUMENTS_BUCKET', 'not set')}")

    # Create FastAPI app
    app = FastAPI(title=AGENT_NAME, version="2026-01-21")

    # Add /ping health endpoint for AWS ALB
    @app.get("/ping")
    async def ping():
        """Health check endpoint for AWS Application Load Balancer."""
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": "2026-01-21",
        }

    # Create agent and A2A server
    agent = create_agent()
    a2a_server = create_a2a_server(agent)

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"Starting uvicorn server on 0.0.0.0:{AGENT_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)


if __name__ == "__main__":
    main()
