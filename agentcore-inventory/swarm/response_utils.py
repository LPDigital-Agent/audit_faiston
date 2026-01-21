# =============================================================================
# Swarm Response Extraction Utilities (BUG-019 + BUG-020 v12)
# =============================================================================
# Infrastructure code for extracting structured data from Strands Swarm results.
#
# Official Strands AgentResult structure (SDK v1.20.0):
# @dataclass
# class AgentResult:
#     stop_reason: StopReason
#     message: Message          # ← Tool output is HERE (can be dict or Message)
#     metrics: EventLoopMetrics
#     state: Any
#     interrupts: Sequence[Interrupt] | None = None
#     structured_output: BaseModel | None = None
#
# Extraction paths (priority order):
# 1. result.results["agent_name"].result.message (BUG-020 v8 - CORRECT)
# 2. result.results["agent_name"].result as dict (fallback for raw dict returns)
# 3. result.entry_point.messages[] (fallback for tool_result blocks)
#
# Message content block format (OFFICIAL Strands SDK - v11 FIX):
# Content blocks use DIRECT KEYS, NOT a "type" field!
# {
#     "role": "user",
#     "content": [
#         {"text": "..."},           # Text block
#         {"toolUse": {...}},        # Tool use block
#         {"toolResult": {...}}      # Tool result block ← OUR DATA IS HERE
#     ]
# }
#
# ToolResult format (official Strands SDK):
# {
#     "toolUseId": str,       # Optional
#     "status": str,          # "success" or "error"
#     "content": [            # List of content items
#         {"json": {...}},    # Structured data ← ANALYSIS HERE
#         {"text": "..."}     # Text data (may be JSON string)
#     ]
# }
#
# VALIDATION (2026-01-15):
# - Follows official Strands Swarm documentation patterns
# - No SDK utility exists - this fills the gap
# - Is INFRASTRUCTURE code (SDK parsing), NOT business logic
# - Business logic runs 100% inside Strands agents with Gemini
#
# BUG-020 v11 FIX (2026-01-16):
# - v10 looked for content_block.get("type") == "tool_result" - WRONG!
# - Official Strands SDK uses "toolResult" as a KEY, NOT a type value
# - v11 checks for "toolResult" in content_block (correct pattern)
# - Extracts from content_block["toolResult"]["content"][0]["json"]
#
# BUG-020 v12 FIX (2026-01-16):
# - CloudWatch revealed the REAL format produced by Strands SDK tools:
#   {"<tool_name>_response": {"output": [{"text": "{'success': True, ...}"}]}}
# - Key is <tool_name>_response (e.g., unified_analyze_file_response), NOT toolResult!
# - Content is Python repr STRING with SINGLE QUOTES, NOT valid JSON!
# - v12 checks for key.endswith("_response") pattern
# - Uses ast.literal_eval() as fallback for Python repr strings
# - CloudWatch evidence: 2026-01-16 12:49:38 shows exact format
#
# Sources:
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/
# - https://strandsagents.com/latest/documentation/docs/api-reference/agent (tool result format)
# - https://github.com/strands-agents/docs/blob/main/docs/user-guide/concepts/tools/custom-tools.md
# - https://github.com/strands-agents/sdk-python/blob/v1.20.0/src/strands/agent/agent_result.py
# - Context7 query 2026-01-16 (confirmed toolResult key format)
# =============================================================================

import ast  # v12: For parsing Python repr strings (single quotes)
import json
import re
import logging
from datetime import datetime
from typing import Any, Dict, Optional

# ADR-004: Global error capture for Debug Agent (BUG-031)
from shared.debug_utils import debug_json_error, debug_error

# BUG-036 FIX: Centralized data contract enforcement
# All STRING↔DICT conversions MUST use these functions
from shared.data_contracts import ensure_dict

logger = logging.getLogger(__name__)


# =============================================================================
# BUG-033 FIX: Debug Analysis Capture Helpers
# =============================================================================
# BUG-032 fixed debug_error() to return synchronously, but callers discarded
# the result. BUG-033 adds helper functions to CAPTURE the analysis and inject
# it directly into the response dict.
#
# Problem: Debug Agent analysis was computed but never reached the frontend
# because results were discarded at 25+ call sites.
#
# Solution: These helpers capture and inject analysis into the response.
# =============================================================================


def _capture_debug_analysis(
    error: Exception,
    operation: str,
    context: dict,
    response: dict,
    timeout: float = 15.0,  # BUG-035: Increased from 5.0 for Gemini Pro + Thinking
) -> None:
    """
    BUG-033 FIX: Capture debug_error() result and add to response.

    Instead of discarding debug_error() results, we now capture
    the analysis and inject it directly into the response dict.

    Args:
        error: The exception that occurred
        operation: Name of the failed operation
        context: Additional context for debugging
        response: Response dict to inject analysis into (modified in-place)
        timeout: Timeout for Debug Agent call (default 5s)

    Side Effects:
        - Sets response["debug_analysis"] if enrichment succeeded
        - Sets response["_debug_enriched"] = True if successful
    """
    try:
        result = debug_error(error, operation, context, timeout=timeout)

        if result.get("enriched"):
            # BUG-036 FIX: Use ensure_dict() for guaranteed STRING→DICT conversion
            # debug_error() now returns analysis as dict (via ensure_dict in debug_utils.py),
            # but we double-check here for safety and legacy compatibility.
            analysis = ensure_dict(
                result.get("analysis", {}),
                f"capture_debug_analysis.{operation}"
            )

            # Check if we already have analysis and need to merge
            if "debug_analysis" in response:
                _merge_debug_analysis(response, analysis)
            else:
                response["debug_analysis"] = analysis

            response["_debug_enriched"] = True
            logger.info(
                "[BUG-033] Debug analysis captured for %s: enriched=True",
                operation
            )
        else:
            logger.warning(
                "[BUG-036] Debug analysis not enriched for %s: %s",
                operation,
                result.get("reason", "unknown")
            )

    except Exception as e:
        # Never let debug capture fail the main flow
        logger.warning(
            "[BUG-036] _capture_debug_analysis failed for %s: %s",
            operation,
            str(e)
        )


def _merge_debug_analysis(response: dict, new_analysis: dict) -> None:
    """
    BUG-033: Merge multiple debug analyses into one comprehensive report.

    During extraction, multiple errors may occur. Instead of replacing,
    we accumulate them for a complete picture.

    Args:
        response: Response dict containing existing debug_analysis
        new_analysis: New analysis to merge

    Side Effects:
        Modifies response["debug_analysis"] in-place
    """
    existing = response.get("debug_analysis", {})

    if not existing:
        response["debug_analysis"] = new_analysis
        return

    if not new_analysis:
        return

    # Merge root_causes
    existing_causes = existing.get("root_causes", [])
    new_causes = new_analysis.get("root_causes", [])
    if new_causes:
        existing["root_causes"] = existing_causes + new_causes

    # Merge debugging_steps
    existing_steps = existing.get("debugging_steps", [])
    new_steps = new_analysis.get("debugging_steps", [])
    if new_steps:
        existing["debugging_steps"] = existing_steps + new_steps

    # Merge doc_links
    existing_links = existing.get("doc_links", [])
    new_links = new_analysis.get("doc_links", [])
    if new_links:
        existing["doc_links"] = existing_links + new_links

    # Keep highest confidence technical_explanation
    new_confidence = new_analysis.get("confidence", 0)
    existing_confidence = existing.get("confidence", 0)
    if new_confidence > existing_confidence:
        existing["technical_explanation"] = new_analysis.get("technical_explanation")
        existing["confidence"] = new_confidence
        existing["classification"] = new_analysis.get("classification")

    # Merge suggested_action (use most severe)
    action_priority = {"abort": 4, "escalate": 3, "fallback": 2, "retry": 1}
    existing_action = existing.get("suggested_action", "retry")
    new_action = new_analysis.get("suggested_action", "retry")
    if action_priority.get(new_action, 0) > action_priority.get(existing_action, 0):
        existing["suggested_action"] = new_action

    # Update recoverable (if any says non-recoverable, it's non-recoverable)
    if not new_analysis.get("recoverable", True):
        existing["recoverable"] = False

    response["debug_analysis"] = existing


# =============================================================================
# BUG-034 FIX: Flash vs Pro Heuristic
# =============================================================================
# Simple errors can use Gemini Flash (faster, cheaper), while complex errors
# benefit from Gemini Pro with Thinking mode. This heuristic can reduce costs
# by ~30-40% for common errors without sacrificing quality for complex ones.
# =============================================================================

# Patterns that indicate "simple" errors suitable for Gemini Flash
FLASH_ERROR_PATTERNS = frozenset({
    # File/S3 errors (clear cause - file doesn't exist)
    "file not found",
    "filenotfounderror",  # Python exception class name
    "no such file",
    "s3",
    "bucket",
    "upload",
    "key not found",
    "nosuchkey",
    "nosuchbucket",
    "access denied",

    # Network/timeout (transient, well-understood)
    "timeout",
    "timed out",
    "connection refused",
    "connection reset",
    "network unreachable",
    "rate limit",
    "throttl",
    "too many requests",
    "429",
    "503",
    "502",

    # Validation (deterministic, clear fix)
    "invalid",
    "required",
    "missing field",
    "validation error",
    "field required",
    "type error",
    "value error",

    # Authentication (clear fix - re-auth)
    "unauthorized",
    "401",
    "403",
    "forbidden",
    "token expired",
    "credentials",
})


