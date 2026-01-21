# =============================================================================
# Analyze Import Tool
# Generates intelligent observations for import data
# =============================================================================

import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime


logger = logging.getLogger(__name__)

# =============================================================================
# Source Type Labels
# =============================================================================

SOURCE_LABELS = {
    "nf_xml": "NF XML",
    "nf_pdf": "NF PDF (OCR)",
    "nf_image": "Imagem de NF (OCR)",
    "spreadsheet": "Planilha (CSV/Excel)",
    "text": "Texto/Manual",
    "sap_export": "Exportação SAP",
}

# =============================================================================
# Analysis Weights
# =============================================================================

CONFIDENCE_FACTORS = {
    "data_completeness": {
        "label": "Completude dos dados",
        "weight": 0.3,
        "description": "Campos obrigatórios preenchidos",
    },
    "format_consistency": {
        "label": "Consistência do formato",
        "weight": 0.3,
        "description": "Formato dos dados padronizado",
    },
    "value_validation": {
        "label": "Validação de valores",
        "weight": 0.4,
        "description": "Valores dentro de faixas esperadas",
    },
}

# =============================================================================
# Tool Implementation
# =============================================================================


async def analyze_import_tool(
    preview_data: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze import preview data and generate intelligent observations.

    Follows the OBSERVE → LEARN → ACT pattern:
    - OBSERVE: Examine data structure, completeness, values
    - LEARN: Identify patterns, compare with expected norms
    - ACT: Generate confidence scores and recommendations

    Args:
        preview_data: Import preview data containing:
            - source_type: Type of import (nf_xml, nf_pdf, etc.)
            - items_count: Number of items
            - total_value: Optional total value
            - items: Optional list of item details
            - validation_warnings: Any warnings from validation
        context: Optional context (project_id, location_id, user_notes)
        session_id: Session ID for audit trail

    Returns:
        Dict with observations, confidence scores, and suggestions
    """
    from shared.audit_emitter import AgentAuditEmitter

    audit = AgentAuditEmitter(agent_id="observation")
    start_time = time.time()

    audit.working(
        "Iniciando análise OBSERVE → LEARN → ACT",
        session_id=session_id,
    )

    try:
        # =================================================================
        # OBSERVE Phase
        # =================================================================
        source_type = preview_data.get("source_type", "unknown")
        items_count = preview_data.get("items_count", 0)
        total_value = preview_data.get("total_value")
        preview_data.get("supplier_name", "")
        preview_data.get("nf_number", "")
        items = preview_data.get("items", [])
        warnings = preview_data.get("validation_warnings", [])
        preview_data.get("hil_required", False)

        audit.working(
            f"OBSERVE: {items_count} itens, fonte {source_type}",
            session_id=session_id,
        )

        # =================================================================
        # LEARN Phase - Analyze patterns and calculate confidence
        # =================================================================

        patterns = []
        suggestions = []
        observation_warnings = []

        # Check data completeness
        completeness_score = _calculate_completeness(preview_data, items)
        if completeness_score < 70:
            suggestions.append("Considere preencher campos faltantes antes de confirmar")

        # Check format consistency
        consistency_score = _calculate_consistency(items)
        if consistency_score < 70:
            suggestions.append("Alguns itens têm formato inconsistente")

        # Check value validation
        value_score, value_patterns, value_warnings = _analyze_values(items, total_value)
        patterns.extend(value_patterns)
        observation_warnings.extend(value_warnings)

        # Identify patterns in items
        item_patterns = _identify_item_patterns(items)
        patterns.extend(item_patterns)

        # Add validation warnings
        if warnings:
            observation_warnings.extend(warnings)

        # Calculate overall confidence
        overall_confidence = (
            completeness_score * CONFIDENCE_FACTORS["data_completeness"]["weight"]
            + consistency_score * CONFIDENCE_FACTORS["format_consistency"]["weight"]
            + value_score * CONFIDENCE_FACTORS["value_validation"]["weight"]
        )

        # Determine risk level
        if overall_confidence >= 75:
            risk_level = "low"
        elif overall_confidence >= 50:
            risk_level = "medium"
        else:
            risk_level = "high"

        audit.working(
            f"LEARN: Confiança {overall_confidence:.0f}%, risco {risk_level}",
            session_id=session_id,
        )

        # =================================================================
        # ACT Phase - Generate recommendations
        # =================================================================

        # Generate AI commentary
        commentary = _generate_commentary(
            source_type=source_type,
            items_count=items_count,
            total_value=total_value,
            overall_confidence=overall_confidence,
            risk_level=risk_level,
            patterns=patterns,
            warnings=observation_warnings,
        )

        # Generate learning insights
        learn_from = _generate_insights(
            source_type=source_type,
            patterns=patterns,
            overall_confidence=overall_confidence,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        audit.completed(
            f"ACT: Geradas {len(patterns)} observações, {len(suggestions)} sugestões",
            session_id=session_id,
            details={
                "confidence": overall_confidence,
                "risk_level": risk_level,
                "processing_time_ms": processing_time_ms,
            },
        )

        return {
            "success": True,
            "confidence": {
                "overall": round(overall_confidence),
                "factors": [
                    {
                        "id": "data_completeness",
                        "label": CONFIDENCE_FACTORS["data_completeness"]["label"],
                        "score": round(completeness_score),
                        "weight": CONFIDENCE_FACTORS["data_completeness"]["weight"],
                    },
                    {
                        "id": "format_consistency",
                        "label": CONFIDENCE_FACTORS["format_consistency"]["label"],
                        "score": round(consistency_score),
                        "weight": CONFIDENCE_FACTORS["format_consistency"]["weight"],
                    },
                    {
                        "id": "value_validation",
                        "label": CONFIDENCE_FACTORS["value_validation"]["label"],
                        "score": round(value_score),
                        "weight": CONFIDENCE_FACTORS["value_validation"]["weight"],
                    },
                ],
                "risk_level": risk_level,
            },
            "observations": {
                "patterns": patterns,
                "suggestions": suggestions,
                "warnings": observation_warnings,
            },
            "ai_commentary": commentary,
            "learn_from": learn_from,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "processing_time_ms": processing_time_ms,
        }

    except Exception as e:
        logger.error(f"[analyze_import] Error: {e}", exc_info=True)
        audit.error(
            "Erro na análise de importação",
            session_id=session_id,
            error=str(e),
        )
        return _get_fallback_result(str(e), start_time)


# =============================================================================
# Analysis Helper Functions
# =============================================================================


def _calculate_completeness(preview_data: Dict[str, Any], items: List[Dict]) -> float:
    """Calculate data completeness score (0-100)."""
    required_fields = ["source_type", "items_count"]
    optional_fields = ["total_value", "supplier_name", "nf_number"]

    # Check required fields
    required_present = sum(1 for f in required_fields if preview_data.get(f))
    required_score = (required_present / len(required_fields)) * 60

    # Check optional fields
    optional_present = sum(1 for f in optional_fields if preview_data.get(f))
    optional_score = (optional_present / len(optional_fields)) * 20

    # Check item details
    items_score = 0
    if items:
        item_fields = ["description", "quantity", "unit_value"]
        items_completeness = []
        for item in items[:10]:  # Sample first 10
            present = sum(1 for f in item_fields if item.get(f))
            items_completeness.append(present / len(item_fields))
        items_score = (sum(items_completeness) / len(items_completeness)) * 20 if items_completeness else 0

    return required_score + optional_score + items_score


def _calculate_consistency(items: List[Dict]) -> float:
    """Calculate format consistency score (0-100)."""
    if not items:
        return 80  # Default for no items

    # Check description format consistency
    descriptions = [item.get("description", "") for item in items if item.get("description")]
    if not descriptions:
        return 70

    # Check if descriptions have similar structure
    has_codes = sum(1 for d in descriptions if any(c.isdigit() for c in d[:10]))
    code_consistency = has_codes / len(descriptions) if len(descriptions) > 0 else 0

    # Check value format consistency
    values = [item.get("unit_value") for item in items if item.get("unit_value") is not None]
    value_consistency = 1.0 if values else 0.5

    return (code_consistency * 50 + value_consistency * 50)


def _analyze_values(items: List[Dict], total_value: Optional[float]) -> tuple:
    """Analyze values and return score, patterns, warnings."""
    patterns = []
    warnings = []
    score = 80  # Base score

    if not items:
        return score, patterns, warnings

    # Extract values
    values = [item.get("unit_value", 0) for item in items if item.get("unit_value")]
    quantities = [item.get("quantity", 0) for item in items if item.get("quantity")]

    if values:
        min_val = min(values)
        max_val = max(values)
        avg_val = sum(values) / len(values)

        # Check for extreme values
        if max_val > avg_val * 10:
            warnings.append(f"Valor máximo (R$ {max_val:,.2f}) muito acima da média")
            score -= 15

        # Check for zero values
        zero_values = sum(1 for v in values if v == 0)
        if zero_values > 0:
            warnings.append(f"{zero_values} item(ns) com valor zero")
            score -= 10

        patterns.append(f"Faixa de preços: R$ {min_val:,.2f} - R$ {max_val:,.2f}")

    # Check quantities
    if quantities:
        total_qty = sum(quantities)
        if total_qty > 100:
            patterns.append(f"Grande volume: {total_qty} unidades")

    # Validate total
    if total_value and values:
        calculated_total = sum(
            (item.get("unit_value", 0) * item.get("quantity", 1))
            for item in items
        )
        if abs(calculated_total - total_value) > total_value * 0.05:
            warnings.append("Total calculado difere do informado")
            score -= 10

    return max(0, min(100, score)), patterns, warnings


def _identify_item_patterns(items: List[Dict]) -> List[str]:
    """Identify patterns in items."""
    patterns = []

    if not items:
        return patterns

    # Count categories
    categories = {}
    for item in items:
        desc = item.get("description", "").lower()
        if "notebook" in desc or "laptop" in desc:
            categories["notebooks"] = categories.get("notebooks", 0) + 1
        elif "monitor" in desc:
            categories["monitores"] = categories.get("monitores", 0) + 1
        elif "teclado" in desc or "keyboard" in desc:
            categories["periféricos"] = categories.get("periféricos", 0) + 1
        elif "mouse" in desc:
            categories["periféricos"] = categories.get("periféricos", 0) + 1

    for category, count in categories.items():
        if count > 1:
            patterns.append(f"Detectados {count} {category}")

    return patterns


def _generate_commentary(
    source_type: str,
    items_count: int,
    total_value: Optional[float],
    overall_confidence: float,
    risk_level: str,
    patterns: List[str],
    warnings: List[str],
) -> str:
    """Generate human-readable AI commentary."""
    source_label = SOURCE_LABELS.get(source_type, source_type.upper())

    # Base commentary
    if overall_confidence >= 80:
        base = f"Importação via {source_label} com {items_count} itens apresenta dados consistentes. "
    elif overall_confidence >= 60:
        base = f"Importação via {source_label} com {items_count} itens requer atenção em alguns pontos. "
    else:
        base = f"Importação via {source_label} com {items_count} itens apresenta inconsistências que precisam ser revisadas. "

    # Add value info
    if total_value:
        base += f"Valor total: R$ {total_value:,.2f}. "

    # Add pattern info
    if patterns:
        base += patterns[0] + ". "

    # Add warning summary
    if warnings:
        if len(warnings) == 1:
            base += f"Atenção: {warnings[0].lower()}."
        else:
            base += f"Atenção: {len(warnings)} alertas identificados."

    return base


def _generate_insights(
    source_type: str,
    patterns: List[str],
    overall_confidence: float,
) -> Dict[str, Any]:
    """Generate insights for memory/learning."""
    return {
        "category": f"import_{source_type}",
        "insights": patterns[:3],  # Top 3 patterns
        "confidence_range": "high" if overall_confidence >= 75 else "medium" if overall_confidence >= 50 else "low",
    }


def _get_fallback_result(error: str, start_time: float) -> Dict[str, Any]:
    """Generate fallback result when analysis fails."""
    return {
        "success": True,  # Still return success to not block UI
        "confidence": {
            "overall": 70,
            "factors": [
                {
                    "id": "fallback",
                    "label": "Análise padrão",
                    "score": 70,
                    "weight": 1.0,
                }
            ],
            "risk_level": "medium",
        },
        "observations": {
            "patterns": [],
            "suggestions": [
                "Verifique os dados antes de confirmar",
                "Considere revisar os itens individualmente",
            ],
            "warnings": [
                "Análise de IA não disponível - usando valores padrão",
            ],
        },
        "ai_commentary": (
            "Não foi possível realizar a análise completa dos dados. "
            "Por favor, revise manualmente os itens antes de confirmar a importação."
        ),
        "learn_from": {
            "category": "import_fallback",
            "insights": [],
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "processing_time_ms": int((time.time() - start_time) * 1000) if start_time else 0,
        "_fallback_reason": error[:100] if error else "unknown",
    }
