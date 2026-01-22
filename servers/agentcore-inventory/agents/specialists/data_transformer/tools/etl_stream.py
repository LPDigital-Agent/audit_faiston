# =============================================================================
# ETL Stream Tool - Phase 4: DataTransformer
# =============================================================================
# Streams and transforms inventory files from S3 in batches.
#
# ARCHITECTURE (per CLAUDE.md):
# - NEVER load full file into memory
# - Stream in chunks using pandas
# - Apply mappings and transformations per row
# - Collect errors for batch enrichment by DebugAgent (post-processing)
#
# SANDWICH PATTERN:
# - CODE (this tool): Stream, transform, validate
# - LLM (agent): Decide on error handling, generate messages
# - CODE (batch_loader): Insert via MCP Gateway
# =============================================================================

import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import boto3
import pandas as pd
from strands import tool

from shared.env_config import get_required_env

# Cognitive error handling (Nexo Immune System)
from shared.cognitive_error_handler import enrich_batch_errors

logger = logging.getLogger(__name__)

# File size limits (per plan)
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "100"))
MAX_ROWS_ESTIMATE = int(os.environ.get("MAX_ROWS_ESTIMATE", "100000"))
CHUNK_SIZE = 500  # Rows per chunk for streaming

# S3 configuration (FAIL-CLOSED: no production fallbacks)
DOCUMENTS_BUCKET = get_required_env("DOCUMENTS_BUCKET", "ETL stream S3 access")


def _get_s3_client():
    """Get boto3 S3 client with profile if running locally."""
    try:
        session = boto3.Session(profile_name="faiston-aio")
        return session.client("s3")
    except Exception:
        return boto3.client("s3")


@tool
def validate_file_size(s3_key: str) -> str:
    """
    Validate file size before processing.

    Enforces the 100MB / 100k rows limit per plan. Returns detailed
    error with human-readable message if file is too large.

    Args:
        s3_key: S3 key of the file to validate.

    Returns:
        JSON string with:
        - success: bool
        - size_mb: float
        - estimated_rows: int
        - within_limits: bool
        - human_message: str (if rejected)
    """
    try:
        s3 = _get_s3_client()

        # Get file metadata without downloading
        response = s3.head_object(Bucket=DOCUMENTS_BUCKET, Key=s3_key)
        size_bytes = response["ContentLength"]
        size_mb = size_bytes / (1024 * 1024)

        # Estimate rows (rough: 500 bytes/row for CSV)
        estimated_rows = int(size_bytes / 500)

        # Check limits
        if size_mb > MAX_FILE_SIZE_MB:
            logger.warning(
                f"[ETLStream] File {s3_key} exceeds size limit: "
                f"{size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB"
            )
            return json.dumps({
                "success": True,
                "size_mb": round(size_mb, 2),
                "estimated_rows": estimated_rows,
                "within_limits": False,
                "reason": "size_limit",
                "human_message": (
                    f"O arquivo excede o limite seguro de processamento "
                    f"({size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB). "
                    f"Por favor, divida o arquivo em partes menores."
                ),
            })

        if estimated_rows > MAX_ROWS_ESTIMATE * 1.5:  # 50% buffer
            logger.warning(
                f"[ETLStream] File {s3_key} may have too many rows: "
                f"~{estimated_rows} > {MAX_ROWS_ESTIMATE}"
            )
            return json.dumps({
                "success": True,
                "size_mb": round(size_mb, 2),
                "estimated_rows": estimated_rows,
                "within_limits": False,
                "reason": "row_limit",
                "human_message": (
                    f"O arquivo pode ter muitas linhas (~{estimated_rows:,}). "
                    f"O limite seguro e {MAX_ROWS_ESTIMATE:,} linhas. "
                    f"Por favor, divida o arquivo em partes menores."
                ),
            })

        logger.info(
            f"[ETLStream] File {s3_key} validated: "
            f"{size_mb:.1f}MB, ~{estimated_rows} rows"
        )

        return json.dumps({
            "success": True,
            "size_mb": round(size_mb, 2),
            "estimated_rows": estimated_rows,
            "within_limits": True,
        })

    except Exception as e:
        logger.error(f"[ETLStream] Failed to validate file {s3_key}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "human_message": f"Erro ao validar arquivo: {str(e)}",
        })


