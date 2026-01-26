# =============================================================================
# Insight Service - Phase 5: Observations, Health Analysis, and Notifications
# =============================================================================
# This module extracts proactive insight and notification logic from the
# InventoryHub orchestrator main.py. It handles:
#
# PHASE 5: Proactive Insights
#   - check_observations: Retrieve pending insights from ObservationAgent
#   - request_health_analysis: Trigger on-demand health analysis
#   - check_notifications: Check for job completion notifications
#
# ARCHITECTURE:
#   - ObservationAgent stores insights in AgentCore Memory (/nexo/intuition/{actor_id})
#   - DataTransformer manages job notifications via A2A protocol
#   - Dynamic batch sizing: CRITICAL -> 1 insight, otherwise -> up to 3 insights
#   - Fire-and-Forget pattern for health analysis triggers
#
# MEMORY NAMESPACES:
#   - /nexo/intuition/{user_id}: Proactive insights from ObservationAgent
#   - Notification storage: DataTransformer internal state
#
# Author: Faiston NEXO Team
# Date: January 2026
# =============================================================================

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from shared.cognitive_error_handler import cognitive_sync_handler
from shared.flow_logger import flow_log
from shared.strands_a2a_client import A2AClient

logger = logging.getLogger(__name__)

# Agent ID for error attribution
AGENT_ID = "inventory_hub"


# =============================================================================
# Proactive Insights (ObservationAgent)
# =============================================================================