def _should_use_flash(error_message: str) -> bool:
    """
    Determine if an error is "simple" and can use Gemini Flash.

    Simple errors have obvious causes and don't need deep reasoning:
    - File not found → check the path
    - Timeout → retry or increase timeout
    - Validation error → fix the input

    Complex errors benefit from Pro with Thinking:
    - Parsing failures (unclear JSON format)
    - Logic errors (unexpected state)
    - Integration errors (multi-system)

    Args:
        error_message: The error message to analyze

    Returns:
        True if Flash is sufficient, False if Pro is recommended
    """
    if not error_message:
        return False  # Unknown error → use Pro for safety

    msg_lower = error_message.lower()
    return any(pattern in msg_lower for pattern in FLASH_ERROR_PATTERNS)


# =============================================================================
# BUG-034 FIX: Final Response Gate
# =============================================================================
# BUG-033 fixed extraction failures, but business logic errors (like "File not
# found at S3 key") were NOT covered because they already have an error field.
#
# The condition `if not success AND not error` was TOO RESTRICTIVE.
#
# BUG-034 FIX: Create a SINGLE EXIT POINT that invokes Debug Agent for
# ALL error responses (success=False), regardless of whether error is set.
#
# This ensures 100% error visibility through Debug Agent:
# - Extraction failures (error=None) - covered by BUG-033
# - Business logic errors (error="...") - NOW COVERED by BUG-034
# - LLM returned errors - NOW COVERED by BUG-034
# =============================================================================


def _finalize_response(
    response: Dict[str, Any],
    action: str,
    session: Dict[str, Any],
    swarm_result: Any,
) -> Dict[str, Any]:
    """
    BUG-034 FIX: Final response gate that ensures:
    1. Response normalization (handle double-encoding, type issues)
    2. Debug Agent invocation for ALL failures (success=False)

    This is the SINGLE exit point for all return paths in _process_swarm_result().

    The key insight is that BUG-033 only invoked Debug Agent when:
        if not success AND not error  # Too restrictive!

    BUG-034 fixes this by invoking Debug Agent for:
        if not success  # Captures ALL errors, including business logic

    Args:
        response: Response dict to finalize
        action: Action name for context
        session: Session dict for context
        swarm_result: Original swarm result for context

    Returns:
        Finalized response dict with:
        - Normalized fields (no double-encoding)
        - debug_analysis (if error occurred and Debug Agent enriched)
    """
    # Step 1: Normalize fields (existing logic from BUG-022)
    response = _normalize_response_fields(response)

    # Step 2: DEBUG GATE - Invoke Debug Agent for ALL error responses
    # This catches:
    # - Extraction failures (error=None, covered by BUG-033)
    # - Business logic errors (error="File not found...", MISSING before!)
    # - LLM returned errors (error="Invalid format", etc.)
    if not response.get("success"):
        if not response.get("debug_analysis"):
            # Get error message for heuristic
            error_message = response.get("error", "Unknown error")

            # BUG-034: Apply Flash vs Pro heuristic
            use_flash = _should_use_flash(error_message)

            # Build context for Debug Agent
            error_context = {
                "action": action,
                "session_id": session.get("session_id", "") if session else "",
                "error_message": error_message,
                "error_type": "business_logic" if response.get("error") else "extraction_failure",
                "swarm_result_type": type(swarm_result).__name__ if swarm_result else "None",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                # BUG-034: Model recommendation for Debug Agent
                "recommended_model": "flash" if use_flash else "pro",
                "use_flash": use_flash,
            }

            # Add swarm result details if available
            if swarm_result:
                if hasattr(swarm_result, "results") and swarm_result.results:
                    error_context["results_keys"] = list(swarm_result.results.keys())[:10]
                if hasattr(swarm_result, "message") and swarm_result.message:
                    msg = swarm_result.message
                    if isinstance(msg, str):
                        error_context["message_preview"] = msg[:500]
                    elif isinstance(msg, dict):
                        error_context["message_keys"] = list(msg.keys())[:10]

            # Create synthetic exception for Debug Agent
            synthetic_error = Exception(
                f"[BUG-034] Error in action={action}: {error_message}"
            )

            # Invoke Debug Agent with comprehensive context
            logger.info(
                "[BUG-034] Final gate: Invoking Debug Agent for error response. "
                "action=%s, error_type=%s, recommended_model=%s",
                action,
                error_context["error_type"],
                error_context["recommended_model"],
            )

            _capture_debug_analysis(
                synthetic_error,
                f"final_gate_{action}",
                error_context,
                response,
                timeout=30.0,  # TIMEOUT-FIX: Maximum for Gemini 2.5 Pro + Thinking
            )

            logger.info(
                "[BUG-034] Debug Agent invocation complete. "
                "debug_analysis present: %s",
                "debug_analysis" in response,
            )

    return response


# =============================================================================
# BUG-022 v9 FIX: Schema validation for response.update()
# =============================================================================
# Security: Only allow known keys to be copied into response objects.
# This prevents field injection and response pollution from untrusted data.
# =============================================================================

# Whitelist of allowed keys in response objects
# BUG-023 FIX: Expanded to include all NEXO-required keys
ALLOWED_RESPONSE_KEYS = frozenset({
    # Core response fields
    "success",
    "error",
    "message",

    # Analysis results
    "analysis",
    "file_analysis",
    "sheets",

    # Mapping fields
    "proposed_mappings",
    "column_mappings",
    "unmapped_columns",

    # HIL fields (BUG-023: expanded for NEXO questioning flow)
    "questions",
    "unmapped_questions",        # Questions for columns not in DB schema
    "pending_questions_count",   # Count of pending questions

    # File metadata (BUG-023: added detected_file_type)
    "filename",
    "s3_key",
    "file_type",
    "detected_file_type",        # More specific file type (csv, xlsx, etc.)

    # Session tracking (BUG-023: expanded for NEXO session management)
    "request_id",
    "import_session_id",         # NEXO import session ID
    "session_id",                # Generic session ID
    "session_state",             # Complete session state object

    # Analysis metadata (BUG-023: NEW for NEXO transparency)
    "overall_confidence",        # Confidence score (0.0-1.0)
    "reasoning_trace",           # NEXO reasoning steps
    "analysis_round",            # Current round number (1, 2, 3...)
    "ready",                     # BUG-037: Frontend alias for ready_for_import
    "ready_for_import",          # Boolean flag: can proceed with import?

    # HIL control signals (BUG-023: NEW for agent STOP/WAIT)
    "stop_action",               # Agent STOP signal for HIL
    "stop_reason",               # Why agent stopped (user message)

    # Debug fields (allowed but logged)
    "debug_gemini_response_keys",
    "raw_response",

    # BUG-032 FIX: Debug Agent analysis fields
    # These fields are added by DebugHook when errors are enriched by Debug Agent
    "debug_analysis",           # Complete analysis from Debug Agent (technical_explanation, root_causes, etc.)
    "_debug_enriched",          # Boolean flag indicating Debug Agent enrichment occurred
})


def _safe_response_update(response: Dict[str, Any], extracted: Dict[str, Any]) -> None:
    """
    Safely update response dict with only allowed keys from extracted data.

    BUG-022 v9 FIX: Schema validation to prevent field injection.

    Args:
        response: Target response dictionary to update
        extracted: Source dictionary with potentially untrusted keys
    """
    if not extracted or not isinstance(extracted, dict):
        return

    for key in ALLOWED_RESPONSE_KEYS:
        if key in extracted:
            response[key] = extracted[key]

    # Log unexpected keys for debugging (but don't copy them)
    unexpected = set(extracted.keys()) - ALLOWED_RESPONSE_KEYS
    if unexpected:
        logger.warning(
            "[_safe_response_update] Ignoring unexpected keys in extracted response: %s",
            unexpected
        )


# =============================================================================
# BUG-021 v5 FIX: Strip markdown code fence wrapper
# =============================================================================
# LLMs often wrap JSON responses in markdown code fences:
# ```json
# {"success": true, ...}
# ```
#
# This helper strips the fence so json.loads() can parse the content.
# =============================================================================


def _strip_markdown_fence(text: str) -> str:
    """
    Strip markdown code fence wrapper from text.

    Handles formats:
    - ```json\n{...}\n```
    - ```python\n{...}\n```
    - ```\n{...}\n```

    Args:
        text: Input text that may have markdown fence

    Returns:
        Text without markdown fence, or original text if no fence found
    """
    if not isinstance(text, str):
        return text

    text = text.strip()

    # Match ```json or ```python or ``` at start, ``` at end
    match = re.match(r'^```(?:json|python)?\s*\n?(.*?)\n?```$', text, re.DOTALL)
    if match:
        stripped = match.group(1).strip()
        logger.info("Stripped markdown fence, len: %d -> %d", len(text), len(stripped))
        return stripped

    return text


# =============================================================================
# BUG-020 v13 FIX: Helper function for _response wrapper extraction
# =============================================================================
# CloudWatch revealed: The "_response" wrapper is INSIDE parsed JSON strings,
# NOT at the content_block level where v12 was looking.
#
# Data flow:
# 1. content_block = {"type": "tool_result", "content": "JSON_STRING"}
# 2. json.loads(content_block["content"]) → {"unified_analyze_file_response": {...}}
# 3. v13 checks HERE (after json.loads) for _response pattern
#
# v12 checked content_block.keys() → ["type", "content"] → No _response found!
# v13 checks parsed.keys() → ["unified_analyze_file_response"] → Found!
# =============================================================================


