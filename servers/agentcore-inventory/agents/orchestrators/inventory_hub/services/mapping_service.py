"""
Mapping Service - Phase 3 Schema Mapping Logic for NEXO Import Pipeline.

This service encapsulates the A2A communication with SchemaMapper agent
and the generation of Human-in-the-Loop (HIL) questions for column mapping.

Phase 3 Flow:
1. InventoryHub calls invoke_schema_mapper_phase3() after Phase 2 analysis
2. SchemaMapper agent performs semantic column matching
3. If missing required fields: generate_hil_questions() creates frontend-compatible questions
4. Frontend presents questions to user for column selection

Architecture:
- A2A via Strands Framework (IMMUTABLE rule: CLAUDE.md lines 31-36)
- Sync-to-async bridge using asyncio.get_event_loop().run_until_complete()
- PII-safe logging via flow_log (count-only pattern)

Reference:
- SchemaMapper Agent: server/agentcore-inventory/agents/specialists/schema_mapper/main.py
- Frontend Contract: client/services/sgaAgentcore.ts (NexoQuestion interface)
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from shared.flow_logger import flow_log
from shared.strands_a2a_client import A2AClient

logger = logging.getLogger(__name__)

__all__ = [
    "invoke_schema_mapper_phase3",
    "generate_hil_questions",
    "_merge_phase3_results",
    "_convert_missing_fields_to_questions",
]


def invoke_schema_mapper_phase3(
    columns: list[str],
    sample_data: list[dict[str, Any]],
    s3_key: str,
    import_session_id: str,
) -> dict[str, Any]:
    """
    Invoke SchemaMapper via A2A to get column mappings and/or HIL questions.

    Called automatically after Phase 2 (file analysis) to trigger Phase 3
    (semantic column mapping). The SchemaMapper uses Gemini 2.5 Pro with
    thinking enabled for high-quality mapping decisions.

    Args:
        columns: List of column names from file analysis.
            Example: ["codigo", "descricao", "quantidade", "valor"]
        sample_data: First 3 rows of sample data for context.
            Example: [{"codigo": "ABC123", "descricao": "Item 1", ...}, ...]
        s3_key: S3 key of the uploaded file for reference.
            Example: "uploads/user123/session456/inventory.csv"
        import_session_id: Session ID for tracking and correlation.
            Example: "nexo_20260125_143000_inventory.csv"

    Returns:
        SchemaMapper response dict with either:
        - status="success": mappings ready for HIL confirmation
            {
                "success": True,
                "status": "success",
                "mappings": [...],
                "overall_confidence": 0.87,
                "questions": [...]  # Optional low-confidence questions
            }
        - status="needs_input": missing_required_fields to convert to questions
            {
                "success": True,
                "status": "needs_input",
                "missing_required_fields": [...],
                "questions": [...]  # AI-generated questions
            }
        - Error dict if A2A call fails
            {
                "success": False,
                "error": "Error message"
            }

    Example:
        >>> result = invoke_schema_mapper_phase3(
        ...     columns=["SKU", "QTD", "PRECO"],
        ...     sample_data=[{"SKU": "ABC", "QTD": "10", "PRECO": "15.50"}],
        ...     s3_key="uploads/user123/file.csv",
        ...     import_session_id="nexo_123"
        ... )
        >>> if result.get("status") == "needs_input":
        ...     questions = result.get("questions", [])
    """
    flow_log.phase_start(
        3, "SchemaMapper", import_session_id, source_columns_count=len(columns)
    )

    async def _invoke() -> dict[str, Any]:
        """Async wrapper for A2A invocation."""
        a2a_client = A2AClient()

        return await a2a_client.invoke_agent(
            agent_id="schema_mapper",
            payload={
                "prompt": f"Map these columns to pending_entry_items schema: {columns}",
                "session_id": import_session_id,
                "columns": columns,
                "sample_data": sample_data[:3] if sample_data else [],
                "target_table": "pending_entry_items",
                "s3_key": s3_key,
            },
            session_id=import_session_id,
            timeout=60.0,  # 60s for schema mapping (shorter than default 15min)
        )

    try:
        # Sync-to-async bridge pattern
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_invoke())

        # Extract response from A2AResponse
        if hasattr(result, "success") and not result.success:
            logger.warning(f"[Phase3] SchemaMapper A2A failed: {result.error}")
            flow_log.phase_end(
                3,
                "SchemaMapper",
                import_session_id,
                "FAILED",
                0,
                error=str(result.error),
            )
            return {"success": False, "error": result.error}

        response_data = getattr(result, "response", result)
        # BUG-028 DIAGNOSTIC: Enhanced logging for A2A response
        logger.info(
            f"[Phase3] Raw A2A result type: {type(result).__name__}, "
            f"has 'response' attr: {hasattr(result, 'response')}, "
            f"success: {getattr(result, 'success', 'N/A')}, "
            f"response_data type: {type(response_data).__name__}"
        )

        # Parse JSON string response if needed
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError:
                logger.warning(
                    "[Phase3] Could not parse response as JSON, returning raw"
                )
                return {"success": True, "raw_response": response_data}

        if isinstance(response_data, dict):
            logger.info(f"[Phase3] Response keys: {list(response_data.keys())}")

            questions_count = len(response_data.get("questions", []))
            flow_log.decision(
                "Questions generated for HIL",
                session_id=import_session_id,
                questions_count=questions_count,
                status=response_data.get("status", "unknown"),
            )

            if "mappings" in response_data:
                flow_log.decision(
                    "Mapping proposal ready",
                    session_id=import_session_id,
                    mappings_count=len(response_data["mappings"]),
                    overall_confidence=response_data.get("overall_confidence", 0.0),
                    unmapped_count=len(
                        response_data.get("unmapped_source_columns", [])
                    ),
                )

            flow_log.phase_end(
                3,
                "SchemaMapper",
                import_session_id,
                "SUCCESS",
                0,  # Duration tracked separately
                questions_count=questions_count,
                mappings_count=len(response_data.get("mappings", [])),
                status=response_data.get("status", "unknown"),
            )
        else:
            logger.error(
                f"[Phase3] SchemaMapper returned non-dict: {type(response_data)}"
            )
            flow_log.phase_end(
                3,
                "SchemaMapper",
                import_session_id,
                "FAILED",
                0,
                error="Non-dict response",
            )

        return (
            response_data
            if isinstance(response_data, dict)
            else {"success": True, "response": response_data}
        )

    except Exception as e:
        logger.warning(f"[Phase3] SchemaMapper invocation failed: {e}")
        flow_log.phase_end(
            3,
            "SchemaMapper",
            import_session_id,
            "FAILED",
            0,
            error_type=type(e).__name__,
        )
        return {"success": False, "error": str(e)}


def generate_hil_questions(missing_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Transform SchemaMapper missing_required_fields to frontend-compatible questions.

    Called when SchemaMapper returns status="needs_input" to convert the
    missing field specifications into user-friendly multiple-choice questions.

    Args:
        missing_fields: List of missing field dicts from SchemaMapper.
            Each entry contains:
            {
                "target_column": "part_number",
                "description": "Codigo do material/SKU",
                "available_sources": ["COD", "SKU", "CODIGO"]
            }

    Returns:
        List of NexoQuestion dicts ready for frontend rendering.
        Each question has:
        {
            "question_id": "q_part_number_a1b2c3d4",
            "question_text": "Qual coluna representa o Codigo do material/SKU?",
            "options": [
                {"value": "COD", "label": "COD", "recommended": True},
                {"value": "SKU", "label": "SKU", "recommended": False},
                ...
            ],
            "field_name": "part_number",
            "importance": "critical",
            "blocking": True
        }

    Example:
        >>> missing = [
        ...     {
        ...         "target_column": "quantity",
        ...         "description": "Quantidade em estoque",
        ...         "available_sources": ["QTD", "QUANTIDADE"]
        ...     }
        ... ]
        >>> questions = generate_hil_questions(missing)
        >>> questions[0]["question_text"]
        'Qual coluna representa Quantidade em estoque?'

    Frontend Contract:
        TypeScript interface at client/services/sgaAgentcore.ts (NexoQuestion)
    """
    # Critical fields that require user input (cannot be ignored)
    CRITICAL_FIELDS = frozenset({
        "part_number",
        "quantity",
        "material_code",
        "sku",
    })

    questions: list[dict[str, Any]] = []

    for field in missing_fields:
        target_column = field.get("target_column", "unknown")
        description = field.get("description", target_column)
        available_sources = field.get("available_sources", [])

        # Build options from available_sources
        options: list[dict[str, Any]] = []
        for i, source in enumerate(available_sources):
            options.append({
                "value": source,
                "label": source,
                "description": f"Usar coluna '{source}' como {description}",
                "recommended": i == 0,  # First option is usually best match
            })

        # Add "ignore" option for non-critical fields
        is_critical = target_column in CRITICAL_FIELDS
        if not is_critical:
            options.append({
                "value": "_ignore_",
                "label": "Ignorar este campo",
                "description": "Nao mapear - campo ficara vazio",
                "warning": True,
            })

        # Generate unique question ID
        question_id = f"q_{target_column}_{uuid.uuid4().hex[:8]}"

        question: dict[str, Any] = {
            "question_id": question_id,
            "question_text": f"Qual coluna representa {description}?",
            "options": options,
            "field_name": target_column,
            # Additional metadata for frontend
            "context": f"Campo obrigatorio: {target_column}",
            "importance": "critical" if is_critical else "high",
            "topic": "column_mapping",
            "blocking": is_critical,
        }

        questions.append(question)

    logger.info(
        f"[HIL] Generated {len(questions)} questions "
        f"({sum(1 for q in questions if q['blocking'])} blocking)"
    )

    return questions


