# =============================================================================
# Analyze File Tool - AI-First with FileAnalyzer A2A Agent (BUG-025 FIX)
# =============================================================================
# Analyzes file structure (sheets, columns, types) from S3 via FileAnalyzer A2A.
#
# BUG-025 FIX: This tool now delegates file analysis to the FileAnalyzer A2A Agent
# instead of using direct google.genai SDK calls (gemini_text_analyzer.py).
# The FileAnalyzer uses Strands structured_output_model for Pydantic enforcement,
# which ensures all HIL questions are properly returned without truncation.
#
# AUDIT-004/4: Vision Analyzer Integration for PDF/Image Files
# For PDF and image files, this tool now first delegates to VisionAnalyzer A2A
# for OCR/table extraction, then processes the extracted data. This enables
# intelligent import of scanned inventory lists and photographed documents.
#
# Philosophy: OBSERVE → THINK → LEARN → EXECUTE (with Multi-Round HIL)
# - OBSERVE: FileAnalyzer reads file from S3
# - OBSERVE (VISION): VisionAnalyzer extracts text/tables from PDF/images
# - THINK: Strands Agent with Gemini Pro analyzes with structured output
# - LEARN: Uses memory context from LearningAgent (AgentCore Memory)
# - EXECUTE: Returns analysis with confidence and HIL questions
#
# Architecture:
# - nexo_import tool → A2A Client → FileAnalyzer A2A Agent (for CSV/XLSX)
# - nexo_import tool → A2A Client → VisionAnalyzer A2A Agent (for PDF/images)
# - Strands structured_output_model ensures complete question responses
# - json-repair fallback for partial response recovery
#
# Module: Gestao de Ativos -> Gestao de Estoque -> Smart Import
# =============================================================================

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import uuid4

from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call
from shared.a2a_client import A2AClient
from shared.data_contracts import ensure_dict
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)

AGENT_ID = "nexo_import"
audit = AgentAuditEmitter(agent_id=AGENT_ID)

# A2A client for FileAnalyzer communication
_a2a_client: Optional[A2AClient] = None


def _get_a2a_client() -> A2AClient:
    """Get or create A2A client singleton."""
    global _a2a_client
    if _a2a_client is None:
        _a2a_client = A2AClient()
    return _a2a_client


# =============================================================================
# BUG-025 FIX: Defensive Question Transformation Helpers
# =============================================================================
# These helpers replace fragile list comprehensions with explicit error handling.
# Each option/question is processed individually, so one malformed item
# doesn't break the entire questions array.


def _safe_build_options(raw_options: list) -> List[Dict[str, Any]]:
    """
    BUG-025 FIX: Build options array safely with explicit error handling.

    Each option is processed individually - if one fails, others still work.
    Handles both string options ("value") and dict options ({"value": "x", "label": "y"}).

    Args:
        raw_options: List of option values (strings or dicts)

    Returns:
        List of properly formatted option dicts
    """
    options = []
    for i, opt in enumerate(raw_options):
        try:
            if isinstance(opt, str):
                options.append({"value": opt, "label": opt})
            elif isinstance(opt, dict):
                options.append({
                    "value": opt.get("value", ""),
                    "label": opt.get("label", opt.get("value", "")),
                    "warning": opt.get("warning", False),
                    "recommended": opt.get("recommended", False),
                })
            else:
                logger.debug("[BUG-025] Ignoring invalid option type at index %d: %s", i, type(opt))
        except Exception as e:
            logger.warning("[BUG-025] Failed to process option at index %d: %s", i, e)
    return options


def _safe_build_hil_questions(hil_questions: list) -> List[Dict[str, Any]]:
    """
    BUG-025 FIX: Build HIL questions array with error handling.

    Each question is processed individually - if one fails, others still work.
    Validates minimum required fields before including in output.

    Args:
        hil_questions: Raw HIL questions from analysis

    Returns:
        List of properly formatted question dicts
    """
    questions = []
    for i, q in enumerate(hil_questions):
        try:
            # Validate minimum required fields
            if not q.get("question"):
                logger.warning("[BUG-025] Skipping hil_question %d - no question text", i)
                continue

            question_obj = {
                "id": q.get("id", f"q{i}"),
                "question": q.get("question", ""),
                "context": q.get("reason", q.get("context", "")),
                "importance": "critical" if q.get("priority") == "high" else "medium",
                "topic": q.get("topic", "column_mapping"),
                "options": _safe_build_options(q.get("options", [])),
                "default_value": q.get("default_value"),
            }
            questions.append(question_obj)
        except Exception as e:
            debug_error(e, "analyze_file_format_hil_question", {"question_index": i})

    return questions


