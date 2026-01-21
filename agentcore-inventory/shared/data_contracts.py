# =============================================================================
# Data Contract Enforcement for A2A Protocol
# =============================================================================
# This module is the SINGLE SOURCE OF TRUTH for data type conversions in the
# A2A (Agent-to-Agent) communication protocol.
#
# ROOT CAUSE OF BUG-032 to BUG-036 (5 days of bugs):
# - A2A Protocol returns `result.response` as STRING JSON, not DICT
# - Multiple parts of the codebase assumed DICT, causing silent failures
#
# SOLUTION:
# - ALL data transformations MUST go through these functions
# - Never use `json.loads()` directly on A2A responses - use `ensure_dict()`
# - Never assume types - always validate/convert
#
# AUDIT-001 NOTE (2026-01-20):
# After implementing Strands Structured Output across all agents, this module
# remains necessary ONLY for A2A protocol responses. For DIRECT agent calls,
# prefer `result.structured_output` instead of `ensure_dict()`.
#
# Use ensure_dict() for:
# - A2A client responses: `ensure_dict(a2a_client.invoke(...).response)`
# - External API responses
# - Legacy code paths not yet migrated
#
# DO NOT use ensure_dict() for:
# - Direct agent invocations: Use `result.structured_output` instead
# - See ADR-005 and shared/agent_schemas.py for the correct pattern
#
# Reference:
# - ADR-004: Global error capture pattern
# - ADR-005: Strands Structured Output Compliance (AUDIT-001)
# - BUG-032 to BUG-036: Data format consistency issues
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Core Conversion Functions
# =============================================================================

def ensure_dict(data: Union[str, Dict, Any], context: str = "") -> Dict[str, Any]:
    """
    Ensure data is a dict, parsing from JSON string if needed.

    This is the SINGLE SOURCE OF TRUTH for STRING → DICT conversion.
    Use this function whenever receiving data from A2A protocol.

    Args:
        data: Data that may be STRING (JSON), DICT, or other type
        context: Context string for logging (e.g., "debug_analysis", "a2a_response")

    Returns:
        Dict[str, Any] - Always returns a dict, never raises exceptions

    Behavior:
        - None → {}
        - {} → {} (passthrough)
        - '{"key": "value"}' → {"key": "value"} (parsed)
        - '' or '   ' → {}
        - 'invalid json' → {"_raw_string": "invalid json"}
        - non-dict JSON (e.g., '[1,2,3]') → {"_raw_value": [1,2,3]}
        - other types → {"_raw_value": <value>}

    Example:
        # A2A response handling
        result = await client.invoke_agent("debug", payload)
        analysis = ensure_dict(result.response, "debug_agent_response")
        # analysis is GUARANTEED to be a dict

    Note:
        This function is designed to NEVER raise exceptions.
        It always returns a valid dict, even for malformed input.
    """
    if data is None:
        return {}

    if isinstance(data, dict):
        return data

    if isinstance(data, str):
        # Empty or whitespace-only string
        if not data.strip():
            return {}

        try:
            parsed = json.loads(data)

            if isinstance(parsed, dict):
                if context:
                    logger.debug(f"[data_contracts] Parsed STRING to DICT for {context}")
                return parsed

            # JSON parsed successfully but result is not a dict (e.g., list, int, etc.)
            logger.warning(
                f"[data_contracts] JSON parsed but not dict for {context}: "
                f"type={type(parsed).__name__}"
            )
            return {"_raw_value": parsed}

        except json.JSONDecodeError as e:
            # Invalid JSON string - wrap it for debugging
            logger.warning(
                f"[data_contracts] JSON parse failed for {context}: {e}"
            )
            return {"_raw_string": data}

    # Unexpected type (int, list, etc.) - wrap it
    logger.warning(
        f"[data_contracts] Unexpected type for {context}: {type(data).__name__}"
    )
    return {"_raw_value": data}


