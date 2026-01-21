# =============================================================================
# SSE Stream Service - Agent Room X-Ray
# =============================================================================
# Server-Sent Events streaming for real-time Agent Room X-Ray traces.
# Streams agent activity events to connected clients with < 1s latency.
#
# Architecture:
# - Polls DynamoDB audit log every second for new events
# - Enriches events with duration, type classification
# - Merges HIL tasks inline with agent events
# - Streams via text/event-stream format
#
# Data Sources:
# - DynamoDB Audit Log (agent activity)
# - HIL Tasks (pending decisions)
# =============================================================================

import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional, Dict, List, Any

from tools.humanizer import (
    get_friendly_agent_name,
)
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Name Mapping
# =============================================================================

AGENT_NAMES: Dict[str, str] = {
    "nexo_import": "NEXO",
    "intake": "Leitor de Notas",
    "data_import": "Importador",  # Renamed from "import" (Python reserved word)
    "estoque_control": "Controlador",
    "compliance": "Validador",
    "schema_evolution": "Arquiteto",
    "learning": "Memória",
    "observation": "Observador",
    # AUDIT-004/2: equipment_research removed - dead code replaced by enrichment agent
    "comunicacao": "Comunicador",
    # BUG-025: Strands structured output agents
    "file_analyzer": "Analisador",
    "vision_analyzer": "Visão",
}


def _get_agent_name(agent_id: Optional[str]) -> str:
    """Map agent ID to human-friendly name."""
    if not agent_id:
        return "Sistema"
    # Try direct mapping first
    if agent_id in AGENT_NAMES:
        return AGENT_NAMES[agent_id]
    # Try humanizer function
    try:
        return get_friendly_agent_name(agent_id)
    except Exception:
        pass
    # Fallback to agent_id
    return agent_id


# =============================================================================
# Event Classification
# =============================================================================

def _classify_event_type(event: Dict[str, Any]) -> str:
    """
    Classify an audit event into X-Ray type categories.

    Returns:
        One of: 'agent_activity', 'hil_decision', 'a2a_delegation', 'error',
                'session_start', 'session_end'
    """
    action = event.get("action", "")
    details = event.get("details", {})
    event_type = event.get("event_type", "")

    # Check for A2A delegation
    if details.get("target_agent"):
        return "a2a_delegation"

    # Check for errors
    if action in ("erro", "error") or "error" in event_type.lower():
        return "error"

    # Check for HIL-related events
    if "hil" in action.lower() or details.get("hil_task_id"):
        return "hil_decision"

    # Check for session events
    if "session_start" in action.lower():
        return "session_start"
    if "session_end" in action.lower() or action == "concluido":
        return "session_end"

    # Default to agent activity
    return "agent_activity"


def _map_action(action: str) -> str:
    """Map backend action to X-Ray action type."""
    action_map = {
        "trabalhando": "trabalhando",
        "working": "trabalhando",
        "processing": "trabalhando",
        "delegando": "delegando",
        "delegating": "delegando",
        "concluido": "concluido",
        "completed": "concluido",
        "success": "concluido",
        "erro": "erro",
        "error": "erro",
        "failed": "erro",
        "esperando": "esperando",
        "waiting": "esperando",
        "idle": "esperando",
        "disponivel": "esperando",
    }
    return action_map.get(action.lower(), "trabalhando")


# =============================================================================
# Event Enrichment
# =============================================================================