def _safe_build_unmapped_questions(unmapped_questions: list) -> List[Dict[str, Any]]:
    """
    BUG-025 FIX: Build unmapped questions array with error handling.

    Each question is processed individually - if one fails, others still work.
    Validates minimum required fields before including in output.

    Args:
        unmapped_questions: Raw unmapped questions from analysis

    Returns:
        List of properly formatted unmapped question dicts
    """
    questions = []
    for i, uq in enumerate(unmapped_questions):
        try:
            # Validate minimum required fields
            if not uq.get("question"):
                logger.warning("[BUG-025] Skipping unmapped_question %d - no question text", i)
                continue

            question_obj = {
                "id": uq.get("id", f"uq{i}"),
                "type": "unmapped",
                "column": uq.get("field", uq.get("column", "")),
                "question": uq.get("question", ""),
                "description": uq.get("reason", uq.get("description", "")),
                "suggested_action": uq.get("suggested_action", "metadata"),
                "options": _safe_build_options(uq.get("options", [])),
                "blocking": True,
            }
            questions.append(question_obj)
        except Exception as e:
            debug_error(e, "analyze_file_format_unmapped_question", {"question_index": i})

    return questions


# =============================================================================
# AUDIT-004/4: Vision Analyzer Integration Helpers
# =============================================================================
# These helpers enable the NEXO import flow to process PDF and image files
# by first extracting tables/text via VisionAnalyzer, then mapping columns.
# =============================================================================


# File extensions that require vision processing (OCR/table extraction)
VISION_FILE_EXTENSIONS = {
    # PDF files (may contain scanned inventory lists, packing lists, etc.)
    ".pdf",
    # Image files (photos of inventory sheets, labels, etc.)
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp",
}


def _is_vision_file(filename: Optional[str], s3_key: str) -> bool:
    """
    Check if file requires vision processing (PDF or image).

    AUDIT-004/4: Determines if we should use VisionAnalyzer A2A Agent
    instead of FileAnalyzer for initial document processing.

    Args:
        filename: Original filename (may include extension)
        s3_key: S3 key (fallback for extension detection)

    Returns:
        True if file requires vision processing
    """
    # Use filename if provided, otherwise fall back to s3_key
    name_to_check = (filename or s3_key or "").lower()

    # Check extension
    for ext in VISION_FILE_EXTENSIONS:
        if name_to_check.endswith(ext):
            return True

    return False


def _infer_document_type_hint(filename: Optional[str], s3_key: str) -> str:
    """
    Infer document type hint for VisionAnalyzer from filename patterns.

    AUDIT-004/4: Helps VisionAnalyzer apply appropriate extraction rules.

    Args:
        filename: Original filename
        s3_key: S3 key

    Returns:
        Document type hint (e.g., "table", "inventory_list", "packing_list")
    """
    name_lower = (filename or s3_key or "").lower()

    # Pattern-based detection
    if any(kw in name_lower for kw in ["romaneio", "packing", "ship", "envio"]):
        return "packing_list"
    elif any(kw in name_lower for kw in ["estoque", "inventario", "inventory", "stock"]):
        return "inventory_list"
    elif any(kw in name_lower for kw in ["tabela", "table", "planilha", "lista"]):
        return "table"
    elif any(kw in name_lower for kw in ["nf", "nota", "fiscal", "danfe"]):
        return "nf-e"  # Tax invoice - IntakeAgent handles these, but VisionAnalyzer can extract
    elif any(kw in name_lower for kw in ["etiqueta", "label", "tag"]):
        return "label"
    elif any(kw in name_lower for kw in ["equip", "asset", "patrimonio"]):
        return "equipment_photo"

    # Default: assume it's a table to extract
    return "table"


