# =============================================================================
# Reason Mappings Tool
# =============================================================================
# Reasons about column mappings using schema context and prior knowledge.
# =============================================================================

import logging
from typing import Dict, Any, Optional


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "nexo_import"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_reason_mappings")
async def reason_mappings_tool(
    file_analysis: Dict[str, Any],
    prior_knowledge: Dict[str, Any],
    schema_context: str,
    target_table: str = "pending_entry_items",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reason about column mappings.

    Uses:
    1. File analysis (column names, sample data)
    2. Prior knowledge (from LearningAgent via A2A)
    3. PostgreSQL schema context

    To generate:
    - Suggested mappings with confidence scores
    - List of columns needing clarification (confidence < 0.8)

    Args:
        file_analysis: Analysis from analyze_file tool
        prior_knowledge: Prior knowledge from LearningAgent
        schema_context: PostgreSQL schema markdown
        target_table: Target table for mapping
        session_id: Optional session ID for audit

    Returns:
        Reasoning result with mappings and confidence
    """
    audit.working(
        message="Raciocinando sobre mapeamentos...",
        session_id=session_id,
    )

    try:
        # Extract columns from file analysis
        sheets = file_analysis.get("sheets", [])
        if not sheets:
            return {
                "success": False,
                "error": "No sheets found in file analysis",
                "suggested_mappings": {},
                "needs_clarification": [],
            }

        # Get primary sheet (usually the first data sheet)
        primary_sheet = sheets[0]
        columns = primary_sheet.get("columns", [])

        # Start with prior knowledge mappings
        suggested_mappings = {}
        prior_mappings = prior_knowledge.get("suggested_mappings", {})

        for mapping_info in prior_mappings.values() if isinstance(prior_mappings, dict) else []:
            if isinstance(mapping_info, dict):
                suggested_mappings.update(mapping_info)

        # Build reasoning result
        needs_clarification = []
        confidence_scores = {}

        for col in columns:
            col_name = col.get("name", "")
            if not col_name:
                continue

            col_name.lower()

            # Check if prior knowledge has this mapping
            if col_name in prior_mappings:
                prior = prior_mappings[col_name]
                confidence = prior.get("confidence", 0.7) if isinstance(prior, dict) else 0.7
                field = prior.get("field") if isinstance(prior, dict) else prior
                suggested_mappings[col_name] = field
                confidence_scores[col_name] = confidence

                if confidence < 0.8:
                    needs_clarification.append({
                        "column": col_name,
                        "suggested_field": field,
                        "confidence": confidence,
                        "reason": "Baixa confiança no mapeamento aprendido",
                    })
            else:
                # Try heuristic matching
                field, confidence = _heuristic_match(col_name, schema_context)
                if field:
                    suggested_mappings[col_name] = field
                    confidence_scores[col_name] = confidence

                    if confidence < 0.8:
                        needs_clarification.append({
                            "column": col_name,
                            "suggested_field": field,
                            "confidence": confidence,
                            "reason": "Mapeamento heurístico com baixa confiança",
                        })
                else:
                    needs_clarification.append({
                        "column": col_name,
                        "suggested_field": None,
                        "confidence": 0.0,
                        "reason": "Coluna não reconhecida",
                    })

        audit.completed(
            message=f"Raciocínio concluído: {len(suggested_mappings)} mapeamentos, "
                    f"{len(needs_clarification)} precisam de clarificação",
            session_id=session_id,
            details={
                "mappings_count": len(suggested_mappings),
                "needs_clarification": len(needs_clarification),
            },
        )

        return {
            "success": True,
            "suggested_mappings": suggested_mappings,
            "confidence_scores": confidence_scores,
            "needs_clarification": needs_clarification,
            "has_prior_knowledge": bool(prior_mappings),
        }

    except Exception as e:
        logger.error(f"[reason_mappings] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao raciocinar sobre mapeamentos",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
            "suggested_mappings": {},
            "needs_clarification": [],
        }


def _heuristic_match(col_name: str, schema_context: str) -> tuple:
    """
    Heuristic matching for common column patterns.

    Returns (field, confidence) tuple.
    """
    col_lower = col_name.lower().strip()

    # Common patterns with high confidence
    patterns = {
        # Part number patterns
        "pn": ("part_number", 0.9),
        "p/n": ("part_number", 0.9),
        "partnumber": ("part_number", 0.95),
        "part_number": ("part_number", 0.99),
        "numero_peca": ("part_number", 0.9),
        "equipamento": ("part_number", 0.85),

        # Quantity patterns
        "qty": ("quantity", 0.9),
        "qtd": ("quantity", 0.9),
        "quantidade": ("quantity", 0.95),
        "quantity": ("quantity", 0.99),

        # Description patterns
        "desc": ("description", 0.85),
        "descricao": ("description", 0.95),
        "description": ("description", 0.99),
        "nome": ("description", 0.8),

        # Serial patterns
        "sn": ("serial_number", 0.9),
        "serial": ("serial_number", 0.95),
        "serial_number": ("serial_number", 0.99),

        # Location patterns
        "loc": ("location", 0.85),
        "localizacao": ("location", 0.9),
        "location": ("location", 0.99),

        # Unit patterns
        "unit": ("unit", 0.9),
        "unidade": ("unit", 0.9),
        "un": ("unit", 0.85),
    }

    if col_lower in patterns:
        return patterns[col_lower]

    # Fuzzy matching for partial matches
    for pattern, (field, conf) in patterns.items():
        if pattern in col_lower or col_lower in pattern:
            return (field, conf * 0.8)  # Lower confidence for partial match

    return (None, 0.0)


# Alias for backward compatibility with main.py imports
reason_mappings_impl = reason_mappings_tool
