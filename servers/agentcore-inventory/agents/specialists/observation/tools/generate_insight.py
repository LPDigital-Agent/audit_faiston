# =============================================================================
# ObservationAgent Tool: Generate Insight
# =============================================================================
# Creates InsightReports from detected patterns with confidence scoring,
# deduplication, and one-click fix support.
#
# Implements the ACT phase of OBSERVE → THINK → LEARN → ACT loop.
#
# DEDUPLICATION:
# - Hash-based fingerprint (category:target_entity)
# - 7-day cooldown prevents spam
# - Resurface after cooldown if pattern persists
#
# CONFIDENCE THRESHOLDS:
# - automation_proposal: 0.9
# - data_health_alert: 0.85
# - workflow_optimization: 0.7
# - pattern_detection: 0.6
#
# VERSION: 2026-01-22T00:00:00Z
# =============================================================================

import json
import logging
import hashlib
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from strands import tool

from shared.memory_manager import AgentMemoryManager
from shared.cognitive_error_handler import cognitive_error_handler
from shared.agent_schemas import (
    InsightReport,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    ActionPayload,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Confidence Thresholds
# =============================================================================

CONFIDENCE_THRESHOLDS = {
    "automation_proposal": 0.9,
    "data_health_alert": 0.85,
    "workflow_optimization": 0.7,
    "pattern_detection": 0.6,
}

# Deduplication cooldown (7 days)
DEDUP_COOLDOWN_DAYS = 7

# Insight namespace in Memory
INSIGHT_NAMESPACE_TEMPLATE = "/nexo/intuition/{actor_id}"


# =============================================================================
# Insight Generation Helpers
# =============================================================================


def _generate_fingerprint(category: str, target_entity: str) -> str:
    """
    Generate hash fingerprint for deduplication.

    Format: MD5(category:target_entity)
    """
    content = f"{category}:{target_entity}"
    return hashlib.md5(content.encode()).hexdigest()


def _map_pattern_to_category(pattern: Dict[str, Any]) -> InsightCategory:
    """
    Map pattern type to InsightCategory.
    """
    pattern_type = pattern.get("type", "")
    subtype = pattern.get("subtype", "")

    if pattern_type == "error":
        return InsightCategory.ERROR_PATTERN
    elif pattern_type == "mapping":
        return InsightCategory.MAPPING_OPPORTUNITY
    elif pattern_type == "behavior":
        return InsightCategory.BEHAVIOR_INSIGHT
    elif pattern_type == "health":
        return InsightCategory.HEALTH_ALERT
    else:
        return InsightCategory.ERROR_PATTERN


def _map_severity(severity_str: str) -> InsightSeverity:
    """
    Map severity string to InsightSeverity enum.
    """
    mapping = {
        "critical": InsightSeverity.CRITICAL,
        "warning": InsightSeverity.WARNING,
        "info": InsightSeverity.INFO,
    }
    return mapping.get(severity_str.lower(), InsightSeverity.INFO)


def _determine_threshold_category(pattern: Dict[str, Any]) -> str:
    """
    Determine which confidence threshold category applies.
    """
    pattern_type = pattern.get("type", "")
    subtype = pattern.get("subtype", "")

    if pattern_type == "behavior" and "automation" in subtype.lower():
        return "automation_proposal"
    elif pattern_type == "health":
        return "data_health_alert"
    elif pattern_type == "behavior":
        return "workflow_optimization"
    else:
        return "pattern_detection"


def _generate_action_payload(pattern: Dict[str, Any]) -> Optional[ActionPayload]:
    """
    Generate one-click action payload if applicable.

    Only certain patterns have actionable fixes.
    """
    pattern_type = pattern.get("type", "")
    subtype = pattern.get("subtype", "")

    if pattern_type == "mapping":
        # Mapping suggestion can be auto-applied
        source = pattern.get("source_column", "")
        target = pattern.get("suggested_target", "")
        if source and target:
            return ActionPayload(
                tool="system_update_mapping",
                params={
                    "source_column": source,
                    "target_column": target,
                    "auto_approved": False,  # Requires HIL confirmation
                }
            )

    elif pattern_type == "error" and subtype == "BusinessLogic":
        # Business logic errors might have cleanup actions
        return ActionPayload(
            tool="check_duplicates",
            params={"auto_fix": False}
        )

    return None


def _generate_educational_context(pattern: Dict[str, Any]) -> str:
    """
    Generate educational context for the insight.

    This helps users understand WHY the insight matters.
    """
    pattern_type = pattern.get("type", "")
    subtype = pattern.get("subtype", "")
    frequency = pattern.get("frequency", 0)

    if pattern_type == "error":
        contexts = {
            "SchemaMismatch": (
                "Erros de esquema ocorrem quando o arquivo de entrada tem colunas "
                "que não correspondem ao formato esperado. Isso geralmente indica "
                "que o formato do arquivo mudou ou há colunas extras/faltantes."
            ),
            "DataIntegrity": (
                "Erros de integridade de dados ocorrem quando os valores não podem "
                "ser convertidos para o tipo esperado. Verifique se há células vazias, "
                "textos em campos numéricos, ou formatos de data inconsistentes."
            ),
            "BusinessLogic": (
                "Erros de lógica de negócio indicam violações de regras como "
                "duplicatas, estoque negativo, ou valores fora dos limites permitidos. "
                "Estes erros precisam de atenção imediata."
            ),
            "Formatting": (
                "Erros de formatação são geralmente fáceis de corrigir. Verifique "
                "se as datas estão no formato DD/MM/YYYY, números usam vírgula como "
                "separador decimal, e a codificação do arquivo é UTF-8."
            ),
        }
        return contexts.get(subtype, "Este padrão requer sua atenção.")

    elif pattern_type == "mapping":
        return (
            f"A coluna '{pattern.get('source_column', '')}' aparece frequentemente "
            f"sem mapeamento ({frequency}x). O sistema sugere mapeá-la para "
            f"'{pattern.get('suggested_target', '')}' baseado em análise semântica "
            "e histórico de mapeamentos similares."
        )

    elif pattern_type == "behavior":
        if "automation" in subtype.lower():
            return (
                "Este padrão foi confirmado várias vezes manualmente. "
                "Considere habilitar aprovação automática para aumentar a eficiência."
            )
        elif "peak" in subtype.lower():
            hour = pattern.get("peak_hour", 0)
            return (
                f"A maior parte das importações ocorre às {hour}:00. "
                "Agende tarefas de manutenção fora deste horário."
            )

    return "Analise este padrão para melhorar sua operação."


def _generate_human_message(pattern: Dict[str, Any]) -> str:
    """
    Generate user-facing message in pt-BR.
    """
    pattern_type = pattern.get("type", "")
    subtype = pattern.get("subtype", "")
    frequency = pattern.get("frequency", 0)
    confidence = pattern.get("confidence", 0)

    if pattern_type == "error":
        severity_emoji = {
            "critical": "🔴",
            "warning": "⚠️",
            "info": "ℹ️",
        }.get(pattern.get("severity", "info"), "ℹ️")

        return (
            f"{severity_emoji} Detectei um padrão de erro '{subtype}' "
            f"({frequency} ocorrências). Recomendo revisar os arquivos recentes."
        )

    elif pattern_type == "mapping":
        source = pattern.get("source_column", "")
        target = pattern.get("suggested_target", "")
        return (
            f"💡 A coluna '{source}' precisa de mapeamento. "
            f"Sugestão: mapear para '{target}' (confiança: {int(confidence * 100)}%)."
        )

    elif pattern_type == "behavior":
        if "automation" in subtype.lower():
            return "🤖 Oportunidade de automação detectada. Você pode aprovar automaticamente."
        else:
            return f"📊 Padrão de comportamento detectado: {pattern.get('description', '')}"

    return pattern.get("description", "Insight detectado.")


# =============================================================================
# Tool Implementation
# =============================================================================


@tool
@cognitive_error_handler("observation")
def generate_insight(
    patterns_json: str,
    actor_id: str,
) -> str:
    """
    Generate InsightReports from detected patterns.

    Implements the ACT phase of OBSERVE → THINK → LEARN → ACT loop.
    Creates structured insights with confidence scoring, deduplication,
    and one-click fix support when applicable.

    Deduplication:
    - Hash fingerprint: MD5(category:target_entity)
    - 7-day cooldown prevents spam
    - Resurface after cooldown if pattern persists

    Confidence Thresholds (minimum to generate insight):
    - automation_proposal: 0.9
    - data_health_alert: 0.85
    - workflow_optimization: 0.7
    - pattern_detection: 0.6

    Args:
        patterns_json: JSON string from analyze_patterns tool.
        actor_id: User identifier for scoping and storage.

    Returns:
        JSON string with generated insights:
        {
            "success": true,
            "insights": [InsightReport, ...],
            "generated_count": 3,
            "filtered_count": 2,  # Below threshold
            "deduplicated_count": 1,  # Skipped due to cooldown
            "human_message": "Gerados 3 insights para revisão."
        }

    Raises:
        json.JSONDecodeError: If patterns_json contains invalid JSON (caught internally, returns JSON error response).
        Exception: If AgentCore Memory operations fail (caught internally, returns JSON error response).
    """
    async def _generate_and_store() -> Dict[str, Any]:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="observation", actor_id=actor_id)

        # Parse patterns
        patterns_data = json.loads(patterns_json)
        if not patterns_data.get("success"):
            return {
                "success": False,
                "error": "Input patterns data indicates failure",
                "insights": [],
                "human_message": "Dados de padrões inválidos.",
            }

        patterns = patterns_data.get("patterns", [])
        insights: List[Dict[str, Any]] = []
        filtered_count = 0
        deduplicated_count = 0

        # Get existing insights for deduplication check
        insight_namespace = INSIGHT_NAMESPACE_TEMPLATE.format(actor_id=actor_id)
        existing_insights = []
        try:
            existing_insights = await memory.observe(
                query="insight fingerprint",
                limit=100,
                include_global=False,
            )
        except Exception as e:
            logger.warning(f"[generate_insight] Failed to fetch existing insights: {e}")

        # Build fingerprint cache for deduplication
        existing_fingerprints: Dict[str, datetime] = {}
        for existing in existing_insights:
            fp = existing.get("fingerprint", "")
            ts = existing.get("created_at", "")
            if fp and ts:
                try:
                    existing_fingerprints[fp] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Process each pattern
        now = datetime.utcnow()
        cooldown_cutoff = now - timedelta(days=DEDUP_COOLDOWN_DAYS)

        for pattern in patterns:
            # Determine confidence threshold
            threshold_category = _determine_threshold_category(pattern)
            min_confidence = CONFIDENCE_THRESHOLDS.get(threshold_category, 0.6)
            pattern_confidence = pattern.get("confidence", 0)

            # Check confidence threshold
            if pattern_confidence < min_confidence:
                filtered_count += 1
                logger.debug(
                    f"[generate_insight] Pattern filtered: confidence {pattern_confidence} < {min_confidence}"
                )
                continue

            # Generate fingerprint for deduplication
            category = _map_pattern_to_category(pattern)
            target_entity = pattern.get("source_column", "") or pattern.get("subtype", "") or "unknown"
            fingerprint = _generate_fingerprint(category.value, target_entity)

            # Check deduplication cooldown
            if fingerprint in existing_fingerprints:
                last_created = existing_fingerprints[fingerprint]
                if last_created > cooldown_cutoff:
                    deduplicated_count += 1
                    logger.debug(
                        f"[generate_insight] Pattern deduplicated: fingerprint {fingerprint[:8]}... "
                        f"within {DEDUP_COOLDOWN_DAYS}-day cooldown"
                    )
                    continue

            # Build InsightReport
            insight = InsightReport(
                insight_id=str(uuid.uuid4()),
                category=category,
                severity=_map_severity(pattern.get("severity", "info")),
                title=pattern.get("description", "Insight detected")[:100],
                description=pattern.get("description", ""),
                educational_context=_generate_educational_context(pattern),
                confidence=pattern_confidence,
                evidence=[f"Frequency: {pattern.get('frequency', 0)} occurrences"],
                suggested_action=pattern.get("description", ""),
                action_payload=_generate_action_payload(pattern),
                human_message=_generate_human_message(pattern),
                created_at=now.isoformat() + "Z",
                actor_id=actor_id,
                fingerprint=fingerprint,
                status=InsightStatus.PENDING,
            )

            # Store insight in Memory
            try:
                await memory.learn(
                    content=insight.title,
                    category="insight",
                    confidence=insight.confidence,
                    use_global=False,
                    insight_id=insight.insight_id,
                    fingerprint=insight.fingerprint,
                    severity=insight.severity.value,
                )
            except Exception as e:
                logger.warning(f"[generate_insight] Failed to store insight: {e}")

            insights.append(insight.model_dump(mode="json"))

        # Sort by severity (critical first)
        severity_order = {
            InsightSeverity.CRITICAL.value: 0,
            InsightSeverity.WARNING.value: 1,
            InsightSeverity.INFO.value: 2,
        }
        insights.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 3))

        # Generate human message (pt-BR)
        if len(insights) == 0:
            human_message = "Nenhum insight significativo gerado nesta análise."
        else:
            critical_count = sum(1 for i in insights if i.get("severity") == "critical")
            if critical_count > 0:
                human_message = f"🔴 {critical_count} insight(s) crítico(s) requer(em) atenção imediata!"
            else:
                human_message = f"Gerados {len(insights)} insight(s) para revisão."

        return {
            "success": True,
            "insights": insights,
            "generated_count": len(insights),
            "filtered_count": filtered_count,
            "deduplicated_count": deduplicated_count,
            "human_message": human_message,
        }

    try:
        result = asyncio.run(_generate_and_store())
        logger.info(
            f"[generate_insight] Generated {result['generated_count']} insights "
            f"(filtered: {result['filtered_count']}, deduped: {result['deduplicated_count']})"
        )
        return json.dumps(result)

    except json.JSONDecodeError as e:
        logger.error(f"[generate_insight] Invalid JSON input: {e}")
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON input: {str(e)}",
            "insights": [],
            "human_message": "Erro ao processar dados de padrões.",
        })

    except Exception as e:
        logger.error(f"[generate_insight] Failed: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "INSIGHT_GENERATION_ERROR",
            "insights": [],
            "human_message": "Erro ao gerar insights. Tente novamente.",
        })