def _extract_from_response_wrapper(data: Any) -> Optional[Dict]:
    """
    Extract data from Strands SDK tool response wrapper format.

    BUG-020 v13 FIX: This helper extracts from the wrapper format produced by
    Strands SDK @tool decorated functions:
    {"<tool_name>_response": {"output": [{"text": "{'success': True, ...}"}]}}

    The text content may be:
    - JSON with double quotes (valid JSON)
    - Python repr with single quotes (requires ast.literal_eval)

    This helper is called AFTER json.loads() at every extraction point where
    the wrapper might appear.

    Args:
        data: Parsed dict that may contain a _response wrapper

    Returns:
        Extracted dict with "analysis" or "success" key, or None if no wrapper found
    """
    if not isinstance(data, dict):
        return None

    for key in data.keys():
        if key.endswith("_response"):
            logger.info("Found _response wrapper: %s", key)
            wrapper = data[key]

            if isinstance(wrapper, dict) and "output" in wrapper:
                for output_item in wrapper.get("output", []):
                    if isinstance(output_item, dict):
                        # Check "text" key (most common - Strands SDK format)
                        if "text" in output_item:
                            text_content = output_item["text"]
                            logger.debug(
                                "Processing text content, type=%s, len=%d",
                                type(text_content).__name__,
                                len(text_content) if isinstance(text_content, str) else 0,
                            )

                            if isinstance(text_content, str):
                                # BUG-021 v5: Strip markdown fence before parsing
                                stripped_content = _strip_markdown_fence(text_content)
                                # Try JSON first (double quotes)
                                try:
                                    parsed = json.loads(stripped_content)
                                    if isinstance(parsed, dict) and (
                                        "analysis" in parsed or "success" in parsed
                                    ):
                                        logger.info(
                                            "SUCCESS: Extracted from _response.output[].text (JSON)"
                                        )
                                        return parsed
                                except json.JSONDecodeError as e:
                                    # ADR-004: Send to Debug Agent for analysis
                                    debug_json_error(e, "json_parse_response_output_text", stripped_content)
                                    # Try Python repr (single quotes)
                                    try:
                                        parsed = ast.literal_eval(stripped_content)
                                        if isinstance(parsed, dict) and (
                                            "analysis" in parsed or "success" in parsed
                                        ):
                                            logger.info(
                                                "SUCCESS: Extracted from _response.output[].text (repr)"
                                            )
                                            return parsed
                                    except (ValueError, SyntaxError) as e:
                                        logger.debug("ast.literal_eval failed: %s", e)
                                        # ADR-004: Send to Debug Agent
                                        debug_error(e, "ast_literal_eval_output_text", {"text_preview": stripped_content[:500] if stripped_content else None})

                            elif isinstance(text_content, dict):
                                if "analysis" in text_content or "success" in text_content:
                                    logger.info(
                                        "SUCCESS: Direct dict from _response.output[].text"
                                    )
                                    return text_content

                        # Check "json" key (alternative format)
                        if "json" in output_item:
                            inner = output_item["json"]
                            if isinstance(inner, dict) and (
                                "analysis" in inner or "success" in inner
                            ):
                                logger.info(
                                    "SUCCESS: Extracted from _response.output[].json"
                                )
                                return inner

    return None


# =============================================================================
# BUG-020 v8 FIX: Extract from AgentResult.message
# =============================================================================
# CloudWatch logs revealed: AgentResult has .message, NOT nested .result!
# The .message attribute contains tool output as JSON string or Message object.
# =============================================================================


