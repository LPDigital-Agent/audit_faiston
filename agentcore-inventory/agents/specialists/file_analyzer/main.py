# =============================================================================
# FileAnalyzer A2A Agent - Strands A2AServer Entry Point
# =============================================================================
# BUG-025 FIX: Specialist agent for file analysis with Pydantic structured output.
#
# This agent replaces the direct google.genai SDK usage in gemini_text_analyzer.py
# with proper Strands Agent + structured_output_model enforcement.
#
# Architecture:
# - Uses Strands Agent with GeminiModel (Gemini 2.5 Pro + Thinking)
# - A2A Protocol for inter-agent communication
# - Pydantic schemas for structured output enforcement
# - Tools for S3 file reading (Python = Hands)
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/structured-output/
# =============================================================================

import os
import sys
import logging
import json
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# A2A Protocol Types for Agent Card Discovery (100% A2A Architecture)
from a2a.types import AgentSkill

# Centralized model configuration (MANDATORY - Gemini 2.5 Pro + Thinking)
from agents.utils import AGENT_VERSION, create_gemini_model

# BUG-027 FIX: Import hooks for error enrichment
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# Local imports (ABSOLUTE - required for AgentCore direct execution)
# BUG-028 FIX: Relative imports fail when AgentCore runs main.py directly
# because Python doesn't recognize file_analyzer as a package.
# Pattern follows official Strands Agents samples.
from agents.specialists.file_analyzer.schemas import InventoryAnalysisResponse
from agents.specialists.file_analyzer.prompts import get_file_analyzer_prompt
from agents.specialists.file_analyzer.tools.file_reader import read_file_from_s3, get_column_statistics
from agents.specialists.file_analyzer.utils import (
    recover_partial_response,
    format_file_content_for_llm,
    build_analysis_prompt,
    validate_analysis_response,
)
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

AGENT_ID = "file_analyzer"
AGENT_NAME = "FileAnalyzer"
AGENT_DESCRIPTION = """FileAnalyzer A2A Agent - Intelligent file analysis specialist.

BUG-025 FIX: This agent provides structured file analysis with Pydantic enforcement,
replacing the direct SDK calls that caused incomplete question responses.

Capabilities:
1. ANALYZE: Parse CSV, XLSX, XLS files from S3
2. DETECT: Identify column types, patterns, and data quality
3. MAP: Suggest column-to-database field mappings with confidence scores
4. ASK: Generate Human-in-the-Loop (HIL) questions for ambiguous mappings
5. VALIDATE: Enforce structured output via Pydantic schemas

Follows CLAUDE.md principles:
- LLM = Brain (reasoning, decisions, mappings)
- Python = Hands (file parsing, validation, S3 I/O)
"""

# =============================================================================
# A2A Agent Skills (100% A2A Architecture - Agent Card Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="analyze_file",
        name="Analyze File",
        description="Analyze file structure from S3, detect columns, suggest mappings, "
                    "and generate HIL questions for ambiguous cases.",
        tags=["file_analyzer", "analysis", "mappings", "hil"],
    ),
    AgentSkill(
        id="continue_analysis",
        name="Continue Analysis",
        description="Continue analysis with user responses from previous round. "
                    "Updates mappings based on HIL answers.",
        tags=["file_analyzer", "hil", "round2"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Health check endpoint returning agent status and version.",
        tags=["file_analyzer", "monitoring", "health"],
    ),
]

# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = get_file_analyzer_prompt(analysis_round=1)

# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================


