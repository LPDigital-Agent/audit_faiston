"""
File analysis tools for inventory management.

This module provides tools for analyzing uploaded inventory files
using the FileInspector library. Tools follow the Sandwich Pattern:
CODE (FileInspector) → LLM (Agent reasoning) → CODE (validation).

Tools:
    get_file_structure: Analyze CSV/Excel file structure without loading full content.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from strands import tool

from tools.library.file_processing import FileInspector, get_file_inspector

# Import debug error handler for error routing
try:
    from agents.specialists.debug.main import debug_error
except ImportError:
    # Fallback if debug module not available
    def debug_error(error: Exception, context: str, metadata: dict) -> None:
        """Fallback error handler."""
        pass


@tool
def get_file_structure(s3_key: str, bucket: Optional[str] = None) -> str:
    """
    Analyze the structure of an uploaded inventory file.

    Extracts column names, 3 sample rows, estimated row count, and format
    without loading the full file. Uses pandas nrows=5 constraint - safe
    for files up to 500 MB.

    IMPORTANT: This tool NEVER loads full file content into memory.
    All processing uses streaming and sampling techniques.

    Supported formats:
        - CSV (comma-separated)
        - CSV (semicolon-separated, common in pt-BR Excel exports)
        - CSV (tab-separated / TSV)
        - Excel (.xlsx) - first sheet only
        - Excel (.xls legacy) - first sheet only

    Encoding support:
        - UTF-8 (primary)
        - Latin-1 (fallback for legacy Brazilian files)

    Args:
        s3_key: S3 object key (e.g., "temp/uploads/abc123_file.csv").
            Must be a valid key in the configured bucket.
        bucket: Optional bucket override. Defaults to DOCUMENTS_BUCKET env var.

    Returns:
        JSON string with structure:
        {
            "success": true,
            "columns": ["codigo", "descricao", "quantidade"],
            "sample_data": [
                {"codigo": "ABC123", "descricao": "Item 1", "quantidade": "10"},
                {"codigo": "DEF456", "descricao": "Item 2", "quantidade": "20"},
                {"codigo": "GHI789", "descricao": "Item 3", "quantidade": "30"}
            ],
            "row_count_estimate": 1500,
            "detected_format": "csv_semicolon",
            "separator": ";",
            "file_size_bytes": 45678,
            "has_header": true,
            "encoding": "utf-8"
        }

        On error:
        {
            "success": false,
            "error": "Error description",
            "error_type": "VALIDATION_ERROR"
        }

    Example:
        >>> result = get_file_structure("temp/uploads/abc123_inventory.csv")
        >>> data = json.loads(result)
        >>> if data["success"]:
        ...     print(f"Found {len(data['columns'])} columns")
    """
    try:
        # Get bucket from parameter or environment
        target_bucket = bucket or os.environ.get("DOCUMENTS_BUCKET")

        if not target_bucket:
            return json.dumps(
                {
                    "success": False,
                    "error": "No bucket specified and DOCUMENTS_BUCKET environment variable not set",
                    "error_type": "CONFIGURATION_ERROR",
                }
            )

        if not s3_key:
            return json.dumps(
                {
                    "success": False,
                    "error": "s3_key is required",
                    "error_type": "VALIDATION_ERROR",
                }
            )

        # Get singleton inspector instance
        inspector = get_file_inspector(bucket=target_bucket)

        # Inspect file structure
        result = inspector.inspect_s3_file(bucket=target_bucket, key=s3_key)

        # Route errors through DebugAgent for enrichment
        if not result.success:
            debug_error(
                Exception(result.error or "Unknown error"),
                "get_file_structure",
                {
                    "s3_key": s3_key,
                    "bucket": target_bucket,
                    "error_type": result.error_type,
                },
            )

        return json.dumps(result.to_dict())

    except Exception as e:
        # Route unexpected errors through DebugAgent
        debug_error(
            e,
            "get_file_structure",
            {"s3_key": s3_key, "bucket": bucket or "default"},
        )
        return json.dumps(
            {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "UNEXPECTED_ERROR",
            }
        )


@tool
def validate_file_columns(
    s3_key: str,
    required_columns: list[str],
    bucket: Optional[str] = None,
) -> str:
    """
    Validate that a file contains required columns.

    Checks if the uploaded file has all required columns for inventory
    processing. Uses case-insensitive matching and normalizes column names.

    Args:
        s3_key: S3 object key of the file to validate.
        required_columns: List of column names that must be present.
        bucket: Optional bucket override.

    Returns:
        JSON string with validation result:
        {
            "success": true,
            "valid": true,
            "found_columns": ["codigo", "descricao", "quantidade"],
            "missing_columns": [],
            "extra_columns": ["observacao"]
        }

        Or on error:
        {
            "success": false,
            "error": "Error description",
            "error_type": "ERROR_TYPE"
        }
    """
    try:
        target_bucket = bucket or os.environ.get("DOCUMENTS_BUCKET")

        if not target_bucket:
            return json.dumps(
                {
                    "success": False,
                    "error": "No bucket specified and DOCUMENTS_BUCKET not set",
                    "error_type": "CONFIGURATION_ERROR",
                }
            )

        # Get file structure first
        inspector = get_file_inspector(bucket=target_bucket)
        result = inspector.inspect_s3_file(bucket=target_bucket, key=s3_key)

        if not result.success:
            return json.dumps(
                {
                    "success": False,
                    "error": result.error,
                    "error_type": result.error_type,
                }
            )

        # Normalize column names for comparison
        def normalize(col: str) -> str:
            return col.lower().strip().replace(" ", "_").replace("-", "_")

        file_columns_normalized = {normalize(c): c for c in result.columns}
        required_normalized = {normalize(c): c for c in required_columns}

        # Find matches
        found = []
        missing = []
        for req_norm, req_orig in required_normalized.items():
            if req_norm in file_columns_normalized:
                found.append(file_columns_normalized[req_norm])
            else:
                missing.append(req_orig)

        # Find extra columns
        extra = [
            orig
            for norm, orig in file_columns_normalized.items()
            if norm not in required_normalized
        ]

        return json.dumps(
            {
                "success": True,
                "valid": len(missing) == 0,
                "found_columns": found,
                "missing_columns": missing,
                "extra_columns": extra,
            }
        )

    except Exception as e:
        debug_error(
            e,
            "validate_file_columns",
            {"s3_key": s3_key, "required_columns": required_columns},
        )
        return json.dumps(
            {
                "success": False,
                "error": f"Validation failed: {str(e)}",
                "error_type": "UNEXPECTED_ERROR",
            }
        )