def _extract_from_agent_message(message: Any) -> Optional[Dict]:
    """
    Extract structured data from AgentResult.message attribute.

    BUG-020 v8 FIX: This is the CORRECT extraction path!
    AgentResult.message contains the tool output, NOT AgentResult.result.

    Handles multiple message formats:
    1. JSON string with tool response wrapper: {"<tool>_response": {"output": [{"json": {...}}]}}
    2. Message object with .content array containing tool_result blocks
    3. Direct JSON string without wrapper

    Args:
        message: The AgentResult.message value (str or Message object)

    Returns:
        Extracted dict with "analysis" or "success" key, or None if invalid
    """
    if message is None:
        return None

    logger.debug(
        "_extract_from_agent_message: type=%s",
        type(message).__name__,
    )

    # Handle Message object with content array (Strands Message type)
    if hasattr(message, "content") and message.content:
        content = message.content

        # Content can be a list of content blocks
        if isinstance(content, list):
            for content_block in content:
                if isinstance(content_block, dict):
                    # Check for tool_result type
                    if content_block.get("type") == "tool_result":
                        tool_content = content_block.get("content", "")
                        if isinstance(tool_content, str):
                            try:
                                parsed = json.loads(tool_content)
                                unwrapped = _unwrap_tool_result(parsed)
                                if unwrapped:
                                    logger.info("Extracted from Message.content tool_result")
                                    return unwrapped
                            except json.JSONDecodeError as e:
                                # ADR-004: Send to Debug Agent
                                debug_json_error(e, "json_parse_message_tool_result", tool_content)
                        elif isinstance(tool_content, dict):
                            unwrapped = _unwrap_tool_result(tool_content)
                            if unwrapped:
                                logger.info("Extracted from Message.content dict")
                                return unwrapped

                    # Check for direct json key
                    if "json" in content_block:
                        inner = content_block["json"]
                        if isinstance(inner, dict):
                            unwrapped = _unwrap_tool_result(inner)
                            if unwrapped:
                                logger.info("Extracted from Message.content json key")
                                return unwrapped

        # Content can be a string
        elif isinstance(content, str):
            try:
                # BUG-021 v5: Strip markdown fence before parsing
                parsed = json.loads(_strip_markdown_fence(content))
                unwrapped = _unwrap_tool_result(parsed)
                if unwrapped:
                    logger.info("Extracted from Message.content string")
                    return unwrapped
            except json.JSONDecodeError as e:
                # ADR-004: Send to Debug Agent
                debug_json_error(e, "json_parse_message_content_string", content)

    # Handle JSON string message (most common case from CloudWatch logs)
    if isinstance(message, str):
        # BUG-022 FIX: Detect double-encoded JSON (starts with '"{' or "'{")
        # This happens when JSON gets serialized twice: {"key": "value"} -> '"{\"key\": \"value\"}"'
        message_stripped = message.strip()
        if message_stripped.startswith('"{') or message_stripped.startswith("'{"):
            logger.warning("[BUG-022] Detected double-encoded JSON: %s...", message_stripped[:100])
            try:
                unwrapped = json.loads(message_stripped)
                if isinstance(unwrapped, str):
                    message = unwrapped
                    logger.info("[BUG-022] Successfully unwrapped double-encoded JSON")
            except json.JSONDecodeError as e:
                # ADR-004: Send to Debug Agent
                debug_json_error(e, "json_parse_double_encoded", message_stripped)

        try:
            # BUG-021 v5: Strip markdown fence before parsing
            parsed = json.loads(_strip_markdown_fence(message))
            if isinstance(parsed, dict):
                # Check for tool response wrapper format
                # Format: {"<tool_name>_response": {"output": [{"json": {...}}]}} OR
                #         {"<tool_name>_response": {"output": [{"text": "{'success': True, ...}"}]}}
                for key, value in parsed.items():
                    if key.endswith("_response") and isinstance(value, dict):
                        logger.info("Found tool_response wrapper in JSON string: %s", key)
                        output = value.get("output", [])
                        if isinstance(output, list):
                            for item in output:
                                if isinstance(item, dict):
                                    # v12 FIX: Check for "text" key with Python repr
                                    if "text" in item:
                                        text_val = item["text"]
                                        if isinstance(text_val, str):
                                            # BUG-021 v5: Strip markdown fence before parsing
                                            stripped_val = _strip_markdown_fence(text_val)
                                            # Try JSON first, then Python repr
                                            try:
                                                inner = json.loads(stripped_val)
                                            except json.JSONDecodeError as e:
                                                # ADR-004: Send to Debug Agent
                                                debug_json_error(e, "json_parse_tool_response_text", stripped_val)
                                                try:
                                                    inner = ast.literal_eval(stripped_val)
                                                except (ValueError, SyntaxError) as e2:
                                                    # ADR-004: Send to Debug Agent
                                                    debug_error(e2, "ast_literal_eval_tool_response", {"text_preview": stripped_val[:500] if stripped_val else None})
                                                    continue
                                            if isinstance(inner, dict) and (
                                                "analysis" in inner or "success" in inner
                                            ):
                                                logger.info(
                                                    "SUCCESS: Extracted from tool_response.output[].text"
                                                )
                                                return inner
                                        elif isinstance(text_val, dict):
                                            if "analysis" in text_val or "success" in text_val:
                                                logger.info(
                                                    "SUCCESS: Direct dict from tool_response.output[].text"
                                                )
                                                return text_val

                                    # Check for "json" key (original format)
                                    if "json" in item:
                                        inner = item["json"]
                                        if isinstance(inner, dict):
                                            # Use unwrap helper or return directly
                                            unwrapped = _unwrap_tool_result(inner)
                                            if unwrapped:
                                                logger.info("Extracted from tool_response wrapper")
                                                return unwrapped
                                            # Direct return if has analysis/success
                                            if "analysis" in inner or "success" in inner:
                                                logger.info("Direct return from tool_response inner")
                                                return inner

                # Try direct unwrap (ToolResult format or direct response)
                unwrapped = _unwrap_tool_result(parsed)
                if unwrapped:
                    logger.info("Extracted from direct JSON string")
                    return unwrapped

                # Fallback: direct dict with analysis/success
                if "analysis" in parsed or "success" in parsed:
                    logger.info("Direct dict from JSON string")
                    return parsed

        except json.JSONDecodeError as e:
            logger.debug("Message is non-JSON string, skipping")
            # ADR-004: Send to Debug Agent (only if message looks like it should be JSON)
            if "{" in message and "}" in message:
                debug_json_error(e, "json_parse_message_string", message)

    # Handle dict message directly (v11 FIX for Message-like dicts)
    if isinstance(message, dict):
        # v11 FIX: Check if dict has Message structure (role + content array)
        # NOTE: hasattr(dict, "content") returns FALSE for dicts - use "key in dict"
        if "content" in message and isinstance(message.get("content"), list):
            logger.info("Dict has Message structure, iterating content array")
            for content_block in message["content"]:
                if isinstance(content_block, dict):
                    # v13 DEBUG: Log content_block structure to trace data flow
                    logger.info(
                        "content_block type=%s, keys=%s",
                        type(content_block).__name__,
                        list(content_block.keys())[:5],
                    )
                    # =====================================================
                    # v11 FIX: Check for "toolResult" KEY (official Strands)
                    # NOT "type": "tool_result" - that format doesn't exist!
                    # Official format: {"toolResult": {"status": "...", "content": [...]}}
                    # Source: Context7 query of strandsagents.com 2026-01-16
                    # =====================================================
                    if "toolResult" in content_block:
                        tool_result = content_block["toolResult"]
                        logger.info(
                            "Found toolResult block, status=%s",
                            tool_result.get("status") if isinstance(tool_result, dict) else "N/A",
                        )

                        # Extract from ToolResult.content array
                        # Format: {"status": "success", "content": [{"json": {...}}, {"text": "..."}]}
                        if isinstance(tool_result, dict) and "content" in tool_result:
                            for tr_content in tool_result.get("content", []):
                                if isinstance(tr_content, dict):
                                    # json block (structured data) - PRIMARY
                                    if "json" in tr_content:
                                        inner = tr_content["json"]
                                        if isinstance(inner, dict):
                                            if "analysis" in inner or "success" in inner:
                                                logger.info("SUCCESS: Extracted from toolResult.content[].json")
                                                return inner
                                            # Try unwrap if nested in another wrapper
                                            unwrapped = _unwrap_tool_result(inner)
                                            if unwrapped:
                                                logger.info("SUCCESS: Unwrapped from toolResult.content[].json")
                                                return unwrapped

                                    # text block (JSON string) - SECONDARY
                                    if "text" in tr_content:
                                        try:
                                            parsed = json.loads(tr_content["text"])
                                            if isinstance(parsed, dict):
                                                if "analysis" in parsed or "success" in parsed:
                                                    logger.info("SUCCESS: Parsed from toolResult.content[].text")
                                                    return parsed
                                                unwrapped = _unwrap_tool_result(parsed)
                                                if unwrapped:
                                                    logger.info("SUCCESS: Unwrapped from toolResult.content[].text")
                                                    return unwrapped
                                        except json.JSONDecodeError as e:
                                            logger.debug("text content is not JSON")
                                            # ADR-004: Send to Debug Agent
                                            debug_json_error(e, "json_parse_toolresult_text", tr_content.get("text", ""))

                        # Fallback: Direct data in toolResult (non-standard but handle it)
                        if isinstance(tool_result, dict):
                            if "analysis" in tool_result or "success" in tool_result:
                                logger.info("SUCCESS: Direct data from toolResult")
                                return tool_result

                    # =====================================================
                    # v12 FIX: Check for "<tool_name>_response" KEY
                    # Strands SDK wraps @tool returns in this format!
                    # Format: {"<tool>_response": {"output": [{"text": "..."}]}}
                    # Source: CloudWatch logs 2026-01-16 12:49:38
                    # =====================================================
                    for key in content_block.keys():
                        if key.endswith("_response"):
                            logger.info("Found tool_response wrapper: %s", key)
                            wrapper = content_block[key]

                            if isinstance(wrapper, dict) and "output" in wrapper:
                                for output_item in wrapper.get("output", []):
                                    if isinstance(output_item, dict):
                                        # Check for "text" key (Strands SDK format)
                                        if "text" in output_item:
                                            text_content = output_item["text"]
                                            logger.info(
                                                "Found text in output, length=%d",
                                                len(text_content) if text_content else 0,
                                            )

                                            # Try JSON first (double quotes)
                                            if isinstance(text_content, str):
                                                try:
                                                    parsed = json.loads(text_content)
                                                    if isinstance(parsed, dict):
                                                        if "analysis" in parsed or "success" in parsed:
                                                            logger.info(
                                                                "SUCCESS: Parsed JSON from tool_response.output[].text"
                                                            )
                                                            return parsed
                                                except json.JSONDecodeError as e:
                                                    # ADR-004: Send to Debug Agent
                                                    debug_json_error(e, "json_parse_tool_response_output_text", text_content)
                                                    # Python repr with single quotes - use ast.literal_eval
                                                    try:
                                                        parsed = ast.literal_eval(text_content)
                                                        if isinstance(parsed, dict):
                                                            if "analysis" in parsed or "success" in parsed:
                                                                logger.info(
                                                                    "SUCCESS: Parsed Python repr from tool_response.output[].text"
                                                                )
                                                                return parsed
                                                    except (ValueError, SyntaxError) as e:
                                                        logger.debug("ast.literal_eval failed: %s", e)
                                                        # ADR-004: Send to Debug Agent
                                                        debug_error(e, "ast_literal_eval_tool_response_output", {"text_preview": text_content[:500] if text_content else None})

                                            elif isinstance(text_content, dict):
                                                if "analysis" in text_content or "success" in text_content:
                                                    logger.info(
                                                        "SUCCESS: Direct dict from tool_response.output[].text"
                                                    )
                                                    return text_content

                                        # Check for "json" key (alternative format)
                                        if "json" in output_item:
                                            inner = output_item["json"]
                                            if isinstance(inner, dict):
                                                if "analysis" in inner or "success" in inner:
                                                    logger.info(
                                                        "SUCCESS: Extracted from tool_response.output[].json"
                                                    )
                                                    return inner

                    # =====================================================
                    # v14 FIX: Handle direct "text" key in content_block
                    # CloudWatch showed: content_block = {"text": "{'success': ...}"}
                    # This format appears when tool returns simple text response
                    # Session: sga-session-8374a4b38be146daaee6092e0ccbd408
                    # =====================================================
                    if "text" in content_block and len(content_block) == 1:
                        text_content = content_block["text"]
                        logger.info(
                            "Found direct text block (no other keys), length=%d",
                            len(text_content) if text_content else 0,
                        )

                        if isinstance(text_content, str):
                            # Try JSON first (double quotes)
                            try:
                                parsed = json.loads(text_content)
                                # v16 DEBUG: Log what we parsed to understand wrapper format
                                logger.info(
                                    "v14 parsed JSON successfully, type=%s, keys=%s",
                                    type(parsed).__name__,
                                    list(parsed.keys())[:5] if isinstance(parsed, dict) else "N/A",
                                )
                                if isinstance(parsed, dict):
                                    if "analysis" in parsed or "success" in parsed:
                                        logger.info("SUCCESS: Parsed JSON from direct text block")
                                        return parsed
                                    # v16 FIX: Log any tool response wrappers found
                                    for key in parsed.keys():
                                        if key.endswith("_response"):
                                            logger.info("Found tool wrapper in text block: %s", key)
                                    # Also check for _response wrapper
                                    from_wrapper = _extract_from_response_wrapper(parsed)
                                    if from_wrapper:
                                        logger.info("SUCCESS: Extracted _response from direct text block")
                                        return from_wrapper
                            except json.JSONDecodeError as e:
                                # v16 DEBUG: Log parse failure details
                                logger.warning(
                                    "v14 JSON parse FAILED: %s (first 200 chars: %s)",
                                    str(e),
                                    text_content[:200] if text_content else "EMPTY",
                                )
                                # ADR-004: Send to Debug Agent for analysis
                                debug_json_error(e, "json_parse_v14_text_block", text_content)
                                # Python repr with single quotes - use ast.literal_eval
                                try:
                                    parsed = ast.literal_eval(text_content)
                                    if isinstance(parsed, dict):
                                        if "analysis" in parsed or "success" in parsed:
                                            logger.info("SUCCESS: Parsed Python repr from direct text block")
                                            return parsed
                                        from_wrapper = _extract_from_response_wrapper(parsed)
                                        if from_wrapper:
                                            logger.info("SUCCESS: Extracted _response from repr text block")
                                            return from_wrapper
                                except (ValueError, SyntaxError) as e:
                                    logger.debug("ast.literal_eval failed: %s", e)
                                    # ADR-004: Send to Debug Agent for analysis
                                    debug_error(e, "ast_literal_eval_v14", {"text_preview": text_content[:500] if text_content else None})

                        elif isinstance(text_content, dict):
                            if "analysis" in text_content or "success" in text_content:
                                logger.info("SUCCESS: Direct dict in text block")
                                return text_content

                    # =====================================================
                    # KEEP legacy patterns as fallback (backward compatibility)
                    # =====================================================

                    # Legacy: "type": "tool_result" format (v10 code - may still work for some edge cases)
                    if content_block.get("type") == "tool_result":
                        tool_content = content_block.get("content", "")
                        logger.info("Found legacy tool_result block (type key)")
                        if isinstance(tool_content, str):
                            try:
                                parsed = json.loads(tool_content)
                                if isinstance(parsed, dict):
                                    if "analysis" in parsed or "success" in parsed:
                                        logger.info("SUCCESS: Direct from legacy tool_result")
                                        return parsed
                                    # v13 FIX: Check for _response wrapper BEFORE _unwrap_tool_result
                                    # This is the CRITICAL path for NEXO Smart Import!
                                    from_wrapper = _extract_from_response_wrapper(parsed)
                                    if from_wrapper:
                                        logger.info("SUCCESS: Extracted _response from legacy tool_result")
                                        return from_wrapper
                                    unwrapped = _unwrap_tool_result(parsed)
                                    if unwrapped:
                                        return unwrapped
                            except json.JSONDecodeError as e:
                                # ADR-004: Send to Debug Agent
                                debug_json_error(e, "json_parse_legacy_tool_result", tool_content)
                        elif isinstance(tool_content, dict):
                            if "analysis" in tool_content or "success" in tool_content:
                                return tool_content
                            # v13 FIX: Check for _response wrapper BEFORE _unwrap_tool_result
                            from_wrapper = _extract_from_response_wrapper(tool_content)
                            if from_wrapper:
                                return from_wrapper
                            unwrapped = _unwrap_tool_result(tool_content)
                            if unwrapped:
                                return unwrapped

                    # Direct json key in content block
                    if "json" in content_block:
                        inner = content_block["json"]
                        if isinstance(inner, dict) and (
                            "analysis" in inner or "success" in inner
                        ):
                            logger.info("SUCCESS: Extracted from dict.content[].json")
                            return inner

        # Fallback: Try standard unwrap (for non-Message dicts)
        unwrapped = _unwrap_tool_result(message)
        if unwrapped:
            logger.info("Extracted from direct dict message")
            return unwrapped

    return None


