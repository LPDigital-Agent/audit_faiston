# =============================================================================
# Batch Loader Tool - Phase 4: DataTransformer
# =============================================================================
# Inserts transformed rows via MCP Gateway batch insert.
#
# ARCHITECTURE (per CLAUDE.md):
# - NEVER insert row-by-row (anti-pattern for 10k+ rows)
# - Use MCP Gateway sga_insert_pending_items_batch tool
# - Batch size: 500 rows per call (balances performance vs Lambda timeout)
#
# SANDWICH PATTERN:
# - CODE (etl_stream): Prepare batches
# - LLM (agent): Decide on retry strategy
# - CODE (this tool): Execute MCP batch insert
# =============================================================================

import json
import logging
import os
from typing import Any, Dict, List, Optional

from strands import tool

# MCP Gateway client (uses IAM SigV4 auth per AWS best practices)
from tools.mcp_gateway_client import MCPGatewayClient, MCPGatewayClientFactory

# FAIL-CLOSED environment configuration (no production fallbacks)
from shared.env_config import get_required_env

logger = logging.getLogger(__name__)

# Batch configuration
BATCH_SIZE = 500  # Rows per MCP call

# Singleton client instance
_mcp_client: Optional[MCPGatewayClient] = None


def _get_mcp_client() -> MCPGatewayClient:
    """Get MCP Gateway client singleton (lazy initialization)."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPGatewayClientFactory.create_from_env()
    return _mcp_client


@tool
def insert_pending_items_batch(
    rows_json: str,
    session_id: str,
    batch_number: int = 1,
) -> str:
    """
    Insert transformed rows via MCP Gateway batch insert.

    Uses the sga_insert_pending_items_batch MCP tool for efficient
    batch insertion. Returns detailed results including any row-level
    errors for rejection report.

    Args:
        rows_json: JSON string of transformed rows to insert.
        session_id: Import session for tracking.
        batch_number: Batch number for logging/tracking.

    Returns:
        JSON string with:
        - success: bool
        - inserted_count: int
        - error_count: int
        - errors: List of row-level insertion errors
    """
    try:
        rows = json.loads(rows_json)
        if not rows:
            return json.dumps({
                "success": True,
                "inserted_count": 0,
                "error_count": 0,
                "errors": [],
                "message": "No rows to insert",
            })

        logger.info(
            f"[BatchLoader] Inserting batch {batch_number}: "
            f"{len(rows)} rows for session {session_id}"
        )

        # Get MCP Gateway client
        mcp_client = _get_mcp_client()

        # Call MCP batch insert tool
        result = mcp_client.invoke_tool(
            tool_name="sga_insert_pending_items_batch",
            parameters={
                "rows": rows,
                "session_id": session_id,
            },
        )

        if not result.get("success"):
            error_msg = result.get("error", "Unknown MCP error")
            logger.error(
                f"[BatchLoader] MCP batch insert failed for batch {batch_number}: "
                f"{error_msg}"
            )
            return json.dumps({
                "success": False,
                "error": error_msg,
                "inserted_count": 0,
                "error_count": len(rows),
                "batch_number": batch_number,
            })

        inserted_count = result.get("inserted_count", 0)
        errors = result.get("errors", [])

        logger.info(
            f"[BatchLoader] Batch {batch_number} complete: "
            f"{inserted_count} inserted, {len(errors)} errors"
        )

        return json.dumps({
            "success": True,
            "inserted_count": inserted_count,
            "error_count": len(errors),
            "errors": errors,
            "batch_number": batch_number,
        })

    except json.JSONDecodeError as e:
        logger.error(f"[BatchLoader] Invalid JSON for batch {batch_number}: {e}")
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON: {str(e)}",
            "inserted_count": 0,
            "error_count": 0,
        })

    except Exception as e:
        logger.error(
            f"[BatchLoader] Unexpected error in batch {batch_number}: {e}"
        )
        return json.dumps({
            "success": False,
            "error": str(e),
            "inserted_count": 0,
            "error_count": 0,
        })


@tool
def insert_all_batches(
    batches_json: str,
    session_id: str,
) -> str:
    """
    Insert all batches sequentially with progress tracking.

    Wrapper around insert_pending_items_batch that handles multiple
    batches and aggregates results. Continues on individual batch
    failure to maximize data ingestion.

    Args:
        batches_json: JSON string of list of batches (list of list of rows).
        session_id: Import session for tracking.

    Returns:
        JSON string with aggregated results across all batches.
    """
    try:
        batches = json.loads(batches_json)
        if not batches:
            return json.dumps({
                "success": True,
                "total_inserted": 0,
                "total_errors": 0,
                "batches_processed": 0,
                "batch_results": [],
            })

        total_inserted = 0
        total_errors = 0
        all_errors = []
        batch_results = []

        logger.info(
            f"[BatchLoader] Processing {len(batches)} batches for session {session_id}"
        )

        for batch_num, batch in enumerate(batches, start=1):
            # Insert each batch
            result_str = insert_pending_items_batch(
                rows_json=json.dumps(batch),
                session_id=session_id,
                batch_number=batch_num,
            )
            result = json.loads(result_str)

            total_inserted += result.get("inserted_count", 0)
            batch_errors = result.get("errors", [])
            total_errors += len(batch_errors)
            all_errors.extend(batch_errors)

            batch_results.append({
                "batch_number": batch_num,
                "rows": len(batch),
                "inserted": result.get("inserted_count", 0),
                "errors": len(batch_errors),
                "success": result.get("success", False),
            })

        success = total_inserted > 0 or total_errors == 0

        logger.info(
            f"[BatchLoader] All batches complete: "
            f"{total_inserted} inserted, {total_errors} errors"
        )

        return json.dumps({
            "success": success,
            "total_inserted": total_inserted,
            "total_errors": total_errors,
            "batches_processed": len(batches),
            "batch_results": batch_results,
            "all_errors": all_errors[:50],  # Limit for response size
        })

    except json.JSONDecodeError as e:
        logger.error(f"[BatchLoader] Invalid batches JSON: {e}")
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON: {str(e)}",
            "total_inserted": 0,
            "total_errors": 0,
        })

    except Exception as e:
        logger.error(f"[BatchLoader] Unexpected error processing batches: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "total_inserted": 0,
            "total_errors": 0,
        })


@tool
def generate_rejection_report(
    errors_json: str,
    enriched_errors_json: str,
    session_id: str,
    job_id: str,
) -> str:
    """
    Generate and upload rejection report to S3.

    Creates a JSON report with enriched errors (human_explanation +
    suggested_fix) and uploads to S3. Returns presigned URL for
    user download.

    Args:
        errors_json: JSON string of raw transformation errors.
        enriched_errors_json: JSON string of DebugAgent-enriched errors.
        session_id: Import session identifier.
        job_id: Job ID for report naming.

    Returns:
        JSON string with presigned_url for report download.
    """
    import boto3
    from datetime import datetime, timezone

    try:
        raw_errors = json.loads(errors_json) if errors_json else []
        enriched_errors = json.loads(enriched_errors_json) if enriched_errors_json else []

        # Build report structure
        report = {
            "job_id": job_id,
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_rejections": len(raw_errors),
            "rejections": [],
        }

        # Merge raw and enriched errors
        enriched_map = {
            (e.get("row_number"), e.get("column")): e
            for e in enriched_errors
        }

        for raw in raw_errors:
            key = (raw.get("row_number"), raw.get("column"))
            enriched = enriched_map.get(key, {})

            report["rejections"].append({
                "row_number": raw.get("row_number"),
                "column": raw.get("column"),
                "original_value": raw.get("original_value"),
                "error_type": raw.get("error_type", "Unknown"),
                "human_explanation": enriched.get(
                    "human_explanation",
                    raw.get("raw_error", "Error during transformation")
                ),
                "suggested_fix": enriched.get(
                    "suggested_fix",
                    "Please review and correct the value"
                ),
            })

        # Upload to S3 (FAIL-CLOSED: no production fallbacks)
        report_key = f"rejection-reports/{session_id}/{job_id}-report.json"
        bucket = get_required_env("DOCUMENTS_BUCKET", "rejection report upload")

        try:
            session = boto3.Session(profile_name="faiston-aio")
            s3 = session.client("s3")
        except Exception:
            s3 = boto3.client("s3")

        s3.put_object(
            Bucket=bucket,
            Key=report_key,
            Body=json.dumps(report, ensure_ascii=False, indent=2),
            ContentType="application/json",
        )

        # Generate presigned URL (valid for 7 days)
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": report_key},
            ExpiresIn=604800,  # 7 days
        )

        logger.info(
            f"[BatchLoader] Rejection report uploaded: {report_key} "
            f"({len(report['rejections'])} rejections)"
        )

        return json.dumps({
            "success": True,
            "report_key": report_key,
            "presigned_url": presigned_url,
            "rejection_count": len(report["rejections"]),
        })

    except Exception as e:
        logger.error(f"[BatchLoader] Failed to generate rejection report: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })
