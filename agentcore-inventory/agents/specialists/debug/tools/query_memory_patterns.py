# =============================================================================
# DebugAgent Tool: query_memory_patterns
# =============================================================================
# Find similar error patterns from historical data stored in AgentCore Memory.
#
# Pattern Matching Strategy:
# 1. Match by error signature (exact or fuzzy)
# 2. Match by error type
# 3. Match by operation
#
# Returns:
# - Similar patterns with similarity scores
# - Past resolutions
# - Success rates
# =============================================================================

import logging
from typing import Dict, Any, Optional

# AgentCore Memory for pattern storage
from shared.memory_manager import AgentMemoryManager

logger = logging.getLogger(__name__)

# Memory namespace for error patterns
MEMORY_NAMESPACE = "/strategy/debug/error_patterns"

# Minimum similarity threshold
MIN_SIMILARITY = 0.5


def _get_memory() -> AgentMemoryManager:
    """
    Get AgentMemoryManager for error pattern queries.

    Returns:
        AgentMemoryManager instance
    """
    return AgentMemoryManager(
        agent_id="debug",
        actor_id="system",
        use_global_namespace=True,
    )


async def query_memory_patterns_tool(
    error_signature: str,
    error_type: Optional[str] = None,
    operation: Optional[str] = None,
    max_patterns: int = 5,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Find similar error patterns from AgentCore Memory.

    Queries the error patterns namespace for:
    - Exact signature matches
    - Similar error types
    - Same operation failures

    Args:
        error_signature: Unique error signature for matching
        error_type: Optional error type filter
        operation: Optional operation filter
        max_patterns: Maximum patterns to return
        session_id: Session ID for context

    Returns:
        Similar patterns with resolutions and success rates
    """
    logger.info(f"[query_memory_patterns] Signature: {error_signature[:16]}...")

    try:
        memory = _get_memory()

        # Build query for semantic search
        query_parts = [f"error_signature:{error_signature}"]
        if error_type:
            query_parts.append(f"error_type:{error_type}")
        if operation:
            query_parts.append(f"operation:{operation}")

        query = " ".join(query_parts)

        # Query AgentCore Memory
        try:
            records = await memory.observe(
                query=query,
                include_facts=True,
                include_episodes=True,
                include_global=True,
            )
        except Exception as e:
            logger.warning(f"[query_memory_patterns] Memory query failed: {e}")
            records = []

        # Process and score patterns
        patterns = []
        for record in records[:max_patterns]:
            # Extract pattern data
            record.get("content", "")
            metadata = record.get("metadata", {})

            # Calculate similarity score
            similarity = _calculate_similarity(
                error_signature=error_signature,
                record_signature=metadata.get("error_signature", ""),
                error_type=error_type,
                record_type=metadata.get("error_type", ""),
                operation=operation,
                record_operation=metadata.get("operation", ""),
            )

            if similarity >= MIN_SIMILARITY:
                patterns.append({
                    "pattern_id": metadata.get("pattern_id", "unknown"),
                    "error_signature": metadata.get("error_signature", ""),
                    "error_type": metadata.get("error_type", ""),
                    "operation": metadata.get("operation", ""),
                    "similarity": similarity,
                    "resolution": metadata.get("resolution", ""),
                    "debugging_steps": metadata.get("debugging_steps", []),
                    "success_rate": metadata.get("success_rate", 0.0),
                    "occurrence_count": metadata.get("occurrence_count", 1),
                    "last_seen": metadata.get("last_seen", ""),
                })

        # Sort by similarity
        patterns.sort(key=lambda p: p["similarity"], reverse=True)

        return {
            "success": True,
            "query_signature": error_signature,
            "patterns_found": len(patterns),
            "patterns": patterns[:max_patterns],
        }

    except Exception as e:
        logger.error(f"[query_memory_patterns] Error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "patterns": [],
        }


def _calculate_similarity(
    error_signature: str,
    record_signature: str,
    error_type: Optional[str],
    record_type: str,
    operation: Optional[str],
    record_operation: str,
) -> float:
    """
    Calculate similarity score between query and record.

    Scoring:
    - Exact signature match: 1.0
    - Same error type + operation: 0.8
    - Same error type only: 0.6
    - Same operation only: 0.5

    Args:
        error_signature: Query signature
        record_signature: Record signature
        error_type: Query error type
        record_type: Record error type
        operation: Query operation
        record_operation: Record operation

    Returns:
        Similarity score (0.0 - 1.0)
    """
    # Exact signature match
    if error_signature and error_signature == record_signature:
        return 1.0

    # Partial signature match (first 8 chars)
    if error_signature and record_signature:
        if error_signature[:8] == record_signature[:8]:
            return 0.9

    # Type + operation match
    type_match = error_type and error_type.lower() == record_type.lower()
    op_match = operation and operation.lower() == record_operation.lower()

    if type_match and op_match:
        return 0.8
    if type_match:
        return 0.6
    if op_match:
        return 0.5

    # No significant match
    return 0.0
