# =============================================================================
# Debug Utils - Global Error Capture for Debug Agent (ADR-004)
# =============================================================================
# Provides global error capture functions for ALL Python try/catch blocks.
# This ensures 100% error visibility through the Debug Agent, regardless of
# where errors occur (LLM, agent lifecycle, or pure Python code).
#
# Usage in any try/catch block:
#   from shared.debug_utils import debug_error
#
#   try:
#       result = json.loads(data)
#   except json.JSONDecodeError as e:
#       debug_error(e, operation="json_parse", context={"data_preview": data[:200]})
#       # Continue with fallback...
#
# Architecture - Strands lifecycle hooks for debug capture:
# - DebugHook only captures Strands Agent lifecycle events (AfterToolCallEvent)
# - Pure Python try/catch blocks need a separate mechanism for Debug Agent
# - This module provides `debug_error()` to capture ALL errors globally
#
# Reference:
# - ADR-003: DebugHook for intelligent error analysis
# - ADR-004: Global error capture pattern (this module)
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a-protocol-contract.html
# =============================================================================

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

# Import ensure_dict for STRING→DICT conversion
# A2A protocol returns result.response as STRING JSON, not DICT
from shared.data_contracts import ensure_dict

logger = logging.getLogger(__name__)

# =============================================================================
# Singleton A2A Client (Lazy Initialization)
# =============================================================================
# Using singleton pattern to avoid creating multiple A2A clients which would
# each maintain their own credential cache and connection pools.

_debug_client = None
_client_lock = asyncio.Lock()


async def _get_debug_client():
    """
    Get or create singleton A2A client for Debug Agent communication.

    Uses lazy initialization with asyncio lock to ensure thread safety
    in async contexts. The client is cached globally to avoid overhead
    of credential refresh and connection pool creation.

    Returns:
        A2AClient instance
    """
    global _debug_client

    if _debug_client is not None:
        return _debug_client

    async with _client_lock:
        # Double-check after acquiring lock
        if _debug_client is None:
            from shared.strands_a2a_client import A2AClient
            _debug_client = A2AClient()
            logger.debug("[debug_utils] Created singleton A2A client")

        return _debug_client


# =============================================================================
# Async Error Capture Function
# =============================================================================

async def debug_error_async(
    error: Exception,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    severity: str = "error",
    timeout: float = 30.0,  # TIMEOUT-FIX: Maximum for Gemini 2.5 Pro with Thinking
) -> Dict[str, Any]:
    """
    Send error to Debug Agent for analysis (async version).

    AUDIT-003: This function ALWAYS logs locally first, then sends to Debug Agent.
    This ensures 100% error visibility in both:
    1. Local CloudWatch logs (immediate)
    2. Debug Agent analysis (enriched)

    NON-BLOCKING: Uses fire-and-forget pattern with configurable timeout.
    Returns enrichment result if available, empty dict on failure.

    This function should be called from ALL try/catch blocks in the codebase
    to ensure 100% error visibility through the Debug Agent (ADR-004).

    Args:
        error: The caught exception instance
        operation: Name of the operation that failed (e.g., "json_parse", "s3_upload")
        context: Optional additional context dict (file name, data preview, etc.)
        severity: Error severity level - "error", "warning", or "critical"
        timeout: Timeout in seconds (default 5s to avoid blocking)

    Returns:
        Dict with:
        - enriched: bool - Whether Debug Agent returned analysis
        - analysis: dict - Analysis result (if enriched=True)
        - reason: str - Failure reason (if enriched=False)

    Example:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as e:
            debug_error_async(
                e,
                "json_parse_gemini_response",
                {"text_preview": response_text[:500], "text_length": len(response_text)}
            )
            # Continue with fallback logic...
    """
    # AUDIT-003: ALWAYS log locally first (replaces logger.error in codebase)
    # This ensures the error appears in CloudWatch even if Debug Agent fails
    logger.error(
        f"[{operation}] {type(error).__name__}: {error}",
        exc_info=True,
    )

    try:
        # Build error payload for Debug Agent
        error_payload = {
            "action": "analyze_error",
            "error_type": type(error).__name__,
            "message": str(error),
            "operation": operation,
            "severity": severity,
            "recoverable": _is_recoverable_error(error),
            "context": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source": "python_exception",
                "stack_trace": traceback.format_exc(),
                **(context or {}),
            },
        }

        # Get or create singleton A2A client
        client = await _get_debug_client()

        # Invoke Debug Agent with timeout
        result = await asyncio.wait_for(
            client.invoke_agent("debug", error_payload, timeout=timeout),
            timeout=timeout + 1.0,  # asyncio timeout slightly higher than HTTP timeout
        )

        if result.success:
            logger.info(
                f"[debug_error] Enriched: {type(error).__name__} in {operation} "
                f"(severity={severity})"
            )
            # Convert STRING to DICT using data contract
            # A2A protocol returns result.response as STRING JSON, not DICT
            # This ensures debug_analysis is usable as a dict in frontend
            analysis_dict = ensure_dict(result.response, "debug_agent_response")
            return {
                "enriched": True,
                "analysis": analysis_dict,  # Now GUARANTEED to be a dict
                "agent_id": result.agent_id,
            }
        else:
            # Log at warning level for visibility in production monitoring
            logger.warning(
                f"[debug_error] Debug Agent call failed: {result.error}"
            )
            return {
                "enriched": False,
                "reason": result.error or "Unknown error",
            }

    except asyncio.TimeoutError:
        # Log at warning level for visibility in production monitoring
        logger.warning(
            f"[debug_error] Timeout ({timeout}s) sending {type(error).__name__} to Debug Agent"
        )
        return {"enriched": False, "reason": "timeout"}

    except Exception as e:
        # Catch-all to prevent debug_error from causing additional errors
        # Log at warning level for visibility in production monitoring
        logger.warning(f"[debug_error] Failed to send to Debug Agent: {e}")
        return {"enriched": False, "reason": str(e)}


