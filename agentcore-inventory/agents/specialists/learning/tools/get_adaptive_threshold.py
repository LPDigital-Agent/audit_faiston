# =============================================================================
# Get Adaptive Threshold Tool
# =============================================================================
# Calculates adaptive confidence threshold based on historical success.
#
# TRUE AGENTIC LEARNING: Implements reinforcement learning principle:
# - Track success/failure patterns per file type
# - Adjust threshold based on historical outcomes
# - Learn from user corrections to become more cautious when needed
# - Lower threshold for proven patterns (trust AI more)
#
# Philosophy: Continuous improvement through outcome-based adaptation
# =============================================================================

import os
import hashlib
import re
import logging
from typing import Dict, Any, List, Optional


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
# Helper Functions
# =============================================================================

def _extract_filename_pattern(filename: str) -> str:
    """Extract normalized pattern from filename."""
    pattern = re.sub(r'\d{4}[-_]\d{2}[-_]\d{2}', 'DATE', filename)
    pattern = re.sub(r'\d{2}[-_]\d{2}[-_]\d{4}', 'DATE', pattern)
    pattern = re.sub(r'_\d+\.', '_N.', pattern)
    pattern = re.sub(r'[a-f0-9]{8,}', 'ID', pattern, flags=re.IGNORECASE)
    return pattern.lower()


def _compute_file_signature(file_analysis: Dict[str, Any]) -> str:
    """Compute a signature based on file structure."""
    sig_parts = []
    for sheet in file_analysis.get("sheets", []):
        sheet_sig = f"{sheet.get('purpose', sheet.get('detected_purpose', 'unknown'))}"
        columns = sheet.get("columns", [])
        col_names = sorted([c.get("name", "").lower() for c in columns[:20]])
        sheet_sig += ":" + ",".join(col_names[:10])
        sig_parts.append(sheet_sig)
    sig_str = "|".join(sig_parts)
    return hashlib.md5(sig_str.encode()).hexdigest()[:16]


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


async def _query_matching_episodes(
    filename_pattern: str,
    file_signature: str,
) -> List[Dict[str, Any]]:
    """Query episodes matching filename pattern or file signature."""
    memory_client = _get_memory_client()
    if not memory_client:
        return []

    try:
        # Query GLOBAL memory
        results = await memory_client.query(
            query=f"imports with pattern {filename_pattern} or signature {file_signature}",
            namespace=MEMORY_NAMESPACE,
            top_k=50,
        )

        matching = []
        similar = []

        for result in results:
            if hasattr(result, 'data'):
                data = result.data
                # Exact signature match
                if data.get("file_signature") == file_signature:
                    matching.append(data)
                # Similar filename pattern
                elif data.get("filename_pattern") == filename_pattern:
                    similar.append(data)

        # Combine: exact matches first, then similar
        return matching + similar[:5]

    except Exception as e:
        logger.error(f"[get_adaptive_threshold] Query failed: {e}")
        return []


# =============================================================================
# Tool Definition
# =============================================================================

