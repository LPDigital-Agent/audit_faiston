# =============================================================================
# ObservationAgent Tool: Scan Recent Activity
# =============================================================================
# Reads from AgentCore Memory (facts, episodes, sessions) with configurable
# time windows for tactical (24h), operational (7d), and strategic (30d) analysis.
#
# PRINCIPLES (per CLAUDE.md):
# - TOOL-FIRST: Python handles deterministic queries
# - NO RAW DATA IN CONTEXT: Returns summaries, not full datasets
# - ACTOR-SCOPED: ALL data is scoped to requesting user
#
# VERSION: 2026-01-22T00:00:00Z
# =============================================================================

import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from strands import tool

from shared.memory_manager import AgentMemoryManager
from shared.cognitive_error_handler import cognitive_error_handler

logger = logging.getLogger(__name__)


# =============================================================================
# Time Window Constants
# =============================================================================

# Configurable time windows for analysis
TIME_WINDOWS = {
    "tactical": 24,      # 24 hours - post-import, quick scan
    "operational": 168,  # 7 days - weekly review
    "strategic": 720,    # 30 days - monthly deep dive
}


# =============================================================================
# Tool Implementation
# =============================================================================


@tool
@cognitive_error_handler("observation")
def scan_recent_activity(
    actor_id: str,
    time_window_hours: int = 24,
    include_facts: bool = True,
    include_episodes: bool = True,
    include_global: bool = False,
) -> str:
    """
    Scan recent Memory activity for patterns and anomalies.

    Reads from AgentCore Memory (facts, episodes, sessions) with configurable
    time windows. This is the first step in the OBSERVE → THINK → LEARN → ACT loop.

    Time Windows:
    - 24 hours (tactical): Quick post-import scan
    - 168 hours (7 days, operational): Weekly review
    - 720 hours (30 days, strategic): Monthly deep dive

    The activity is actor-scoped: ALL data belongs to the requesting user only.
    No cross-tenant data mixing is allowed.

    Args:
        actor_id: User identifier for scoping queries.
        time_window_hours: Analysis window in hours (default 24 = tactical).
        include_facts: Include confirmed facts from SemanticStrategy.
        include_episodes: Include episodes from EpisodicStrategy.
        include_global: Include global patterns (company-wide, optional).

    Returns:
        JSON string with activity summary:
        {
            "success": true,
            "actor_id": "user-123",
            "time_window_hours": 24,
            "time_window_type": "tactical",
            "facts": [{"content": "...", "category": "...", "confidence": 0.9}, ...],
            "episodes": [{"content": "...", "outcome": "success", ...}, ...],
            "session_history": [{"session_id": "...", "event_count": 5}, ...],
            "activity_summary": {
                "total_facts": 12,
                "total_episodes": 5,
                "unique_sessions": 3,
                "top_categories": ["column_mapping", "import_completed"],
                "error_count": 2,
                "success_rate": 0.85
            },
            "human_message": "Encontrei 12 fatos e 5 episódios nas últimas 24 horas."
        }
    """
    async def _scan_memory() -> Dict[str, Any]:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="observation", actor_id=actor_id)

        # Determine time window type for display
        time_window_type = "custom"
        for name, hours in TIME_WINDOWS.items():
            if time_window_hours == hours:
                time_window_type = name
                break

        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        cutoff_iso = cutoff_time.isoformat() + "Z"

        # Build search query (time-based)
        query = f"activity after {cutoff_iso}"

        facts: List[Dict[str, Any]] = []
        episodes: List[Dict[str, Any]] = []

        # Fetch facts (confirmed knowledge)
        if include_facts:
            try:
                raw_facts = await memory.observe_facts(query=query, limit=50)
                for record in raw_facts:
                    facts.append({
                        "content": record.get("content", ""),
                        "category": record.get("category", "unknown"),
                        "confidence": record.get("confidence_level", 0.7),
                        "origin_type": record.get("origin_type", "unknown"),
                        "timestamp": record.get("timestamp", ""),
                    })
            except Exception as e:
                logger.warning(f"[scan_recent_activity] Error fetching facts: {e}")

        # Fetch episodes (interaction history)
        if include_episodes:
            try:
                raw_episodes = await memory.observe_episodes(query=query, limit=30)
                for record in raw_episodes:
                    episodes.append({
                        "content": record.get("content", ""),
                        "outcome": record.get("outcome", "unknown"),
                        "session_id": record.get("session_id", ""),
                        "category": record.get("category", "unknown"),
                        "timestamp": record.get("timestamp", ""),
                    })
            except Exception as e:
                logger.warning(f"[scan_recent_activity] Error fetching episodes: {e}")

        # Fetch global patterns (optional, for cross-learning context)
        global_patterns: List[Dict[str, Any]] = []
        if include_global:
            try:
                raw_global = await memory.observe_global(query=query, limit=20)
                for record in raw_global:
                    global_patterns.append({
                        "content": record.get("content", ""),
                        "category": record.get("category", "unknown"),
                    })
            except Exception as e:
                logger.warning(f"[scan_recent_activity] Error fetching global: {e}")

        # Analyze session history from episodes
        session_counts: Dict[str, int] = {}
        for episode in episodes:
            session_id = episode.get("session_id", "unknown")
            session_counts[session_id] = session_counts.get(session_id, 0) + 1

        session_history = [
            {"session_id": sid, "event_count": count}
            for sid, count in sorted(session_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Compute activity summary
        categories: Dict[str, int] = {}
        error_count = 0
        success_count = 0

        for fact in facts:
            cat = fact.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        for episode in episodes:
            cat = episode.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            outcome = episode.get("outcome", "").lower()
            if "error" in outcome or "fail" in outcome:
                error_count += 1
            elif "success" in outcome or "complet" in outcome:
                success_count += 1

        total_outcomes = error_count + success_count
        success_rate = success_count / total_outcomes if total_outcomes > 0 else 1.0

        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
        top_categories = [cat for cat, _ in top_categories]

        activity_summary = {
            "total_facts": len(facts),
            "total_episodes": len(episodes),
            "total_global_patterns": len(global_patterns),
            "unique_sessions": len(session_counts),
            "top_categories": top_categories,
            "error_count": error_count,
            "success_count": success_count,
            "success_rate": round(success_rate, 2),
        }

        # Generate human message (pt-BR)
        window_name = {
            "tactical": "últimas 24 horas",
            "operational": "última semana",
            "strategic": "último mês",
            "custom": f"últimas {time_window_hours} horas",
        }[time_window_type]

        human_message = (
            f"Encontrei {len(facts)} fato(s) e {len(episodes)} episódio(s) "
            f"nas {window_name}. "
            f"Taxa de sucesso: {round(success_rate * 100)}%."
        )

        if error_count > 0:
            human_message += f" ⚠️ {error_count} erro(s) detectado(s)."

        return {
            "success": True,
            "actor_id": actor_id,
            "time_window_hours": time_window_hours,
            "time_window_type": time_window_type,
            "facts": facts[:20],  # Limit to avoid context overload
            "episodes": episodes[:15],
            "global_patterns": global_patterns[:10],
            "session_history": session_history[:10],
            "activity_summary": activity_summary,
            "human_message": human_message,
        }

    try:
        result = asyncio.run(_scan_memory())
        logger.info(
            f"[scan_recent_activity] Scanned {result['activity_summary']['total_facts']} facts, "
            f"{result['activity_summary']['total_episodes']} episodes for actor={actor_id}"
        )
        return json.dumps(result)

    except Exception as e:
        logger.error(f"[scan_recent_activity] Failed: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "MEMORY_SCAN_ERROR",
            "actor_id": actor_id,
            "human_message": "Erro ao escanear atividade recente. Tente novamente.",
        })


# =============================================================================
# Module Exports
# =============================================================================

__all__ = ["scan_recent_activity"]
