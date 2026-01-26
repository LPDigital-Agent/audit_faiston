# =============================================================================
# Cognitive Error Handler - Nexo Immune System
# =============================================================================
# Global middleware that routes ALL agent errors to DebugAgent for enrichment.
# This creates a "Cognitive Immune System" where every error is analyzed,
# diagnosed, and returned with human-readable explanations.
#
# ARCHITECTURE (per CLAUDE.md):
# - AI-FIRST: Errors enriched by LLM (DebugAgent) not just logged
# - SANDWICH PATTERN: Code catches error → LLM analyzes → Code returns enriched
# - HIL FRIENDLY: Error messages are user-facing, not stack traces
#
# SAFETY:
# - Circuit breaker prevents cascade failures
# - DebugAgent self-errors bypass enrichment (prevents infinite loops)
# - Graceful degradation when DebugAgent unavailable
#
# Author: Faiston NEXO Team
# Date: January 2026
# =============================================================================

import asyncio
import functools
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from shared.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# Type variable for decorator return type preservation
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# CognitiveError Exception
# =============================================================================


@dataclass
class CognitiveError(Exception):
    """
    Enriched error with human-readable diagnosis from DebugAgent.

    This exception type indicates the error has been processed by the
    Nexo Immune System and contains actionable information for the user.

    Attributes:
        technical_message: Original error message (for logging)
        human_explanation: User-friendly explanation in pt-BR
        suggested_fix: Actionable fix suggestion in pt-BR
        original_exception: The underlying exception that was caught
        context: Additional context from the failed operation
        error_type: Classification of error type
        recoverable: Whether the operation can be retried
    """
    technical_message: str
    human_explanation: str = field(default="Ocorreu um erro durante o processamento.")
    suggested_fix: str = field(default="Tente novamente ou contate o suporte.")
    original_exception: Optional[Exception] = field(default=None)
    context: Optional[Dict[str, Any]] = field(default=None)
    error_type: str = field(default="UnknownError")
    recoverable: bool = field(default=False)

    def __post_init__(self):
        """Initialize the Exception base class with technical message."""
        super().__init__(self.technical_message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for API responses.
        """
        return {
            "error_type": self.error_type,
            "technical_message": self.technical_message,
            "human_explanation": self.human_explanation,
            "suggested_fix": self.suggested_fix,
            "recoverable": self.recoverable,
            "context": self.context,
        }

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self.human_explanation} | Sugestão: {self.suggested_fix}"


# =============================================================================
# Circuit Breaker Instance (Global for DebugAgent calls)
# =============================================================================

# Global circuit breaker for cognitive middleware
# - failure_threshold=3: Open circuit after 3 failures
# - reset_timeout=60.0: Try again after 60 seconds
_debug_circuit = CircuitBreaker(
    failure_threshold=3,
    reset_timeout=60.0,
    name="cognitive_middleware"
)


# =============================================================================
# DebugAgent Enrichment
# =============================================================================


async def _enrich_with_debug_agent(
    error: Exception,
    context: Dict[str, Any],
    timeout: float = 10.0
) -> Dict[str, Any]:
    """
    Call DebugAgent to enrich error with diagnosis.

    This function is the core of the Nexo Immune System. It sends
    error context to the DebugAgent which uses Gemini 2.5 Pro + Thinking
    to analyze root causes and suggest fixes.

    Args:
        error: The exception to analyze
        context: Additional context (operation, parameters, etc.)
        timeout: Maximum time to wait for DebugAgent response

    Returns:
        Dictionary with human_explanation, suggested_fix, and other analysis.
        Falls back to basic info if DebugAgent unavailable.
    """
    # Import here to avoid circular imports
    from shared.strands_a2a_client import A2AClient

    # Check circuit breaker
    if not _debug_circuit.can_execute():
        logger.warning(
            "[CognitiveMiddleware] Circuit open - DebugAgent unavailable. "
            "Returning degraded response."
        )
        return {
            "human_explanation": str(error),
            "suggested_fix": "Sistema de diagnóstico temporariamente indisponível. Tente novamente em breve.",
            "error_type": type(error).__name__,
            "recoverable": False,
        }

    try:
        client = A2AClient()

        # Build error payload for DebugAgent
        error_payload = {
            "action": "analyze_error",
            "error_message": str(error),
            "error_type": type(error).__name__,
            "stack_trace": traceback.format_exc(),
            "context": context,
        }

        # Call DebugAgent with timeout
        result = await asyncio.wait_for(
            client.invoke_agent(
                agent_id="debug",
                payload=error_payload,
                timeout=timeout,
            ),
            timeout=timeout + 2.0  # Extra buffer for network
        )

        if result.success:
            _debug_circuit.record_success()

            # Parse response
            import json
            try:
                analysis = json.loads(result.response)
                return {
                    "human_explanation": analysis.get(
                        "technical_explanation",
                        analysis.get("human_explanation", str(error))
                    ),
                    "suggested_fix": _extract_suggested_fix(analysis),
                    "error_type": analysis.get("error_type", type(error).__name__),
                    "recoverable": analysis.get("recoverable", False),
                    "root_causes": analysis.get("root_causes", []),
                    "debugging_steps": analysis.get("debugging_steps", []),
                }
            except json.JSONDecodeError:
                # Response wasn't JSON, use as-is
                return {
                    "human_explanation": result.response[:500] if result.response else str(error),
                    "suggested_fix": "Verifique os detalhes do erro acima.",
                    "error_type": type(error).__name__,
                    "recoverable": False,
                }
        else:
            _debug_circuit.record_failure()
            logger.warning(f"[CognitiveMiddleware] DebugAgent returned error: {result.error}")
            return _create_fallback_response(error)

    except asyncio.TimeoutError:
        _debug_circuit.record_failure()
        logger.warning("[CognitiveMiddleware] DebugAgent timed out")
        return _create_fallback_response(error)

    except Exception as e:
        _debug_circuit.record_failure()
        logger.warning(f"[CognitiveMiddleware] Error calling DebugAgent: {e}")
        return _create_fallback_response(error)


def _extract_suggested_fix(analysis: Dict[str, Any]) -> str:
    """
    Extract actionable fix suggestion from DebugAgent analysis.

    Looks for suggested_action, debugging_steps, or falls back to generic message.

    Args:
        analysis: DebugAgent analysis response

    Returns:
        User-friendly fix suggestion in pt-BR
    """
    # Check for explicit suggested action
    suggested = analysis.get("suggested_action", "")
    if suggested and suggested != "investigate":
        action_map = {
            "retry": "Tente executar a operação novamente.",
            "fallback": "Utilize um método alternativo.",
            "escalate": "Contate o suporte técnico.",
            "abort": "Cancele a operação e revise os dados.",
        }
        return action_map.get(suggested, suggested)

    # Check for debugging steps
    steps = analysis.get("debugging_steps", [])
    if steps:
        return steps[0]  # Return first step as suggestion

    # Fallback
    return "Verifique os dados de entrada e tente novamente."


def _create_fallback_response(error: Exception) -> Dict[str, Any]:
    """
    Create fallback response when DebugAgent is unavailable.

    Provides basic error information without LLM enrichment.

    Args:
        error: The original exception

    Returns:
        Basic error dictionary
    """
    error_type = type(error).__name__

    # Provide basic hints based on common error types
    hints = {
        "ValueError": "Verifique se os valores fornecidos estão no formato correto.",
        "TypeError": "Verifique os tipos de dados dos parâmetros.",
        "KeyError": "Um campo obrigatório está faltando nos dados.",
        "FileNotFoundError": "O arquivo especificado não foi encontrado.",
        "ConnectionError": "Erro de conexão. Verifique sua rede.",
        "TimeoutError": "A operação demorou muito. Tente novamente.",
        "PermissionError": "Sem permissão para executar esta operação.",
    }

    return {
        "human_explanation": str(error),
        "suggested_fix": hints.get(error_type, "Análise de erro não disponível no momento."),
        "error_type": error_type,
        "recoverable": error_type in ("ConnectionError", "TimeoutError"),
    }


async def _invoke_repair_agent(
    error: Exception,
    context: Dict[str, Any],
    debug_analysis: Dict[str, Any],
    session_id: Optional[str] = None,
    timeout: float = 120.0,  # 2 minutes for Git operations
) -> Dict[str, Any]:
    """
    Invoke RepairAgent to attempt automated fix.

    This function is called by cognitive_error_handler when DebugAgent
    returns suggested_action == "repair" in its analysis.

    Args:
        error: The original exception
        context: Error context from cognitive handler
        debug_analysis: DebugAgent analysis with root causes
        session_id: Session ID for tracing
        timeout: Max time for repair operations

    Returns:
        Repair result dict with fix_applied, pr_url, etc.
        {
            "fix_applied": bool,
            "branch_name": str | None,
            "pr_url": str | None,
            "error": str | None,
            ...
        }
    """
    from shared.strands_a2a_client import A2AClient

    try:
        client = A2AClient()

        # Build RepairAgent payload
        repair_payload = {
            "action": "apply_fix",
            "error_signature": debug_analysis.get("error_signature", ""),
            "error_type": debug_analysis.get("error_type", ""),
            "root_causes": debug_analysis.get("root_causes", []),
            "suggested_fix": debug_analysis.get("suggested_fix", ""),
            "file_context": context,
            "debug_analysis": debug_analysis,
        }

        logger.info(
            f"[CognitiveMiddleware] Invoking RepairAgent for error: "
            f"{debug_analysis.get('error_signature', 'unknown')}"
        )

        # Invoke RepairAgent
        result = await client.invoke_agent(
            agent_id="repair",
            payload=repair_payload,
            session_id=session_id,
            timeout=timeout,
        )

        if result.success:
            import json
            try:
                repair_result = json.loads(result.response)
                logger.info(
                    f"[CognitiveMiddleware] RepairAgent completed. "
                    f"Fix applied: {repair_result.get('fix_applied', False)}"
                )
                return repair_result
            except json.JSONDecodeError:
                logger.error(
                    f"[CognitiveMiddleware] RepairAgent returned invalid JSON: "
                    f"{result.response[:200]}"
                )
                return {
                    "fix_applied": False,
                    "error": "RepairAgent response was not valid JSON",
                }
        else:
            logger.warning(
                f"[CognitiveMiddleware] RepairAgent invocation failed: {result.error}"
            )
            return {
                "fix_applied": False,
                "error": result.error or "RepairAgent invocation failed",
            }

    except Exception as e:
        logger.error(f"[CognitiveMiddleware] Error invoking RepairAgent: {e}")
        return {
            "fix_applied": False,
            "error": str(e),
        }


# =============================================================================
# Cognitive Error Handler Decorator
# =============================================================================


def cognitive_error_handler(agent_id: str):
    """
    Decorator that wraps agent execution with DebugAgent enrichment.

    CRITICAL: If agent_id == "debug", skip enrichment to prevent infinite loops.

    This decorator is the main entry point for the Nexo Immune System.
    Wrap any async function that may fail with this decorator to get
    automatic error enrichment.

    Args:
        agent_id: ID of the agent being wrapped (e.g., "data_transformer")

    Returns:
        Decorated function that catches exceptions and enriches them

    Usage:
        @cognitive_error_handler("data_transformer")
        async def process_import(s3_key: str, mappings: list) -> dict:
            # Your code here
            pass

    Example:
        try:
            result = await process_import(s3_key, mappings)
        except CognitiveError as e:
            # e.human_explanation contains user-friendly message
            # e.suggested_fix contains actionable suggestion
            return {"error": e.to_dict()}
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)

            except CognitiveError:
                # Already a CognitiveError - re-raise as-is
                raise

            except Exception as e:
                # Prevent infinite loop - DebugAgent errors go through raw
                if agent_id == "debug":
                    logger.error(
                        f"[CognitiveMiddleware] DebugAgent error (not enriched to prevent loop): {e}"
                    )
                    raise

                # Build context from function arguments
                context = {
                    "agent_id": agent_id,
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                }

                # Add session_id if present in kwargs
                if "session_id" in kwargs:
                    context["session_id"] = kwargs["session_id"]

                logger.info(
                    f"[CognitiveMiddleware] Enriching error for {agent_id}: "
                    f"{type(e).__name__}: {str(e)[:100]}"
                )

                # Enrich error via DebugAgent
                enriched = await _enrich_with_debug_agent(e, context)

                # ============================================================
                # RepairAgent Trigger (BUG-044 Implementation)
                # ============================================================
                # If DebugAgent suggests repair, attempt automated fix
                suggested_action = enriched.get("suggested_action", "")

                if suggested_action == "repair":
                    logger.info(
                        f"[CognitiveMiddleware] DebugAgent suggested repair for {agent_id}. "
                        f"Invoking RepairAgent..."
                    )

                    # Invoke RepairAgent via A2A
                    repair_result = await _invoke_repair_agent(
                        error=e,
                        context=context,
                        debug_analysis=enriched,
                        session_id=kwargs.get("session_id"),
                    )

                    # If repair succeeded, include repair details in enriched error
                    if repair_result.get("fix_applied"):
                        enriched["repair_applied"] = True
                        enriched["repair_details"] = repair_result
                        logger.info(
                            f"[CognitiveMiddleware] RepairAgent successfully applied fix: "
                            f"PR {repair_result.get('pr_url')}"
                        )

                    else:
                        enriched["repair_applied"] = False
                        enriched["repair_error"] = repair_result.get("error")
                        logger.warning(
                            f"[CognitiveMiddleware] RepairAgent failed to apply fix: "
                            f"{repair_result.get('error')}"
                        )
                # ============================================================
                # END RepairAgent Trigger
                # ============================================================

                # Raise enriched error
                raise CognitiveError(
                    technical_message=str(e),
                    human_explanation=enriched.get("human_explanation", str(e)),
                    suggested_fix=enriched.get("suggested_fix", "Contate o suporte."),
                    original_exception=e,
                    context=enriched.get("context", context),
                    error_type=enriched.get("error_type", type(e).__name__),
                    recoverable=enriched.get("recoverable", False),
                )

        return cast(F, wrapper)
    return decorator