def _enrich_events(
    events: List[Dict[str, Any]],
    session_timings: Optional[Dict[str, datetime]] = None
) -> List[Dict[str, Any]]:
    """
    Enrich raw audit events with X-Ray metadata.

    Adds:
    - type: Event classification
    - agentName: Human-friendly name
    - duration: Time since previous event in session
    - Normalized field names for frontend
    """
    if session_timings is None:
        session_timings = {}

    enriched = []

    for event in events:
        try:
            agent_id = event.get("actor_id") or event.get("agent_id", "")
            details = event.get("details", {})
            timestamp_str = event.get("timestamp", datetime.utcnow().isoformat())
            session_id = event.get("session_id")

            # Build enriched event
            enriched_event: Dict[str, Any] = {
                "id": event.get("event_id") or event.get("SK", f"evt-{datetime.utcnow().timestamp()}"),
                "timestamp": timestamp_str,
                "type": _classify_event_type(event),
                "agentId": agent_id,
                "agentName": _get_agent_name(agent_id),
                "action": _map_action(event.get("action", "trabalhando")),
                "message": details.get("message", "") or event.get("action", ""),
                "sessionId": session_id,
                "details": details,
            }

            # Add target agent for A2A delegation
            target_agent = details.get("target_agent")
            if target_agent:
                enriched_event["targetAgent"] = target_agent
                enriched_event["targetAgentName"] = _get_agent_name(target_agent)

            # Calculate duration from previous event in same session
            if session_id:
                try:
                    current_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if session_id in session_timings:
                        prev_time = session_timings[session_id]
                        duration_ms = int((current_time - prev_time).total_seconds() * 1000)
                        if duration_ms >= 0:
                            enriched_event["duration"] = duration_ms
                    session_timings[session_id] = current_time
                except (ValueError, TypeError):
                    pass

            enriched.append(enriched_event)

        except Exception as e:
            debug_error(e, "sse_enrich_event", {"event_id": event.get("event_id")})
            continue

    return enriched


