# =============================================================================
# Intake Service - File Intake and Analysis Logic (Phase 1-2)
# =============================================================================
# This module extracts deterministic file intake and analysis logic from the
# InventoryHub orchestrator main.py. It handles:
#
# PHASE 1: File Upload
#   - Presigned URL generation (get_nf_upload_url)
#   - File verification (verify_file)
#
# PHASE 2: File Analysis
#   - File structure extraction (nexo_analyze_file)
#   - Quality confidence calculation
#   - Response transformation to frontend contract
#
# ARCHITECTURE:
#   - Follows "Sandwich Pattern": CODE (extract) -> LLM (reason) -> CODE (validate)
#   - LambdaInvoker handles Phase 1 operations via Lambda
#   - Direct tool calls handle Phase 2 (get_file_structure)
#   - Pydantic models ensure type-safe frontend contract
#
# Author: Faiston NEXO Team
# Date: January 2026
# =============================================================================

from __future__ import annotations

import json
import logging
import unicodedata
from datetime import datetime
from typing import Any

from shared.agent_schemas import (
    NexoAnalyzeFileResponse,
    NexoAnalysisData,
    NexoSheetData,
)
from shared.cognitive_error_handler import cognitive_sync_handler
from shared.lambda_invoker import LambdaInvoker

logger = logging.getLogger(__name__)

# Agent ID for error attribution
AGENT_ID = "inventory_hub"


# =============================================================================
# Quality Confidence Calculation
# =============================================================================


def calculate_file_quality_confidence(sheet: NexoSheetData) -> float:
    """
    Calculate preliminary confidence based on file quality metrics.

    This function evaluates file readability, header detection quality,
    and data quality to produce an overall confidence score. Used in
    Phase 2 before schema mapping (Phase 3 adds mapping confidence).

    Formula:
        confidence = (readability x 0.30) + (header_quality x 0.35) + (data_quality x 0.35)

    Args:
        sheet: NexoSheetData containing columns, sample_data, and detected_format.

    Returns:
        Float between 0.0 and 1.0 representing file quality confidence.

    Scoring Details:
        - File readability (0.30 weight):
            - 1.0 if format detected (csv_semicolon, csv_comma, excel, etc.)
            - 0.5 if format is "unknown"

        - Header detection (0.35 weight):
            - 1.0 if >= 4 columns detected
            - 0.7 if >= 2 columns detected
            - 0.4 if 1 column detected
            - 0.0 if no columns detected

        - Data quality (0.35 weight):
            - Ratio of valid rows in sample_data (rows with at least one non-empty value)
            - 0.0 if no sample_data available

    Example:
        >>> sheet = NexoSheetData(
        ...     columns=["codigo", "descricao", "quantidade", "preco"],
        ...     sample_data=[{"codigo": "ABC", "descricao": "Item 1", "quantidade": "10", "preco": "99.90"}],
        ...     row_count=1500,
        ...     detected_format="csv_semicolon"
        ... )
        >>> confidence = calculate_file_quality_confidence(sheet)
        >>> assert 0.9 <= confidence <= 1.0
    """
    # File readability (0.30 weight) - if we got here, file was parsed
    readability = 1.0 if sheet.detected_format != "unknown" else 0.5

    # Header detection (0.35 weight)
    num_columns = len(sheet.columns) if sheet.columns else 0
    if num_columns >= 4:
        header_score = 1.0
    elif num_columns >= 2:
        header_score = 0.7
    elif num_columns >= 1:
        header_score = 0.4
    else:
        header_score = 0.0

    # Data quality (0.35 weight) - check sample_data validity
    if not sheet.sample_data:
        data_score = 0.0
    else:
        valid_rows = sum(1 for row in sheet.sample_data if row and any(row.values()))
        data_score = valid_rows / len(sheet.sample_data)

    confidence = (readability * 0.30) + (header_score * 0.35) + (data_score * 0.35)
    return round(confidence, 2)


# =============================================================================
# Response Transformation
# =============================================================================