# =============================================================================
# Backward Compatibility Exports (BUG-045)
# =============================================================================
# These functions were in main.py before modular refactoring.
# Re-exported here for test compatibility.


def _convert_missing_fields_to_questions(missing_fields: list) -> list:
    """
    Convert SchemaMapper's missing_required_fields to NexoQuestion format.

    BUG-022 FIX: SchemaMapper returns `missing_required_fields` when status="needs_input".
    Each entry contains:
        {
            "target_column": "part_number",
            "description": "Código do material/SKU",
            "available_sources": ["COD", "SKU"]
        }

    This function converts them to the frontend's NexoQuestion interface.

    Note:
        This is a wrapper around generate_hil_questions() for backward compatibility.
        New code should use generate_hil_questions() directly.

    Args:
        missing_fields: List of missing field dicts from SchemaMapper

    Returns:
        List of NexoQuestion dicts ready for frontend
    """
    # Delegate to the canonical implementation
    questions = generate_hil_questions(missing_fields)

    # Transform to legacy format (id vs question_id, question vs question_text)
    legacy_questions = []
    for q in questions:
        legacy_q = {
            "id": q.get("question_id", q.get("id")),
            "question": q.get("question_text", q.get("question")),
            "context": q.get("context"),
            "importance": q.get("importance"),
            "topic": q.get("topic"),
            "options": q.get("options"),
            "column": q.get("field_name"),
            "blocking": q.get("blocking"),
        }
        legacy_questions.append(legacy_q)

    return legacy_questions


