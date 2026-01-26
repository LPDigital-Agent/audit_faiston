"""
Job Service - Phase 4 ETL Job Management for NEXO Import Pipeline.

This service encapsulates the fire-and-forget ETL processing via A2A
communication with the DataTransformer agent.

Phase 4 Flow:
1. InventoryHub calls invoke_transform_import() after HIL confirmation (Phase 3)
2. DataTransformer agent receives the job and starts async processing
3. Job ID is returned immediately (fire-and-forget pattern)
4. Frontend can poll check_import_job_status() for progress updates
5. Job completion notifications are delivered via check_notifications()

Architecture:
- A2A via Strands Framework (IMMUTABLE rule: CLAUDE.md lines 31-36)
- Sync-to-async bridge using asyncio event loop management
- PII-safe logging via flow_log (count-only pattern)
- Cognitive error handling with DebugAgent enrichment

Reference:
- DataTransformer Agent: server/agentcore-inventory/agents/specialists/data_transformer/main.py
- Frontend Contract: client/services/sgaAgentcore.ts (ImportJobStatus interface)
"""

import asyncio
import json
import logging
from typing import Any

from shared.cognitive_error_handler import cognitive_sync_handler
from shared.flow_logger import flow_log
from shared.strands_a2a_client import A2AClient

logger = logging.getLogger(__name__)

__all__ = [
    "invoke_transform_import",
    "check_import_job_status",
]