def transform_file_structure_to_nexo_response(
    file_structure: dict[str, Any],
    s3_key: str,
) -> dict[str, Any]:
    """
    Transform get_file_structure() flat output to nested NexoAnalyzeFileResponse.

    Standardizes Mode 2.5 response to match frontend contract. This function
    applies the "Sandwich Pattern" (CODE -> LLM -> CODE):
        1. Tool returns deterministic flat structure
        2. This function transforms to nested structure
        3. Frontend receives consistent contract

    Args:
        file_structure: Flat structure from get_file_structure() tool.
            Expected keys:
            {
                "success": true,
                "columns": ["col1", "col2"],
                "sample_data": [{...}, {...}],
                "row_count_estimate": 1500,
                "detected_format": "csv_semicolon",
                ...
            }
        s3_key: S3 key used for generating import_session_id and extracting filename.

    Returns:
        Nested structure matching NexoAnalyzeFileResponse Pydantic model:
        {
            "success": true,
            "import_session_id": "nexo_20260122_143000_file.csv",
            "filename": "file.csv",
            "detected_file_type": "csv_semicolon",
            "analysis": {
                "sheets": [{
                    "columns": ["col1", "col2"],
                    "sample_data": [{...}, {...}],
                    "row_count": 1500,
                    "detected_format": "csv_semicolon"
                }],
                "sheet_count": 1,
                "total_rows": 1500,
                "recommended_strategy": "direct_import"
            },
            "column_mappings": [],
            "overall_confidence": 0.85,
            "questions": []
        }

    TypeScript Contract:
        client/services/sgaAgentcore.ts:1461-1502 (NexoAnalyzeFileResponse interface)

    Pydantic Models:
        shared/agent_schemas.py:347+ (NexoAnalyzeFileResponse, NexoAnalysisData, NexoSheetData)
    """
    # Extract filename from S3 key (e.g., "uploads/user123/file.csv" -> "file.csv")
    filename = s3_key.split("/")[-1]

    # Generate unique import_session_id for tracking this analysis session
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    import_session_id = f"nexo_{timestamp}_{filename}"

    # Build single sheet structure (CSV/TXT files always have 1 sheet)
    # For Excel files, this would be called once per sheet
    sheet = NexoSheetData(
        columns=file_structure.get("columns", []),
        sample_data=file_structure.get("sample_data", []),
        row_count=file_structure.get("row_count_estimate", 0),
        detected_format=file_structure.get("detected_format", "unknown"),
    )

    # Build nested analysis object
    analysis = NexoAnalysisData(
        sheets=[sheet],  # Single sheet for CSV/TXT
        sheet_count=1,   # Always 1 for CSV/TXT
        total_rows=sheet.row_count,
        recommended_strategy="direct_import",  # Default strategy for Mode 2.5
    )

    # Build complete response using Pydantic model (validates structure)
    response = NexoAnalyzeFileResponse(
        success=True,
        import_session_id=import_session_id,
        filename=filename,
        detected_file_type=file_structure.get("detected_format", "unknown"),
        analysis=analysis,
        column_mappings=[],      # Empty - populated by SchemaMapper in Phase 3
        overall_confidence=calculate_file_quality_confidence(sheet),
        questions=[],            # Empty - generated by SchemaMapper in Phase 3
    )

    # Convert Pydantic model to dict for JSON serialization
    return response.model_dump()


# =============================================================================
# Direct Action Handling (No LLM)
# =============================================================================


# Supported direct actions (deterministic, no LLM needed)
DIRECT_ACTIONS = {"get_nf_upload_url", "verify_file", "nexo_analyze_file"}


@cognitive_sync_handler(AGENT_ID)
def handle_direct_action(
    action: str,
    payload: dict[str, Any],
    user_id: str,
    session_id: str,
) -> dict[str, Any]:
    """
    Handle deterministic actions without LLM invocation.

    Returns response in A2A envelope format matching frontend expectations.
    Exceptions are caught by @cognitive_sync_handler and enriched via DebugAgent.

    Routing:
        - get_nf_upload_url, verify_file: sga-intake-tools Lambda via LambdaInvoker
        - nexo_analyze_file: get_file_structure tool -> transform response

    Args:
        action: The action name. Valid values:
            - "get_nf_upload_url": Generate presigned PUT URL for file upload
            - "verify_file": Check if file exists in S3 and get metadata
            - "nexo_analyze_file": Analyze file structure without LLM
        payload: Request payload with action-specific parameters.
            - get_nf_upload_url: {"filename": str}
            - verify_file: {"s3_key": str}
            - nexo_analyze_file: {"s3_key": str}
        user_id: User identifier for tenant-isolated S3 paths.
        session_id: Session identifier for path namespacing and audit.

    Returns:
        Dict matching OrchestratorEnvelope format:
        {
            "success": bool,
            "specialist_agent": "intake" | "analyst",
            "response": {...action-specific response...}
        }

    Raises:
        ValueError: If action is not in DIRECT_ACTIONS (enriched by DebugAgent).
        CognitiveError: If an error occurs during processing (with human_explanation).

    Example:
        >>> result = handle_direct_action(
        ...     action="get_nf_upload_url",
        ...     payload={"filename": "inventory.xlsx"},
        ...     user_id="user-123",
        ...     session_id="session-456",
        ... )
        >>> assert result["success"] is True
        >>> assert "upload_url" in result["response"]
    """
    # Phase 1: Intake operations via Lambda
    if action in ("get_nf_upload_url", "verify_file"):
        invoker = LambdaInvoker(audit_agent_id=AGENT_ID)
        return invoker.invoke_intake(
            action=action,
            payload=payload,
            user_id=user_id,
            session_id=session_id,
        )

    # Phase 2: File analysis (direct tool call, no LLM)
    if action == "nexo_analyze_file":
        return _handle_nexo_analyze_file(payload)

    # Unknown action
    raise ValueError(
        f"Acao desconhecida: '{action}'. Acoes validas: {', '.join(sorted(DIRECT_ACTIONS))}"
    )


