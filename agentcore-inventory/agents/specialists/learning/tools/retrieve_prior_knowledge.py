# =============================================================================
# Retrieve Prior Knowledge Tool
# =============================================================================
# Searches AgentCore Memory for similar past imports and suggests mappings.
#
# Called BEFORE analysis to find:
# - Similar past imports
# - Pre-populate suggested mappings
# - Calculate confidence boost from history
#
# CRITICAL: Uses GLOBAL namespace - what João learned, Maria can use!
# =============================================================================

import os
import hashlib
import re
import logging
from typing import Dict, Any, List, Optional, Tuple


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


def _compute_similarity(
    episode: Dict[str, Any],
    filename_pattern: str,
    file_signature: str,
) -> float:
    """Compute similarity between episode and current file."""
    similarity = 0.0

    # Exact signature match = high similarity
    ep_sig = episode.get("file_signature", "")
    if ep_sig == file_signature:
        similarity += 0.6

    # Filename pattern match
    ep_pattern = episode.get("filename_pattern", "")
    if ep_pattern == filename_pattern:
        similarity += 0.3
    elif ep_pattern and filename_pattern and ep_pattern in filename_pattern:
        similarity += 0.15

    # Success bonus
    if episode.get("success", False):
        similarity += 0.1

    return min(similarity, 1.0)


def _aggregate_mappings(
    episodes: List[Tuple[Dict[str, Any], float]],
) -> Dict[str, Dict[str, Any]]:
    """Aggregate mappings from multiple episodes with voting."""
    mapping_votes = {}  # {column: {field: count}}

    for episode, similarity in episodes:
        mappings = episode.get("column_mappings", {})
        for column, field in mappings.items():
            if column not in mapping_votes:
                mapping_votes[column] = {}
            if field not in mapping_votes[column]:
                mapping_votes[column][field] = 0
            mapping_votes[column][field] += similarity

    # Select winning mapping for each column
    suggested = {}
    for column, votes in mapping_votes.items():
        if votes:
            winner = max(votes.items(), key=lambda x: x[1])
            total_votes = sum(votes.values())
            suggested[column] = {
                "field": winner[0],
                "confidence": winner[1] / total_votes if total_votes > 0 else 0,
                "vote_count": len(episodes),
            }

    return suggested


def _calculate_confidence_boost(
    episodes: List[Tuple[Dict[str, Any], float]],
) -> float:
    """Calculate confidence boost from historical success."""
    if not episodes:
        return 0.0

    total_weight = 0
    success_weight = 0

    for episode, similarity in episodes:
        total_weight += similarity
        if episode.get("success", False):
            success_weight += similarity * episode.get("match_rate", 0)

    if total_weight == 0:
        return 0.0

    # Boost ranges from 0.0 to 0.15
    return min((success_weight / total_weight) * 0.15, 0.15)


def _validate_column_exists(target_table: str, field_name: str) -> bool:
    """Check if a field name exists in the current schema."""
    try:
        from tools.schema_provider import SchemaProvider
        from tools.postgres_client import PostgresClient
        postgres_client = PostgresClient()
        provider = SchemaProvider(postgres_client)
        return provider.validate_column_exists(target_table, field_name)
    except Exception as e:
        logger.warning(f"[retrieve_prior_knowledge] Schema validation error: {e}")
        return True  # Permissive on error


def _filter_stale_mappings(
    mappings: Dict[str, Dict[str, Any]],
    target_table: str,
) -> Dict[str, Dict[str, Any]]:
    """Filter out mappings that reference non-existent columns."""
    filtered = {}
    for column, mapping_info in mappings.items():
        target_field = mapping_info.get("field", "")
        if _validate_column_exists(target_table, target_field):
            filtered[column] = mapping_info
        else:
            logger.info(
                f"[retrieve_prior_knowledge] Filtered stale mapping: "
                f"{column} -> {target_field}"
            )
    return filtered


def _get_schema_version(target_table: str) -> str:
    """Get current schema version hash for a table."""
    try:
        from tools.schema_provider import SchemaProvider
        from tools.postgres_client import PostgresClient
        postgres_client = PostgresClient()
        provider = SchemaProvider(postgres_client)
        return provider.get_schema_version(target_table)
    except Exception:
        return ""


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
            logger.info("[retrieve_prior_knowledge] Memory client initialized")
        except ImportError:
            logger.warning("[retrieve_prior_knowledge] Memory SDK not available")
        except Exception as e:
            logger.error(f"[retrieve_prior_knowledge] Memory init failed: {e}")
    return _memory_client


async def _query_memory_episodes(
    filename_pattern: str,
    file_signature: str,
) -> List[Tuple[Dict[str, Any], float]]:
    """Query AgentCore Memory for similar episodes."""
    memory_client = _get_memory_client()
    if not memory_client:
        return []

    try:
        # Query GLOBAL namespace (NOT per-user!)
        results = await memory_client.query(
            query=f"import file similar to {filename_pattern} with structure {file_signature[:16]}",
            namespace=MEMORY_NAMESPACE,
            top_k=20,
        )

        episodes = []
        for result in results:
            if hasattr(result, 'data'):
                data = result.data
                similarity = result.score if hasattr(result, 'score') else 0.7
                episodes.append((data, similarity))

        return episodes
    except Exception as e:
        logger.error(f"[retrieve_prior_knowledge] Query failed: {e}")
        return []