def ensure_string(data: Union[str, Dict, Any], context: str = "") -> str:
    """
    Ensure data is a JSON string, serializing from dict if needed.

    This is the SINGLE SOURCE OF TRUTH for DICT → STRING conversion.
    Use this function when sending data to A2A protocol or storing as JSON.

    Args:
        data: Data that may be STRING, DICT, or other type
        context: Context string for logging

    Returns:
        str - Always returns a valid JSON string, never raises exceptions

    Behavior:
        - None → "{}"
        - '{"key": "value"}' → '{"key": "value"}' (passthrough)
        - {"key": "value"} → '{"key": "value"}' (serialized)
        - other types → '{"_raw_value": <serialized>}'

    Example:
        # Sending data via A2A
        payload_str = ensure_string(payload_dict, "a2a_request")
    """
    if data is None:
        return "{}"

    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        try:
            return json.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.warning(f"[data_contracts] Dict serialization failed for {context}: {e}")
            return json.dumps({"_serialization_error": str(e)})

    # Try to serialize any other type
    try:
        return json.dumps({"_raw_value": data}, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.warning(f"[data_contracts] Value serialization failed for {context}: {e}")
        return json.dumps({"_raw_value": str(data)})


# =============================================================================
# Response Validation Functions
# =============================================================================

def validate_response_format(
    response: Union[str, Dict, Any],
    context: str = ""
) -> Dict[str, Any]:
    """
    Validate and normalize response format for frontend consumption.

    Ensures:
    - Response is a dict
    - "success" is boolean (not string "true"/"false")
    - "error" is string or None (not other types)
    - "debug_analysis" is dict (if present)

    Args:
        response: Response that may be STRING, DICT, or other type
        context: Context string for logging

    Returns:
        Dict[str, Any] - Normalized response with correct types

    Example:
        # Before returning to frontend
        response = validate_response_format(raw_response, "nexo_analyze_file")
        return response  # Guaranteed correct types
    """
    # First ensure it's a dict
    if not isinstance(response, dict):
        response = ensure_dict(response, context)

    # Normalize "success" field - MUST be boolean
    success = response.get("success")
    if isinstance(success, str):
        response["success"] = success.lower() in ("true", "1", "yes")
    elif not isinstance(success, bool):
        # Default to False for safety if success is not boolean
        response["success"] = False

    # Normalize "error" field - MUST be string or None
    error = response.get("error")
    if error is not None and not isinstance(error, str):
        response["error"] = str(error)

    # Normalize "debug_analysis" field - MUST be dict
    if "debug_analysis" in response:
        response["debug_analysis"] = ensure_dict(
            response["debug_analysis"],
            f"{context}.debug_analysis"
        )

    return response


def validate_a2a_response(
    response: Any,
    expected_fields: List[str] = None,
    context: str = ""
) -> Dict[str, Any]:
    """
    Validate A2A protocol response with expected fields check.

    Use this for more strict validation when you know exactly what
    fields should be present in the response.

    Args:
        response: Raw A2A response (usually STRING)
        expected_fields: List of fields that MUST be present
        context: Context string for logging

    Returns:
        Dict with:
        - All fields from response (normalized)
        - "_validation_warnings": List of missing expected fields (if any)

    Example:
        result = validate_a2a_response(
            a2a_result.response,
            expected_fields=["technical_explanation", "root_causes"],
            context="debug_analysis"
        )
        if result.get("_validation_warnings"):
            logger.warning(f"Missing fields: {result['_validation_warnings']}")
    """
    # First convert to dict
    data = ensure_dict(response, context)

    # Check expected fields
    if expected_fields:
        missing = [f for f in expected_fields if f not in data]
        if missing:
            data["_validation_warnings"] = missing
            logger.warning(
                f"[data_contracts] Missing expected fields for {context}: {missing}"
            )

    return data


# =============================================================================
# Specialized Debug Agent Functions
# =============================================================================

def normalize_debug_analysis(
    analysis: Union[str, Dict, Any],
    context: str = "debug_analysis"
) -> Dict[str, Any]:
    """
    Normalize Debug Agent analysis response.

    This function is specifically designed for Debug Agent responses,
    which have a known schema. It ensures all expected fields are present
    with sensible defaults.

    Args:
        analysis: Raw analysis from Debug Agent (usually STRING from A2A)
        context: Context string for logging

    Returns:
        Dict with normalized Debug Agent analysis

    Expected Debug Agent Schema:
        {
            "error_type": str,
            "technical_explanation": str,
            "root_causes": List[Dict],
            "debugging_steps": List[str],
            "documentation_links": List[str],
            "similar_patterns": List[str],
            "recoverable": bool,
            "suggested_action": str
        }
    """
    # Convert to dict
    data = ensure_dict(analysis, context)

    # Provide defaults for expected fields
    defaults = {
        "error_type": "Unknown",
        "technical_explanation": "",
        "root_causes": [],
        "debugging_steps": [],
        "documentation_links": [],
        "similar_patterns": [],
        "recoverable": False,
        "suggested_action": "investigate",
    }

    # Merge with defaults (data takes precedence)
    result = {**defaults, **data}

    # Ensure root_causes is a list
    if not isinstance(result["root_causes"], list):
        result["root_causes"] = [result["root_causes"]] if result["root_causes"] else []

    # Ensure debugging_steps is a list
    if not isinstance(result["debugging_steps"], list):
        result["debugging_steps"] = [result["debugging_steps"]] if result["debugging_steps"] else []

    # Ensure recoverable is boolean
    if not isinstance(result["recoverable"], bool):
        result["recoverable"] = str(result["recoverable"]).lower() in ("true", "1", "yes")

    return result


# =============================================================================
# Double-Encoding Detection & Fix
# =============================================================================

def fix_double_encoded_json(data: str, max_depth: int = 3) -> Union[str, Dict, Any]:
    """
    Detect and fix double-encoded JSON strings.

    Sometimes data gets double-encoded (JSON string within JSON string).
    Example: '"{\\"key\\": \\"value\\"}"' → {"key": "value"}

    This was a contributing factor to BUG-022.

    Args:
        data: Potentially double-encoded string
        max_depth: Maximum levels of encoding to unwrap (default 3)

    Returns:
        The innermost parsed value (dict, list, or original string)

    Example:
        # Double-encoded JSON
        raw = '"{\\"success\\": true}"'
        result = fix_double_encoded_json(raw)
        # result = {"success": True}
    """
    if not isinstance(data, str):
        return data

    result = data
    for _ in range(max_depth):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, str):
                # Still a string - might be double-encoded, continue
                result = parsed
                continue
            else:
                # Not a string - we're done
                return parsed
        except json.JSONDecodeError:
            # Can't parse further - return what we have
            break

    return result


# =============================================================================
# Type Checking Utilities
# =============================================================================

def is_json_string(data: Any) -> bool:
    """
    Check if data is a valid JSON string (not just any string).

    Args:
        data: Value to check

    Returns:
        True if data is a string containing valid JSON
    """
    if not isinstance(data, str):
        return False

    try:
        json.loads(data)
        return True
    except json.JSONDecodeError:
        return False


def is_dict_like(data: Any) -> bool:
    """
    Check if data is dict-like (dict or JSON string containing dict).

    Args:
        data: Value to check

    Returns:
        True if data is a dict or a JSON string containing a dict
    """
    if isinstance(data, dict):
        return True

    if isinstance(data, str):
        try:
            return isinstance(json.loads(data), dict)
        except json.JSONDecodeError:
            return False

    return False