async def _analyze_with_vision(
    s3_key: str,
    filename: Optional[str],
    session_id: Optional[str],
    memory_context: Optional[str],
) -> Dict[str, Any]:
    """
    Analyze PDF/image file using VisionAnalyzer A2A Agent.

    AUDIT-004/4: This function delegates to VisionAnalyzer for OCR/table extraction,
    then transforms the result into a format compatible with the NEXO import flow.

    Args:
        s3_key: S3 key where file is stored
        filename: Original filename
        session_id: Session ID for context
        memory_context: Learned patterns from memory (for context)

    Returns:
        Analysis result in NEXO import format
    """
    logger.info(
        "[AUDIT-004/4] Analyzing PDF/image via VisionAnalyzer: %s",
        filename or s3_key
    )

    client = _get_a2a_client()
    document_type = _infer_document_type_hint(filename, s3_key)

    try:
        # Call VisionAnalyzer A2A Agent
        vision_response = await client.invoke_agent(
            agent_id="vision_analyzer",
            payload={
                "action": "analyze",
                "s3_key": s3_key,
                "document_type": document_type,
                "extract_tables": True,  # Request table extraction
            },
            session_id=session_id,
            timeout=900.0,  # 15 minutes - PDF processing may be slow
        )

        if not vision_response.success:
            logger.warning(
                "[AUDIT-004/4] VisionAnalyzer A2A call failed: %s",
                vision_response.error
            )
            return {
                "success": False,
                "error": f"VisionAnalyzer failed: {vision_response.error}",
                "requires_fallback": True,
            }

        # Parse VisionAnalyzer response
        vision_result = ensure_dict(vision_response.response, "vision_analyzer_response")

        if not vision_result.get("success", False):
            logger.warning(
                "[AUDIT-004/4] VisionAnalyzer analysis failed: %s",
                vision_result.get("warnings", [])
            )
            return {
                "success": False,
                "error": "VisionAnalyzer analysis failed",
                "warnings": vision_result.get("warnings", []),
                "requires_fallback": True,
            }

        # Extract table data if available
        extracted_tables = vision_result.get("extracted_tables", [])
        extracted_items = vision_result.get("extracted_items", [])
        raw_text = vision_result.get("raw_text_preview", "")

        # If no tables extracted, check for items or text
        if not extracted_tables and not extracted_items:
            logger.info(
                "[AUDIT-004/4] No tables extracted from %s, checking for text/items",
                filename or s3_key
            )

            # Check if we got any usable data
            if not raw_text and not extracted_items:
                return {
                    "success": False,
                    "error": "VisionAnalyzer could not extract tables or structured data from document",
                    "vision_confidence": vision_result.get("analysis_confidence", 0),
                    "document_type_detected": vision_result.get("document_type", "unknown"),
                    "requires_fallback": True,
                }

        # Transform VisionAnalyzer response to FileAnalyzer-like format
        # This allows the rest of the NEXO import flow to work seamlessly
        transformed_result = _transform_vision_to_file_analysis(
            vision_result=vision_result,
            filename=filename,
            s3_key=s3_key,
            memory_context=memory_context,
        )

        logger.info(
            "[AUDIT-004/4] VisionAnalyzer extraction complete: %d columns, confidence %.2f",
            len(transformed_result.get("columns", [])),
            transformed_result.get("analysis_confidence", 0),
        )

        return transformed_result

    except Exception as e:
        logger.error("[AUDIT-004/4] VisionAnalyzer call failed: %s", e, exc_info=True)
        debug_error(e, "analyze_file_vision", {"s3_key": s3_key, "filename": filename})
        return {
            "success": False,
            "error": f"VisionAnalyzer exception: {str(e)}",
            "requires_fallback": True,
        }


