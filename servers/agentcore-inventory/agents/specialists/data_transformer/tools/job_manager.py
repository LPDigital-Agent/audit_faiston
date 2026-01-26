# =============================================================================
# Job Manager Tool - Phase 4: DataTransformer
# =============================================================================
# Manages Fire-and-Forget job tracking for background ETL processing.
#
# Fire-and-Forget Pattern:
# 1. Job is created and returns job_id immediately
# 2. Processing happens in background
# 3. On completion, notification is saved to AgentCore Memory
# 4. On next user message, orchestrator checks for notifications
#
# ARCHITECTURE (per CLAUDE.md):
# - Jobs stored in memory (MVP) or DynamoDB (production)
# - Notifications via AgentCore Memory (natural conversation UX)
# =============================================================================

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from strands import tool

# A2A Client for inter-agent communication (Strands Framework)
from shared.strands_a2a_client import LocalA2AClient

# Memory (AgentCore Memory SDK)
from shared.memory_manager import AgentMemoryManager, MemoryOriginType

# Schemas
from shared.agent_schemas import TransformationStatus

logger = logging.getLogger(__name__)

# Agent ID for cognitive error routing (matches parent agent)
AGENT_ID = "data_transformer"

# In-memory job storage (MVP - use DynamoDB in production)
# Format: {job_id: TransformationResult-like dict}
_JOBS: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    """Get current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


async def _trigger_observation_analysis(
    session_id: str,
    job_id: str,
    user_id: str,
) -> None:
    """
    Fire-and-forget trigger to ObservationAgent after job completion.

    Non-blocking call to notify the ObservationAgent that a transformation
    job has completed, enabling proactive pattern analysis.

    This follows the Fire-and-Forget pattern:
    - Does NOT block the main flow
    - Logs warnings on failure (does not raise)
    - ObservationAgent analyzes the session asynchronously

    Args:
        session_id: Import session that completed.
        job_id: The completed job identifier.
        user_id: User who owns the data (for actor-scoped analysis).
    """
    try:
        client = LocalA2AClient()
        await client.invoke_agent(
            agent_id="observation",
            payload={
                "action": "analyze_session",
                "session_id": session_id,
                "job_id": job_id,
                "actor_id": user_id,
                "time_window_hours": 24,  # Tactical analysis
            },
            timeout=5.0,  # Short timeout - fire and forget
        )
        logger.info(
            f"[JobManager] Triggered ObservationAgent for session={session_id}, "
            f"job={job_id}"
        )
    except Exception as e:
        # Non-blocking - log warning and continue
        # The main job flow must not be affected by observation failures
        logger.warning(
            f"[JobManager] ObservationAgent trigger failed (non-blocking): {e}"
        )


@tool
def create_job(
    session_id: str,
    s3_key: str,
    user_id: str,
    strategy: str = "LOG_AND_CONTINUE",
) -> str:
    """
    Create a new transformation job and return job_id immediately.

    This is the entry point for Fire-and-Forget pattern. The job_id
    is returned immediately while processing happens in background.

    Args:
        session_id: Import session this job belongs to.
        s3_key: S3 key of the file to process.
        user_id: User who initiated the import.
        strategy: Error handling strategy from preferences.

    Returns:
        JSON string with:
        - success: bool
        - job_id: str (UUID)
        - status: "started"
        - human_message: str (pt-BR)

    Raises:
        None: This function does not raise exceptions; always returns valid JSON.
    """
    try:
        job_id = f"job-{uuid.uuid4().hex[:12]}"

        job_data = {
            "job_id": job_id,
            "session_id": session_id,
            "s3_key": s3_key,
            "user_id": user_id,
            "status": TransformationStatus.STARTED.value,
            "strategy_used": strategy,
            "rows_total": 0,
            "rows_processed": 0,
            "rows_inserted": 0,
            "rows_rejected": 0,
            "rejection_report_url": None,
            "rejection_summary": [],
            "human_message": "Processamento iniciado em background.",
            "started_at": _now_iso(),
            "completed_at": None,
            "debug_analysis": None,
        }

        _JOBS[job_id] = job_data

        logger.info(
            f"[JobManager] Created job {job_id} for session {session_id}, "
            f"s3_key={s3_key}, strategy={strategy}"
        )

        return json.dumps({
            "success": True,
            "job_id": job_id,
            "status": "started",
            "human_message": (
                "Iniciando processamento em background. "
                "Você será notificado quando terminar."
            ),
        })

    except Exception as e:
        logger.exception(f"[JobManager] Error creating job: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@tool
def get_job_status(job_id: str) -> str:
    """
    Get current status of a transformation job.

    Used by orchestrator to check on background jobs when user asks
    "Como está a importação?" or on periodic status checks.

    Args:
        job_id: Unique job identifier from create_job.

    Returns:
        JSON string with full job status including progress metrics.

    Raises:
        None: This function does not raise exceptions; returns error JSON if job not found.
    """
    try:
        if job_id not in _JOBS:
            logger.warning(f"[JobManager] Job {job_id} not found")
            return json.dumps({
                "success": False,
                "error": f"Job {job_id} not found",
                "human_message": "Não encontrei esse job. Pode ter expirado.",
            })

        job = _JOBS[job_id]

        # Calculate progress percentage
        progress = 0
        if job["rows_total"] > 0:
            progress = int((job["rows_processed"] / job["rows_total"]) * 100)

        logger.info(
            f"[JobManager] Status check for job {job_id}: "
            f"status={job['status']}, progress={progress}%"
        )

        return json.dumps({
            "success": True,
            **job,
            "progress_percent": progress,
        })

    except Exception as e:
        logger.exception(f"[JobManager] Error getting job status: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@tool
def update_job_status(
    job_id: str,
    status: str = "",
    rows_total: int = -1,
    rows_processed: int = -1,
    rows_inserted: int = -1,
    rows_rejected: int = -1,
    rejection_report_url: str = "",
    rejection_summary: str = "[]",
    human_message: str = "",
    debug_analysis: str = "",
) -> str:
    """
    Update job status during processing.

    Called by ETL stream tool as processing progresses. Only updates
    fields that are provided (non-default values).

    Args:
        job_id: Unique job identifier.
        status: New status (started, processing, completed, failed, partial).
        rows_total: Total rows in file (set once on start).
        rows_processed: Rows processed so far.
        rows_inserted: Rows successfully inserted.
        rows_rejected: Rows that failed.
        rejection_report_url: S3 presigned URL for report.
        rejection_summary: JSON string of first 10 rejections.
        human_message: User-facing status message.
        debug_analysis: JSON string of DebugAgent analysis.

    Returns:
        JSON string with updated job status.

    Raises:
        json.JSONDecodeError: If rejection_summary or debug_analysis contains invalid JSON (caught internally).
        A2AClientError: If ObservationAgent trigger fails (non-blocking, logged as warning).
    """
    try:
        if job_id not in _JOBS:
            return json.dumps({
                "success": False,
                "error": f"Job {job_id} not found",
            })

        job = _JOBS[job_id]

        # Update only provided fields
        if status:
            job["status"] = status
        if rows_total >= 0:
            job["rows_total"] = rows_total
        if rows_processed >= 0:
            job["rows_processed"] = rows_processed
        if rows_inserted >= 0:
            job["rows_inserted"] = rows_inserted
        if rows_rejected >= 0:
            job["rows_rejected"] = rows_rejected
        if rejection_report_url:
            job["rejection_report_url"] = rejection_report_url
        if rejection_summary and rejection_summary != "[]":
            try:
                job["rejection_summary"] = json.loads(rejection_summary)
            except json.JSONDecodeError:
                pass
        if human_message:
            job["human_message"] = human_message
        if debug_analysis:
            try:
                job["debug_analysis"] = json.loads(debug_analysis)
            except json.JSONDecodeError:
                pass

        # Set completed_at if terminal status
        if status in ["completed", "failed", "partial"]:
            job["completed_at"] = _now_iso()

            # Fire-and-forget: Trigger ObservationAgent for pattern analysis
            # This is non-blocking and does not affect the job completion flow
            try:
                asyncio.create_task(
                    _trigger_observation_analysis(
                        session_id=job["session_id"],
                        job_id=job_id,
                        user_id=job["user_id"],
                    )
                )
            except RuntimeError:
                # No running event loop - skip observation trigger
                logger.warning(
                    f"[JobManager] Cannot trigger ObservationAgent: no running event loop"
                )

        logger.info(
            f"[JobManager] Updated job {job_id}: status={job['status']}, "
            f"processed={job['rows_processed']}/{job['rows_total']}"
        )

        return json.dumps({
            "success": True,
            "job_id": job_id,
            "status": job["status"],
        })

    except Exception as e:
        logger.exception(f"[JobManager] Error updating job status: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@tool
def save_job_notification(
    job_id: str,
    user_id: str,
) -> str:
    """
    Save job completion notification to AgentCore Memory.

    Called when job finishes (completed, failed, or partial). The
    notification is stored in Memory and retrieved on next user message
    by the orchestrator, enabling natural conversation UX.

    Args:
        job_id: Unique job identifier.
        user_id: User to notify.

    Returns:
        JSON string with memory_id of saved notification.

    Raises:
        MemoryAPIError: If AgentCore Memory save fails (caught internally).
    """
    if job_id not in _JOBS:
        return json.dumps({
            "success": False,
            "error": f"Job {job_id} not found",
        })

    job = _JOBS[job_id]

    # Build notification content
    notification = {
        "job_id": job_id,
        "job_type": "transformation",
        "status": job["status"],
        "rows_inserted": job["rows_inserted"],
        "rows_rejected": job["rows_rejected"],
        "rejection_report_url": job.get("rejection_report_url"),
        "human_message": _build_completion_message(job),
        "created_at": _now_iso(),
    }

    try:
        memory_manager = AgentMemoryManager()

        # Save notification to user's Memory (STM for quick retrieval)
        memory_id = memory_manager.save_memory(
            type="NOTIFICATION",
            category="job_completion",
            content=notification,
            actor_id=user_id,
        )

        logger.info(
            f"[JobManager] Saved notification for job {job_id} to user {user_id}: "
            f"memory_id={memory_id}"
        )

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "notification": notification,
        })

    except Exception as e:
        logger.error(
            f"[JobManager] Failed to save notification for job {job_id}: {e}"
        )
        return json.dumps({
            "success": False,
            "error": str(e),
        })


def _build_completion_message(job: Dict[str, Any]) -> str:
    """Build user-friendly completion message in pt-BR."""
    status = job["status"]
    inserted = job["rows_inserted"]
    rejected = job["rows_rejected"]

    if status == "completed":
        return (
            f"Importacao finalizada com sucesso! "
            f"{inserted} itens inseridos."
        )
    elif status == "partial":
        return (
            f"Importacao finalizada com alguns erros. "
            f"{inserted} itens inseridos, {rejected} rejeitados. "
            f"Baixe o relatorio de rejeicoes para ver os detalhes."
        )
    elif status == "failed":
        return (
            f"A importacao falhou. "
            f"Verifique o relatorio de erros para mais detalhes."
        )
    else:
        return f"Job status: {status}"


@tool
def check_pending_notifications(user_id: str) -> str:
    """
    Check for pending job notifications for a user.

    Called by orchestrator at start of each request to check if any
    background jobs have completed since the last message.

    Args:
        user_id: User to check notifications for.

    Returns:
        JSON string with list of pending notifications.

    Raises:
        MemoryAPIError: If AgentCore Memory query fails (caught internally).
    """
    try:
        memory_manager = AgentMemoryManager()

        # Query pending notifications from Memory
        notifications = memory_manager.observe(
            query="pending job notifications",
            category="job_completion",
            actor_id=user_id,
            max_results=5,
        )

        if not notifications:
            return json.dumps({
                "success": True,
                "has_notifications": False,
                "notifications": [],
            })

        logger.info(
            f"[JobManager] Found {len(notifications)} pending notifications "
            f"for user {user_id}"
        )

        return json.dumps({
            "success": True,
            "has_notifications": True,
            "notifications": [n.get("content", {}) for n in notifications],
        })

    except Exception as e:
        logger.error(
            f"[JobManager] Failed to check notifications for user {user_id}: {e}"
        )
        return json.dumps({
            "success": False,
            "error": str(e),
            "has_notifications": False,
            "notifications": [],
        })