# =============================================================================
# BUG-020 v4 FIX: Helper function to unwrap ToolResult format
# =============================================================================


def _unwrap_tool_result(data: Any) -> Optional[Dict]:
    """
    Unwrap ToolResult format and validate response structure.

    Handles two formats:
    - ToolResult format: {"status": "...", "content": [{"json": {...}}]}
    - Direct response: {"success": ..., "analysis": {...}}

    The ToolResult format is the official Strands SDK tool return format.
    Reference: https://strandsagents.com SDK examples

    Args:
        data: Raw data to unwrap (dict, str, or other)

    Returns:
        Unwrapped dict with "analysis" or "success" key, or None if invalid

    Example:
        >>> tool_output = {"status": "success", "content": [{"json": {"analysis": {...}}}]}
        >>> unwrapped = _unwrap_tool_result(tool_output)
        >>> print(unwrapped)  # {"analysis": {...}}
    """
    # BUG-020 v6: Diagnostic logging for extraction debugging
    logger.info(
        "[_unwrap] input type=%s, has_content=%s, has_analysis=%s, has_success=%s",
        type(data).__name__ if data else "None",
        "content" in data if isinstance(data, dict) else False,
        "analysis" in data if isinstance(data, dict) else False,
        "success" in data if isinstance(data, dict) else False,
    )

    if not isinstance(data, dict):
        return None

    # Priority 1: Handle ToolResult format
    # {"status": "success", "content": [{"json": {...actual data...}}]}
    if "content" in data and isinstance(data["content"], list):
        for content_item in data["content"]:
            if isinstance(content_item, dict) and "json" in content_item:
                inner = content_item["json"]
                if isinstance(inner, dict) and ("analysis" in inner or "success" in inner):
                    logger.debug("[_unwrap] Extracted from ToolResult format")
                    return inner

    # Priority 2: Direct valid response (backwards compatibility)
    if "analysis" in data or "success" in data:
        return data

    # Priority 3: v13 FIX - Check for _response wrapper as last resort
    # This provides automatic coverage for ALL code paths that call _unwrap_tool_result()
    from_wrapper = _extract_from_response_wrapper(data)
    if from_wrapper:
        logger.info("Extracted from _response wrapper via _unwrap_tool_result")
        return from_wrapper

    return None


# =============================================================================
# BUG-022 v8 FIX: Response Field Normalizer
# =============================================================================
# Defense-in-depth normalization for response fields after extraction.
# This function handles ALL edge cases that slip through individual fixes.
# =============================================================================


def _normalize_response_fields(response: dict) -> dict:
    """
    BUG-022 v8 FIX: Normalize response fields after extraction.

    Handles three scenarios that cause the '"success"' error:
    1. Double-encoded strings in any field ('"value"' → 'value')
    2. success field that's a string instead of boolean ('true' → True)
    3. "success" appearing as error (wrong field assignment)

    This function provides defense-in-depth normalization AFTER extraction
    to ensure the response contract is always valid.

    Args:
        response: Dict to normalize (modified in-place and returned)

    Returns:
        The normalized response dict
    """
    if not isinstance(response, dict):
        return response

    # =========================================================================
    # Step 1: Unwrap double-encoded strings in ALL relevant fields
    # =========================================================================
    # Extended from original BUG-022 fix to include "success" field
    for key in ["error", "message", "response", "success"]:
        if key in response and isinstance(response[key], str):
            val = response[key]
            # Check for double-encoded pattern: '"...' or "'..."
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                try:
                    unwrapped = json.loads(val)
                    # Only accept if unwrapping produced a different value
                    if unwrapped != val:
                        response[key] = unwrapped
                        logger.info(
                            "[BUG-022 v8] Unwrapped double-encoded %s: %s → %s",
                            key,
                            val[:50] if len(str(val)) > 50 else val,
                            unwrapped,
                        )
                except json.JSONDecodeError as e:
                    # ADR-004: Send to Debug Agent
                    debug_json_error(e, "json_parse_double_encoded_field", val)

    # =========================================================================
    # Step 2: Normalize success field to boolean
    # =========================================================================
    # The success field MUST be a boolean for frontend contract compliance
    success_val = response.get("success")
    if isinstance(success_val, str):
        # Convert string to boolean
        original = success_val
        response["success"] = success_val.lower() in ("true", "1", "yes", "t")
        logger.warning(
            "[BUG-022 v8] Normalized success from string to bool: '%s' → %s",
            original,
            response["success"],
        )

    # =========================================================================
    # Step 3: Detect "success" appearing as error value (semantic mismatch)
    # =========================================================================
    # If error field equals the literal word "success", this is clearly wrong
    # BUG-022 v10 FIX: Check ALL quote variations (previous only checked bare "success")
    error_val = response.get("error")
    if error_val in ("success", '"success"', "'success'"):
        logger.warning(
            "[BUG-022 v10] SEMANTIC MISMATCH: error='%s' detected (likely field swap or double-encoding)",
            error_val
        )

        # BUG-022 v12 FIX: Check for key EXISTENCE using 'in', not truthy values
        # Empty arrays/dicts are still valid meaningful data (structure exists)
        # Python: bool([]) = False, but "key" in dict = True if key exists
        has_meaningful_data = (
            "analysis" in response
            or "column_mappings" in response
            or "sheets" in response
            or "file_analysis" in response
            or "questions" in response
        )

        if has_meaningful_data:
            logger.info(
                "[BUG-022 v12] Meaningful data present despite error='%s', treating as success.",
                error_val,
            )
            response["success"] = True
            if "error" in response:
                del response["error"]
        else:
            # AUDIT-003: Use debug_error for enriched error analysis
            semantic_mismatch_error = ValueError(f"SEMANTIC MISMATCH: no meaningful data found. Response keys: {list(response.keys())}")
            debug_error(semantic_mismatch_error, "swarm_semantic_mismatch", {
                "response_keys": list(response.keys()),
                "error_val": error_val,
            })
            # No meaningful data - set informative error
            response["error"] = (
                "Erro interno: campo de resposta malformado. "
                "Por favor, tente novamente ou entre em contato com suporte."
            )
            response["success"] = False

    # =========================================================================
    # Step 4: BUG-037 FIX - Field Aliasing for Frontend Contract Compliance
    # =========================================================================
    # Backend schema uses "ready_for_import" but frontend expects "ready".
    # Copy value to maintain backward compatibility while satisfying frontend.
    # This follows the Sandwich Pattern: CODE handles contract transformation.
    if "ready_for_import" in response and "ready" not in response:
        response["ready"] = response["ready_for_import"]
        logger.debug(
            "[BUG-037] Created 'ready' alias from 'ready_for_import': %s",
            response["ready"],
        )

    return response


