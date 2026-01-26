# =============================================================================
# Preference Loader Tool - Phase 4: DataTransformer
# =============================================================================
# Loads user import strategy preferences from AgentCore Memory.
#
# This is "The Brain" of the DataTransformer - it remembers user preferences
# like error handling strategy (STOP_ON_ERROR vs LOG_AND_CONTINUE).
#
# ARCHITECTURE (per CLAUDE.md):
# - LLM = Brain (decide what to load)
# - Python = Hands (execute Memory API call)
# =============================================================================

import json
import logging
from typing import Any, Dict

from strands import tool

# Memory (AgentCore Memory SDK)
from shared.memory_manager import AgentMemoryManager, MemoryOriginType

logger = logging.getLogger(__name__)

# Agent ID for cognitive error routing (matches parent agent)
AGENT_ID = "data_transformer"

# Default strategy when no preference exists
DEFAULT_STRATEGY = "LOG_AND_CONTINUE"


@tool
def load_import_preferences(user_id: str, session_id: str = "") -> str:
    """
    Load user's import strategy preference from AgentCore Memory.

    This tool retrieves learned preferences from prior imports, including:
    - Error handling strategy (STOP_ON_ERROR or LOG_AND_CONTINUE)
    - Notification preferences
    - Any custom transformations

    On first import (no preference found), returns system default with
    a flag indicating the user should be asked for preference.

    Args:
        user_id: User identifier for preference lookup.
        session_id: Current session ID for context logging.

    Returns:
        JSON string with:
        - success: bool
        - strategy: "STOP_ON_ERROR" | "LOG_AND_CONTINUE"
        - source: "memory" | "system_default"
        - first_import: bool (True if no prior preference)
        - notification_preference: str | None

    Raises:
        MemoryAPIError: If AgentCore Memory query fails (graceful degradation to default).
    """
    try:
        memory_manager = AgentMemoryManager()

        # Query user preferences from LTM
        preferences = memory_manager.observe(
            query=f"import preferences for user {user_id}",
            category="preferences",
            actor_id=user_id,
            max_results=1,
        )

        if preferences:
            pref = preferences[0]
            content = pref.get("content", {})

            logger.info(
                f"[PreferenceLoader] Found preferences for user {user_id}: "
                f"strategy={content.get('strategy', DEFAULT_STRATEGY)}"
            )

            return json.dumps({
                "success": True,
                "strategy": content.get("strategy", DEFAULT_STRATEGY),
                "source": "memory",
                "first_import": False,
                "notification_preference": content.get("notification_preference"),
                "custom_transforms": content.get("custom_transforms", []),
            })

        # No preferences found - first import for this user
        logger.info(
            f"[PreferenceLoader] No preferences found for user {user_id}. "
            f"Using default: {DEFAULT_STRATEGY}"
        )

        return json.dumps({
            "success": True,
            "strategy": DEFAULT_STRATEGY,
            "source": "system_default",
            "first_import": True,
            "notification_preference": None,
            "custom_transforms": [],
            "note": (
                "First import detected. Consider informing user about "
                "error handling options and saving their preference."
            ),
        })

    except Exception as e:
        logger.error(
            f"[PreferenceLoader] Failed to load preferences for user {user_id}: {e}"
        )
        # Graceful degradation - use default
        return json.dumps({
            "success": False,
            "error": str(e),
            "strategy": DEFAULT_STRATEGY,
            "source": "fallback",
            "first_import": True,
        })


@tool
def save_import_preference(
    user_id: str,
    strategy: str,
    notification_preference: str = "memory_event",
) -> str:
    """
    Save user's import strategy preference to AgentCore Memory.

    Called after user explicitly chooses their preferred error handling
    strategy. This enables personalized behavior on subsequent imports.

    Args:
        user_id: User identifier for preference storage.
        strategy: Error handling strategy ("STOP_ON_ERROR" or "LOG_AND_CONTINUE").
        notification_preference: How to notify on completion ("memory_event" default).

    Returns:
        JSON string with success status and memory_id.

    Raises:
        ValueError: If strategy is not STOP_ON_ERROR or LOG_AND_CONTINUE (returned as error JSON).
        MemoryAPIError: If AgentCore Memory save fails (caught internally).
    """
    # Validate strategy
    valid_strategies = ["STOP_ON_ERROR", "LOG_AND_CONTINUE"]
    if strategy not in valid_strategies:
        return json.dumps({
            "success": False,
            "error": f"Invalid strategy. Must be one of: {valid_strategies}",
        })

    try:
        memory_manager = AgentMemoryManager()

        # Save preference to LTM (use_global=False for user-specific)
        memory_id = memory_manager.learn_fact(
            category="preferences",
            content={
                "strategy": strategy,
                "notification_preference": notification_preference,
                "custom_transforms": [],
            },
            actor_id=user_id,
            use_global=False,  # User-specific preference
        )

        logger.info(
            f"[PreferenceLoader] Saved preference for user {user_id}: "
            f"strategy={strategy}, memory_id={memory_id}"
        )

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "strategy": strategy,
            "message": f"Preference saved: {strategy}",
        })

    except Exception as e:
        logger.error(
            f"[PreferenceLoader] Failed to save preference for user {user_id}: {e}"
        )
        return json.dumps({
            "success": False,
            "error": str(e),
        })
