# =============================================================================
# Generate Reflection Tool
# =============================================================================
# Generates cross-episode insights for continuous improvement.
#
# TRUE AGENTIC LEARNING: After multiple imports, the agent reflects
# on patterns and generates insights that improve future performance.
#
# Philosophy: "What did I learn from this experience?"
# =============================================================================

import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_memory_operation

logger = logging.getLogger(__name__)

# Agent configuration
AGENT_ID = "learning"
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "nexo_sga_learning_memory-u3ypElEdl1")
MEMORY_NAMESPACE = "/strategy/import/company"  # GLOBAL!

# Audit emitter
audit = AgentAuditEmitter(agent_id=AGENT_ID)


# =============================================================================
# Types
# =============================================================================

@dataclass
class ImportReflection:
    """Cross-episode insight generated from multiple imports."""
    reflection_id: str
    pattern: str          # Natural language pattern description
    confidence: float     # 0.0 to 1.0
    episode_count: int    # Number of episodes supporting this
    applicable_to: str    # File type, supplier, or general
    recommendation: str   # Action to take when pattern matches
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_id(prefix: str = "REF") -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# =============================================================================
# Memory Client
# =============================================================================

_memory_client = None


def _get_memory_client():
    """Lazy-load AgentCore Memory client."""
    global _memory_client
    if _memory_client is None:
        try:
            from bedrock_agentcore.memory import MemoryClient
            _memory_client = MemoryClient(memory_id=MEMORY_ID)
        except Exception:
            pass
    return _memory_client


async def _query_episodes_for_pattern(filename_pattern: str) -> List[Dict[str, Any]]:
    """Query episodes matching a filename pattern."""
    memory_client = _get_memory_client()
    if not memory_client:
        return []

    try:
        results = await memory_client.query(
            query=f"imports matching pattern {filename_pattern}",
            namespace=MEMORY_NAMESPACE,
            top_k=50,  # Get more for reflection analysis
        )

        episodes = []
        for result in results:
            if hasattr(result, 'data'):
                data = result.data
                if data.get("filename_pattern") == filename_pattern:
                    episodes.append(data)

        return episodes
    except Exception as e:
        logger.error(f"[generate_reflection] Query failed: {e}")
        return []


# =============================================================================
# Tool Definition
# =============================================================================