@trace_memory_operation("get_adaptive_threshold")
async def get_adaptive_threshold_tool(
    user_id: str,
    filename: str,
    file_analysis: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate adaptive confidence threshold based on historical success.

    TRUE AGENTIC LEARNING through reinforcement:
    - Track success/failure patterns per file type
    - Adjust threshold based on historical outcomes
    - Learn from user corrections to become more cautious when needed
    - Lower threshold for proven patterns (trust AI more)

    Threshold Logic:
    - Base: 0.75 (75% confidence required)
    - User corrected AI frequently: 0.85 (be cautious)
    - Proven pattern (90%+ success, 10+ episodes): 0.65 (trust AI)
    - Good track record (80%+): 0.70
    - Mixed results: 0.75 (standard)
    - Poor history (<50%): 0.85 (require confirmation)

    Args:
        user_id: User performing the import (for audit trail)
        filename: Current filename
        file_analysis: Current file analysis
        session_id: Optional session ID for audit trail

    Returns:
        Dict with threshold, reasoning, and historical metrics
    """
    audit.working(
        message=f"Calculando threshold adaptativo para: {filename}",
        session_id=session_id,
    )

    try:
        base_threshold = 0.75

        # Compute signatures for matching
        filename_pattern = _extract_filename_pattern(filename)
        file_signature = _compute_file_signature(file_analysis)

        # Query GLOBAL memory for matching episodes
        all_relevant = await _query_matching_episodes(
            filename_pattern,
            file_signature,
        )

        # No history - be cautious with new patterns
        if not all_relevant:
            return {
                "threshold": 0.80,
                "reasoning": "Padrão novo - sendo cauteloso",
                "episode_count": 0,
                "success_rate": 0.0,
                "recent_corrections": 0,
                "adaptive_threshold": 0.80,
            }

        # Calculate success rate
        successful = sum(1 for ep in all_relevant if ep.get("success", False))
        success_rate = successful / len(all_relevant) if all_relevant else 0

        # Check for RECENT user corrections (last 5 imports)
        # Key for reinforcement learning: if user corrected AI recently,
        # system should be MORE cautious
        recent_corrections = 0
        for ep in all_relevant[:5]:
            corrections = ep.get("user_corrections", {})
            if corrections and len(corrections) > 0:
                recent_corrections += 1

        # Adaptive threshold logic (reinforcement learning principle)
        threshold = base_threshold
        reasoning = ""

        # Case 1: User corrected AI frequently → MORE cautious
        if recent_corrections >= 2:
            threshold = 0.85
            reasoning = (
                f"Usuário corrigiu IA em {recent_corrections}/5 imports "
                f"recentes - sendo mais cauteloso"
            )

        # Case 2: Proven pattern with 90%+ success and 10+ episodes → TRUST AI
        elif success_rate >= 0.90 and len(all_relevant) >= 10:
            threshold = 0.65
            reasoning = (
                f"Padrão comprovado: {len(all_relevant)} imports com "
                f"{success_rate:.0%} sucesso - confiando mais na IA"
            )

        # Case 3: Good track record (80%+) → slightly lower threshold
        elif success_rate >= 0.80 and len(all_relevant) >= 5:
            threshold = 0.70
            reasoning = (
                f"Bom histórico: {success_rate:.0%} sucesso em "
                f"{len(all_relevant)} imports"
            )

        # Case 4: Mixed results (50-80%) → standard threshold
        elif success_rate >= 0.50:
            threshold = base_threshold
            reasoning = (
                f"Histórico misto: {success_rate:.0%} sucesso - "
                f"usando threshold padrão"
            )

        # Case 5: Poor history (<50%) → MORE cautious
        else:
            threshold = 0.85
            reasoning = (
                f"Histórico problemático: apenas {success_rate:.0%} sucesso - "
                f"requerendo confirmação"
            )

        audit.completed(
            message=f"Threshold: {threshold:.0%} - {reasoning}",
            session_id=session_id,
            details={
                "threshold": threshold,
                "episode_count": len(all_relevant),
                "success_rate": success_rate,
            },
        )

        return {
            "threshold": threshold,
            "reasoning": reasoning,
            "episode_count": len(all_relevant),
            "success_rate": success_rate,
            "recent_corrections": recent_corrections,
            "adaptive_threshold": threshold,  # Legacy compatibility
        }

    except Exception as e:
        logger.error(f"[get_adaptive_threshold] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao calcular threshold",
            session_id=session_id,
            error=str(e),
        )
        # Return safe default on error
        return {
            "threshold": 0.80,
            "reasoning": f"Erro ao calcular: {str(e)[:50]} - usando threshold seguro",
            "episode_count": 0,
            "success_rate": 0.0,
            "recent_corrections": 0,
            "adaptive_threshold": 0.80,
        }