def cognitive_sync_handler(agent_id: str):
    """
    Synchronous version of cognitive_error_handler.

    For sync functions that need error enrichment, wraps them
    and runs the async enrichment in an event loop.

    Args:
        agent_id: ID of the agent being wrapped

    Returns:
        Decorated sync function

    Usage:
        @cognitive_sync_handler("data_transformer")
        def sync_process(data: dict) -> dict:
            # Your sync code here
            pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)

            except CognitiveError:
                raise

            except Exception as e:
                if agent_id == "debug":
                    raise

                context = {
                    "agent_id": agent_id,
                    "function": func.__name__,
                }

                # Run async enrichment in event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're in an async context - create task
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            enriched = pool.submit(
                                asyncio.run,
                                _enrich_with_debug_agent(e, context)
                            ).result(timeout=15.0)
                    else:
                        enriched = loop.run_until_complete(
                            _enrich_with_debug_agent(e, context)
                        )
                except Exception:
                    enriched = _create_fallback_response(e)

                raise CognitiveError(
                    technical_message=str(e),
                    human_explanation=enriched.get("human_explanation", str(e)),
                    suggested_fix=enriched.get("suggested_fix", "Contate o suporte."),
                    original_exception=e,
                    context=context,
                    error_type=enriched.get("error_type", type(e).__name__),
                    recoverable=enriched.get("recoverable", False),
                )

        return cast(F, wrapper)
    return decorator


# =============================================================================
# Batch Error Enrichment (Post-Processing Pattern)
# =============================================================================


async def enrich_batch_errors(
    errors: list,
    file_context: Dict[str, Any],
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Batch-enrich a list of errors with DebugAgent pattern analysis.

    This is used in the DataTransformer's post-processing phase:
    1. Collect all row errors during ETL
    2. Send a sample (first 100) to DebugAgent for pattern analysis
    3. DebugAgent identifies common patterns and suggests bulk fixes

    Args:
        errors: List of error dicts with row_number, column, value, raw_error
        file_context: Context about the file being processed (s3_key, mappings)
        timeout: Maximum time to wait for analysis

    Returns:
        Dictionary with:
        - pattern_summary: High-level summary of error patterns
        - enriched_errors: List of errors with human_explanation and suggested_fix
        - common_causes: List of common root causes across all errors
    """
    from shared.strands_a2a_client import A2AClient

    if not errors:
        return {
            "pattern_summary": "Nenhum erro encontrado.",
            "enriched_errors": [],
            "common_causes": [],
        }

    # Check circuit breaker
    if not _debug_circuit.can_execute():
        return _create_fallback_batch_response(errors)

    try:
        client = A2AClient()

        # Sample first 100 errors for pattern analysis
        sample_size = min(100, len(errors))
        sample_errors = errors[:sample_size]

        payload = {
            "action": "analyze_batch_errors",
            "errors": sample_errors,
            "total_error_count": len(errors),
            "file_context": file_context,
        }

        result = await asyncio.wait_for(
            client.invoke_agent(
                agent_id="debug",
                payload=payload,
                timeout=timeout,
            ),
            timeout=timeout + 5.0
        )

        if result.success:
            _debug_circuit.record_success()

            import json
            try:
                analysis = json.loads(result.response)
                return {
                    "pattern_summary": analysis.get(
                        "pattern_summary",
                        f"Encontrados {len(errors)} erros durante o processamento."
                    ),
                    "enriched_errors": _enrich_errors_with_patterns(
                        errors,
                        analysis.get("patterns", {})
                    ),
                    "common_causes": analysis.get("common_causes", []),
                }
            except json.JSONDecodeError:
                return _create_fallback_batch_response(errors)
        else:
            _debug_circuit.record_failure()
            return _create_fallback_batch_response(errors)

    except Exception as e:
        _debug_circuit.record_failure()
        logger.warning(f"[CognitiveMiddleware] Batch enrichment failed: {e}")
        return _create_fallback_batch_response(errors)