@trace_memory_operation("generate_reflection")
async def generate_reflection_tool(
    user_id: str,
    filename_pattern: str,
    recent_outcomes: Optional[List[Dict[str, Any]]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate cross-episode reflection for continuous improvement.

    TRUE AGENTIC LEARNING: After multiple imports, reflect on patterns
    and generate insights that improve future performance.

    Philosophy: LEARN phase - "What did I learn from this experience?"

    Args:
        user_id: User for whom to generate reflection
        filename_pattern: File pattern to focus reflection on
        recent_outcomes: Recent import outcomes (optional)
        session_id: Optional session ID for audit trail

    Returns:
        Reflection with patterns, insights, and recommendations
    """
    audit.learning(
        message=f"Gerando reflexão para padrão: {filename_pattern}",
        session_id=session_id,
    )

    try:
        # Get episodes for this pattern from GLOBAL memory
        relevant_episodes = await _query_episodes_for_pattern(filename_pattern)

        # Add recent outcomes if provided
        if recent_outcomes:
            for outcome in recent_outcomes:
                if outcome.get("filename_pattern") == filename_pattern:
                    relevant_episodes.append(outcome)

        # Need minimum 3 episodes for meaningful reflection
        if len(relevant_episodes) < 3:
            return {
                "has_reflection": False,
                "reason": "Não há episódios suficientes para reflexão (mínimo: 3)",
                "episode_count": len(relevant_episodes),
            }

        # Analyze patterns
        successful = [ep for ep in relevant_episodes if ep.get("success", False)]
        [ep for ep in relevant_episodes if not ep.get("success", False)]
        success_rate = len(successful) / len(relevant_episodes) if relevant_episodes else 0

        # Find common mappings in successful episodes
        common_mappings = {}
        for ep in successful:
            mappings = ep.get("column_mappings", {})
            for col, field in mappings.items():
                if col not in common_mappings:
                    common_mappings[col] = {}
                if field not in common_mappings[col]:
                    common_mappings[col][field] = 0
                common_mappings[col][field] += 1

        # Find best mappings (most frequent in successful imports)
        best_mappings = {}
        for col, votes in common_mappings.items():
            if votes:
                best_field = max(votes.items(), key=lambda x: x[1])
                if best_field[1] >= 2:  # At least 2 occurrences
                    best_mappings[col] = best_field[0]

        # Analyze user corrections (areas where AI needs improvement)
        all_corrections = {}
        for ep in relevant_episodes:
            corrections = ep.get("user_corrections", {})
            for col, correction in corrections.items():
                if col not in all_corrections:
                    all_corrections[col] = []
                all_corrections[col].append(correction)

        # Frequent corrections = problem areas
        problem_areas = []
        for col, corrections in all_corrections.items():
            if len(corrections) >= 2:
                # Find most common correction
                from collections import Counter
                most_common = Counter(
                    c for c in corrections if isinstance(c, str)
                ).most_common(1)
                problem_areas.append({
                    "column": col,
                    "correction_count": len(corrections),
                    "common_correction": most_common[0][0] if most_common else None,
                })

        # Generate natural language reflection
        reflection_text = _generate_reflection_text(
            filename_pattern=filename_pattern,
            episode_count=len(relevant_episodes),
            success_rate=success_rate,
            best_mappings=best_mappings,
            problem_areas=problem_areas,
        )

        # Build reflection
        reflection = ImportReflection(
            reflection_id=_generate_id("REF"),
            pattern=filename_pattern,
            confidence=success_rate,
            episode_count=len(relevant_episodes),
            applicable_to=filename_pattern,
            recommendation=reflection_text[:500] if reflection_text else "",
        )

        # Store reflection in memory
        memory_client = _get_memory_client()
        if memory_client:
            try:
                await memory_client.create_event(
                    event_type="reflection_generated",
                    data={
                        "reflection_id": reflection.reflection_id,
                        "pattern": reflection.pattern,
                        "confidence": reflection.confidence,
                        "recommendation": reflection.recommendation,
                    },
                    namespace=MEMORY_NAMESPACE,
                    role="TOOL",
                )
            except Exception as e:
                logger.warning(f"[generate_reflection] Store failed: {e}")

        audit.completed(
            message=f"Reflexão gerada: {reflection.reflection_id}",
            session_id=session_id,
            details={
                "episode_count": len(relevant_episodes),
                "success_rate": f"{success_rate:.0%}",
            },
        )

        return {
            "has_reflection": True,
            "reflection_id": reflection.reflection_id,
            "pattern": filename_pattern,
            "episode_count": len(relevant_episodes),
            "success_rate": success_rate,
            "best_mappings": best_mappings,
            "problem_areas": problem_areas,
            "reflection_text": reflection_text,
            "recommendation": reflection.recommendation,
        }

    except Exception as e:
        logger.error(f"[generate_reflection] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao gerar reflexão",
            session_id=session_id,
            error=str(e),
        )
        return {
            "has_reflection": False,
            "error": str(e),
        }


def _generate_reflection_text(
    filename_pattern: str,
    episode_count: int,
    success_rate: float,
    best_mappings: Dict[str, str],
    problem_areas: List[Dict[str, Any]],
) -> str:
    """Generate natural language reflection text."""
    parts = []

    # Success rate summary
    if success_rate >= 0.9:
        parts.append(
            f"Padrão '{filename_pattern}' tem excelente histórico: "
            f"{success_rate:.0%} de sucesso em {episode_count} imports."
        )
    elif success_rate >= 0.7:
        parts.append(
            f"Padrão '{filename_pattern}' tem bom histórico: "
            f"{success_rate:.0%} de sucesso em {episode_count} imports."
        )
    else:
        parts.append(
            f"Padrão '{filename_pattern}' precisa de atenção: "
            f"apenas {success_rate:.0%} de sucesso em {episode_count} imports."
        )

    # Best mappings summary
    if best_mappings:
        mapping_count = len(best_mappings)
        parts.append(
            f"Aprendi {mapping_count} mapeamentos consistentes que funcionam bem."
        )

    # Problem areas
    if problem_areas:
        problem_cols = [p["column"] for p in problem_areas[:3]]
        parts.append(
            f"Áreas que precisam de melhoria: colunas {', '.join(problem_cols)} "
            f"frequentemente precisam de correção."
        )

    # Recommendation
    if success_rate >= 0.9 and not problem_areas:
        parts.append(
            "Recomendação: Confiar mais na IA para este padrão, "
            "threshold pode ser reduzido."
        )
    elif problem_areas:
        parts.append(
            "Recomendação: Ser mais cauteloso com as colunas problemáticas, "
            "sempre pedir confirmação."
        )
    else:
        parts.append(
            "Recomendação: Continuar coletando dados para melhorar a confiança."
        )

    return " ".join(parts)