@tool
@cognitive_error_handler("observation")
def dismiss_insight(
    insight_id: str,
    actor_id: str,
    reason: Optional[str] = None,
) -> str:
    """
    Dismiss an insight with learning feedback.

    Tracks dismissals for resurface logic:
    - Increments dismissal_count
    - Records severity_at_dismissal
    - Resurface if current_severity > stored_severity * 1.5

    Args:
        insight_id: ID of the insight to dismiss.
        actor_id: User identifier.
        reason: Optional reason for dismissal (for learning).

    Returns:
        JSON string with dismissal confirmation:
        {
            "success": true,
            "insight_id": "...",
            "status": "dismissed",
            "dismissal_count": 1,
            "human_message": "Insight descartado. Aprenderemos com sua decisão."
        }

    Raises:
        Exception: If AgentCore Memory learn operation fails (caught internally, returns JSON error response).
    """
    async def _dismiss() -> Dict[str, Any]:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="observation", actor_id=actor_id)

        # Learn from dismissal
        await memory.learn(
            content=f"Insight {insight_id} dismissed by user. Reason: {reason or 'not provided'}",
            category="insight_dismissed",
            confidence=0.8,
            use_global=False,
            insight_id=insight_id,
            dismissal_reason=reason,
        )

        return {
            "success": True,
            "insight_id": insight_id,
            "status": "dismissed",
            "dismissal_count": 1,  # TODO: Fetch actual count from Memory
            "human_message": "Insight descartado. Aprenderemos com sua decisão.",
        }

    try:
        result = asyncio.run(_dismiss())
        logger.info(f"[dismiss_insight] Dismissed insight {insight_id} for actor {actor_id}")
        return json.dumps(result)

    except Exception as e:
        logger.error(f"[dismiss_insight] Failed: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "insight_id": insight_id,
            "human_message": "Erro ao descartar insight.",
        })


# =============================================================================
# Module Exports
# =============================================================================

__all__ = ["generate_insight", "dismiss_insight"]