def _merge_phase3_results(phase2_response: dict, phase3_response: dict) -> dict:
    """
    Merge Phase 3 (SchemaMapper) results into Phase 2 response.

    BUG-022 FIX: This function merges:
    - column_mappings: From Phase 3 if available
    - questions: Converted from missing_required_fields if status="needs_input"
    - mapping_confidence: From Phase 3 overall_confidence

    BUG-045 FIX: Prefer AI-generated questions from SchemaMapper directly.
    SchemaMapper now generates intelligent, context-aware questions using sample_data.
    Only fall back to template-based conversion if SchemaMapper doesn't return questions.

    The original overall_confidence from Phase 2 represents FILE QUALITY.
    Phase 3 adds MAPPING CONFIDENCE which is a separate concern.

    Args:
        phase2_response: Dict from _transform_file_structure_to_nexo_response
        phase3_response: Dict from SchemaMapper A2A response

    Returns:
        Merged response with Phase 3 data integrated
    """
    # Start with Phase 2 response
    merged = phase2_response.copy()

    # If Phase 3 failed, return Phase 2 response with warning
    if not phase3_response.get("success", True):
        merged["phase3_error"] = phase3_response.get("error", "Unknown Phase 3 error")
        logger.warning(f"[Phase3] Returning Phase 2 only due to error: {merged['phase3_error']}")
        return merged

    # Extract Phase 3 status
    status = phase3_response.get("status", "unknown")

    # BUG-028 DIAGNOSTIC: Log merge context for debugging
    logger.info(
        f"[Phase3] Merging results - status: {status}, "
        f"phase3_response keys: {list(phase3_response.keys())}, "
        f"has 'mappings': {'mappings' in phase3_response}, "
        f"mappings type: {type(phase3_response.get('mappings', 'N/A')).__name__}"
    )

    # Case 1: status="needs_input" - Use questions from SchemaMapper
    if status == "needs_input":
        # BUG-045 FIX: Prefer AI-generated questions from SchemaMapper directly
        # SchemaMapper now returns intelligent questions with context from sample_data
        if "questions" in phase3_response and phase3_response["questions"]:
            merged["questions"] = phase3_response["questions"]
            logger.info(
                f"[Phase3] Using {len(merged['questions'])} AI-generated questions from SchemaMapper"
            )
        else:
            # Fallback: Convert missing_required_fields to template-based questions
            missing_fields = phase3_response.get("missing_required_fields", [])
            if missing_fields:
                questions = _convert_missing_fields_to_questions(missing_fields)
                merged["questions"] = questions
                logger.info(f"[Phase3] Fallback: Generated {len(questions)} template questions")

    # Case 2: status="success" - Use proposed mappings
    # BUG-023 FIX: Check key existence, not truthiness (empty list is valid state)
    # GHOST BUG MITIGATION: LLMs may use different key names for mappings
    elif status == "success":
        # Key-tolerant extraction: Try multiple possible key names
        mappings = (
            phase3_response.get("mappings")
            or phase3_response.get("column_mappings")
            or phase3_response.get("columns_map")
            or phase3_response.get("mapping_list")
            or []
        )

        # BUG-028 FIX: ALWAYS set column_mappings, even if empty
        # Frontend expects this field to exist (empty [] is valid state)
        merged["column_mappings"] = mappings

        if mappings:
            logger.info(f"[Phase3] Received {len(mappings)} column mappings")
        else:
            # Log warning but still include empty list in response
            logger.warning(
                f"[Phase3] status=success but mappings list is empty. "
                f"Available keys: {list(phase3_response.keys())}. "
                f"SchemaMapper may need more context or sample data."
            )

        # BUG-045: Even on success, include AI questions for low-confidence mappings
        if "questions" in phase3_response and phase3_response["questions"]:
            merged["questions"] = phase3_response["questions"]
            logger.info(
                f"[Phase3] Added {len(merged['questions'])} questions for low-confidence mappings"
            )

    # Add Phase 3 confidence (distinct from file quality confidence)
    if "overall_confidence" in phase3_response:
        merged["mapping_confidence"] = phase3_response["overall_confidence"]

    # Mark that Phase 3 completed
    merged["phase3_status"] = status

    # Add requires_confirmation flag (always true per plan - even at 100% confidence)
    merged["requires_confirmation"] = True

    return merged