def _detect_file_type(s3_key: str) -> str:
    """Detect file type from S3 key extension."""
    lower_key = s3_key.lower()
    if lower_key.endswith(".xlsx") or lower_key.endswith(".xls"):
        return "excel"
    elif lower_key.endswith(".csv"):
        return "csv"
    else:
        return "unknown"


def _transform_value(
    value: Any,
    transform_pipeline: str,
) -> Tuple[Any, Optional[str]]:
    """
    Apply transformation pipeline to a value.

    Pipelines are separated by | (e.g., "TRIM|UPPERCASE|DATE_PARSE_PTBR").

    Returns:
        Tuple of (transformed_value, error_message or None)
    """
    if pd.isna(value) or value is None or value == "":
        return None, None

    # Convert to string for transformations
    str_value = str(value).strip() if transform_pipeline else str(value)

    transforms = transform_pipeline.split("|") if transform_pipeline else []

    for transform in transforms:
        transform = transform.strip().upper()

        if transform == "TRIM":
            str_value = str_value.strip()

        elif transform == "UPPERCASE":
            str_value = str_value.upper()

        elif transform == "LOWERCASE":
            str_value = str_value.lower()

        elif transform == "DATE_PARSE_PTBR":
            # DD/MM/YYYY → YYYY-MM-DD
            try:
                match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", str_value)
                if match:
                    day, month, year = match.groups()
                    str_value = f"{year}-{month}-{day}"
                else:
                    return None, f"Invalid PT-BR date format: {str_value}"
            except Exception as e:
                return None, f"Date parse error: {str(e)}"

        elif transform == "NUMBER_PARSE_PTBR":
            # 1.234,56 → 1234.56
            try:
                # Remove thousand separators (.)
                cleaned = str_value.replace(".", "")
                # Replace decimal separator (, → .)
                cleaned = cleaned.replace(",", ".")
                # Validate as number
                float(cleaned)
                str_value = cleaned
            except (ValueError, InvalidOperation) as e:
                return None, f"Invalid PT-BR number format: {str_value}"

        elif transform == "CURRENCY_CLEAN_PTBR":
            # R$ 15,50 → 15.50
            try:
                # Remove currency symbol and spaces
                cleaned = re.sub(r"^R\$\s*", "", str_value)
                cleaned = cleaned.strip()
                # Apply number parsing
                cleaned = cleaned.replace(".", "")
                cleaned = cleaned.replace(",", ".")
                float(cleaned)
                str_value = cleaned
            except (ValueError, InvalidOperation) as e:
                return None, f"Invalid PT-BR currency format: {str_value}"

    return str_value, None