def _convert_hil_to_events(hil_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert HIL tasks to X-Ray event format.

    HIL tasks appear inline in the X-Ray timeline as 'hil_decision' events.
    """
    events = []

    for task in hil_tasks:
        try:
            task_id = task.get("task_id") or task.get("id", "")
            agent_id = task.get("agent_id", "system")

            event = {
                "id": f"hil-{task_id}",
                "timestamp": task.get("created_at") or task.get("createdAt") or datetime.utcnow().isoformat(),
                "type": "hil_decision",
                "agentId": agent_id,
                "agentName": _get_agent_name(agent_id),
                "action": "hil_pending",
                "message": task.get("question", "Decisão pendente"),
                "sessionId": task.get("session_id"),
                "hilTaskId": task_id,
                "hilStatus": "pending",
                "hilQuestion": task.get("question"),
                "hilOptions": task.get("options", []),
                "details": task.get("details", {}),
            }

            events.append(event)

        except Exception as e:
            debug_error(e, "sse_convert_hil_task", {"task_id": task.get("task_id") or task.get("id")})
            continue

    return events


# =============================================================================
# SSE Stream Class
# =============================================================================

class SSEStream:
    """
    Manages Server-Sent Events connections for Agent Room X-Ray.

    Usage:
        stream = SSEStream(user_id="user-123")
        async for event in stream.event_generator():
            yield event  # SSE formatted string
    """

    def __init__(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        poll_interval: float = 1.0,
        initial_minutes: int = 5,
    ):
        """
        Initialize SSE stream.

        Args:
            user_id: User ID for HIL task filtering
            session_id: Optional session ID to filter events
            poll_interval: Seconds between polls (default 1s)
            initial_minutes: Minutes of history for initial batch
        """
        self.user_id = user_id
        self.session_id = session_id
        self.poll_interval = poll_interval
        self.initial_minutes = initial_minutes

        # Track last event time to avoid duplicates
        self.last_event_time = datetime.utcnow() - timedelta(minutes=initial_minutes)
        self.seen_event_ids: set = set()
        self.session_timings: Dict[str, datetime] = {}

    async def event_generator(self) -> AsyncGenerator[str, None]:
        """
        Generate SSE events for the connected client.

        Yields:
            SSE formatted strings: "data: {json}\n\n"
        """
        # Send initial batch of recent events
        try:
            initial_events = await self._get_initial_events()
            for event in initial_events:
                self.seen_event_ids.add(event["id"])
                yield self._format_sse(event)
        except Exception as e:
            debug_error(e, "sse_get_initial_events", {"session_id": self.session_id})
            yield self._format_sse({"type": "error", "message": str(e)})

        # Stream new events as they arrive
        while True:
            try:
                new_events = await self._poll_new_events()
                for event in new_events:
                    if event["id"] not in self.seen_event_ids:
                        self.seen_event_ids.add(event["id"])
                        yield self._format_sse(event)

                        # Keep seen_event_ids bounded
                        if len(self.seen_event_ids) > 500:
                            # Remove oldest half
                            self.seen_event_ids = set(list(self.seen_event_ids)[-250:])

            except asyncio.CancelledError:
                # Client disconnected
                break
            except Exception as e:
                debug_error(e, "sse_poll_events", {"session_id": self.session_id})
                yield self._format_sse({"type": "error", "message": str(e)})

            await asyncio.sleep(self.poll_interval)

    async def _get_initial_events(self) -> List[Dict[str, Any]]:
        """Get initial batch of events (recent history)."""
        from tools.agent_room_service import get_recent_events, get_pending_decisions

        # Get recent agent events
        events = get_recent_events(days_back=1, limit=50)

        # Convert to raw format for enrichment
        raw_events = []
        for e in events:
            raw_events.append({
                "event_id": e.get("id"),
                "timestamp": e.get("timestamp"),
                "actor_id": e.get("agentName", "").lower().replace(" ", "_"),  # Reverse lookup
                "action": e.get("type", "trabalhando"),
                "details": {"message": e.get("message", "")},
                "event_type": e.get("eventType", "AGENT_ACTIVITY"),
            })

        enriched = _enrich_events(raw_events, self.session_timings)

        # Get pending HIL tasks and merge
        hil_tasks = get_pending_decisions(self.user_id)
        hil_events = _convert_hil_to_events(hil_tasks)

        # Merge and sort by timestamp (newest first)
        all_events = enriched + hil_events
        all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return all_events[:50]  # Limit initial batch

    async def _poll_new_events(self) -> List[Dict[str, Any]]:
        """Poll for new events since last check."""
        from tools.agent_room_service import get_recent_events, get_pending_decisions

        # Get recent events (will include new ones)
        events = get_recent_events(days_back=1, limit=20)

        # Filter to only newer events
        new_events = []
        for e in events:
            try:
                event_time = datetime.fromisoformat(
                    e.get("timestamp", "").replace("Z", "+00:00")
                )
                if event_time > self.last_event_time:
                    new_events.append({
                        "event_id": e.get("id"),
                        "timestamp": e.get("timestamp"),
                        "actor_id": e.get("agentName", "").lower().replace(" ", "_"),
                        "action": e.get("type", "trabalhando"),
                        "details": {"message": e.get("message", "")},
                        "event_type": e.get("eventType", "AGENT_ACTIVITY"),
                    })
            except (ValueError, TypeError):
                continue

        if new_events:
            # Update last event time
            latest = max(
                datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                for e in new_events
            )
            self.last_event_time = latest

        enriched = _enrich_events(new_events, self.session_timings)

        # Also check for new HIL tasks
        hil_tasks = get_pending_decisions(self.user_id)
        hil_events = _convert_hil_to_events(hil_tasks)

        # Only include HIL events not already seen
        new_hil = [h for h in hil_events if h["id"] not in self.seen_event_ids]

        return enriched + new_hil

    def _format_sse(self, event: Dict[str, Any]) -> str:
        """Format event as SSE message."""
        return f"data: {json.dumps(event, default=str)}\n\n"


# =============================================================================
# Heartbeat Generator (keep-alive)
# =============================================================================

async def heartbeat_generator(interval: float = 30.0) -> AsyncGenerator[str, None]:
    """
    Generate periodic heartbeat events to keep connection alive.

    Args:
        interval: Seconds between heartbeats

    Yields:
        SSE formatted heartbeat strings
    """
    while True:
        await asyncio.sleep(interval)
        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