def _extract_tool_output_from_swarm_result(
    swarm_result: Any,
    agent_name: str = "",
    tool_name: str = "",
) -> Optional[Dict]:
    """
    Extract tool output from a Strands Swarm result.

    Uses the OFFICIAL Strands pattern: result.results["agent_name"].result

    Handles multiple formats (priority order):
    1. result.results[agent_name].result (official Strands pattern)
    2. result.results[agent_name].result as JSON string
    3. ToolResult format: {"status": "...", "content": [{"json": {...}}]}
    4. result.entry_point.messages[] (fallback for tool_result blocks)
    5. Iterate all results if agent_name not specified

    Args:
        swarm_result: Result from swarm() invocation (MultiAgentResult/SwarmResult)
        agent_name: Name of the agent to extract results from (e.g., "file_analyst")
        tool_name: Name of the tool for logging (e.g., "unified_analyze_file")

    Returns:
        Extracted dict or None if no valid output found

    Example:
        >>> result = swarm("Analyze file.csv")
        >>> data = _extract_tool_output_from_swarm_result(
        ...     result, agent_name="file_analyst", tool_name="unified_analyze_file"
        ... )
        >>> if data:
        ...     print(data["analysis"])
    """
    if swarm_result is None:
        logger.warning("[_extract] swarm_result is None!")
        return None

    # BUG-020 v6: Diagnostic logging for Swarm result structure
    logger.info(
        "[_extract] START: swarm_result type=%s, has_results=%s, has_entry_point=%s, has_structured_output=%s",
        type(swarm_result).__name__,
        hasattr(swarm_result, "results") and bool(swarm_result.results),
        hasattr(swarm_result, "entry_point") and bool(swarm_result.entry_point),
        hasattr(swarm_result, "structured_output") and bool(swarm_result.structured_output),
    )
    if hasattr(swarm_result, "results") and swarm_result.results:
        logger.info("[_extract] results_keys=%s", list(swarm_result.results.keys()))

    # -------------------------------------------------------------------------
    # BUG-035 FIX: Priority 0 — Check structured_output at swarm_result level
    # -------------------------------------------------------------------------
    # Some Strands patterns may store structured_output directly on SwarmResult
    # -------------------------------------------------------------------------
    if hasattr(swarm_result, "structured_output") and swarm_result.structured_output:
        structured = swarm_result.structured_output
        logger.info(
            "[_extract] BUG-035: Found structured_output at swarm_result level, type=%s",
            type(structured).__name__,
        )
        data = None
        if hasattr(structured, "model_dump"):
            data = structured.model_dump()
        elif hasattr(structured, "dict"):
            data = structured.dict()
        elif isinstance(structured, dict):
            data = structured

        if data and isinstance(data, dict):
            logger.info(
                "[_extract] BUG-035 SUCCESS: Extracted from swarm_result.structured_output, keys=%s",
                list(data.keys())[:8],
            )
            return data

    # -------------------------------------------------------------------------
    # Priority 1: Extract from specific agent's result (official Strands pattern)
    # Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/
    # Pattern: result.results["analyst"].result
    # -------------------------------------------------------------------------
    if hasattr(swarm_result, "results") and swarm_result.results:
        # Priority 1: Try specific agent name if provided AND exists (official pattern)
        if agent_name and agent_name in swarm_result.results:
            agent_result = swarm_result.results[agent_name]
            extracted = _extract_from_agent_result(agent_result, agent_name, tool_name)
            if extracted:
                return extracted

        # Priority 2: Iterate ALL agents as fallback
        # BUG-020 v3 FIX: This now runs unconditionally when Priority 1 fails
        # (when agent_name not found in results OR agent_name not provided)
        for name, agent_result in swarm_result.results.items():
            extracted = _extract_from_agent_result(agent_result, name, tool_name)
            if extracted:
                logger.debug(
                    "[_extract] Found valid output from agent %s (fallback iteration)",
                    name,
                )
                return extracted

    # -------------------------------------------------------------------------
    # Priority 2: Extract from entry_point messages (fallback)
    # Used when Swarm returns natural language with embedded tool_result
    # -------------------------------------------------------------------------
    if hasattr(swarm_result, "entry_point") and swarm_result.entry_point:
        if hasattr(swarm_result.entry_point, "messages"):
            extracted = _extract_from_messages(swarm_result.entry_point.messages, tool_name)
            if extracted:
                return extracted

    # -------------------------------------------------------------------------
    # Priority 3: Direct message attribute
    # Some Swarm results have a direct .message property with JSON
    # -------------------------------------------------------------------------
    if hasattr(swarm_result, "message") and swarm_result.message and isinstance(swarm_result.message, str):
        # BUG-037 FIX: Use ensure_dict() for guaranteed STRING→DICT conversion
        data = ensure_dict(swarm_result.message, "swarm_direct_message")
        if data and not data.get("_raw_string"):  # Valid JSON was parsed
            logger.debug("[_extract] Found JSON in direct message attribute")
            return data

    logger.debug(
        "[_extract] No valid structured output found in swarm result for agent=%s tool=%s",
        agent_name,
        tool_name,
    )
    return None


def _extract_from_agent_result(
    agent_result: Any,
    agent_name: str,
    tool_name: str,
) -> Optional[Dict]:
    """
    Extract structured data from a single agent's result (AgentResult object).

    BUG-020 v8 FIX: Priority order for extraction:
    1. AgentResult.result.message (v8 - CORRECT path for AgentResult containing AgentResult)
    2. AgentResult.message (v8 - CORRECT path for direct AgentResult)
    3. AgentResult.result as dict (fallback for tools returning raw dicts)
    4. ToolResult format unwrapping (handles BUG-015 format)

    Official Strands AgentResult structure:
    - .message → Contains tool output (JSON string or Message object)
    - .stop_reason, .metrics, .state → Metadata (not useful for extraction)
    - .structured_output → May contain Pydantic model (rarely used)
    """
    # BUG-020 v8: Enhanced diagnostic logging
    logger.info(
        "[_extract_agent] agent=%s, has_result=%s, has_message=%s, result_type=%s",
        agent_name,
        hasattr(agent_result, "result"),
        hasattr(agent_result, "message"),
        type(agent_result.result).__name__ if hasattr(agent_result, "result") and agent_result.result else "None",
    )

    # BUG-021 v17: FULL INSPECTION for debugging extraction failures
    # This logs the complete structure to help identify why extraction fails
    try:
        attrs = [a for a in dir(agent_result) if not a.startswith("_")][:15]
        msg_type = type(agent_result.message).__name__ if hasattr(agent_result, "message") else "N/A"
        msg_preview = str(agent_result.message)[:500] if hasattr(agent_result, "message") and agent_result.message else "EMPTY"
        logger.info(
            "agent_result FULL INSPECTION: "
            "type=%s, attrs=%s, message_type=%s, message_preview=%s",
            type(agent_result).__name__,
            attrs,
            msg_type,
            msg_preview,
        )
    except Exception as e:
        logger.warning("Failed to inspect agent_result: %s", e)
        # ADR-004: Send to Debug Agent
        debug_error(e, "inspect_agent_result", {"agent_name": agent_name, "tool_name": tool_name})

    # =========================================================================
    # BUG-035 FIX: Priority 0 — structured_output (HIGHEST PRIORITY)
    # =========================================================================
    # AUDIT-001 mandated all agents use structured_output_model for Pydantic
    # validation. Strands SDK stores the validated result in .structured_output.
    # This MUST be checked FIRST as it's the official Strands pattern.
    # Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/
    # =========================================================================
    if hasattr(agent_result, "structured_output") and agent_result.structured_output:
        structured = agent_result.structured_output
        logger.info(
            "[_extract_agent] BUG-035: Found structured_output, type=%s",
            type(structured).__name__,
        )
        # Convert Pydantic model to dict (Pydantic v2 uses model_dump, v1 uses dict)
        data = None
        if hasattr(structured, "model_dump"):
            data = structured.model_dump()
        elif hasattr(structured, "dict"):
            data = structured.dict()  # Pydantic v1 fallback
        elif isinstance(structured, dict):
            data = structured

        if data and isinstance(data, dict):
            logger.info(
                "[_extract_agent] BUG-035 SUCCESS: Extracted from structured_output, keys=%s",
                list(data.keys())[:8],
            )
            return data
        else:
            logger.warning(
                "[_extract_agent] BUG-035: structured_output exists but could not convert to dict"
            )

    # =========================================================================
    # BUG-021 v4 FIX: Priority 1 — Direct .result access (OFFICIAL STRANDS PATTERN)
    # =========================================================================
    # Official Strands docs: result.results["agent"].result → Direct tool output
    # Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/
    #
    # Check if agent_result.result IS the raw tool output dict directly.
    # This aligns with: analyst_result = result.results["analyst"].result
    # =========================================================================
    if hasattr(agent_result, "result") and agent_result.result:
        result_data = agent_result.result

        # If result is already a dict with our expected keys, return it directly
        if isinstance(result_data, dict):
            if "analysis" in result_data or "success" in result_data:
                logger.info(
                    "BUG-021 v4 OFFICIAL PATTERN: Direct .result access SUCCESS! "
                    "keys=%s",
                    list(result_data.keys())[:5],
                )
                return result_data

            # Check for _response wrapper (tool_name_response format)
            from_wrapper = _extract_from_response_wrapper(result_data)
            if from_wrapper:
                logger.info("SUCCESS via _response wrapper in .result")
                return from_wrapper

    # =========================================================================
    # BUG-020 v8 FIX: Priority 1 — Extract from .message attribute
    # =========================================================================
    # CloudWatch logs revealed: AgentResult has .message, NOT nested .result!
    # The .message attribute contains tool output as JSON string.
    # =========================================================================

    # Priority 1a: Check if agent_result.result is an AgentResult with .message
    if hasattr(agent_result, "result") and agent_result.result:
        inner_result = agent_result.result

        # If inner_result is an AgentResult (has .message), extract from it
        if hasattr(inner_result, "message") and inner_result.message:
            logger.info(
                "[_extract_agent] v8: inner_result has .message, attempting extraction"
            )
            extracted = _extract_from_agent_message(inner_result.message)
            if extracted:
                logger.info(
                    "[_extract_agent] v8: SUCCESS from inner_result.message for agent=%s",
                    agent_name,
                )
                return extracted

    # Priority 1b: Check if agent_result itself has .message
    if hasattr(agent_result, "message") and agent_result.message:
        logger.info(
            "[_extract_agent] v8: agent_result has .message, attempting extraction"
        )
        extracted = _extract_from_agent_message(agent_result.message)
        if extracted:
            logger.info(
                "[_extract_agent] v8: SUCCESS from agent_result.message for agent=%s",
                agent_name,
            )
            return extracted

    # =========================================================================
    # Priority 2: Fallback to .result as dict (for tools returning raw dicts)
    # =========================================================================

    if not hasattr(agent_result, "result") or not agent_result.result:
        logger.warning("[_extract_agent] agent=%s has NO result attribute!", agent_name)
        return None

    result_data = agent_result.result

    # Handle string JSON (LLM may return JSON as string)
    # BUG-037 FIX: Use ensure_dict() for guaranteed STRING→DICT conversion
    if isinstance(result_data, str):
        result_data = ensure_dict(result_data, f"agent_{agent_name}_result")
        if result_data.get("_raw_string"):
            logger.debug(
                "[_extract] Agent %s result is non-JSON string, skipping",
                agent_name,
            )
            return None

    # =========================================================================
    # BUG-020 v16 FIX: Handle nested AgentResult recursively
    # =========================================================================
    # Strands Swarm may return nested AgentResult structures:
    # result.results["agent"] = AgentResult where .result is ANOTHER AgentResult
    # When this happens, we need to recursively extract from the inner AgentResult.
    # =========================================================================
    if hasattr(result_data, "result") or hasattr(result_data, "message"):
        logger.info(
            "result_data is AgentResult (nested), type=%s, recursively extracting",
            type(result_data).__name__,
        )
        nested_extraction = _extract_from_agent_result(result_data, agent_name + "_nested", "unified_analyze_file")
        if nested_extraction:
            logger.info("SUCCESS: Extracted from nested AgentResult for agent=%s", agent_name)
            return nested_extraction

    # If result_data is not a dict at this point, we can't extract
    if not isinstance(result_data, dict):
        # Log available attributes for debugging
        logger.warning(
            "[_extract_agent] agent=%s result_data is NOT a dict! type=%s, attrs=%s",
            agent_name,
            type(result_data).__name__,
            [a for a in dir(result_data) if not a.startswith("_")][:10] if hasattr(result_data, "__dir__") else "N/A",
        )
        return None

    # =========================================================================
    # Priority 3: Unwrap ToolResult format (handles BUG-015 format)
    # =========================================================================

    unwrapped = _unwrap_tool_result(result_data)
    if unwrapped:
        logger.debug(
            "[_extract] Found valid result from agent %s via unwrap",
            agent_name,
        )
        return unwrapped

    # =========================================================================
    # Priority 4: Text content in ToolResult format
    # =========================================================================

    if "content" in result_data and isinstance(result_data["content"], list):
        for content_item in result_data["content"]:
            if isinstance(content_item, dict) and "text" in content_item:
                try:
                    text_data = json.loads(content_item["text"])
                    if isinstance(text_data, dict) and ("analysis" in text_data or "success" in text_data):
                        logger.debug(
                            "[_extract] Parsed JSON from text content, agent %s",
                            agent_name,
                        )
                        return text_data
                except json.JSONDecodeError as e:
                    # ADR-004: Send to Debug Agent
                    debug_json_error(e, "json_parse_text_content_item", content_item.get("text", ""))

    return None


