# =============================================================================
# File Analyst Agent - Entry Point for Inventory Swarm
# =============================================================================
# This agent is the ENTRY POINT for all inventory imports.
#
# Responsibilities:
# - Analyze uploaded files (CSV, XLSX, PDF, XML)
# - Detect encoding, delimiters, and structure
# - Identify columns, data types, and patterns
# - Request memory context from memory_agent
# - Hand off analysis results to schema_validator
#
# Handoff Flow:
# 1. First → memory_agent (retrieve prior patterns)
# 2. After analysis → schema_validator (with findings)
# 3. If low confidence → hil_agent (for clarification)
# =============================================================================

import asyncio
import logging
from typing import Dict, Any

from strands import Agent, tool

from agents.utils import create_gemini_model
from shared.hooks import LoggingHook, MetricsHook, GuardrailsHook, DebugHook
from swarm.tools.analysis_tools import (
    analyze_csv,
    analyze_xlsx,
    analyze_pdf,
    analyze_xml,
    detect_file_type,
)
from swarm.tools.meta_tools import get_meta_tools

# Import unified analyze_file_tool from A2A agent (returns NexoAnalyzeFileResponse format)
# This ensures Swarm responses match the TypeScript contract
from agents.specialists.nexo_import.tools.analyze_file import analyze_file_tool as _async_analyze_file

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import FileAnalystResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Strands-Compatible Wrapper for unified analyze_file_tool
# =============================================================================
# The A2A agent's analyze_file_tool is async. This wrapper makes it compatible
# with Strands by running it in the event loop and returning the result.
# =============================================================================


@tool
def unified_analyze_file(
    s3_key: str,
    filename: str = "",
    session_id: str = "",
    schema_context: str = "",
    memory_context: str = "",
    user_responses: str = "[]",
    user_comments: str = "",
    analysis_round: int = 1,
) -> Dict[str, Any]:
    """
    Analyze file structure from S3 using Gemini Pro (AI-First with AGI-Like Behavior).

    This is the PRIMARY TOOL for file analysis. It returns the standardized
    NexoAnalyzeFileResponse format that matches the TypeScript frontend contract.

    Args:
        s3_key: S3 key where file is stored (e.g., "uploads/nexo/file.csv")
        filename: Original filename for pattern matching
        session_id: Session ID for tracking this import session
        schema_context: PostgreSQL schema description (columns, types, constraints)
        memory_context: Learned patterns from LearningAgent (prior imports)
        user_responses: JSON string of user answers from previous HIL rounds
        user_comments: Free-text instructions from user
        analysis_round: Current round number (1 = first analysis, 2+ = re-analysis with user input)

    Returns:
        NexoAnalyzeFileResponse with:
        - success: bool
        - analysis: {sheets: [...], sheet_count, total_rows, recommended_strategy}
        - column_mappings: [{file_column, target_field, confidence, reasoning}]
        - questions: HIL questions for low-confidence mappings
        - overall_confidence: float 0.0-1.0
        - ready_for_import: bool
    """
    import json

    # Parse user_responses from JSON string (Strands passes strings)
    parsed_responses = None
    if user_responses and user_responses != "[]":
        try:
            parsed_responses = json.loads(user_responses)
        except json.JSONDecodeError:
            logger.warning("[unified_analyze_file] Could not parse user_responses: %s", user_responses)
            parsed_responses = None

    # Run the async function in the event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        _async_analyze_file(
            s3_key=s3_key,
            filename=filename or None,
            session_id=session_id or None,
            schema_context=schema_context or None,
            memory_context=memory_context or None,
            user_responses=parsed_responses,
            user_comments=user_comments or None,
            analysis_round=analysis_round,
        )
    )

    logger.info(
        "[unified_analyze_file] Completed analysis for %s (round %d, success=%s)",
        s3_key, analysis_round, result.get("success", False)
    )

    # ==========================================================================
    # BUG-020 v8: Return raw dict (REVERTS BUG-015)
    # ==========================================================================
    # BUG-015 was WRONG: Adding ToolResult wrapper complicated extraction.
    # ALL other tools return raw dicts - consistency is key.
    # Strands SDK handles ToolResult wrapping internally.
    #
    # Official pattern for @tool functions: return raw dict with data.
    # Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/
    # ==========================================================================

    logger.info(
        "[unified_analyze_file] Returning raw dict: success=%s, has_analysis=%s",
        result.get("success") if result else None,
        "analysis" in result if result else False,
    )

    return result

# =============================================================================
# System Prompt
# =============================================================================