@cognitive_sync_handler("inventory_hub")
def invoke_transform_import(
    s3_key: str,
    mappings: list[dict[str, Any]],
    session_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Invoke DataTransformer via A2A for fire-and-forget ETL processing.

    This is the entry point for Phase 4 of the NEXO import pipeline. After
    the user confirms the column mappings (Phase 3 HIL), this function
    triggers the DataTransformer agent to:
    1. Read the source file from S3
    2. Apply column mappings
    3. Transform data to target schema
    4. Insert rows into Aurora PostgreSQL (pending_entry_items table)
    5. Post completion notification to AgentCore Memory

    The function returns immediately with a job_id (fire-and-forget pattern).
    The user is notified of completion via check_notifications().

    Args:
        s3_key: S3 key of the uploaded file to transform.
            Example: "uploads/user123/session456/inventory.csv"
        mappings: List of confirmed column mappings from SchemaMapper.
            Each mapping contains:
            {
                "source_column": "COD",
                "target_column": "part_number",
                "confidence": 0.95,
                "transform": None | "uppercase" | "trim" | ...
            }
        session_id: Import session identifier for tracing.
            Example: "nexo_20260125_143000_inventory.csv"
        user_id: User who initiated the import (for notifications).
            Example: "user123"

    Returns:
        Job initiation response dict:
        {
            "success": True,
            "job_id": "job-abc123-def456",
            "status": "started",
            "human_message": "Processamento iniciado em background..."
        }

        On error:
        {
            "success": False,
            "error": "Error description",
            "human_message": "User-friendly message in pt-BR"
        }

    Example:
        >>> result = invoke_transform_import(
        ...     s3_key="uploads/user123/file.csv",
        ...     mappings=[{"source_column": "COD", "target_column": "part_number"}],
        ...     session_id="nexo_123",
        ...     user_id="user123"
        ... )
        >>> if result.get("success"):
        ...     job_id = result["job_id"]
        ...     print(f"Job started: {job_id}")

    Frontend Contract:
        TypeScript interface at client/services/sgaAgentcore.ts (TransformImportResponse)
    """
    # Log Phase 4 start with count-only pattern (PII-safe)
    flow_log.phase_start(
        4,
        "DataTransformer",
        session_id,
        s3_key=s3_key,
        mappings_count=len(mappings),
    )

    async def _invoke_transformer() -> dict[str, Any]:
        """Async wrapper for A2A invocation to DataTransformer."""
        a2a_client = A2AClient()

        # Convert mappings to JSON string for A2A payload
        mappings_json = json.dumps(mappings, ensure_ascii=False)

        return await a2a_client.invoke_agent(
            agent_id="data_transformer",
            payload={
                "action": "start_transformation",
                "s3_key": s3_key,
                "mappings": mappings_json,
                "session_id": session_id,
                "user_id": user_id,
                "fire_and_forget": True,
            },
            session_id=session_id,
            timeout=30.0,  # Short timeout - fire-and-forget handoff
        )

    try:
        logger.info(
            f"[JobService] Starting transformation: session={session_id}, "
            f"s3_key={s3_key}, user={user_id}, mappings_count={len(mappings)}"
        )

        # Sync-to-async bridge pattern (same as mapping_service.py)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_invoke_transformer())

        # Extract response from A2AResponse
        if hasattr(result, "success") and not result.success:
            error_msg = getattr(result, "error", "DataTransformer unavailable")
            logger.warning(f"[JobService] A2A call failed: {error_msg}")

            flow_log.phase_end(
                4,
                "DataTransformer",
                session_id,
                "HANDOFF_FAILED",
                0,
                error=error_msg,
            )

            return {
                "success": False,
                "error": error_msg,
                "human_message": (
                    "Nao consegui iniciar o processamento. "
                    "Por favor, tente novamente em alguns minutos."
                ),
            }

        # Parse response
        response_data = getattr(result, "response", result)
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError:
                logger.warning("[JobService] Could not parse response as JSON")
                response_data = {"raw_response": response_data}

        # Check if response indicates success
        if isinstance(response_data, dict):
            job_id = response_data.get("job_id")

            if job_id or response_data.get("success", False):
                logger.info(f"[JobService] Transformation started: job_id={job_id}")

                flow_log.decision(
                    "Transformation job started",
                    session_id=session_id,
                    job_id=job_id,
                    status="STARTED",
                )
                flow_log.phase_end(
                    4,
                    "DataTransformer",
                    session_id,
                    "HANDOFF_SUCCESS",
                    0,
                    job_id=job_id,
                )

                return {
                    "success": True,
                    "job_id": job_id,
                    "status": "started",
                    "human_message": (
                        "Iniciei o processamento do seu arquivo em background. "
                        "Te aviso assim que terminar!"
                    ),
                }

        # Fallback for unexpected response format
        logger.warning(f"[JobService] Unexpected response format: {type(response_data)}")
        flow_log.phase_end(
            4,
            "DataTransformer",
            session_id,
            "HANDOFF_FAILED",
            0,
            error="Unexpected response format",
        )

        return {
            "success": False,
            "error": "Unexpected response from DataTransformer",
            "human_message": (
                "Recebi uma resposta inesperada do processador. "
                "Por favor, tente novamente."
            ),
        }

    except Exception as e:
        logger.exception(f"[JobService] Error invoking DataTransformer: {e}")

        flow_log.phase_end(
            4,
            "DataTransformer",
            session_id,
            "EXCEPTION",
            0,
            error_type=type(e).__name__,
        )

        # Re-raise to let @cognitive_sync_handler enrich the error
        raise


@cognitive_sync_handler("inventory_hub")
def check_import_job_status(job_id: str, user_id: str) -> dict[str, Any]:
    """
    Check status of a running import job via DataTransformer A2A.

    Called when the user asks about import progress, e.g.,
    "Como esta a importacao?" or "Ja terminou?"

    This function queries the DataTransformer agent for the current
    status of a background ETL job.

    Args:
        job_id: Job identifier from invoke_transform_import response.
            Example: "job-abc123-def456"
        user_id: User identifier for authorization check.
            Example: "user123"

    Returns:
        Job status response dict:
        {
            "success": True,
            "job_id": "job-abc123",
            "status": "processing" | "completed" | "failed" | "pending",
            "progress": {
                "rows_processed": 750,
                "rows_total": 1500,
                "rows_inserted": 740,
                "rows_rejected": 10,
                "percentage": 50
            },
            "human_message": "Processando... 50% concluido (750/1500 linhas)"
        }

        When completed:
        {
            "success": True,
            "job_id": "job-abc123",
            "status": "completed",
            "progress": {
                "rows_processed": 1500,
                "rows_total": 1500,
                "rows_inserted": 1480,
                "rows_rejected": 20,
                "percentage": 100
            },
            "human_message": "Importacao finalizada! 1480 itens inseridos, 20 rejeitados."
        }

        On error:
        {
            "success": False,
            "error": "Job not found",
            "human_message": "Nao encontrei esse job. Verifique o ID."
        }

    Example:
        >>> status = check_import_job_status("job-abc123", "user123")
        >>> if status["status"] == "completed":
        ...     print(f"Done! {status['progress']['rows_inserted']} rows inserted")

    Frontend Contract:
        TypeScript interface at client/services/sgaAgentcore.ts (ImportJobStatus)
    """
    async def _check_status() -> dict[str, Any]:
        """Async wrapper for A2A call to DataTransformer."""
        a2a_client = A2AClient()

        return await a2a_client.invoke_agent(
            agent_id="data_transformer",
            payload={
                "action": "get_job_status",
                "job_id": job_id,
                "user_id": user_id,
            },
            timeout=15.0,  # Short timeout for status check
        )

    try:
        logger.info(f"[JobService] Checking job status: job_id={job_id}, user={user_id}")

        # Sync-to-async bridge pattern
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_check_status())

        # Extract response from A2AResponse
        if hasattr(result, "success") and not result.success:
            error_msg = getattr(result, "error", "Status check failed")
            logger.warning(f"[JobService] Status check A2A failed: {error_msg}")

            return {
                "success": False,
                "job_id": job_id,
                "error": error_msg,
                "human_message": (
                    "Nao consegui verificar o status do job. "
                    "Tente novamente em alguns segundos."
                ),
            }

        # Parse response
        response_data = getattr(result, "response", result)
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError:
                logger.warning("[JobService] Could not parse status response as JSON")
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": "Invalid response format",
                    "human_message": "Resposta invalida do processador.",
                }

        if isinstance(response_data, dict):
            status = response_data.get("status", "unknown")
            progress = response_data.get("progress", {})

            logger.info(
                f"[JobService] Job status: job_id={job_id}, status={status}, "
                f"progress={progress.get('percentage', 0)}%"
            )

            # Build human-readable message based on status
            human_message = _build_status_message(status, progress)

            return {
                "success": True,
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "human_message": human_message,
            }

        # Fallback
        return {
            "success": False,
            "job_id": job_id,
            "error": "Unexpected response format",
            "human_message": "Resposta inesperada do processador.",
        }

    except Exception as e:
        logger.exception(f"[JobService] Error checking job status: {e}")
        # Re-raise to let @cognitive_sync_handler enrich the error
        raise


def _build_status_message(status: str, progress: dict[str, Any]) -> str:
    """
    Build human-readable status message in pt-BR.

    Args:
        status: Job status string (pending/processing/completed/failed)
        progress: Progress dict with rows_processed, rows_total, etc.

    Returns:
        User-friendly message in Brazilian Portuguese
    """
    rows_processed = progress.get("rows_processed", 0)
    rows_total = progress.get("rows_total", 0)
    rows_inserted = progress.get("rows_inserted", 0)
    rows_rejected = progress.get("rows_rejected", 0)
    percentage = progress.get("percentage", 0)

    if status == "pending":
        return "Job na fila de processamento. Aguarde..."

    elif status == "processing":
        if rows_total > 0:
            return (
                f"Processando... {percentage}% concluido "
                f"({rows_processed}/{rows_total} linhas)"
            )
        return "Processando arquivo..."

    elif status == "completed":
        if rows_rejected > 0:
            return (
                f"Importacao finalizada! {rows_inserted} itens inseridos, "
                f"{rows_rejected} rejeitados."
            )
        return f"Importacao finalizada! {rows_inserted} itens inseridos com sucesso."

    elif status == "failed":
        error_msg = progress.get("error", "Erro desconhecido")
        return f"Importacao falhou: {error_msg}"

    else:
        return f"Status: {status}"
