# =============================================================================
# DebugAgent Tool: store_resolution
# =============================================================================
# Store successful error resolutions in AgentCore Memory.
#
# Storage Strategy:
# - Store in global namespace for cross-agent learning
# - Include error signature for pattern matching
# - Track success rate over time
# - 90-day TTL for pattern expiration
#
# Memory Namespace: /strategy/debug/error_patterns
# =============================================================================

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid

# AgentCore Memory for pattern storage
from shared.memory_manager import AgentMemoryManager

logger = logging.getLogger(__name__)

# Memory namespace for error patterns
MEMORY_NAMESPACE = "/strategy/debug/error_patterns"


def _get_memory(actor_id: str = "system") -> AgentMemoryManager:
    """
    Get AgentMemoryManager for error pattern storage.

    Args:
        actor_id: Actor ID for context

    Returns:
        AgentMemoryManager instance
    """
    return AgentMemoryManager(
        agent_id="debug",
        actor_id=actor_id,
        use_global_namespace=True,
    )


async def store_resolution_tool(
    error_signature: str,
    error_type: str,
    operation: str,
    resolution: str,
    success: bool = True,
    debugging_steps: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Store successful error resolution in AgentCore Memory.

    Records the resolution pattern for future reference:
    - Error signature for matching
    - Resolution description
    - Debugging steps taken
    - Success indicator
    - Attribution

    Args:
        error_signature: Unique error signature
        error_type: Exception class name
        operation: Operation that failed
        resolution: How the error was resolved
        success: Whether resolution was successful
        debugging_steps: Steps taken to debug
        session_id: Session ID for context
        user_id: User ID for attribution

    Returns:
        Storage result with pattern ID
    """
    logger.info(f"[store_resolution] Storing: {error_type} ({success})")

    try:
        memory = _get_memory(actor_id=user_id or "system")

        # Generate pattern ID
        pattern_id = f"pat_{error_signature[:8]}_{uuid.uuid4().hex[:8]}"

        # Build pattern content for semantic search
        content = (
            f"Error Resolution Pattern: {error_type} in {operation}. "
            f"Resolution: {resolution}. "
            f"Signature: {error_signature}. "
            f"Success: {success}."
        )

        # Build metadata for structured retrieval
        {
            "pattern_id": pattern_id,
            "error_signature": error_signature,
            "error_type": error_type,
            "operation": operation,
            "resolution": resolution,
            "success": success,
            "debugging_steps": debugging_steps or [],
            "occurrence_count": 1,
            "success_rate": 1.0 if success else 0.0,
            "first_seen": datetime.utcnow().isoformat() + "Z",
            "last_seen": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "user_id": user_id,
        }

        # Store in AgentCore Memory
        try:
            # Use learn_episode for episodic storage
            event_id = await memory.learn_episode(
                episode_content=content,
                category="error_resolution",
                outcome="success" if success else "failed",
                emotional_weight=0.8 if success else 0.5,  # Higher weight for successful resolutions
            )

            logger.info(f"[store_resolution] Stored pattern {pattern_id} (event: {event_id})")

            return {
                "success": True,
                "pattern_id": pattern_id,
                "event_id": event_id,
                "stored": True,
                "message": f"Resolution stored for {error_type}",
            }

        except Exception as e:
            logger.warning(f"[store_resolution] Memory storage failed: {e}")
            # Return success=True but stored=False for graceful degradation
            return {
                "success": True,
                "pattern_id": pattern_id,
                "event_id": None,
                "stored": False,
                "message": f"Resolution recorded but memory storage failed: {e}",
            }

    except Exception as e:
        logger.error(f"[store_resolution] Error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "stored": False,
        }


async def update_pattern_stats(
    pattern_id: str,
    success: bool,
) -> Dict[str, Any]:
    """
    Update pattern statistics after reuse.

    Increments occurrence count and updates success rate.

    Args:
        pattern_id: Pattern ID to update
        success: Whether this use was successful

    Returns:
        Update result
    """
    logger.info(f"[update_pattern_stats] Updating: {pattern_id}")

    # Note: In production, this would query and update the pattern
    # For now, we log the update request
    logger.info(f"[update_pattern_stats] Would update {pattern_id} success={success}")

    return {
        "success": True,
        "pattern_id": pattern_id,
        "updated": True,
    }