@tool
def analyze_file_content(
    s3_key: str,
    filename: Optional[str] = None,
    bucket: str = "faiston-one-sga-documents-prod",
    max_rows: int = 100,
) -> Dict[str, Any]:
    """
    Read and prepare file content for LLM analysis.

    This tool handles the Python/Hands side:
    - Read file from S3
    - Parse CSV/XLSX/XLS format
    - Extract headers and sample rows
    - Calculate column statistics

    The LLM will analyze the structured data and generate mappings.

    Args:
        s3_key: S3 key where file is stored
        filename: Original filename for type detection (optional)
        bucket: S3 bucket name
        max_rows: Maximum rows to read for analysis

    Returns:
        Dict with file content, headers, sample rows, and statistics
    """
    logger.info(f"[{AGENT_NAME}] Reading file from S3: {s3_key}")

    try:
        # Read file from S3
        file_data = read_file_from_s3(
            s3_key=s3_key,
            bucket=bucket,
            max_rows=max_rows,
        )

        if not file_data.get("success"):
            return {
                "success": False,
                "error": file_data.get("error", "Failed to read file"),
                "file_type": file_data.get("file_type", "unknown"),
            }

        # Get column statistics
        stats = {}
        if file_data.get("headers") and file_data.get("rows"):
            stats = get_column_statistics(
                rows=file_data["rows"],
                headers=file_data["headers"],
            )

        # Format content for LLM
        formatted_content = format_file_content_for_llm(
            headers=file_data["headers"],
            rows=file_data["rows"],
            max_rows=20,  # Show more rows for better analysis
            max_value_length=150,
        )

        logger.info(
            f"[{AGENT_NAME}] File parsed: {file_data['column_count']} columns, "
            f"{file_data['row_count']} rows"
        )

        return {
            "success": True,
            "file_type": file_data["file_type"],
            "headers": file_data["headers"],
            "row_count": file_data["row_count"],
            "column_count": file_data["column_count"],
            "formatted_content": formatted_content,
            "column_statistics": stats,
            "sample_rows": file_data["rows"][:10],  # First 10 for preview
            "sheets": file_data.get("sheets"),  # For Excel files
            "active_sheet": file_data.get("active_sheet"),
        }

    except Exception as e:
        debug_error(e, "file_analyzer_analyze_content", {"s3_key": s3_key, "filename": filename})
        return {
            "success": False,
            "error": str(e),
            "file_type": "unknown",
        }


@tool
def health_check() -> Dict[str, Any]:
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
        "protocol": "A2A",
        "port": 9000,  # A2A standard port (BUG-029 FIX)
    }


# =============================================================================
# Strands Agent Configuration with Structured Output
# =============================================================================

def create_agent() -> Agent:
    """
    Create Strands Agent with structured output enforcement.

    BUG-025 FIX: Uses structured_output_model to ensure Pydantic validation
    of all responses. This prevents incomplete/malformed JSON that caused
    the original question loss bug.

    Returns:
        Configured Strands Agent with structured output
    """
    return Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # GeminiModel via Google AI Studio
        tools=[
            analyze_file_content,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        # BUG-025 FIX: Enforce Pydantic structured output
        # This ensures ALL responses match InventoryAnalysisResponse schema
        structured_output_model=InventoryAnalysisResponse,
        # BUG-027 FIX: Add hooks for logging, metrics, and error enrichment
        # DebugHook intercepts errors and sends to Debug Agent for analysis
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
    )


# =============================================================================
# Custom A2A Handler for Analysis with Context
# =============================================================================

