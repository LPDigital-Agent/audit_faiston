# =============================================================================
# Memory Tools - AgentCore Memory Integration for Inventory Swarm
# =============================================================================
# Tools for episodic memory management using AWS Bedrock AgentCore Memory.
#
# Used by: memory_agent
#
# Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
# =============================================================================

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from strands import tool

logger = logging.getLogger(__name__)


@tool
def retrieve_episodes(
    query: str,
    file_type: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Retrieve prior import patterns from AgentCore Memory.

    Args:
        query: Search query (column names, file pattern, etc.)
        file_type: Optional filter by file type (csv, xlsx, etc.)
        limit: Maximum number of patterns to return

    Returns:
        dict with:
        - patterns: List of relevant prior import patterns
        - total_found: Total matching patterns
        - query_metadata: Search metadata
    """
    logger.info("[retrieve_episodes] Query: %s, file_type: %s", query, file_type)

    # In production, this would query AgentCore Memory
    # For now, return simulated patterns based on query
    try:
        from shared.agentcore_memory import AgentMemoryManager

        memory = AgentMemoryManager()
        episodes = memory.search_episodes(
            query=query,
            filters={"file_type": file_type} if file_type else None,
            limit=limit,
        )

        return {
            "patterns": episodes,
            "total_found": len(episodes),
            "query_metadata": {
                "query": query,
                "file_type": file_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    except ImportError:
        # Sandwich Pattern: Be honest about mock mode - LLM must know data is fake
        logger.warning("[retrieve_episodes] AgentMemoryManager not available, using mock")
        mock_patterns = _get_mock_patterns(query, file_type, limit)
        return {
            "success": False,  # Honest: Real memory lookup failed
            "is_mock_data": True,
            "patterns": mock_patterns.get("patterns", []),
            "total_found": mock_patterns.get("total_found", 0),
            "error_context": {
                "error_type": "ImportError",
                "operation": "retrieve_episodes",
                "memory_available": False,
            },
            "warning": "AgentCore Memory not available - patterns are MOCK data for development only",
            "suggested_actions": ["use_default_mappings", "ask_user_for_guidance"],
        }


@tool
def store_episode(
    file_pattern: str,
    file_type: str,
    column_mappings: List[Dict[str, Any]],
    user_preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Store a successful import pattern in AgentCore Memory.

    Args:
        file_pattern: Pattern to match file names (regex or glob)
        file_type: File type (csv, xlsx, pdf, xml)
        column_mappings: Successful column mappings
        user_preferences: User preferences learned from this import

    Returns:
        dict with:
        - episode_id: ID of stored episode
        - success: Whether storage succeeded
        - message: Status message
    """
    logger.info(
        "[store_episode] Storing pattern for %s (%s)",
        file_pattern,
        file_type,
    )

    episode = {
        "episode_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file_pattern": file_pattern,
        "file_type": file_type,
        "column_mappings": column_mappings,
        "user_preferences": user_preferences or {},
        "success_count": 1,
        "last_used": datetime.now(timezone.utc).isoformat(),
    }

    try:
        from shared.agentcore_memory import AgentMemoryManager

        memory = AgentMemoryManager()
        memory.store_episode(episode)

        return {
            "episode_id": episode["episode_id"],
            "success": True,
            "message": f"Pattern stored successfully for {file_type} files",
        }

    except ImportError:
        # Sandwich Pattern: Be honest - data was NOT stored
        logger.warning("[store_episode] AgentMemoryManager not available - pattern NOT stored")
        return {
            "episode_id": episode["episode_id"],
            "success": False,  # Honest: Storage actually failed
            "is_mock_mode": True,
            "error_context": {
                "error_type": "ImportError",
                "operation": "store_episode",
                "memory_available": False,
            },
            "warning": "AgentCore Memory not available - pattern was NOT persisted",
            "suggested_actions": ["log_pattern_locally", "proceed_without_learning"],
        }


@tool
def get_adaptive_threshold(file_type: str) -> Dict[str, Any]:
    """
    Calculate adaptive confidence threshold based on historical accuracy.

    Args:
        file_type: File type to get threshold for

    Returns:
        dict with:
        - threshold: Recommended confidence threshold
        - basis: How threshold was calculated
        - historical_accuracy: Historical accuracy for this file type
    """
    logger.info("[get_adaptive_threshold] Calculating for file_type: %s", file_type)

    # Default thresholds
    default_thresholds = {
        "csv": 0.75,  # CSV is usually well-structured
        "xlsx": 0.80,  # Excel may have merged cells, formatting
        "pdf": 0.85,  # PDF extraction is less reliable
        "xml": 0.70,  # XML has clear structure
    }

    base_threshold = default_thresholds.get(file_type, 0.80)

    try:
        from shared.agentcore_memory import AgentMemoryManager

        memory = AgentMemoryManager()
        stats = memory.get_accuracy_stats(file_type)

        if stats and stats.get("total_imports", 0) > 5:
            # Adjust threshold based on historical accuracy
            accuracy = stats.get("accuracy", 0.0)
            if accuracy > 0.95:
                # High accuracy - can lower threshold
                threshold = max(0.65, base_threshold - 0.10)
            elif accuracy < 0.80:
                # Low accuracy - raise threshold
                threshold = min(0.90, base_threshold + 0.10)
            else:
                threshold = base_threshold

            return {
                "threshold": threshold,
                "basis": "Historical accuracy",
                "historical_accuracy": accuracy,
                "total_imports": stats.get("total_imports", 0),
            }

    except ImportError:
        # Sandwich Pattern: Be honest about memory unavailability
        logger.warning("[get_adaptive_threshold] AgentMemoryManager not available")
        return {
            "success": False,
            "is_mock_mode": True,
            "threshold": base_threshold,
            "basis": "Default for file type (memory unavailable)",
            "historical_accuracy": None,
            "total_imports": 0,
            "error_context": {
                "error_type": "ImportError",
                "operation": "get_adaptive_threshold",
                "memory_available": False,
            },
            "warning": "Using default threshold - historical data not available",
        }


@tool
def similarity_search(
    columns: List[str],
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Find similar past imports by column name similarity.

    Args:
        columns: List of column names from current file
        limit: Maximum number of similar patterns to return

    Returns:
        dict with:
        - similar_patterns: List of patterns with similarity scores
        - best_match: Highest similarity pattern
    """
    logger.info("[similarity_search] Searching with %d columns", len(columns))

    try:
        from shared.agentcore_memory import AgentMemoryManager

        memory = AgentMemoryManager()
        results = memory.similarity_search(
            column_names=columns,
            limit=limit,
        )

        return {
            "similar_patterns": results,
            "best_match": results[0] if results else None,
        }

    except ImportError:
        # Sandwich Pattern: Be honest about memory unavailability
        logger.warning("[similarity_search] AgentMemoryManager not available")
        return {
            "success": False,
            "is_mock_mode": True,
            "similar_patterns": [],
            "best_match": None,
            "error_context": {
                "error_type": "ImportError",
                "operation": "similarity_search",
                "memory_available": False,
            },
            "warning": "Similarity search unavailable - no historical patterns to match against",
            "suggested_actions": ["use_default_mappings", "ask_user_for_guidance"],
        }


@tool
def update_pattern_success(
    episode_id: str,
    success: bool = True,
) -> Dict[str, Any]:
    """
    Update the success count for a pattern after import.

    Args:
        episode_id: ID of the episode to update
        success: Whether the import was successful

    Returns:
        dict with:
        - updated: Whether update succeeded
        - new_success_count: Updated success count
    """
    logger.info("[update_pattern_success] Updating %s (success=%s)", episode_id, success)

    try:
        from shared.agentcore_memory import AgentMemoryManager

        memory = AgentMemoryManager()
        result = memory.update_success_count(episode_id, success)

        return {
            "updated": True,
            "new_success_count": result.get("success_count", 0),
        }

    except ImportError:
        # Sandwich Pattern: Be honest - update did NOT happen
        logger.warning("[update_pattern_success] AgentMemoryManager not available - update NOT persisted")
        return {
            "success": False,
            "updated": False,  # Honest: Nothing was actually updated
            "is_mock_mode": True,
            "new_success_count": None,
            "error_context": {
                "error_type": "ImportError",
                "operation": "update_pattern_success",
                "memory_available": False,
            },
            "warning": "Pattern success count was NOT updated - memory unavailable",
        }


# =============================================================================
# Helper Functions
# =============================================================================


def _get_mock_patterns(
    query: str,
    file_type: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    """
    Return mock patterns for development.

    BUG-022 v9 FIX (CRITICAL-S4): Defense-in-depth - mock patterns are now
    OBVIOUSLY INVALID so they would fail validation if accidentally used:
    - episode_id starts with "MOCK_DO_NOT_USE_"
    - confidence is 0.0 (not realistic 0.95)
    - relevance_score is 0.0
    - success_count is 0

    This ensures that even if an agent ignores is_mock_data flag,
    the patterns themselves would fail any reasonable validation.
    """
    # BUG-022 v9: Mock patterns are now OBVIOUSLY INVALID
    # If these patterns are used in production, they SHOULD fail!
    mock_patterns = [
        {
            "episode_id": "MOCK_DO_NOT_USE_001",  # Obviously invalid ID
            "file_pattern": "EXPEDIÇÃO*.csv",
            "file_type": "csv",
            "column_mappings": [
                {"source": "PN", "target": "part_number", "confidence": 0.0},  # Zero confidence
                {"source": "SN", "target": "serial_number", "confidence": 0.0},
                {"source": "QTD", "target": "quantity", "confidence": 0.0},
            ],
            "user_preferences": {"unmapped_handling": "metadata"},
            "success_count": 0,  # Zero success - never validated
            "relevance_score": 0.0,  # Zero relevance - don't use
            "_is_mock": True,  # Extra flag
            "_warning": "DO NOT USE IN PRODUCTION - mock data only",
        },
        {
            "episode_id": "MOCK_DO_NOT_USE_002",  # Obviously invalid ID
            "file_pattern": "ESTOQUE*.xlsx",
            "file_type": "xlsx",
            "column_mappings": [
                {"source": "PART_NUMBER", "target": "part_number", "confidence": 0.0},
                {"source": "SERIAL", "target": "serial_number", "confidence": 0.0},
                {"source": "QUANTIDADE", "target": "quantity", "confidence": 0.0},
            ],
            "user_preferences": {"date_format": "DD/MM/YYYY"},
            "success_count": 0,  # Zero success - never validated
            "relevance_score": 0.0,  # Zero relevance - don't use
            "_is_mock": True,  # Extra flag
            "_warning": "DO NOT USE IN PRODUCTION - mock data only",
        },
    ]

    # Filter by file_type if provided
    if file_type:
        mock_patterns = [p for p in mock_patterns if p["file_type"] == file_type]

    logger.warning(
        "[_get_mock_patterns] BUG-022 v9: Returning %d MOCK patterns with zero confidence. "
        "These should NOT be used for real mappings!",
        len(mock_patterns[:limit]),
    )

    return {
        "patterns": mock_patterns[:limit],
        "total_found": len(mock_patterns),
        "query_metadata": {
            "query": query,
            "file_type": file_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "mock",
            "_warning": "MOCK DATA - do not use for production mappings",
        },
    }