def _transform_vision_to_file_analysis(
    vision_result: Dict[str, Any],
    filename: Optional[str],
    s3_key: str,
    memory_context: Optional[str],
) -> Dict[str, Any]:
    """
    Transform VisionAnalyzer response to FileAnalyzer-compatible format.

    AUDIT-004/4: This enables seamless integration with the existing NEXO import flow
    by converting vision extraction results to the format expected by analyze_file_tool.

    Args:
        vision_result: VisionAnalyzer response
        filename: Original filename
        s3_key: S3 key
        memory_context: Memory context (passed through for enrichment)

    Returns:
        Analysis result in FileAnalyzer format
    """
    # Extract key fields from vision result
    extracted_tables = vision_result.get("extracted_tables", [])
    extracted_items = vision_result.get("extracted_items", [])
    confidence = vision_result.get("analysis_confidence", 0.5)
    document_type = vision_result.get("document_type", "table")

    # Build columns from extracted tables or items
    columns = []
    sample_data = {}
    row_count = 0

    if extracted_tables:
        # Use first table for column extraction (most common case)
        table = extracted_tables[0]
        table_headers = table.get("headers", [])
        table_rows = table.get("rows", [])

        for i, header in enumerate(table_headers):
            col_name = header if isinstance(header, str) else str(header)
            # Collect sample values from first 5 rows
            samples = []
            for row in table_rows[:5]:
                if isinstance(row, list) and i < len(row):
                    samples.append(str(row[i]) if row[i] is not None else "")
                elif isinstance(row, dict):
                    samples.append(str(row.get(col_name, "")))

            columns.append({
                "name": col_name,
                "source_name": col_name,
                "data_type": _infer_column_type(samples),
                "sample_values": samples[:3],
                "suggested_mapping": None,  # Will be filled by FileAnalyzer or HIL
                "mapping_confidence": 0.5,  # Lower confidence for vision-extracted data
            })
            sample_data[col_name] = samples

        row_count = len(table_rows)

    elif extracted_items:
        # Extract columns from item structure
        if extracted_items and isinstance(extracted_items[0], dict):
            item_keys = set()
            for item in extracted_items[:10]:
                item_keys.update(item.keys())

            for key in item_keys:
                samples = [str(item.get(key, "")) for item in extracted_items[:5] if key in item]
                columns.append({
                    "name": key,
                    "source_name": key,
                    "data_type": _infer_column_type(samples),
                    "sample_values": samples[:3],
                    "suggested_mapping": None,
                    "mapping_confidence": 0.5,
                })
                sample_data[key] = samples

        row_count = len(extracted_items)

    # Generate HIL questions for vision-extracted data
    # Vision extraction typically has lower confidence, so we generate more questions
    hil_questions = []
    unmapped_columns = []

    for col in columns:
        col_name = col.get("name", "")
        # All columns from vision extraction need confirmation
        hil_questions.append({
            "id": f"vision_mapping_{col_name}",
            "question": f"A coluna '{col_name}' foi extraída via OCR. Qual campo ela representa no sistema?",
            "reason": f"Coluna extraída de documento {document_type} via análise de visão",
            "topic": "column_mapping",
            "priority": "high",
            "options": [
                {"value": "part_number", "label": "Número da Peça (Part Number)"},
                {"value": "serial_number", "label": "Número de Série"},
                {"value": "quantity", "label": "Quantidade"},
                {"value": "description", "label": "Descrição"},
                {"value": "unit_price", "label": "Preço Unitário"},
                {"value": "location", "label": "Localização"},
                {"value": "metadata", "label": "Guardar como Metadado"},
                {"value": "ignore", "label": "Ignorar esta Coluna", "warning": True},
            ],
        })

    return {
        "success": True,
        "file_type": document_type,
        "filename": filename or s3_key.split("/")[-1],
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "sample_data": sample_data,
        "analysis_confidence": confidence * 0.8,  # Reduce confidence for vision data
        "recommended_action": "needs_review",  # Vision data always needs review
        "hil_questions": hil_questions,
        "unmapped_columns": unmapped_columns,
        "unmapped_questions": [],
        "ready_for_import": False,  # Vision extraction always requires HIL
        "analysis_round": 1,
        "source": "vision_analyzer",  # Mark source for debugging
        "vision_metadata": {
            "document_type": document_type,
            "page_count": vision_result.get("page_count", 1),
            "tables_extracted": len(extracted_tables),
            "items_extracted": len(extracted_items),
            "ocr_confidence": confidence,
        },
    }


def _infer_column_type(samples: List[str]) -> str:
    """Infer column data type from sample values."""
    if not samples:
        return "string"

    # Check for numeric patterns
    numeric_count = 0
    date_count = 0
    for sample in samples:
        sample = sample.strip()
        if not sample:
            continue
        # Check numeric
        try:
            float(sample.replace(",", ".").replace(" ", ""))
            numeric_count += 1
        except ValueError:
            pass
        # Check date-like patterns
        if any(c in sample for c in ["/", "-"]) and len(sample) >= 8:
            date_count += 1

    total = len([s for s in samples if s.strip()])
    if total == 0:
        return "string"
    if numeric_count / total > 0.8:
        return "number"
    if date_count / total > 0.8:
        return "date"
    return "string"