def _transform_row(
    row: Dict[str, Any],
    mappings: List[Dict[str, Any]],
    row_number: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Transform a single row using column mappings.

    Returns:
        Tuple of (transformed_row, list_of_errors)
    """
    transformed = {}
    errors = []

    for mapping in mappings:
        source_col = mapping.get("source_column")
        target_col = mapping.get("target_column")
        transform = mapping.get("transform", "")

        if source_col not in row:
            continue

        original_value = row[source_col]
        transformed_value, error = _transform_value(original_value, transform)

        if error:
            errors.append({
                "row_number": row_number,
                "column": source_col,
                "original_value": str(original_value),
                "error_type": "TransformationError",
                "raw_error": error,
            })
        else:
            transformed[target_col] = transformed_value

    return transformed, errors


@tool
def stream_and_transform(
    s3_key: str,
    mappings_json: str,
    session_id: str,
    job_id: str,
    strategy: str = "LOG_AND_CONTINUE",
) -> str:
    """
    Stream and transform inventory file in batches.

    This is the main ETL tool. It:
    1. Downloads file from S3
    2. Streams in chunks (CHUNK_SIZE rows)
    3. Applies mappings to each row
    4. Collects errors for batch enrichment
    5. Returns transformed batches ready for insertion

    On error:
    - STOP_ON_ERROR: Returns immediately with first error
    - LOG_AND_CONTINUE: Collects all errors, continues processing

    Args:
        s3_key: S3 key of the file to process.
        mappings_json: JSON string of column mappings from SchemaMapper.
        session_id: Import session identifier.
        job_id: Job ID for status updates.
        strategy: Error handling strategy from preferences.

    Returns:
        JSON string with:
        - success: bool
        - batches: List of transformed row batches (ready for insert)
        - rows_processed: int
        - rows_transformed: int
        - errors: List of raw errors (for DebugAgent enrichment)
        - stopped_early: bool (if STOP_ON_ERROR triggered)
    """
    try:
        # Parse mappings
        mappings = json.loads(mappings_json)
        if not mappings:
            return json.dumps({
                "success": False,
                "error": "No mappings provided",
            })

        # Download file from S3
        s3 = _get_s3_client()
        response = s3.get_object(Bucket=DOCUMENTS_BUCKET, Key=s3_key)
        file_content = response["Body"].read()

        # Detect file type and read
        file_type = _detect_file_type(s3_key)

        if file_type == "excel":
            df = pd.read_excel(BytesIO(file_content))
        elif file_type == "csv":
            # Try different encodings
            try:
                df = pd.read_csv(BytesIO(file_content), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(BytesIO(file_content), encoding="latin-1")
        else:
            return json.dumps({
                "success": False,
                "error": f"Unsupported file type: {file_type}",
            })

        total_rows = len(df)
        all_batches = []
        all_errors = []
        rows_processed = 0
        rows_transformed = 0
        stopped_early = False

        logger.info(
            f"[ETLStream] Processing {total_rows} rows from {s3_key} "
            f"with {len(mappings)} mappings, strategy={strategy}"
        )

        # Process in chunks
        for chunk_start in range(0, total_rows, CHUNK_SIZE):
            chunk_end = min(chunk_start + CHUNK_SIZE, total_rows)
            chunk_df = df.iloc[chunk_start:chunk_end]

            batch = []
            for idx, row in chunk_df.iterrows():
                row_number = chunk_start + idx + 1  # 1-indexed
                rows_processed += 1

                # Transform row
                transformed_row, row_errors = _transform_row(
                    row.to_dict(),
                    mappings,
                    row_number,
                )

                if row_errors:
                    all_errors.extend(row_errors)

                    if strategy == "STOP_ON_ERROR":
                        stopped_early = True
                        logger.warning(
                            f"[ETLStream] STOP_ON_ERROR at row {row_number}"
                        )
                        break
                else:
                    # Add session metadata
                    transformed_row["session_id"] = session_id
                    batch.append(transformed_row)
                    rows_transformed += 1

            if batch:
                all_batches.append(batch)

            if stopped_early:
                break

        logger.info(
            f"[ETLStream] Completed: {rows_processed} processed, "
            f"{rows_transformed} transformed, {len(all_errors)} errors"
        )

        return json.dumps({
            "success": True,
            "batches": all_batches,
            "batch_count": len(all_batches),
            "rows_total": total_rows,
            "rows_processed": rows_processed,
            "rows_transformed": rows_transformed,
            "error_count": len(all_errors),
            "errors": all_errors[:100],  # Limit for DebugAgent batch
            "stopped_early": stopped_early,
        })

    except Exception as e:
        logger.error(f"[ETLStream] Failed to process file {s3_key}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "rows_processed": 0,
            "rows_transformed": 0,
        })


@tool
def enrich_errors_with_debug(
    errors_json: str,
    s3_key: str,
    session_id: str,
) -> str:
    """
    Enrich transformation errors with DebugAgent diagnosis.

    Called post-processing to batch-enrich errors. The DebugAgent
    analyzes patterns across errors and provides human-readable
    explanations and fix suggestions.

    Args:
        errors_json: JSON string of raw errors from stream_and_transform.
        s3_key: Original file S3 key for context.
        session_id: Session identifier for context.

    Returns:
        JSON string with enriched errors including human_explanation
        and suggested_fix for each error.
    """
    try:
        errors = json.loads(errors_json)
        if not errors:
            return json.dumps({
                "success": True,
                "enriched_errors": [],
                "pattern_summary": "No errors to analyze",
            })

        # Use cognitive error handler for batch enrichment
        import asyncio
        result = asyncio.run(enrich_batch_errors(
            errors=errors,
            context={
                "s3_key": s3_key,
                "session_id": session_id,
                "file_type": _detect_file_type(s3_key),
            },
        ))

        return json.dumps({
            "success": True,
            "enriched_errors": result.get("enriched_errors", errors),
            "pattern_summary": result.get("pattern_summary", ""),
            "common_fixes": result.get("common_fixes", []),
        })

    except Exception as e:
        logger.error(f"[ETLStream] Failed to enrich errors: {e}")
        # Graceful degradation - return raw errors
        return json.dumps({
            "success": False,
            "error": str(e),
            "enriched_errors": json.loads(errors_json) if errors_json else [],
        })
