"""
Execution tools for InventoryHub orchestrator.

These tools handle import transformation, job status checking,
and notification delivery for background processing workflows.
"""

import asyncio
import json
import logging

from strands import tool

from shared.debug_utils import debug_error
from shared.flow_logger import flow_log
from shared.strands_a2a_client import A2AClient

__all__ = ["transform_import", "check_import_status", "check_notifications"]

logger = logging.getLogger(__name__)


@tool
def transform_import(
    s3_key: str,
    mappings_json: str,
    session_id: str,
    user_id: str,
) -> str:
    """
    Trigger DataTransformer agent for background processing (Fire-and-Forget).

    After HIL confirmation of mappings (confirm_mapping with approved=True),
    this tool starts the actual data transformation and loading process.
    The DataTransformer works in background - returns job_id immediately.

    Args:
        s3_key: S3 key of the uploaded file to transform.
        mappings_json: JSON string of confirmed column mappings from SchemaMapper.
        session_id: Import session identifier.
        user_id: User who initiated the import.

    Returns:
        JSON string with job_id and status="started" (Fire-and-Forget).
        Example:
        {
            "success": true,
            "job_id": "job-abc123",
            "status": "started",
            "human_message": "Processamento iniciado em background..."
        }
    """
    try:
        mappings = json.loads(mappings_json)
        mappings_count = len(mappings) if isinstance(mappings, list) else 0
    except json.JSONDecodeError:
        mappings_count = 0

    flow_log.phase_start(4, "DataTransformer", session_id, s3_key=s3_key, mappings_count=mappings_count)

    async def _invoke_transformer() -> dict:
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent("data_transformer", {
            "action": "start_transformation",
            "s3_key": s3_key,
            "mappings": mappings_json,
            "session_id": session_id,
            "user_id": user_id,
            "fire_and_forget": True,
        })

    try:
        logger.info(
            f"[InventoryHub] Starting transformation for session {session_id}, "
            f"s3_key={s3_key}, user={user_id}"
        )

        result = asyncio.run(_invoke_transformer())

        if result.get("success"):
            job_id = result.get("job_id")
            logger.info(f"[InventoryHub] Transformation started: job_id={job_id}")

            flow_log.decision(
                "Transformation job started",
                session_id=session_id,
                job_id=job_id,
                status="STARTED"
            )
            flow_log.phase_end(4, "DataTransformer", session_id, "HANDOFF_SUCCESS", 0, job_id=job_id)

            return json.dumps({
                "success": True,
                "job_id": job_id,
                "status": "started",
                "human_message": (
                    "Iniciei o processamento do seu arquivo em background. "
                    "Te aviso assim que terminar!"
                ),
            })
        else:
            error_msg = result.get("error", "DataTransformer unavailable")
            flow_log.phase_end(4, "DataTransformer", session_id, "HANDOFF_FAILED", 0, error=error_msg)

            return json.dumps({
                "success": False,
                "error": error_msg,
                "human_message": (
                    "Nao consegui iniciar o processamento. "
                    "Por favor, tente novamente em alguns minutos."
                ),
            })

    except Exception as e:
        debug_error(e, "transform_import", {
            "s3_key": s3_key,
            "session_id": session_id,
        })

        flow_log.phase_end(4, "DataTransformer", session_id, "EXCEPTION", 0, error_type=type(e).__name__)

        return json.dumps({
            "success": False,
            "error": f"Failed to start transformation: {str(e)}",
            "error_type": "A2A_ERROR",
        })


@tool
def check_import_status(job_id: str) -> str:
    """
    Check status of a background transformation job.

    Use this when the user asks about import progress, e.g.,
    "Como esta a importacao?" or "Ja terminou?"

    Args:
        job_id: Job identifier from transform_import response.

    Returns:
        JSON string with current job status and progress.
    """
    async def _check_status() -> dict:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent("data_transformer", {
            "action": "get_job_status",
            "job_id": job_id,
        })

    try:
        result = asyncio.run(_check_status())
        return json.dumps(result)

    except Exception as e:
        debug_error(e, "check_import_status", {"job_id": job_id})
        return json.dumps({
            "success": False,
            "error": f"Failed to check status: {str(e)}",
            "error_type": "A2A_ERROR",
        })


@tool
def check_notifications(user_id: str) -> str:
    """
    Check for pending job completion notifications.

    Called at the start of each conversation turn to see if any
    background jobs have completed since the last message.
    Part of the Fire-and-Forget UX - notifications appear naturally
    in the conversation flow.

    Args:
        user_id: User to check notifications for.

    Returns:
        JSON string with list of pending notifications.
        Example:
        {
            "has_notifications": true,
            "notifications": [{
                "job_id": "job-abc123",
                "status": "completed",
                "rows_inserted": 1480,
                "rows_rejected": 20,
                "human_message": "Importacao finalizada! 1480 itens inseridos."
            }]
        }
    """
    async def _check() -> dict:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent("data_transformer", {
            "action": "check_notifications",
            "user_id": user_id,
        })

    try:
        result = asyncio.run(_check())
        return json.dumps(result)

    except Exception as e:
        debug_error(e, "check_notifications", {"user_id": user_id})
        return json.dumps({
            "success": False,
            "has_notifications": False,
            "notifications": [],
            "error": str(e),
        })
