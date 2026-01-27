"""Intake tools for InventoryHub orchestrator.

This module contains tools for the initial file intake and analysis phase
(Phase 2) of the NEXO Cognitive Import Pipeline.

Tools:
    analyze_file_structure: Analyze uploaded inventory file structure (LOCAL function).
"""

import json
import logging

from strands import tool

from core_tools.library.file_processing import get_file_inspector
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


@tool
def analyze_file_structure(s3_key: str) -> str:
    """
    Analyze the structure of an uploaded inventory file.

    THIS IS A LOCAL PYTHON FUNCTION - NOT an MCP agent call.
    The analysis runs directly in this container using FileInspector.

    Use this AFTER verifying the file exists with verify_file_availability.

    The analysis returns:
    - Column names exactly as they appear in the file
    - First 3 rows of sample data
    - Detected file format (CSV/Excel) and encoding
    - Estimated total row count
    - Whether the file has a header row

    Args:
        s3_key: The S3 object key returned from verify_file_availability.
            Example: "uploads/user123/session456/inventory.csv"

    Returns:
        JSON string with file structure analysis:
        {
            "success": true,
            "columns": ["codigo", "descricao", "quantidade"],
            "sample_data": [{"codigo": "ABC", "descricao": "Item 1", "quantidade": "10"}, ...],
            "row_count_estimate": 1500,
            "detected_format": "csv_semicolon",
            "has_header": true,
            "encoding": "utf-8"
        }

        On error:
        {
            "success": false,
            "error": "Error description",
            "error_type": "ERROR_TYPE"
        }
    """
    try:
        if not s3_key:
            return json.dumps({
                "success": False,
                "error": "s3_key is required",
                "error_type": "VALIDATION_ERROR",
            })

        logger.info(f"[InventoryHub] Analyzing file structure for {s3_key}")

        # LOCAL execution via FileInspector (not MCP Gateway)
        inspector = get_file_inspector()
        result = inspector.inspect_s3_file(bucket=None, key=s3_key)
        parsed = result.to_dict()

        # Log outcome based on parsed result
        if parsed.get("success"):
            columns = parsed.get("columns", [])
            logger.info(
                f"[InventoryHub] File analysis succeeded: {len(columns)} columns detected"
            )
        else:
            error_type = parsed.get("error_type", "UNKNOWN")
            logger.warning(
                f"[InventoryHub] File analysis failed: {error_type} - {parsed.get('error', 'No details')}"
            )
            debug_error(
                Exception(parsed.get("error", "Analysis failed")),
                "analyze_file_structure",
                {"s3_key": s3_key, "error_type": error_type},
            )

        return json.dumps(parsed)

    except Exception as e:
        debug_error(e, "analyze_file_structure", {"s3_key": s3_key})
        logger.exception(f"[InventoryHub] Unexpected error in analyze_file_structure: {e}")
        return json.dumps({
            "success": False,
            "error": f"Analysis error: {str(e)}",
            "error_type": "ANALYSIS_ERROR",
        })


__all__ = ["analyze_file_structure"]
