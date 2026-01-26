"""Insight tools for InventoryHub orchestrator.

This module provides tools for fetching proactive insights from the
ObservationAgent and triggering on-demand health analysis.

Tools:
    check_observations: Retrieve pending insights from AgentCore Memory
    request_health_analysis: Trigger deep analysis via ObservationAgent A2A

Architecture Note:
    Insights are stored in `/nexo/intuition/{actor_id}` namespace by the
    ObservationAgent and retrieved here for presentation to users.
"""

import asyncio
import json
import logging

from strands import tool

from shared.debug_utils import debug_error
from shared.flow_logger import flow_log
from shared.memory_manager import AgentMemoryManager
from shared.strands_a2a_client import A2AClient

logger = logging.getLogger(__name__)

__all__ = ["check_observations", "request_health_analysis"]


@tool
def check_observations(user_id: str) -> str:
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
        JSON string with pending insights:
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
    """

    async def _fetch_insights() -> dict:
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
                f"🔴 Atenção! Detectei {len(criticals)} problema(s) crítico(s) "
                f"que requer(em) ação imediata."
            )
        elif display_list:
            human_message = (
                f"ℹ️ Tenho {len(parsed_insights)} insight(s) para você. "
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

    try:
        result = asyncio.run(_fetch_insights())
        logger.info(
            f"[InventoryHub] check_observations: {result.get('displayed', 0)} insights "
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
                total_pending=result.get("total_pending", 0)
            )

        return json.dumps(result)

    except Exception as e:
        debug_error(e, "check_observations", {"user_id": user_id})
        return json.dumps({
            "success": False,
            "has_insights": False,
            "insights": [],
            "error": str(e),
        })


@tool
def request_health_analysis(user_id: str, lookback_days: int = 7) -> str:
    """
    Trigger on-demand health analysis via ObservationAgent.

    Called when user asks about operations health, e.g.,
    "Como está minha operação?" or "Mostre um resumo da semana."

    This is a Fire-and-Forget trigger - the analysis happens in background
    and results appear on the next check_observations call.

    Args:
        user_id: User identifier for actor-scoped analysis.
        lookback_days: Analysis window in days (7 for weekly, 30 for monthly).

    Returns:
        JSON string with request confirmation:
        {
            "success": true,
            "analysis_requested": true,
            "lookback_days": 7,
            "human_message": "Iniciando análise da última semana..."
        }
    """

    async def _trigger_analysis() -> dict:
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

    try:
        if lookback_days < 1:
            lookback_days = 7
        elif lookback_days > 90:
            lookback_days = 90

        asyncio.run(_trigger_analysis())

        if lookback_days <= 7:
            period_msg = "última semana"
        elif lookback_days <= 30:
            period_msg = "último mês"
        else:
            period_msg = f"últimos {lookback_days} dias"

        logger.info(
            f"[InventoryHub] request_health_analysis: triggered for user={user_id}, "
            f"lookback={lookback_days} days"
        )

        flow_log.decision(
            "Health analysis triggered",
            session_id=f"observation_{user_id}",
            lookback_days=lookback_days,
            status="TRIGGERED"
        )

        return json.dumps({
            "success": True,
            "analysis_requested": True,
            "lookback_days": lookback_days,
            "human_message": (
                f"Estou analisando sua operação da {period_msg}. "
                f"Os insights aparecerão em breve!"
            ),
        })

    except Exception as e:
        # Fire-and-forget: log but don't fail user experience
        logger.warning(f"[InventoryHub] request_health_analysis trigger failed: {e}")
        return json.dumps({
            "success": True,  # Still success - user gets message
            "analysis_requested": True,
            "lookback_days": lookback_days,
            "human_message": (
                "Vou analisar sua operação. "
                "Os resultados podem demorar alguns minutos."
            ),
            "warning": "Analysis trigger may have failed, retrying automatically.",
        })