def _enrich_errors_with_patterns(
    errors: list,
    patterns: Dict[str, Any]
) -> list:
    """
    Apply pattern-based enrichment to individual errors.

    Args:
        errors: List of raw error dicts
        patterns: Pattern dict from DebugAgent with error_type → suggestion mappings

    Returns:
        List of enriched error dicts
    """
    enriched = []

    for error in errors:
        error_type = error.get("error_type", "Unknown")

        # Look up pattern
        pattern_info = patterns.get(error_type, {})

        enriched.append({
            **error,
            "human_explanation": pattern_info.get(
                "human_explanation",
                f"Erro ao processar valor: {error.get('raw_error', 'desconhecido')}"
            ),
            "suggested_fix": pattern_info.get(
                "suggested_fix",
                "Verifique o formato do valor e tente novamente."
            ),
        })

    return enriched


def _create_fallback_batch_response(errors: list) -> Dict[str, Any]:
    """
    Create fallback batch response when DebugAgent unavailable.

    Args:
        errors: List of raw errors

    Returns:
        Basic batch response with generic enrichment
    """
    enriched = []

    for error in errors:
        enriched.append({
            **error,
            "human_explanation": f"Erro ao processar linha {error.get('row_number', '?')}: {error.get('raw_error', 'desconhecido')}",
            "suggested_fix": "Verifique o formato do valor e tente novamente.",
        })

    return {
        "pattern_summary": f"Encontrados {len(errors)} erros. Análise detalhada não disponível.",
        "enriched_errors": enriched,
        "common_causes": [],
    }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CognitiveError",
    "cognitive_error_handler",
    "cognitive_sync_handler",
    "enrich_batch_errors",
]