@cognitive_sync_handler(AGENT_ID)
def check_observations(user_id: str) -> dict[str, Any]:
    """
    Check for proactive insights from the ObservationAgent.

    Called at session start to see if the ObservationAgent has detected
    patterns, anomalies, or optimization opportunities. Uses dynamic
    batch sizing:
        - If CRITICAL insight exists: Returns only 1 insight (focus mode)
        - Otherwise: Returns up to 3 insights (routine mode)

    Insights are stored in `/nexo/intuition/{actor_id}` namespace and
    marked as "delivered" after retrieval.

    Args:
        user_id: User identifier for scoped insights.

    Returns:
        Dict with pending insights:
        {
            "success": true,
            "has_insights": true,
            "insights": [{
                "insight_id": "...",
                "category": "ERROR_PATTERN",
                "severity": "critical",
                "title": "Duplicate Part Numbers",
                "description": "...",
                "action_payload": {"tool": "...", "params": {...}}
            }],
            "total_pending": 5,
            "displayed": 1,
            "human_message": "..."
        }

    Raises:
        CognitiveError: If insight retrieval fails (enriched by DebugAgent).

    Example:
        >>> result = check_observations("user-123")
        >>> if result["has_insights"]:
        ...     for insight in result["insights"]:
        ...         print(f"[{insight['severity']}] {insight['title']}")
    """
    from shared.memory_manager import AgentMemoryManager

    async def _fetch_insights() -> dict[str, Any]:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="inventory_hub", actor_id=user_id)

        insights = await memory.observe(
            query="status:pending",
            namespace=f"/nexo/intuition/{user_id}",
            category="insight",
            max_results=10,
        )

        if not insights:
            return {
                "success": True,
                "has_insights": False,
                "insights": [],
                "total_pending": 0,
                "displayed": 0,
                "human_message": None,
            }

        parsed_insights = []
        criticals = []
        for item in insights:
            content = item.get("content", {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    continue

            severity = content.get("severity", "info")
            parsed_insights.append(content)
            if severity == "critical":
                criticals.append(content)

        # Dynamic batch sizing (per plan)
        if criticals:
            display_list = [criticals[0]]  # Crisis mode: 1 only
        else:
            display_list = parsed_insights[:3]  # Routine: top 3

        # Mark displayed insights as delivered (fire-and-forget)
        for insight in display_list:
            insight_id = insight.get("insight_id")
            if insight_id:
                try:
                    await memory.update_status(
                        entity_id=insight_id,
                        status="delivered",
                    )
                except Exception:
                    pass  # Non-blocking

        # Build human message (pt-BR)
        if criticals:
            human_message = (
                f"Atencao! Detectei {len(criticals)} problema(s) critico(s) "
                f"que requer(em) acao imediata."
            )
        elif display_list:
            human_message = (
                f"Tenho {len(parsed_insights)} insight(s) para voce. "
                f"Mostrando os {len(display_list)} mais relevantes."
            )
        else:
            human_message = None

        return {
            "success": True,
            "has_insights": len(display_list) > 0,
            "insights": display_list,
            "total_pending": len(parsed_insights),
            "displayed": len(display_list),
            "human_message": human_message,
        }

    result = asyncio.run(_fetch_insights())
    logger.info(
        f"[InsightService] check_observations: {result.get('displayed', 0)} insights "
        f"for user={user_id}"
    )

    if result.get("has_insights"):
        insights_list = result.get("insights", [])
        critical_count = sum(1 for i in insights_list if i.get("severity") == "critical")
        warning_count = sum(1 for i in insights_list if i.get("severity") == "warning")
        info_count = sum(1 for i in insights_list if i.get("severity") == "info")

        flow_log.decision(
            "Proactive insights retrieved",
            session_id=f"observation_{user_id}",
            insights_count=len(insights_list),
            critical_count=critical_count,
            warning_count=warning_count,
            info_count=info_count,
            total_pending=result.get("total_pending", 0),
        )

    return result


# =============================================================================
# Health Analysis (ObservationAgent)
# =============================================================================


@cognitive_sync_handler(AGENT_ID)
def request_health_analysis(user_id: str, lookback_days: int = 7) -> dict[str, Any]:
    """
    Trigger on-demand health analysis via ObservationAgent.

    Called when user asks about operations health, e.g.,
    "Como esta minha operacao?" or "Mostre um resumo da semana."

    This is a Fire-and-Forget trigger - the analysis happens in background
    and results appear on the next check_observations call.

    Args:
        user_id: User identifier for actor-scoped analysis.
        lookback_days: Analysis window in days.
            - 7 for weekly analysis (default)
            - 30 for monthly analysis
            - Maximum: 90 days

    Returns:
        Dict with request confirmation:
        {
            "success": true,
            "analysis_requested": true,
            "lookback_days": 7,
            "human_message": "Iniciando analise da ultima semana..."
        }

    Raises:
        CognitiveError: If analysis trigger fails (enriched by DebugAgent).

    Note:
        This function uses Fire-and-Forget pattern. Even if the A2A call
        fails, it returns success with a warning to preserve user experience.
        The analysis may retry automatically in the background.

    Example:
        >>> result = request_health_analysis("user-123", lookback_days=30)
        >>> print(result["human_message"])
        "Estou analisando sua operacao do ultimo mes. Os insights aparecerao em breve!"
    """
    async def _trigger_analysis() -> dict[str, Any]:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent(
            agent_id="observation",
            payload={
                "action": "deep_analysis",
                "actor_id": user_id,
                "lookback_hours": lookback_days * 24,
            },
            timeout=5.0,  # Fire-and-forget: short timeout
        )

    # Validate and normalize lookback_days
    if lookback_days < 1:
        lookback_days = 7
    elif lookback_days > 90:
        lookback_days = 90

    try:
        asyncio.run(_trigger_analysis())
    except Exception as e:
        # Fire-and-forget: log but don't fail user experience
        logger.warning(f"[InsightService] request_health_analysis trigger failed: {e}")
        # Continue to return success message

    # Build human-readable period message (pt-BR)
    if lookback_days <= 7:
        period_msg = "ultima semana"
    elif lookback_days <= 30:
        period_msg = "ultimo mes"
    else:
        period_msg = f"ultimos {lookback_days} dias"

    logger.info(
        f"[InsightService] request_health_analysis: triggered for user={user_id}, "
        f"lookback={lookback_days} days"
    )

    flow_log.decision(
        "Health analysis triggered",
        session_id=f"observation_{user_id}",
        lookback_days=lookback_days,
        status="TRIGGERED",
    )

    return {
        "success": True,
        "analysis_requested": True,
        "lookback_days": lookback_days,
        "human_message": (
            f"Estou analisando sua operacao da {period_msg}. "
            f"Os insights aparecerao em breve!"
        ),
    }


# =============================================================================
# Job Notifications (DataTransformer)
# =============================================================================


@cognitive_sync_handler(AGENT_ID)
def check_notifications(user_id: str) -> dict[str, Any]:
    """
    Check for pending job completion notifications.

    Called at the start of each conversation turn to see if any
    background jobs have completed since the last message.
    Part of the Fire-and-Forget UX - notifications appear naturally
    in the conversation flow.

    Args:
        user_id: User to check notifications for.

    Returns:
        Dict with list of pending notifications:
        {
            "success": true,
            "has_notifications": true,
            "notifications": [{
                "job_id": "job-abc123",
                "status": "completed",
                "rows_inserted": 1480,
                "rows_rejected": 20,
                "human_message": "Importacao finalizada! 1480 itens inseridos."
            }]
        }

    Raises:
        CognitiveError: If notification check fails (enriched by DebugAgent).

    Example:
        >>> result = check_notifications("user-123")
        >>> if result["has_notifications"]:
        ...     for notif in result["notifications"]:
        ...         print(notif["human_message"])
    """
    async def _check() -> dict[str, Any]:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent(
            agent_id="data_transformer",
            payload={
                "action": "check_notifications",
                "user_id": user_id,
            },
        )

    try:
        result = asyncio.run(_check())

        # Handle A2AResponse object
        if hasattr(result, "success") and not result.success:
            logger.warning(f"[InsightService] check_notifications A2A failed: {result.error}")
            return {
                "success": False,
                "has_notifications": False,
                "notifications": [],
                "error": result.error,
            }

        # Extract response from A2AResponse
        response_data = getattr(result, "response", result)
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError:
                response_data = {"raw_response": response_data}

        if isinstance(response_data, dict):
            return response_data

        return {
            "success": True,
            "has_notifications": False,
            "notifications": [],
        }

    except Exception as e:
        logger.warning(f"[InsightService] check_notifications failed: {e}")
        return {
            "success": False,
            "has_notifications": False,
            "notifications": [],
            "error": str(e),
        }


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Observations (Phase 5)
    "check_observations",
    # Health Analysis (Phase 5)
    "request_health_analysis",
    # Notifications (Phase 4/5)
    "check_notifications",
]
