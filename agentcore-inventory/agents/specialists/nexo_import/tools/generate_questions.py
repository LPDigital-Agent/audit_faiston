# =============================================================================
# Generate Questions Tool (AGI-Like Behavior)
# =============================================================================
# Generates HIL (Human-in-the-Loop) questions for:
# - Low-confidence mappings (confidence < 80%)
# - Unmapped columns (columns not in DB schema)
#
# AGI-Like Behavior:
# - Questions are presented to user for decision
# - User responses feed back into Gemini for re-analysis
# - Unmapped columns MUST be decided before import proceeds
# =============================================================================

import logging
from typing import Dict, Any, List, Optional


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "nexo_import"
audit = AgentAuditEmitter(agent_id=AGENT_ID)

# =============================================================================
# Unmapped Column Options (AGI-Like - Requires User Decision)
# =============================================================================

UNMAPPED_OPTIONS = [
    {
        "value": "ignore",
        "label": "Ignorar (dados serão perdidos)",
        "description": "Esta coluna não será importada. Os dados serão descartados.",
        "warning": True,
    },
    {
        "value": "metadata",
        "label": "Guardar em metadata (preservar)",
        "description": "Os dados serão preservados no campo JSONB 'metadata' para consulta futura.",
        "recommended": True,
    },
    {
        "value": "request_db_update",
        "label": "Solicitar criação de campo no DB",
        "description": "Você deve contatar a equipe de TI da Faiston para criar o campo no PostgreSQL. Após a criação, tente a importação novamente.",
        "contact_it": True,
    },
]