# =============================================================================
# Sync Error Capture Function (Wrapper)
# =============================================================================
# Synchronous wrapper with timeout for Debug Agent invocation.
# This ensures the Debug Agent's analysis is RETURNED in the response flow,
# not lost in a background task.
# =============================================================================

def debug_error(
    error: Exception,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    severity: str = "error",
    timeout: float = 30.0,  # TIMEOUT-FIX: Maximum for Gemini 2.5 Pro with Thinking
) -> Dict[str, Any]:
    """
    Send error to Debug Agent for analysis and RETURN the result.

    AUDIT-003: This function REPLACES logger.error() across the codebase.
    It ALWAYS logs locally first, then sends to Debug Agent for enrichment.

    Waits for Debug Agent response instead of fire-and-forget. The analysis
    is returned in the response dict so it can be propagated to the frontend
    via response["debug_analysis"].

    This is the PRIMARY function to use in try/catch blocks. It handles
    all async/sync context detection automatically.

    Args:
        error: The caught exception instance
        operation: Name of the operation that failed (e.g., "json_parse", "s3_upload")
        context: Optional additional context dict
        severity: Error severity level - "error", "warning", or "critical"
        timeout: Timeout in seconds (default 5s)

    Returns:
        Dict with:
        - enriched: bool - Whether Debug Agent returned analysis
        - analysis: dict - Complete analysis from Debug Agent (if enriched=True)
        - agent_id: str - Debug Agent ID (if enriched=True)
        - reason: str - Failure reason (if enriched=False)

    Example:
        from shared.debug_utils import debug_error

        # AUDIT-028: Use enrichment result in error response
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.HTTPError as e:
            enrichment = debug_error(e, "http_request", {"url": url})
            analysis = enrichment.get("analysis", {}) if enrichment.get("enriched") else {}
            return {
                "success": False,
                "error": str(e),
                "human_explanation": analysis.get("human_explanation", "Erro na requisição HTTP."),
                "suggested_fix": analysis.get("suggested_fix", "Verifique a conexão e tente novamente."),
                "debug_analysis": analysis,
            }
    """
    try:
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already in async context - we need to await properly
            # Use run_coroutine_threadsafe to get result without blocking event loop
            import concurrent.futures

            # Run in thread pool to avoid blocking the event loop
            # but still get the result back synchronously
            future = asyncio.run_coroutine_threadsafe(
                debug_error_async(error, operation, context, severity, timeout),
                loop
            )

            try:
                # Wait with timeout to get the actual result
                result = future.result(timeout=timeout + 1.0)
                return result
            except concurrent.futures.TimeoutError:
                # Log at warning level for visibility in production monitoring
                logger.warning(
                    f"[debug_error] Timeout ({timeout}s) waiting for Debug Agent analysis"
                )
                return {"enriched": False, "reason": "timeout_sync"}
            except Exception as e:
                # Log at warning level for visibility in production monitoring
                logger.warning(f"[debug_error] Concurrent execution failed: {e}")
                return {"enriched": False, "reason": str(e)}

        else:
            # Sync context - run in new event loop
            # This blocks briefly, but timeout ensures bounded wait time
            return asyncio.run(
                debug_error_async(error, operation, context, severity, timeout)
            )

    except Exception as e:
        # Absolute last resort - never let debug_error fail the main code
        # Log at warning level for visibility in production monitoring
        logger.warning(f"[debug_error] Wrapper failed: {e}")
        return {"enriched": False, "reason": str(e)}