@cognitive_sync_handler(AGENT_ID)
def _handle_nexo_analyze_file(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze file structure directly (Mode 2.5 - no LLM).

    Uses get_file_structure tool directly for deterministic execution.
    Transforms response to match frontend NexoAnalyzeFileResponse contract.

    Acceptance Criteria: < 2 seconds latency

    Args:
        payload: Request payload with s3_key field.
            {"s3_key": "uploads/user123/session456/inventory.csv"}

    Returns:
        Orchestrator envelope with nested analysis response:
        {
            "success": true,
            "specialist_agent": "analyst",
            "response": NexoAnalyzeFileResponse {...}
        }

    Raises:
        ValueError: If s3_key is missing (enriched by DebugAgent).
        RuntimeError: If file analysis fails (enriched by DebugAgent).
    """
    from agents.tools.analysis_tools import get_file_structure
    from shared.flow_logger import flow_log

    s3_key = payload.get("s3_key")
    if not s3_key:
        raise ValueError("O parametro 's3_key' e obrigatorio para analise de arquivo")

    # Normalize s3_key to NFC (Portuguese filename support)
    s3_key = unicodedata.normalize("NFC", s3_key)

    # Generate session ID for logging correlation
    import_session_id = f"nexo_{s3_key.split('/')[-1]}"

    flow_log.phase_start(2, "InventoryAnalyst", import_session_id, s3_key=s3_key)

    # Direct call to get_file_structure (no A2A, no LLM)
    result_json = get_file_structure(s3_key)
    result = json.loads(result_json)

    # If tool failed, raise to trigger CognitiveError enrichment
    if not result.get("success", False):
        error_msg = result.get("error", "Falha ao analisar estrutura do arquivo")
        error_type = result.get("error_type", "ANALYSIS_ERROR")
        flow_log.phase_end(
            2, "InventoryAnalyst", import_session_id, "FAILED", 0, error_type=error_type
        )
        raise RuntimeError(f"[{error_type}] {error_msg}")

    flow_log.decision(
        "File structure analyzed",
        session_id=import_session_id,
        columns_found=len(result.get("columns", [])),
        row_estimate=result.get("row_count_estimate", 0),
        detected_format=result.get("detected_format", "unknown"),
        file_size_bytes=result.get("file_size_bytes", 0),
    )

    # Transform flat structure to nested NexoAnalyzeFileResponse
    transformed = transform_file_structure_to_nexo_response(result, s3_key)

    flow_log.phase_end(
        2,
        "InventoryAnalyst",
        import_session_id,
        "SUCCESS",
        0,  # Duration calculated by context manager if used
        sheets_count=transformed.get("analysis", {}).get("sheet_count", 0),
        total_rows=transformed.get("analysis", {}).get("total_rows", 0),
    )

    # ===========================================================================
    # BUG-022/BUG-023 FIX: Call Phase 3 (SchemaMapper) after Phase 2 succeeds
    # Previously this function returned immediately, leaving column_mappings empty.
    # Now we invoke SchemaMapper to get column mappings and/or HIL questions.
    # ===========================================================================
    from agents.orchestrators.inventory_hub.services.mapping_service import (
        invoke_schema_mapper_phase3,
        _merge_phase3_results,
    )

    # Extract columns and sample_data from Phase 2 analysis
    sheets = transformed.get("analysis", {}).get("sheets", [])
    columns = sheets[0].get("columns", []) if sheets else []
    sample_data = sheets[0].get("sample_data", []) if sheets else []

    logger.info(
        f"[InventoryHub] Phase 2→3 transition: columns={len(columns)}, "
        f"session={import_session_id}, s3_key={s3_key}"
    )

    # Call Phase 3 (SchemaMapper A2A)
    phase3_result = invoke_schema_mapper_phase3(
        columns=columns,
        sample_data=sample_data,
        s3_key=s3_key,
        import_session_id=import_session_id,
    )

    # Merge Phase 3 results into Phase 2 response
    merged_response = _merge_phase3_results(transformed, phase3_result)

    logger.info(
        f"[InventoryHub] Phase 3 complete: "
        f"column_mappings={len(merged_response.get('column_mappings', []))}, "
        f"questions={len(merged_response.get('questions', []))}, "
        f"status={merged_response.get('phase3_status', 'unknown')}"
    )

    return {
        "success": True,
        "specialist_agent": "analyst",
        "response": merged_response,
    }


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Public functions
    "calculate_file_quality_confidence",
    "transform_file_structure_to_nexo_response",
    "handle_direct_action",
    # Constants
    "DIRECT_ACTIONS",
]
