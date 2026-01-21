# =============================================================================
# X-Ray Tracer - Distributed Tracing for A2A Communication
# =============================================================================
# Provides decorators and utilities for X-Ray tracing of A2A calls.
# Enables distributed tracing across AgentCore Runtimes.
#
# Usage:
#   from shared.xray_tracer import trace_a2a_call, init_xray_tracing
#
#   init_xray_tracing()  # Call once at agent startup
#
#   @trace_a2a_call("learning")
#   async def delegate_to_learning(payload):
#       ...
#
# Architecture:
# - Uses AWS X-Ray SDK for Python
# - Creates subsegments for each A2A call
# - Annotates with target agent and session info
# - Patches httpx, boto3 for automatic instrumentation
#
# Reference:
# - https://docs.aws.amazon.com/xray/latest/devguide/xray-sdk-python.html
# =============================================================================

import os
import functools
from typing import Callable, Optional, Any
from contextlib import contextmanager

# Lazy imports for cold start optimization
_xray_recorder = None
_xray_patched = False


def _get_xray_recorder():
    """Lazy load X-Ray recorder."""
    global _xray_recorder
    if _xray_recorder is None:
        try:
            from aws_xray_sdk.core import xray_recorder
            _xray_recorder = xray_recorder
        except ImportError:
            # X-Ray SDK not installed, use no-op
            _xray_recorder = _NoOpRecorder()
    return _xray_recorder


class _NoOpRecorder:
    """No-op recorder when X-Ray SDK is not available."""

    def in_subsegment(self, name: str):
        return _NoOpContext()

    def begin_subsegment(self, name: str):
        return _NoOpSubsegment()

    def end_subsegment(self):
        pass

    def put_annotation(self, key: str, value: Any):
        pass

    def put_metadata(self, key: str, value: Any, namespace: str = "default"):
        pass


class _NoOpSubsegment:
    """No-op subsegment when X-Ray SDK is not available."""

    def put_annotation(self, key: str, value: Any):
        pass

    def put_metadata(self, key: str, value: Any, namespace: str = "default"):
        pass

    def add_exception(self, exception: Exception, stack: Any = None):
        pass


class _NoOpContext:
    """No-op context manager when X-Ray SDK is not available."""

    def __enter__(self):
        return _NoOpSubsegment()

    def __exit__(self, *args):
        pass


def init_xray_tracing(
    service_name: Optional[str] = None,
    patch_modules: bool = True
):
    """
    Initialize X-Ray tracing for the agent.

    Call this once at agent startup (in main.py).

    Args:
        service_name: Service name for X-Ray (default: agent ID from env)
        patch_modules: Whether to patch httpx, boto3, etc. for auto-instrumentation
    """
    global _xray_patched

    if _xray_patched:
        return

    try:
        from aws_xray_sdk.core import xray_recorder, patch_all

        # Configure recorder
        agent_id = os.environ.get("AGENT_ID", "unknown_agent")
        service = service_name or f"sga-{agent_id}"

        xray_recorder.configure(
            service=service,
            context_missing="LOG_ERROR",  # Don't fail if not in X-Ray context
            daemon_address=os.environ.get("AWS_XRAY_DAEMON_ADDRESS", "127.0.0.1:2000"),
        )

        # Patch modules for automatic instrumentation
        if patch_modules:
            patch_all()

        _xray_patched = True
        print(f"[X-Ray] Initialized tracing for service: {service}")

    except ImportError:
        print("[X-Ray] SDK not installed, tracing disabled")
    except Exception as e:
        print(f"[X-Ray] Failed to initialize: {e}")


def trace_a2a_call(target_agent: str):
    """
    Decorator to trace A2A calls with X-Ray.

    Creates a subsegment for the A2A call with annotations
    for the target agent.

    Args:
        target_agent: ID of the agent being called

    Example:
        @trace_a2a_call("learning")
        async def delegate_to_learning(payload, session_id=None):
            client = A2AClient()
            return await client.invoke_agent("learning", payload, session_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            recorder = _get_xray_recorder()

            with recorder.in_subsegment(f"A2A-{target_agent}") as subsegment:
                # Add annotations
                subsegment.put_annotation("target_agent", target_agent)
                subsegment.put_annotation("caller_agent", os.environ.get("AGENT_ID", "unknown"))

                # Add session ID if provided
                session_id = kwargs.get("session_id")
                if session_id:
                    subsegment.put_annotation("session_id", session_id)

                try:
                    result = await func(*args, **kwargs)

                    # Add success annotation
                    if hasattr(result, "success"):
                        subsegment.put_annotation("success", result.success)

                    return result

                except Exception as e:
                    subsegment.add_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            recorder = _get_xray_recorder()

            with recorder.in_subsegment(f"A2A-{target_agent}") as subsegment:
                subsegment.put_annotation("target_agent", target_agent)
                subsegment.put_annotation("caller_agent", os.environ.get("AGENT_ID", "unknown"))

                session_id = kwargs.get("session_id")
                if session_id:
                    subsegment.put_annotation("session_id", session_id)

                try:
                    result = func(*args, **kwargs)
                    if hasattr(result, "success"):
                        subsegment.put_annotation("success", result.success)
                    return result
                except Exception as e:
                    subsegment.add_exception(e)
                    raise

        # Return appropriate wrapper based on function type
        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def asyncio_iscoroutinefunction(func: Callable) -> bool:
    """Check if function is async."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