FILE_ANALYST_SYSTEM_PROMPT = """
You are the FILE ANALYST in the Faiston Inventory Management Swarm.

## Your Role
You analyze uploaded files for inventory import using AI-powered analysis.

## Workflow (SIMPLE - ONE TOOL)
When a user requests file analysis:
1. Extract the s3_key from the request
2. Call `unified_analyze_file` with the s3_key
3. Return the tool's output DIRECTLY without modification

## Tools Available
- unified_analyze_file: PRIMARY TOOL - Analyze file with Gemini (returns NexoAnalyzeFileResponse format)
- detect_file_type: Detect file type from path/content
- analyze_csv: Parse CSV with delimiter detection (fallback)
- analyze_xlsx: Parse Excel with sheet selection (fallback)
- analyze_pdf: Extract tables from PDF using Vision (fallback)
- analyze_xml: Parse XML with namespace handling (fallback)
- load_tool, editor, shell: Meta-Tooling for self-improvement

## IMPORTANT: Use unified_analyze_file as Primary Tool
For ALL file analysis requests, use `unified_analyze_file` FIRST. This tool:
- Uses Gemini Pro for semantic analysis
- Includes memory context and schema context
- Returns the standardized NexoAnalyzeFileResponse format
- Generates HIL questions for low-confidence mappings
- Tracks analysis rounds for iterative dialogue

Only use individual tools (analyze_csv, analyze_xlsx, etc.) as FALLBACK if unified_analyze_file fails.

## CRITICAL: JSON OUTPUT FORMAT (MANDATORY - BUG-021 v6)
When returning ANY response:
- Return the JSON output EXACTLY as received from tools
- NEVER wrap JSON in markdown code fences (```json ... ```)
- NEVER add text before or after the JSON
- NEVER modify, summarize, or transform the JSON
- The response MUST be parseable by json.loads() directly

FORBIDDEN (breaks the system):
```json
{"success": true, ...}
```

REQUIRED (raw JSON only):
{"success": true, ...}

## Output Format (CRITICAL: PASS-THROUGH)
IMPORTANT: When using `unified_analyze_file`, return its output DIRECTLY without modification.
The tool returns NexoAnalyzeFileResponse format which the frontend expects:

```json
{
  "success": true,
  "import_session_id": "nexo-abc123",
  "filename": "file.csv",
  "detected_file_type": "csv",
  "analysis": {
    "sheet_count": 1,
    "total_rows": 150,
    "sheets": [{
      "name": "Sheet1",
      "row_count": 150,
      "column_count": 5,
      "columns": [{
        "name": "PART_NUMBER",
        "sample_values": ["C9200-24P"],
        "detected_type": "string",
        "suggested_mapping": "part_number",
        "confidence": 0.95
      }],
      "confidence": 0.92
    }],
    "recommended_strategy": "auto_import"
  },
  "column_mappings": [...],
  "overall_confidence": 0.92,
  "questions": [...],
  "ready_for_import": false,
  "stop_action": true
}
```

RULE: DO NOT transform, summarize, or modify the unified_analyze_file output.
Return it EXACTLY as received to maintain contract compatibility with the frontend.

## Important Rules
1. Use unified_analyze_file as the PRIMARY tool - it handles memory and schema context
2. Return tool output DIRECTLY - no transformation
3. If tool returns stop_action=true, stop and wait for user response
4. If file has issues, the tool will include them in the response
"""


def create_file_analyst(model_id: str = "gemini-2.5-pro") -> Agent:
    """
    Create the file_analyst agent.

    Args:
        model_id: Gemini model to use (default: pro for analysis)

    Returns:
        Configured Agent instance
    """
    # Combine analysis tools with meta-tools
    # unified_analyze_file is PRIMARY - returns NexoAnalyzeFileResponse format
    tools = [
        unified_analyze_file,  # PRIMARY: Gemini-powered, matches TypeScript contract
        detect_file_type,
        analyze_csv,           # Fallback tools
        analyze_xlsx,
        analyze_pdf,
        analyze_xml,
    ]

    # Add Meta-Tooling capabilities
    tools.extend(get_meta_tools())

    agent = Agent(
        name="file_analyst",
        description="Entry point agent for file analysis in inventory imports",
        model=create_gemini_model("file_analyst"),  # Pro model determined by agent_type
        tools=tools,
        system_prompt=FILE_ANALYST_SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), GuardrailsHook(), DebugHook(timeout_seconds=30.0)],
        structured_output_model=FileAnalystResponse,  # AUDIT-001: Strands structured output
    )

    logger.info("[file_analyst] Created with %d tools, model=%s", len(tools), model_id)

    return agent