def _extract_from_messages(messages: list, tool_name: str) -> Optional[Dict]:
    """
    Extract structured data from entry_point messages.

    Searches for tool_result blocks in message history.
    Handles both direct JSON and ToolResult format (BUG-020 v4 fix).
    """
    for msg in reversed(messages if isinstance(messages, list) else []):
        # Handle dict-style messages
        if isinstance(msg, dict):
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        block_content = block.get("content", "")
                        try:
                            data = json.loads(block_content) if isinstance(block_content, str) else block_content
                            # BUG-020 v4 FIX: Use helper to handle ToolResult format
                            unwrapped = _unwrap_tool_result(data)
                            if unwrapped:
                                logger.debug("[_extract] Found JSON in tool_result block")
                                return unwrapped
                        except (json.JSONDecodeError, TypeError) as e:
                            # ADR-004: Send to Debug Agent
                            if isinstance(block_content, str):
                                debug_json_error(e, "json_parse_tool_result_block", block_content)
                            continue

        # Handle object-style messages
        if hasattr(msg, "content") and msg.content:
            try:
                data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                # BUG-020 v4 FIX: Use helper to handle ToolResult format
                unwrapped = _unwrap_tool_result(data)
                if unwrapped:
                    logger.debug("[_extract] Found JSON in entry_point messages")
                    return unwrapped
            except (json.JSONDecodeError, TypeError) as e:
                # ADR-004: Send to Debug Agent
                if hasattr(msg, "content") and isinstance(msg.content, str):
                    debug_json_error(e, "json_parse_entry_point_msg", msg.content)
                continue

    return None