# =============================================================================
# Helper Functions
# =============================================================================

def _is_recoverable_error(error: Exception) -> bool:
    """
    Determine if an error is potentially recoverable.

    Recoverable errors are typically transient and may succeed on retry:
    - Network timeouts
    - Rate limiting (429)
    - Service unavailable (503)

    Non-recoverable errors require code/config changes:
    - Validation errors
    - Permission denied
    - Missing resources

    Args:
        error: The exception to analyze

    Returns:
        True if error is likely recoverable, False otherwise
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # Known recoverable error patterns
    recoverable_patterns = [
        "timeout",
        "timed out",
        "rate limit",
        "throttl",
        "too many requests",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "connection reset",
        "connection refused",
        "network unreachable",
        "temporary failure",
        "retry",
        "concurrency",
    ]

    # Known non-recoverable error types
    non_recoverable_types = {
        "ValidationError",
        "ValueError",
        "TypeError",
        "KeyError",
        "AttributeError",
        "ImportError",
        "ModuleNotFoundError",
        "PermissionError",
        "FileNotFoundError",
        "NotImplementedError",
    }

    # Check if error type is known non-recoverable
    if error_type in non_recoverable_types:
        return False

    # Check if error message contains recoverable patterns
    for pattern in recoverable_patterns:
        if pattern in error_msg:
            return True

    # Default to non-recoverable for safety
    return False


# =============================================================================
# Convenience Functions for Common Error Types
# =============================================================================

def debug_json_error(
    error: Exception,
    operation: str,
    json_text: str,
    max_preview: int = 500,
) -> Dict[str, Any]:
    """
    Convenience function for JSON parsing errors.

    Automatically includes relevant context for JSON parsing failures.

    Args:
        error: The JSON-related exception
        operation: Operation name (e.g., "parse_gemini_response")
        json_text: The text that failed to parse
        max_preview: Maximum characters to include in preview

    Returns:
        Debug error result
    """
    return debug_error(
        error,
        operation,
        context={
            "error_subtype": "json_parse",
            "text_preview": json_text[:max_preview] if json_text else None,
            "text_length": len(json_text) if json_text else 0,
            "text_ends_with": json_text[-100:] if json_text and len(json_text) > 100 else None,
        },
        severity="error",
    )


def debug_http_error(
    error: Exception,
    operation: str,
    url: str,
    status_code: Optional[int] = None,
    response_body: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function for HTTP request errors.

    Automatically includes relevant context for HTTP failures.

    Args:
        error: The HTTP-related exception
        operation: Operation name (e.g., "call_external_api")
        url: The URL that was being accessed
        status_code: HTTP status code if available
        response_body: Response body preview if available

    Returns:
        Debug error result
    """
    return debug_error(
        error,
        operation,
        context={
            "error_subtype": "http_request",
            "url": url,
            "status_code": status_code,
            "response_preview": response_body[:500] if response_body else None,
        },
        severity="error" if status_code and status_code >= 500 else "warning",
    )


def debug_aws_error(
    error: Exception,
    operation: str,
    service: str,
    resource: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function for AWS service errors.

    Automatically extracts botocore ClientError details.

    Args:
        error: The AWS-related exception
        operation: Operation name (e.g., "s3_put_object")
        service: AWS service name (e.g., "s3", "dynamodb")
        resource: Resource identifier if available

    Returns:
        Debug error result
    """
    context = {
        "error_subtype": "aws_service",
        "service": service,
        "resource": resource,
    }

    # Extract botocore ClientError details if available
    if hasattr(error, "response"):
        error_info = getattr(error, "response", {}).get("Error", {})
        context["aws_error_code"] = error_info.get("Code")
        context["aws_error_message"] = error_info.get("Message")

        http_status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        context["http_status"] = http_status

    return debug_error(
        error,
        operation,
        context=context,
        severity="critical" if "access" in str(error).lower() else "error",
    )