@trace_tool_call("sga_generate_questions")
async def generate_questions_tool(
    needs_clarification: List[Dict[str, Any]],
    schema_context: str,
    unmapped_columns: Optional[List[Dict[str, Any]]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate HIL questions for columns needing clarification (AGI-Like).

    Builds intelligent questions for:
    - Columns with confidence < 80%
    - Columns with no prior knowledge
    - Columns with multiple possible mappings
    - UNMAPPED columns (not in DB schema) - CRITICAL

    Args:
        needs_clarification: List of columns needing user input
        schema_context: PostgreSQL schema markdown for context
        unmapped_columns: List of columns not in DB schema (AGI-like)
        session_id: Optional session ID for audit

    Returns:
        Generated questions for HIL review (mapping + unmapped)
    """
    unmapped_columns = unmapped_columns or []
    total_items = len(needs_clarification) + len(unmapped_columns)

    audit.working(
        message=f"Gerando {total_items} pergunta(s) (mapeamento: {len(needs_clarification)}, não mapeadas: {len(unmapped_columns)})...",
        session_id=session_id,
    )

    try:
        questions = []
        unmapped_questions = []

        # Parse available fields from schema context
        available_fields = _extract_fields_from_schema(schema_context)

        # 1. Generate mapping questions (low confidence)
        for item in needs_clarification:
            column = item.get("column", "")
            suggested_field = item.get("suggested_field")
            confidence = item.get("confidence", 0.0)
            reason = item.get("reason", "")

            if not column:
                continue

            # Build question based on situation
            question = _build_question(
                column=column,
                suggested_field=suggested_field,
                confidence=confidence,
                reason=reason,
                available_fields=available_fields,
            )

            if question:
                questions.append(question)

        # 2. Generate unmapped column questions (AGI-like - CRITICAL)
        for item in unmapped_columns:
            source_name = item.get("source_name", "")
            description = item.get("description", "")
            suggested_action = item.get("suggested_action", "metadata")

            if not source_name:
                continue

            unmapped_q = _build_unmapped_question(
                column=source_name,
                description=description,
                suggested_action=suggested_action,
            )

            if unmapped_q:
                unmapped_questions.append(unmapped_q)

        total_questions = len(questions) + len(unmapped_questions)

        audit.completed(
            message=f"Geradas {total_questions} pergunta(s) para revisão",
            session_id=session_id,
            details={
                "mapping_questions": len(questions),
                "unmapped_questions": len(unmapped_questions),
                "total_questions": total_questions,
            },
        )

        return {
            "success": True,
            "questions": questions,
            "unmapped_questions": unmapped_questions,
            "total_questions": total_questions,
            "available_fields": available_fields,
            "has_unmapped": len(unmapped_questions) > 0,
        }

    except Exception as e:
        logger.error(f"[generate_questions] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao gerar perguntas",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
            "questions": [],
            "unmapped_questions": [],
        }


def _build_unmapped_question(
    column: str,
    description: str,
    suggested_action: str,
) -> Dict[str, Any]:
    """
    Build a question for an unmapped column (AGI-like behavior).

    These columns don't exist in the PostgreSQL schema and require
    user decision before import can proceed.

    Args:
        column: Column name from source file
        description: Inferred description of the column
        suggested_action: Suggested action (ignore, metadata, request_db_update)

    Returns:
        Question dict with options for user decision
    """
    question_id = f"uq_{column.lower().replace(' ', '_').replace('°', '').replace('/', '_')}"

    # Build options with suggested one first
    options = []
    for opt in UNMAPPED_OPTIONS:
        option = opt.copy()
        if opt["value"] == suggested_action:
            option["label"] = f"{opt['label']} (recomendado)"
        options.append(option)

    # Reorder to put suggested first
    options.sort(key=lambda x: 0 if suggested_action in x.get("label", "") else 1)

    return {
        "id": question_id,
        "type": "unmapped",
        "column": column,
        "question": f"A coluna '{column}' NÃO existe no banco de dados. O que deseja fazer?",
        "description": description,
        "suggested_action": suggested_action,
        "options": options,
        "blocking": True,  # Import cannot proceed without decision
        "it_contact_note": (
            "Se escolher 'Solicitar criação de campo no DB', entre em contato com a "
            "equipe de Tecnologia da Faiston para preparar o banco de dados. "
            "Após a criação do campo, tente a importação novamente."
        ),
    }


def _extract_fields_from_schema(schema_context: str) -> List[str]:
    """
    Extract available fields from schema context.

    Returns list of field names from pending_entry_items table.
    """
    # Standard fields in pending_entry_items
    standard_fields = [
        "part_number",
        "description",
        "quantity",
        "serial_number",
        "location",
        "unit",
        "condition",
        "notes",
        "project_code",
        "batch_number",
        "manufacturer",
        "supplier",
    ]

    # Try to parse additional fields from schema context
    additional_fields = []
    if schema_context:
        # Look for column definitions
        lines = schema_context.split("\n")
        for line in lines:
            line_lower = line.lower().strip()
            if "column" in line_lower or "|" in line:
                # Try to extract column name from markdown table or text
                parts = line.split("|")
                if len(parts) >= 2:
                    potential_field = parts[1].strip().lower()
                    if potential_field and potential_field not in standard_fields:
                        if potential_field.isidentifier():
                            additional_fields.append(potential_field)

    return standard_fields + additional_fields


def _build_question(
    column: str,
    suggested_field: Optional[str],
    confidence: float,
    reason: str,
    available_fields: List[str],
) -> Dict[str, Any]:
    """
    Build a structured question for HIL review.

    Returns question dict with type, options, and context.
    """
    question_id = f"q_{column.lower().replace(' ', '_')}"

    if suggested_field and confidence >= 0.5:
        # Medium confidence - ask to confirm suggestion
        return {
            "id": question_id,
            "type": "confirmation",
            "column": column,
            "question": f"A coluna '{column}' parece corresponder ao campo '{suggested_field}'. Confirma?",
            "suggested_field": suggested_field,
            "confidence": confidence,
            "reason": reason,
            "options": [
                {"value": suggested_field, "label": f"Sim, mapear para '{suggested_field}'"},
                {"value": "_select_other", "label": "Não, escolher outro campo"},
                {"value": "_skip", "label": "Ignorar esta coluna"},
                {"value": "_create_new", "label": "Criar nova coluna"},
            ],
            "available_fields": available_fields,
        }

    elif suggested_field:
        # Low confidence - show suggestion but ask for selection
        return {
            "id": question_id,
            "type": "selection",
            "column": column,
            "question": f"Para qual campo a coluna '{column}' deve ser mapeada?",
            "suggested_field": suggested_field,
            "confidence": confidence,
            "reason": reason,
            "options": _build_field_options(available_fields, suggested_field),
            "available_fields": available_fields,
        }

    else:
        # No suggestion - ask for mapping
        return {
            "id": question_id,
            "type": "mapping",
            "column": column,
            "question": f"A coluna '{column}' não foi reconhecida. Para qual campo deve ser mapeada?",
            "suggested_field": None,
            "confidence": 0.0,
            "reason": reason,
            "options": _build_field_options(available_fields, None),
            "available_fields": available_fields,
        }


def _build_field_options(
    available_fields: List[str],
    suggested_field: Optional[str],
) -> List[Dict[str, str]]:
    """
    Build options list for field selection.

    Puts suggested field first if provided.
    """
    options = []

    # Add suggested field first with indicator
    if suggested_field and suggested_field in available_fields:
        options.append({
            "value": suggested_field,
            "label": f"{suggested_field} (sugerido)",
        })

    # Add other fields
    for field in available_fields:
        if field != suggested_field:
            options.append({
                "value": field,
                "label": field,
            })

    # Add special options
    options.extend([
        {"value": "_skip", "label": "Ignorar esta coluna"},
        {"value": "_create_new", "label": "Criar nova coluna"},
    ])

    return options


# Alias for backward compatibility with main.py imports
generate_questions_impl = generate_questions_tool