class FileAnalyzerHandler:
    """
    Custom handler for FileAnalyzer A2A messages.

    Handles multi-round analysis with user responses and memory context.
    """

    def __init__(self, agent: Agent):
        self.agent = agent
        self._current_round = 1

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming A2A message.

        Args:
            message: A2A message with action and parameters

        Returns:
            Analysis result as InventoryAnalysisResponse
        """
        action = message.get("action", "analyze_file")
        logger.info(f"[{AGENT_NAME}] Handling action: {action}")

        try:
            if action == "analyze_file":
                return await self._handle_analyze(message)
            elif action == "continue_analysis":
                return await self._handle_continue(message)
            elif action == "health_check":
                return health_check()
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "file_type": "unknown",
                    "analysis_confidence": 0.0,
                    "analysis_round": 1,
                    "row_count": 0,
                    "column_count": 0,
                    "columns": [],
                    "suggested_mappings": {},
                    "unmapped_columns": [],
                    "hil_questions": [],
                    "unmapped_questions": [],
                    "all_questions_answered": False,
                    "ready_for_import": False,
                    "recommended_action": "error",
                }

        except Exception as e:
            debug_error(e, "file_analyzer_handler", {"action": action})
            return {
                "success": False,
                "error": str(e),
                "file_type": "unknown",
                "analysis_confidence": 0.0,
                "analysis_round": self._current_round,
                "row_count": 0,
                "column_count": 0,
                "columns": [],
                "suggested_mappings": {},
                "unmapped_columns": [],
                "hil_questions": [],
                "unmapped_questions": [],
                "all_questions_answered": False,
                "ready_for_import": False,
                "recommended_action": "error",
            }

    async def _handle_analyze(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle initial file analysis request.

        Args:
            message: A2A message with s3_key, filename, etc.

        Returns:
            Analysis result
        """
        s3_key = message.get("s3_key")
        filename = message.get("filename")
        schema_context = message.get("schema_context")
        memory_context = message.get("memory_context")

        if not s3_key:
            return {
                "success": False,
                "error": "Missing required parameter: s3_key",
                "file_type": "unknown",
                "analysis_confidence": 0.0,
                "analysis_round": 1,
                "row_count": 0,
                "column_count": 0,
                "columns": [],
                "suggested_mappings": {},
                "unmapped_columns": [],
                "hil_questions": [],
                "unmapped_questions": [],
                "all_questions_answered": False,
                "ready_for_import": False,
                "recommended_action": "error",
            }

        self._current_round = 1

        # Build prompt with context
        prompt = get_file_analyzer_prompt(
            analysis_round=1,
            schema_context=schema_context,
            memory_context=memory_context,
        )

        # Call agent with file analysis request
        logger.info(f"[{AGENT_NAME}] Starting Round 1 analysis for {filename or s3_key}")

        try:
            # The agent will call analyze_file_content tool and then reason about mappings
            result = self.agent(
                f"Analyze the file at S3 key '{s3_key}' (filename: {filename}). "
                f"Call analyze_file_content first, then analyze the columns and "
                f"generate structured output with mappings and HIL questions."
            )

            # BUG-025: Log question counts for debugging
            if hasattr(result, 'structured_output') and result.structured_output:
                analysis = result.structured_output
                logger.info(
                    f"[BUG-025 DEBUG] FileAnalyzer output: "
                    f"hil_questions={len(analysis.hil_questions)}, "
                    f"unmapped_questions={len(analysis.unmapped_questions)}"
                )
                return analysis.model_dump()

            # Fallback: Try to parse response as JSON
            logger.warning("[BUG-025] No structured_output, attempting recovery...")
            if hasattr(result, 'message') and result.message:
                recovered = recover_partial_response(result.message)
                if recovered:
                    # Validate and return
                    is_valid, errors = validate_analysis_response(recovered)
                    if is_valid:
                        recovered["debug_partial_recovery"] = True
                        return recovered
                    else:
                        logger.warning(f"[BUG-025] Recovered JSON invalid: {errors}")

            # Return error response
            return {
                "success": False,
                "error": "Failed to generate structured analysis",
                "file_type": "unknown",
                "analysis_confidence": 0.0,
                "analysis_round": 1,
                "row_count": 0,
                "column_count": 0,
                "columns": [],
                "suggested_mappings": {},
                "unmapped_columns": [],
                "hil_questions": [],
                "unmapped_questions": [],
                "all_questions_answered": False,
                "ready_for_import": False,
                "recommended_action": "error",
            }

        except Exception as e:
            debug_error(e, "file_analyzer_analysis", {"s3_key": s3_key, "filename": filename})
            raise

    async def _handle_continue(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle continuation with user responses.

        Args:
            message: A2A message with user_responses from previous round

        Returns:
            Updated analysis result
        """
        s3_key = message.get("s3_key")
        filename = message.get("filename")
        user_responses = message.get("user_responses", {})
        analysis_round = message.get("analysis_round", 2)
        schema_context = message.get("schema_context")
        memory_context = message.get("memory_context")

        self._current_round = analysis_round

        # Build prompt with user responses
        prompt = get_file_analyzer_prompt(
            analysis_round=analysis_round,
            user_responses=json.dumps(user_responses, ensure_ascii=False),
            schema_context=schema_context,
            memory_context=memory_context,
        )

        logger.info(
            f"[{AGENT_NAME}] Starting Round {analysis_round} analysis with "
            f"{len(user_responses)} user responses"
        )

        try:
            result = self.agent(
                f"Continue analysis for file '{filename or s3_key}' with user responses. "
                f"User responses: {json.dumps(user_responses, ensure_ascii=False)}. "
                f"Update mappings based on these responses and generate new questions if needed."
            )

            if hasattr(result, 'structured_output') and result.structured_output:
                analysis = result.structured_output
                logger.info(
                    f"[BUG-025 DEBUG] FileAnalyzer Round {analysis_round} output: "
                    f"hil_questions={len(analysis.hil_questions)}, "
                    f"ready_for_import={analysis.ready_for_import}"
                )
                return analysis.model_dump()

            # Fallback recovery
            if hasattr(result, 'message') and result.message:
                recovered = recover_partial_response(result.message)
                if recovered:
                    recovered["debug_partial_recovery"] = True
                    return recovered

            return {
                "success": False,
                "error": "Failed to continue analysis",
                "file_type": "unknown",
                "analysis_confidence": 0.0,
                "analysis_round": analysis_round,
                "row_count": 0,
                "column_count": 0,
                "columns": [],
                "suggested_mappings": {},
                "unmapped_columns": [],
                "hil_questions": [],
                "unmapped_questions": [],
                "all_questions_answered": False,
                "ready_for_import": False,
                "recommended_action": "error",
            }

        except Exception as e:
            debug_error(e, "file_analyzer_continue", {"s3_key": s3_key, "analysis_round": analysis_round})
            raise


# =============================================================================
# A2A Request Processing (BUG-030 FIX)
# =============================================================================


def process_file_analysis_request(
    agent: Agent,
    request: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a file analysis request and return structured JSON output.

    BUG-030 FIX: This function extracts structured_output.model_dump() from the
    agent result, ensuring clean JSON is returned to the orchestrator instead of
    raw Gemini conversation text (which includes "thinking" output).

    Args:
        agent: The Strands Agent instance
        request: A2A request with action and parameters

    Returns:
        InventoryAnalysisResponse as dict (clean JSON)
    """
    action = request.get("action", "analyze_file")
    s3_key = request.get("s3_key")
    filename = request.get("filename")
    schema_context = request.get("schema_context")
    memory_context = request.get("memory_context")
    analysis_round = request.get("analysis_round", 1)
    user_responses = request.get("user_responses", {})

    logger.info(
        f"[{AGENT_NAME}] Processing request: action={action}, "
        f"s3_key={s3_key}, round={analysis_round}"
    )

    # Validate required parameters
    if not s3_key and action != "health_check":
        debug_error(ValueError("Missing required parameter: s3_key"), "file_analyzer_validate", {"action": action})
        return {
            "success": False,
            "error": "Missing required parameter: s3_key",
            "file_type": "unknown",
            "analysis_confidence": 0.0,
            "analysis_round": analysis_round,
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "suggested_mappings": {},
            "unmapped_columns": [],
            "hil_questions": [],
            "unmapped_questions": [],
            "all_questions_answered": False,
            "ready_for_import": False,
            "recommended_action": "error",
        }

    # Handle health check
    if action == "health_check":
        return health_check()

    try:
        # Build prompt based on action
        if action == "continue_analysis" and user_responses:
            prompt = (
                f"Continue analysis for file '{filename or s3_key}' with user responses. "
                f"User responses: {json.dumps(user_responses, ensure_ascii=False)}. "
                f"Update mappings based on these responses and generate new questions if needed."
            )
        else:
            prompt = (
                f"Analyze the file at S3 key '{s3_key}' (filename: {filename}). "
                f"Call analyze_file_content first, then analyze the columns and "
                f"generate structured output with mappings and HIL questions."
            )

        # Add context if provided
        if schema_context:
            prompt += f"\n\nSchema context: {schema_context}"
        if memory_context:
            prompt += f"\n\nMemory context: {memory_context}"

        logger.info(f"[{AGENT_NAME}] Invoking agent for round {analysis_round}...")

        # Invoke agent - structured_output_model ensures Pydantic validation
        result = agent(prompt)

        # BUG-030 FIX: Extract structured output (NOT raw conversation text)
        if hasattr(result, "structured_output") and result.structured_output:
            analysis = result.structured_output
            response = analysis.model_dump()

            logger.info(
                f"[BUG-030 FIX] Extracted structured output: "
                f"success={response.get('success')}, "
                f"hil_questions={len(response.get('hil_questions', []))}, "
                f"ready_for_import={response.get('ready_for_import')}"
            )
            return response

        # Fallback: Try to recover from text response
        logger.warning(f"[{AGENT_NAME}] No structured_output, attempting recovery...")
        if hasattr(result, "message") and result.message:
            recovered = recover_partial_response(result.message)
            if recovered:
                is_valid, errors = validate_analysis_response(recovered)
                if is_valid:
                    recovered["debug_partial_recovery"] = True
                    logger.info(f"[{AGENT_NAME}] Recovered valid JSON from text response")
                    return recovered
                else:
                    logger.warning(f"[{AGENT_NAME}] Recovered JSON invalid: {errors}")

        # Return error response if all else fails
        debug_error(Exception("Failed to extract structured output"), "file_analyzer_structured_output", {"s3_key": s3_key})
        return {
            "success": False,
            "error": "Failed to generate structured analysis",
            "file_type": "unknown",
            "analysis_confidence": 0.0,
            "analysis_round": analysis_round,
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "suggested_mappings": {},
            "unmapped_columns": [],
            "hil_questions": [],
            "unmapped_questions": [],
            "all_questions_answered": False,
            "ready_for_import": False,
            "recommended_action": "error",
        }

    except Exception as e:
        debug_error(e, "file_analyzer_request_processing", {"s3_key": s3_key, "action": action})
        return {
            "success": False,
            "error": str(e),
            "file_type": "unknown",
            "analysis_confidence": 0.0,
            "analysis_round": analysis_round,
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "suggested_mappings": {},
            "unmapped_columns": [],
            "hil_questions": [],
            "unmapped_questions": [],
            "all_questions_answered": False,
            "ready_for_import": False,
            "recommended_action": "error",
        }


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with 100% A2A Architecture.

    Port 9000 is the A2A standard port (BUG-029 FIX).
    Agent Card is served at /.well-known/agent-card.json for discovery.

    BUG-030 FIX: Custom message handler extracts structured_output.model_dump()
    instead of returning raw Gemini conversation text.

    IMPORTANT: Uses FastAPI wrapper with /ping endpoint for AgentCore health checks.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Skills: {[s.id for s in AGENT_SKILLS]}")
    logger.info(f"[{AGENT_NAME}] Agent Card: GET /.well-known/agent-card.json")

    # Create FastAPI app FIRST for immediate health check response
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    @app.get("/ping")
    def ping():
        """Health check endpoint - responds immediately for AgentCore cold start."""
        return {"status": "healthy", "agent": AGENT_ID, "version": AGENT_VERSION}

    logger.info(f"[{AGENT_NAME}] Health check endpoint ready: GET /ping")

    # Create agent (uses LazyGeminiModel for deferred initialization)
    agent = create_agent()

    # =========================================================================
    # BUG-030 FIX: Custom A2A message handler with structured output extraction
    # =========================================================================
    # The default A2AServer.to_fastapi_app() returns raw agent conversation text
    # which includes Gemini's "thinking" output. This custom handler extracts
    # ONLY the structured_output.model_dump() for clean JSON responses.
    # =========================================================================

    @app.post("/")
    async def handle_a2a_message(request: Request):
        """
        Custom A2A message handler with structured output extraction.

        BUG-030 FIX: Extracts structured_output from agent result instead of
        returning raw conversation text that includes Gemini's thinking output.
        """
        try:
            body = await request.json()
            logger.info(f"[{AGENT_NAME}] Received A2A request: {json.dumps(body)[:500]}")

            # Validate JSON-RPC 2.0 format
            if body.get("jsonrpc") != "2.0":
                return {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32600, "message": "Invalid Request: not JSON-RPC 2.0"},
                }

            method = body.get("method", "")
            request_id = body.get("id", "unknown")

            # Handle message/send method (A2A Protocol)
            if method == "message/send":
                params = body.get("params", {})
                message = params.get("message", {})
                parts = message.get("parts", [])

                # Extract text from message parts
                text_content = ""
                for part in parts:
                    if part.get("kind") == "text":
                        text_content += part.get("text", "")

                # Try to parse as JSON payload (orchestrator sends JSON in text)
                payload = {}
                if text_content:
                    try:
                        payload = json.loads(text_content)
                    except json.JSONDecodeError:
                        # Not JSON, use as prompt directly
                        payload = {"prompt": text_content}

                # Process the file analysis request
                result = process_file_analysis_request(agent, payload)

                # Return A2A JSON-RPC response with structured output
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "message": {
                            "role": "assistant",
                            "parts": [
                                {
                                    "kind": "text",
                                    "text": json.dumps(result, ensure_ascii=False),
                                }
                            ],
                        },
                    },
                }

            # Unknown method
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        except Exception as e:
            debug_error(e, "file_analyzer_a2a_handler", {})
            return {
                "jsonrpc": "2.0",
                "id": body.get("id") if "body" in dir() else "unknown",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            }

    # Create A2A server for Agent Card discovery only (NOT message handling)
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,  # A2A standard port (BUG-029 FIX)
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
        serve_at_root=False,  # Don't serve at root - we have custom handler
    )

    # Mount A2A server for /.well-known/agent-card.json discovery
    a2a_app = a2a_server.to_fastapi_app()
    app.mount("/.well-known", a2a_app)

    logger.info(f"[{AGENT_NAME}] BUG-030 FIX: Custom A2A handler with structured output extraction")
    logger.info(f"[{AGENT_NAME}] A2A server mounted, starting uvicorn...")

    # Start uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=9000)  # A2A standard port (BUG-029 FIX)


if __name__ == "__main__":
    main()