async def _get_relevant_reflections(filename_pattern: str) -> List[Dict[str, Any]]:
    """Get reflections relevant to current file pattern."""
    memory_client = _get_memory_client()
    if not memory_client:
        return []

    try:
        memory_reflections = await memory_client.get_reflections(
            namespace=MEMORY_NAMESPACE,
            query=filename_pattern,
        )
        reflections = []
        for ref in memory_reflections:
            reflections.append({
                "pattern": ref.text if hasattr(ref, 'text') else str(ref),
                "confidence": ref.confidence if hasattr(ref, 'confidence') else 0.7,
                "recommendation": ref.recommendation if hasattr(ref, 'recommendation') else "",
            })
        return reflections[:5]
    except Exception:
        return []


# =============================================================================
# Tool Definition
# =============================================================================

@trace_memory_operation("retrieve_prior_knowledge")
async def retrieve_prior_knowledge_tool(
    user_id: str,
    filename: str,
    file_analysis: Dict[str, Any],
    target_table: str = "pending_entry_items",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve prior knowledge relevant to current import.

    Searches GLOBAL memory for similar past imports and suggests
    mappings based on learned patterns. This enables company-wide
    learning: what João learned, Maria can use.

    SCHEMA-AWARE: Validates mappings against current schema to
    filter out stale suggestions for columns that no longer exist.

    Args:
        user_id: User performing the import (for audit trail)
        filename: Current filename
        file_analysis: Current file analysis
        target_table: Target PostgreSQL table for schema validation
        session_id: Optional session ID for audit trail

    Returns:
        Prior knowledge with suggested mappings and confidence
    """
    # Emit audit event
    audit.learning(
        message=f"Buscando conhecimento prévio para: {filename}",
        session_id=session_id,
    )

    try:
        # Compute signatures for matching
        filename_pattern = _extract_filename_pattern(filename)
        file_signature = _compute_file_signature(file_analysis)

        # Query AgentCore Memory (GLOBAL namespace)
        similar_episodes = await _query_memory_episodes(
            filename_pattern,
            file_signature,
        )

        # Calculate similarity for each episode
        scored_episodes = []
        for episode, base_score in similar_episodes:
            similarity = _compute_similarity(episode, filename_pattern, file_signature)
            # Combine base score from vector search with structural similarity
            combined_score = (base_score + similarity) / 2
            if combined_score > 0.5:  # Relevance threshold
                scored_episodes.append((episode, combined_score))

        # Sort by score and take top 5
        scored_episodes.sort(key=lambda x: x[1], reverse=True)
        top_episodes = scored_episodes[:5]

        if not top_episodes:
            audit.completed(
                message="Nenhum conhecimento prévio encontrado",
                session_id=session_id,
            )
            return {
                "has_prior_knowledge": False,
                "similar_episodes": [],
                "suggested_mappings": {},
                "confidence_boost": 0.0,
            }

        # Aggregate mappings from similar episodes
        suggested_mappings = _aggregate_mappings(top_episodes)

        # SCHEMA-AWARE: Filter stale mappings
        original_count = len(suggested_mappings)
        suggested_mappings = _filter_stale_mappings(suggested_mappings, target_table)
        filtered_count = original_count - len(suggested_mappings)

        # Calculate confidence boost
        confidence_boost = _calculate_confidence_boost(top_episodes)

        # Get relevant reflections
        reflections = await _get_relevant_reflections(filename_pattern)

        # Get current schema version
        schema_version = _get_schema_version(target_table)

        # Emit completion event
        audit.completed(
            message=f"Encontrei {len(top_episodes)} episódios similares, "
                    f"{len(suggested_mappings)} mapeamentos sugeridos",
            session_id=session_id,
            details={
                "similar_episodes": len(top_episodes),
                "suggested_mappings": len(suggested_mappings),
                "filtered_stale": filtered_count,
            },
        )

        logger.info(
            f"[retrieve_prior_knowledge] Found {len(top_episodes)} episodes, "
            f"{len(suggested_mappings)} mappings, {filtered_count} filtered"
        )

        return {
            "has_prior_knowledge": True,
            "similar_episodes": [
                {
                    "episode_id": ep.get("episode_id"),
                    "filename_pattern": ep.get("filename_pattern"),
                    "similarity": sim,
                    "success": ep.get("success"),
                    "match_rate": ep.get("match_rate"),
                    "schema_version": ep.get("schema_version", ""),
                }
                for ep, sim in top_episodes
            ],
            "suggested_mappings": suggested_mappings,
            "confidence_boost": confidence_boost,
            "reflections": reflections,
            "schema_version": schema_version,
            "filtered_stale_mappings": filtered_count,
            "namespace": MEMORY_NAMESPACE,
        }

    except Exception as e:
        logger.error(f"[retrieve_prior_knowledge] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao buscar conhecimento prévio",
            session_id=session_id,
            error=str(e),
        )
        return {
            "has_prior_knowledge": False,
            "error": str(e),
            "similar_episodes": [],
            "suggested_mappings": {},
            "confidence_boost": 0.0,
        }