def _process_swarm_result(
    swarm_result: Any,
    session: Dict,
    action: str = "",
) -> Dict:
    """
    Process Swarm result and update session context.

    This function:
    1. Extracts structured data from the Swarm result
    2. Updates session context with analysis data, mappings, questions
    3. Returns a standardized response dict

    Priority order for extraction:
    1. Use results dict first (most reliable - official Strands pattern)
    2. Fall back to message JSON
    3. Extract JSON from natural language text
    4. Store raw message as fallback

    Args:
        swarm_result: Result from swarm() invocation
        session: Session dict to update with context (modified in-place)
        action: Action name for logging/tracking

    Returns:
        Processed response dict with at minimum:
        - success: bool
        - action: str
        - session_id: str
        Plus any extracted data (analysis, column_mappings, questions, etc.)

    Example:
        >>> session = {"context": {}, "awaiting_response": False}
        >>> result = swarm("Analyze inventory.csv")
        >>> response = _process_swarm_result(result, session, action="analyze_file")
        >>> print(response["success"])
        True
    """
    response = {
        "success": False,
        "action": action,
        "session_id": session.get("session_id", ""),
    }

    # Ensure session has context dict
    if "context" not in session:
        session["context"] = {}

    # -------------------------------------------------------------------------
    # Try structured extraction first (most reliable - official Strands pattern)
    # -------------------------------------------------------------------------
    extracted = _extract_tool_output_from_swarm_result(swarm_result)
    if extracted:
        _safe_response_update(response, extracted)

        # BUG-022 v11 DEBUG: Log what keys were extracted to help diagnose missing data
        logger.info(
            "[BUG-022 v11] Extracted keys: %s, has_analysis=%s, has_sheets=%s",
            list(extracted.keys())[:10] if extracted else "NONE",
            "analysis" in extracted,
            "sheets" in extracted,
        )

        # BUG-022 v9 FIX: SAFE boolean normalization - default to FALSE not TRUE
        # If success key is missing, we cannot assume success - that masks failures
        raw_success = extracted.get("success")
        if raw_success is None:
            # No success field - check if there's an error to determine status
            has_error = bool(extracted.get("error"))
            response["success"] = not has_error
            logger.warning(
                "[BUG-022 v9] Response missing 'success' field, inferred %s based on error presence",
                response["success"]
            )
        elif isinstance(raw_success, str):
            # BUG-022 v10 FIX: Unwrap double-encoded success BEFORE comparison
            # TIMING BUG: Previous fix (lines 1280-1293) ran AFTER this comparison
            # If raw_success is '"true"', .lower() preserves quotes: '"true"'.lower() = '"true"'
            # Then '"true"' in ("true", "1", "yes", "t") = False (WRONG!)
            success_str = raw_success
            if success_str.startswith('"') and success_str.endswith('"'):
                try:
                    unwrapped = json.loads(success_str)
                    if isinstance(unwrapped, str):
                        success_str = unwrapped
                        logger.info("[BUG-022 v10] Unwrapped double-encoded success: '%s' → '%s'", raw_success, success_str)
                except json.JSONDecodeError as e:
                    # ADR-004: Send to Debug Agent
                    debug_json_error(e, "json_parse_double_encoded_success", success_str)
            response["success"] = success_str.lower() in ("true", "1", "yes", "t")
            logger.info("[BUG-022 v10] Normalized string success: '%s' → %s", raw_success, response["success"])
        elif isinstance(raw_success, bool):
            response["success"] = raw_success
        else:
            # Unknown type - default to False for safety
            response["success"] = False
            logger.warning("[BUG-022 v9] Unknown success type %s, defaulting to False", type(raw_success).__name__)
        # BUG-021 FIX: Explicitly preserve error field if present
        # This ensures error messages from Gemini/tools reach the frontend
        if "error" in extracted and extracted["error"]:
            response["error"] = extracted["error"]
            logger.info("[_process] BUG-021: Preserved error field: %s", extracted["error"][:100] if len(extracted["error"]) > 100 else extracted["error"])

        # BUG-022 FIX: Detect and unwrap double-encoded JSON strings
        # Double-encoding happens when A2A client or model returns JSON string that gets re-serialized
        # Pattern: '"success"' (a JSON-encoded string containing a JSON string)
        # BUG-022 v8 FIX: Added "success" to the list (was missing, causing persistent bug)
        for key in ["error", "message", "response", "success"]:
            if key in extracted and isinstance(extracted[key], str):
                val = extracted[key]
                # Check for double-encoded pattern (JSON string containing JSON)
                if val.startswith('"') and val.endswith('"'):
                    try:
                        unwrapped = json.loads(val)
                        if isinstance(unwrapped, str):
                            extracted[key] = unwrapped
                            if key in response:
                                response[key] = unwrapped
                            logger.info("[_process] BUG-022: Unwrapped double-encoded %s: %s...", key, unwrapped[:50] if len(unwrapped) > 50 else unwrapped)
                    except json.JSONDecodeError:
                        pass

        # Update session context with extracted data
        # Use the SAME keys as extracted (analysis, proposed_mappings, etc.)
        if "analysis" in extracted:
            session["context"]["analysis"] = extracted["analysis"]
            logger.debug("[_process] Updated session with analysis")

        if "proposed_mappings" in extracted:
            session["context"]["proposed_mappings"] = extracted["proposed_mappings"]
            logger.debug("[_process] Updated session with proposed_mappings")

        if "column_mappings" in extracted:
            session["context"]["proposed_mappings"] = extracted["column_mappings"]
            logger.debug("[_process] Updated session with column_mappings -> proposed_mappings")

        if "unmapped_columns" in extracted:
            session["context"]["unmapped_columns"] = extracted["unmapped_columns"]
            logger.debug("[_process] Updated session with unmapped_columns")

        if "questions" in extracted:
            session["context"]["hil_questions"] = extracted["questions"]
            if extracted["questions"]:
                session["awaiting_response"] = True
                logger.debug("[_process] Set awaiting_response=True (HIL questions)")

        # BUG-034 FIX: Use finalize gate instead of direct normalize
        # This ensures Debug Agent is invoked for ALL error responses
        return _finalize_response(response, action, session, swarm_result)

    # -------------------------------------------------------------------------
    # Fallback: Try to extract JSON from message text
    # -------------------------------------------------------------------------
    if hasattr(swarm_result, "message") and swarm_result.message and isinstance(swarm_result.message, str):
        message = swarm_result.message

        # Try direct JSON parse
        try:
            data = json.loads(message)
            _safe_response_update(response, data)
            # BUG-022 v9 FIX: Don't hardcode success=True - check actual data
            response["success"] = data.get("success", not bool(data.get("error")))
            logger.debug("[_process] Extracted JSON from message directly, success=%s", response["success"])
            # BUG-034 FIX: Use finalize gate
            return _finalize_response(response, action, session, swarm_result)
        except json.JSONDecodeError as e:
            # ADR-004: Send to Debug Agent
            debug_json_error(e, "json_parse_swarm_message_direct", message)

        # Try to find JSON block in text (LLM sometimes wraps JSON in explanation)
        json_match = re.search(r'\{[\s\S]*\}', message)
        if json_match:
            try:
                data = json.loads(json_match.group())
                _safe_response_update(response, data)
                # BUG-022 v9 FIX: Don't hardcode success=True - check actual data
                response["success"] = data.get("success", not bool(data.get("error")))
                logger.debug("[_process] Extracted JSON block from message text, success=%s", response["success"])
                # BUG-034 FIX: Use finalize gate
                return _finalize_response(response, action, session, swarm_result)
            except json.JSONDecodeError as e:
                # ADR-004: Send to Debug Agent
                debug_json_error(e, "json_parse_regex_extracted_block", json_match.group())

        # Store raw message as fallback (at least preserve the response)
        # BUG-022 v9 FIX: Raw message fallback is NOT a success - we couldn't parse structured data
        response["message"] = message
        response["success"] = False
        response["error"] = "Não foi possível extrair dados estruturados da resposta"
        logger.warning("[_process] Stored raw message as fallback - marking as failure")

        # BUG-033 FIX: Capture Debug Agent analysis for parsing failure
        parse_failure = Exception(
            f"Failed to extract structured data from message. "
            f"Message length: {len(message) if message else 0}, "
            f"Contains JSON: {'{' in message and '}' in message if message else False}"
        )
        _capture_debug_analysis(
            parse_failure,
            "structured_data_extraction_failure",
            {
                "message_preview": message[:500] if message else None,
                "message_length": len(message) if message else 0,
                "action": action,
            },
            response,
            timeout=30.0,  # TIMEOUT-FIX: Maximum for Gemini 2.5 Pro + Thinking
        )

    # -------------------------------------------------------------------------
    # BUG-021 v4 FIX: Handle dict-style message (Official Strands format)
    # -------------------------------------------------------------------------
    # Official Strands docs: result.message["content"][0]["text"]
    # Message is a DICT with "content" key, NOT a string!
    # -------------------------------------------------------------------------
    if hasattr(swarm_result, "message") and swarm_result.message:
        message = swarm_result.message

        # Dict-style message (official format)
        if isinstance(message, dict):
            logger.info(
                "swarm_result.message is DICT (official format), keys=%s",
                list(message.keys())[:5],
            )

            # Check for direct data
            if "analysis" in message or "success" in message:
                _safe_response_update(response, message)
                response["success"] = message.get("success", not bool(message.get("error")))
                logger.info("SUCCESS: Direct dict message with analysis/success")
                # BUG-034 FIX: Use finalize gate
                return _finalize_response(response, action, session, swarm_result)

            # Check for content array (official format: message["content"][0]["text"])
            if "content" in message and isinstance(message["content"], list):
                for content_block in message["content"]:
                    if isinstance(content_block, dict) and "text" in content_block:
                        text_content = content_block["text"]
                        if isinstance(text_content, str):
                            # BUG-021 v5 FIX: Strip markdown fence before parsing
                            stripped_content = _strip_markdown_fence(text_content)
                            try:
                                data = json.loads(stripped_content)
                                # Direct data with analysis/success
                                if isinstance(data, dict) and ("analysis" in data or "success" in data):
                                    _safe_response_update(response, data)
                                    response["success"] = data.get("success", not bool(data.get("error")))
                                    logger.info("SUCCESS: Extracted from message.content[].text")
                                    # BUG-034 FIX: Use finalize gate
                                    return _finalize_response(response, action, session, swarm_result)

                                # BUG-021 v5: Handle _response wrapper (e.g., unified_analyze_file_response)
                                if isinstance(data, dict):
                                    from_wrapper = _extract_from_response_wrapper(data)
                                    if from_wrapper:
                                        _safe_response_update(response, from_wrapper)
                                        response["success"] = from_wrapper.get("success", not bool(from_wrapper.get("error")))
                                        logger.info("SUCCESS: Extracted via _response wrapper in message.content[].text")
                                        # BUG-034 FIX: Use finalize gate
                                        return _finalize_response(response, action, session, swarm_result)
                            except json.JSONDecodeError as e:
                                # ADR-004: Send to Debug Agent
                                debug_json_error(e, "json_parse_message_content_text_dict", stripped_content)
                                # Try ast.literal_eval for Python repr (single quotes)
                                try:
                                    data = ast.literal_eval(stripped_content)
                                    if isinstance(data, dict) and ("analysis" in data or "success" in data):
                                        _safe_response_update(response, data)
                                        response["success"] = data.get("success", not bool(data.get("error")))
                                        logger.info("SUCCESS: Extracted from message.content[].text (repr)")
                                        # BUG-034 FIX: Use finalize gate
                                        return _finalize_response(response, action, session, swarm_result)
                                except (ValueError, SyntaxError) as e2:
                                    # ADR-004: Send to Debug Agent
                                    debug_error(e2, "ast_literal_eval_message_content", {"text_preview": stripped_content[:500] if stripped_content else None})

            # Try _extract_from_agent_message for complex structures
            extracted = _extract_from_agent_message(message)
            if extracted:
                _safe_response_update(response, extracted)
                response["success"] = extracted.get("success", not bool(extracted.get("error")))
                logger.info("SUCCESS: Extracted via _extract_from_agent_message(dict)")
                # BUG-034 FIX: Use finalize gate
                return _finalize_response(response, action, session, swarm_result)

        # Message object (has .content attribute)
        elif hasattr(message, "content"):
            logger.info("swarm_result.message is Message object")
            extracted = _extract_from_agent_message(message)
            if extracted:
                _safe_response_update(response, extracted)
                response["success"] = extracted.get("success", not bool(extracted.get("error")))
                logger.info("SUCCESS: Extracted via _extract_from_agent_message(object)")
                # BUG-034 FIX: Use finalize gate
                return _finalize_response(response, action, session, swarm_result)

    # -------------------------------------------------------------------------
    # BUG-021 FIX: Fallback error when ALL extraction fails
    # BUG-034 FIX: Debug Agent invocation moved to _finalize_response()
    # -------------------------------------------------------------------------
    # When we reach here with success=False and no error field, extraction
    # failed completely. Add a fallback error for user visibility.
    # Debug Agent invocation is now handled by _finalize_response().
    # -------------------------------------------------------------------------
    if not response.get("success") and not response.get("error"):
        logger.warning(
            "[_process] BUG-021: Extraction failed completely, adding fallback error. "
            "swarm_result type=%s, has_results=%s",
            type(swarm_result).__name__,
            hasattr(swarm_result, "results") and bool(swarm_result.results),
        )
        # SCHEMA-FIX: Improved error message - more specific about extraction failure
        response["error"] = (
            "Erro na extração de dados. A resposta do agente não contém os campos "
            "esperados (analysis/success). Verifique os logs para mais detalhes."
        )

    # BUG-034 FIX: Final gate handles normalization + Debug Agent invocation
    return _finalize_response(response, action, session, swarm_result)