@contextmanager
def trace_subsegment(name: str, annotations: Optional[dict] = None):
    """
    Context manager for creating X-Ray subsegments.

    Args:
        name: Subsegment name
        annotations: Optional dict of annotations to add

    Example:
        with trace_subsegment("fetch_from_memory", {"query": "column mappings"}):
            records = await memory_client.retrieve_memory_records(query)
    """
    recorder = _get_xray_recorder()

    with recorder.in_subsegment(name) as subsegment:
        if annotations:
            for key, value in annotations.items():
                subsegment.put_annotation(key, value)
        yield subsegment


def add_trace_annotation(key: str, value: Any):
    """
    Add annotation to current X-Ray segment.

    Args:
        key: Annotation key
        value: Annotation value (str, int, float, or bool)
    """
    recorder = _get_xray_recorder()
    recorder.put_annotation(key, value)


def add_trace_metadata(key: str, value: Any, namespace: str = "default"):
    """
    Add metadata to current X-Ray segment.

    Metadata can be any JSON-serializable value.

    Args:
        key: Metadata key
        value: Metadata value
        namespace: Namespace for organizing metadata
    """
    recorder = _get_xray_recorder()
    recorder.put_metadata(key, value, namespace)


# =============================================================================
# Tracing Decorators for Specific Operations
# =============================================================================

def trace_memory_operation(operation: str):
    """
    Decorator to trace AgentCore Memory operations.

    Args:
        operation: Operation name (e.g., "retrieve", "create", "search")

    Example:
        @trace_memory_operation("retrieve")
        async def retrieve_prior_knowledge(query):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            recorder = _get_xray_recorder()

            with recorder.in_subsegment(f"Memory-{operation}") as subsegment:
                subsegment.put_annotation("memory_operation", operation)
                subsegment.put_annotation("agent_id", os.environ.get("AGENT_ID", "unknown"))

                try:
                    result = await func(*args, **kwargs)
                    subsegment.put_annotation("success", True)
                    return result
                except Exception as e:
                    subsegment.put_annotation("success", False)
                    subsegment.add_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            recorder = _get_xray_recorder()

            with recorder.in_subsegment(f"Memory-{operation}") as subsegment:
                subsegment.put_annotation("memory_operation", operation)
                subsegment.put_annotation("agent_id", os.environ.get("AGENT_ID", "unknown"))

                try:
                    result = func(*args, **kwargs)
                    subsegment.put_annotation("success", True)
                    return result
                except Exception as e:
                    subsegment.put_annotation("success", False)
                    subsegment.add_exception(e)
                    raise

        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def trace_tool_call(tool_name: str):
    """
    Decorator to trace MCP tool calls.

    Args:
        tool_name: Name of the MCP tool being called

    Example:
        @trace_tool_call("sga_list_inventory")
        async def list_inventory(filters):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            recorder = _get_xray_recorder()

            with recorder.in_subsegment(f"Tool-{tool_name}") as subsegment:
                subsegment.put_annotation("tool_name", tool_name)
                subsegment.put_annotation("agent_id", os.environ.get("AGENT_ID", "unknown"))

                try:
                    result = await func(*args, **kwargs)
                    subsegment.put_annotation("success", True)
                    return result
                except Exception as e:
                    subsegment.put_annotation("success", False)
                    subsegment.add_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            recorder = _get_xray_recorder()

            with recorder.in_subsegment(f"Tool-{tool_name}") as subsegment:
                subsegment.put_annotation("tool_name", tool_name)
                subsegment.put_annotation("agent_id", os.environ.get("AGENT_ID", "unknown"))

                try:
                    result = func(*args, **kwargs)
                    subsegment.put_annotation("success", True)
                    return result
                except Exception as e:
                    subsegment.put_annotation("success", False)
                    subsegment.add_exception(e)
                    raise

        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