@trace_tool_call("sga_analyze_file")
async def analyze_file_tool(
    s3_key: str,
    filename: Optional[str] = None,
    session_id: Optional[str] = None,
    schema_context: Optional[str] = None,
    memory_context: Optional[str] = None,
    user_responses: Optional[List[Dict[str, Any]]] = None,
    user_comments: Optional[str] = None,
    analysis_round: int = 1,
) -> Dict[str, Any]:
    """
    Analyze file structure from S3 using Gemini Pro (AI-First with AGI-Like Behavior).

    Examines the file to determine:
    - Column names and suggested mappings
    - Confidence scores for each mapping
    - HIL questions for low-confidence mappings
    - Unmapped columns requiring user decision
    - Row counts and data types

    AGI-Like Multi-Round HIL:
    - Round 1: Initial analysis (Memory + File + Schema)
    - Round 2+: Re-analysis with user responses (Memory + File + Schema + Responses)
    - Continues until ready_for_import=True

    Args:
        s3_key: S3 key where file is stored
        filename: Original filename for pattern matching
        session_id: Optional session ID for audit
        schema_context: PostgreSQL schema description (optional)
        memory_context: Learned patterns from LearningAgent (optional)
        user_responses: User answers from previous HIL rounds (AGI-like)
        user_comments: Free-text instructions from user (AGI-like)
        analysis_round: Current round number (1 = first, 2+ = re-analysis)

    Returns:
        File analysis with structure, mappings, HIL questions, and readiness status
    """
    round_label = f"Round {analysis_round}"
    if user_responses:
        audit.working(
            message=f"[{round_label}] Re-analisando com {len(user_responses)} respostas: {filename or s3_key}",
            session_id=session_id,
        )
    else:
        audit.working(
            message=f"[{round_label}] Analisando arquivo com Gemini: {filename or s3_key}",
            session_id=session_id,
        )

    try:
        # =============================================================================
        # AUDIT-004/4: Vision Analyzer Integration for PDF/Image Files
        # =============================================================================
        # For PDF and image files, we first use VisionAnalyzer to extract tables/text
        # via OCR, then process the extracted data. This enables intelligent import
        # of scanned inventory lists and photographed documents.
        # =============================================================================
        if analysis_round == 1 and _is_vision_file(filename, s3_key):
            logger.info(
                "[AUDIT-004/4] Detected vision file (PDF/image), using VisionAnalyzer: %s",
                filename or s3_key
            )
            audit.working(
                message=f"[{round_label}] Extraindo dados via OCR/Visão: {filename or s3_key}",
                session_id=session_id,
            )

            # Use VisionAnalyzer for initial extraction
            analysis = await _analyze_with_vision(
                s3_key=s3_key,
                filename=filename,
                session_id=session_id,
                memory_context=memory_context,
            )

            # If vision analysis succeeded, use its result directly
            if analysis.get("success"):
                logger.info(
                    "[AUDIT-004/4] Vision analysis succeeded, skipping FileAnalyzer"
                )
                # Vision analysis returns FileAnalyzer-compatible format
                # Continue to the response formatting below
            elif analysis.get("requires_fallback"):
                logger.info(
                    "[AUDIT-004/4] Vision analysis requires fallback to FileAnalyzer"
                )
                # Fall through to FileAnalyzer (vision analysis was not conclusive)
                analysis = None  # Reset to trigger FileAnalyzer call
            else:
                # Vision analysis failed without fallback option - return error
                logger.warning(
                    "[AUDIT-004/4] Vision analysis failed: %s",
                    analysis.get("error", "Unknown error")
                )
                # Continue with analysis result (error will be handled below)

        else:
            # Not a vision file or continuation round - use FileAnalyzer
            analysis = None

        # =============================================================================
        # BUG-025 FIX: Use FileAnalyzer A2A Agent instead of direct SDK call
        # =============================================================================
        # The FileAnalyzer agent uses Strands structured_output_model with Pydantic
        # schemas to ensure all HIL questions are properly returned. This replaces
        # the gemini_text_analyzer.py which had truncation issues.
        # =============================================================================

        # Only call FileAnalyzer if vision analysis was not used or failed
        if analysis is None:
            client = _get_a2a_client()

            # Determine action based on round
            action = "continue_analysis" if analysis_round > 1 else "analyze_file"

            # Build A2A payload
            a2a_payload = {
                "action": action,
                "s3_key": s3_key,
                "filename": filename,
                "schema_context": schema_context,
                "memory_context": memory_context,
                "analysis_round": analysis_round,
            }

            # Add user responses for continuation rounds
            if user_responses:
                a2a_payload["user_responses"] = {
                    f"q{i}": resp.get("answer") or resp.get("value")
                    for i, resp in enumerate(user_responses)
                    if isinstance(resp, dict)
                }
            if user_comments:
                a2a_payload["user_comments"] = user_comments

            logger.info(
                "[BUG-025] Invoking FileAnalyzer A2A Agent: action=%s, round=%d",
                action, analysis_round
            )

            # Call FileAnalyzer via A2A
            a2a_response = await client.invoke_agent(
                agent_id="file_analyzer",
                payload=a2a_payload,
                session_id=session_id,
                timeout=900.0,  # 15 minutes - AWS AgentCore MAXIMUM for large inventory files (BUG-038)
            )

            # Parse FileAnalyzer A2A response
            if not a2a_response.success:
                debug_error(
                    Exception(a2a_response.error or "FileAnalyzer A2A call failed"),
                    "analyze_file_a2a_call",
                    {"s3_key": s3_key, "action": action}
                )
                analysis = {
                    "success": False,
                    "error": a2a_response.error or "FileAnalyzer A2A call failed",
                }
            else:
                # BUG-037 FIX: Use ensure_dict() for guaranteed STRING→DICT conversion
                analysis = ensure_dict(a2a_response.response, "file_analyzer_response")

            # BUG-024/025 FIX: Log analysis result for debugging (permanent)
            logger.info(
                "[BUG-025 DEBUG] FileAnalyzer A2A result: success=%s, keys=%s, error=%s",
                analysis.get("success") if isinstance(analysis, dict) else "NOT_DICT",
                list(analysis.keys())[:10] if isinstance(analysis, dict) else "NOT_DICT",
                str(analysis.get("error", "no_error_field"))[:100] if isinstance(analysis, dict) else "N/A"
            )
        else:
            # AUDIT-004/4: Vision analysis was used, log the result
            logger.info(
                "[AUDIT-004/4] Vision analysis result: success=%s, keys=%s, source=%s",
                analysis.get("success") if isinstance(analysis, dict) else "NOT_DICT",
                list(analysis.keys())[:10] if isinstance(analysis, dict) else "NOT_DICT",
                analysis.get("source", "unknown") if isinstance(analysis, dict) else "N/A"
            )

        if not analysis.get("success", False):
            # Extract detailed error information for debugging
            error_detail = analysis.get("error", "Unknown error")
            analysis_keys = list(analysis.keys()) if isinstance(analysis, dict) else []

            # BUG-022 v9 FIX: Detect semantic mismatch where error="success" due to field swap
            # This happens when response parsing fails and fields get misaligned
            if error_detail in ("success", '"success"', "'success'", "true", "True"):
                logger.warning(
                    "[analyze_file] BUG-022 v9: Detected semantic mismatch - "
                    f"error field contains '{error_detail}' which is meaningless. "
                    "Extracting real error from other fields."
                )
                # Try to extract real error from other fields
                error_detail = (
                    analysis.get("message")
                    or analysis.get("details")
                    or analysis.get("reason")
                    or "Análise falhou: erro interno do servidor (resposta malformada)"
                )

            # Log full analysis response for debugging (critical for troubleshooting)
            debug_error(
                Exception(error_detail),
                "analyze_file_gemini_analysis",
                {"analysis_keys": analysis_keys, "s3_key": s3_key}
            )

            audit.error(
                message=f"Falha na análise com Gemini: {error_detail}",
                session_id=session_id,
                error=f"Keys: {analysis_keys}",
            )

            # BUG-022 v14 FIX: Always return NESTED structure to match TypeScript contract
            # Frontend expects: { analysis: { sheets: [...] } } - NOT top-level sheets
            return {
                "success": False,
                "error": error_detail,
                "analysis": {
                    "sheets": [],
                    "sheet_count": 0,
                    "total_rows": 0,
                    "recommended_strategy": "manual_review",
                },
                "file_analysis": {},  # Deprecated but kept for backward compatibility
                "debug_gemini_response_keys": analysis_keys,
            }

        # Extract key metrics
        row_count = analysis.get("row_count", 0)
        column_count = analysis.get("column_count", 0)
        confidence = analysis.get("analysis_confidence", 0.0)
        recommended_action = analysis.get("recommended_action", "unknown")
        hil_questions = analysis.get("hil_questions", [])

        # AGI-like fields
        unmapped_columns = analysis.get("unmapped_columns", [])
        unmapped_questions = analysis.get("unmapped_questions", [])
        # Note: all_questions_answered is tracked via pending_questions_count
        ready_for_import = analysis.get("ready_for_import", False)
        current_round = analysis.get("analysis_round", analysis_round)

        # Calculate total pending questions
        total_pending = len(hil_questions) + len(unmapped_questions)

        # Determine status message
        if ready_for_import:
            status_msg = f"[{round_label}] Pronto para importação: {row_count} linhas"
        elif total_pending > 0:
            status_msg = f"[{round_label}] Aguardando {total_pending} resposta(s)"
        else:
            status_msg = f"[{round_label}] Análise: {row_count} linhas, confiança {confidence:.0%}"

        audit.completed(
            message=status_msg,
            session_id=session_id,
            details={
                "row_count": row_count,
                "column_count": column_count,
                "confidence": confidence,
                "recommended_action": recommended_action,
                "hil_questions_count": len(hil_questions),
                "unmapped_columns_count": len(unmapped_columns),
                "ready_for_import": ready_for_import,
                "analysis_round": current_round,
            },
        )

        # Determine if agent should stop and wait for user response
        # CRITICAL: This flag tells the Strands ReAct loop to pause
        should_stop = total_pending > 0 or not ready_for_import

        # Generate session ID if not provided
        effective_session_id = session_id or f"nexo-{uuid4().hex[:8]}"
        effective_filename = filename or s3_key.split("/")[-1]

        # Build column_mappings array (matches TypeScript NexoColumnMapping[])
        column_mappings = [
            {
                "file_column": col.get("source_name", col.get("name", "")),
                "target_field": col.get("suggested_mapping") or col.get("target_field", ""),
                "confidence": col.get("mapping_confidence", col.get("confidence", 0.0)),
                "reasoning": col.get("reason", "Mapped based on column name pattern"),
                "alternatives": [],
            }
            for col in analysis.get("columns", [])
            if col.get("suggested_mapping") or col.get("target_field")
        ]

        # Build questions array (matches TypeScript NexoQuestion[])
        # BUG-025 FIX: Use defensive helper instead of fragile list comprehension
        questions = _safe_build_hil_questions(hil_questions)

        # Build unmapped_questions array (matches TypeScript)
        # BUG-025 FIX: Use defensive helper instead of fragile list comprehension
        unmapped_questions_formatted = _safe_build_unmapped_questions(unmapped_questions)

        # =============================================================================
        # BUG-023 FIX: Fallback question generation
        # =============================================================================
        # If confidence is low but no questions were generated by Gemini,
        # create a fallback question so the user has a way to proceed.
        # This prevents the import flow from being stuck at "0% confidence"
        # with no way to move forward.
        # =============================================================================
        total_questions_after_format = len(questions) + len(unmapped_questions_formatted)
        if total_questions_after_format == 0 and confidence < 0.8 and not ready_for_import:
            logger.warning(
                "[analyze_file] BUG-023: Confidence %.2f but no questions generated. Adding fallback question.",
                confidence
            )
            fallback_question = {
                "id": "fallback_low_confidence",
                "question": (
                    "A análise automática não conseguiu mapear as colunas com confiança suficiente. "
                    "Como deseja proceder?"
                ),
                "context": (
                    f"O arquivo '{effective_filename}' foi analisado, mas a confiança no mapeamento "
                    f"está em {confidence:.0%}. Isso pode acontecer com formatos de arquivo novos ou "
                    "colunas com nomes não-padrão."
                ),
                "importance": "critical",
                "topic": "low_confidence_fallback",
                "options": [
                    {"value": "manual_review", "label": "Revisar mapeamentos manualmente"},
                    {"value": "show_columns", "label": "Mostrar colunas detectadas para eu mapear"},
                    {"value": "retry_with_hints", "label": "Tentar novamente com dicas adicionais"},
                    {"value": "cancel", "label": "Cancelar esta importação"},
                ],
                "default_value": "manual_review",
            }
            questions.append(fallback_question)
            total_pending = 1  # Update to reflect the fallback question
            should_stop = True  # Ensure agent waits for user response

        # Build reasoning_trace (matches TypeScript NexoReasoningStep[])
        reasoning_trace = [
            {
                "type": "observation",
                "content": f"Analyzed file: {effective_filename}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "type": "thought",
                "content": f"Detected {column_count} columns, {row_count} rows with {confidence:.0%} confidence",
            },
            {
                "type": "action",
                "content": f"Recommended action: {recommended_action}",
                "tool": "file_analyzer",  # BUG-025 FIX: Updated from gemini_text_analyzer
            },
        ]

        # Build nested analysis object (CRITICAL - matches TypeScript NexoAnalyzeFileResponse.analysis)
        analysis_nested = {
            "sheet_count": 1,
            "total_rows": row_count,
            "sheets": [{
                "name": analysis.get("filename", "Sheet1"),
                "purpose": "items",  # Default purpose for single-sheet files
                "row_count": row_count,
                "column_count": column_count,
                "columns": [
                    {
                        "name": col.get("source_name", col.get("name", "")),
                        "sample_values": col.get("sample_values", []),
                        "detected_type": col.get("data_type", col.get("detected_type", "string")),
                        "suggested_mapping": col.get("suggested_mapping") or col.get("target_field"),
                        "confidence": col.get("mapping_confidence", col.get("confidence", 0.0)),
                    }
                    for col in analysis.get("columns", [])
                ],
                "confidence": confidence,
            }],
            "recommended_strategy": recommended_action,
        }

        return {
            # Core response fields (matches TypeScript NexoAnalyzeFileResponse)
            "success": True,
            "import_session_id": effective_session_id,
            "filename": effective_filename,
            "detected_file_type": analysis.get("file_type", "csv"),

            # NESTED analysis object (CRITICAL - matches TypeScript contract)
            "analysis": analysis_nested,

            # Column mappings array
            "column_mappings": column_mappings,

            # Overall confidence (renamed from confidence)
            "overall_confidence": confidence,

            # Questions array (renamed from hil_questions)
            "questions": questions,

            # Unmapped questions for AGI-like behavior
            "unmapped_questions": unmapped_questions_formatted if unmapped_questions_formatted else None,

            # Reasoning trace for transparency
            "reasoning_trace": reasoning_trace,

            # Session IDs
            "user_id": None,  # Set by orchestrator if needed
            "session_id": effective_session_id,

            # STATELESS: Session state for frontend storage
            "session_state": {
                "session_id": effective_session_id,
                "filename": effective_filename,
                "s3_key": s3_key,
                "stage": "questioning" if total_pending > 0 else "processing",
                "file_analysis": {
                    "sheets": analysis_nested["sheets"],
                    "sheet_count": 1,
                    "total_rows": row_count,
                    "detected_type": analysis.get("file_type", "csv"),
                    "recommended_strategy": recommended_action,
                },
                "reasoning_trace": reasoning_trace,
                "questions": questions,
                "answers": {},
                "learned_mappings": {},
                "ai_instructions": {},
                "requested_new_columns": [],
                "column_mappings": {
                    m["file_column"]: m["target_field"]
                    for m in column_mappings
                },
                "confidence": {
                    "overall": confidence,
                    "extraction_quality": 1.0,
                    "evidence_strength": 1.0,
                    "historical_match": 1.0,
                    "risk_level": "low" if confidence >= 0.8 else "medium" if confidence >= 0.5 else "high",
                    "factors": [],
                    "requires_hil": confidence < 0.6,
                },
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },

            # AGI-like control fields (for internal use)
            "ready_for_import": ready_for_import,
            "analysis_round": current_round,
            "pending_questions_count": total_pending,

            # Strands ReAct control
            "stop_action": should_stop,
            "stop_reason": "Aguardando respostas do usuário" if should_stop else None,

            # DEPRECATED: Legacy fields for backward compatibility
            "file_analysis": analysis,  # Keep for debugging
        }

    except Exception as e:
        debug_error(e, "analyze_file", {"s3_key": s3_key, "filename": filename})
        audit.error(
            message="Erro ao analisar arquivo",
            session_id=session_id,
            error=str(e),
        )
        # BUG-022 v14 FIX: Always return NESTED structure to match TypeScript contract
        # Frontend expects: { analysis: { sheets: [...] } } - NOT top-level sheets
        return {
            "success": False,
            "error": str(e),
            "analysis": {
                "sheets": [],
                "sheet_count": 0,
                "total_rows": 0,
                "recommended_strategy": "manual_review",
            },
            "file_analysis": {},  # Deprecated but kept for backward compatibility
        }


# Alias for backward compatibility with main.py imports
analyze_file_impl = analyze_file_tool
