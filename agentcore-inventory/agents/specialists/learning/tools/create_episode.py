# =============================================================================
# Create Episode Tool
# =============================================================================
# Stores an import episode in AgentCore Memory for future learning.
#
# Called after successful imports to capture:
# - File structure (sheets, columns)
# - Final mappings used
# - User corrections (if any)
# - Import result (success/failure, items processed)
#
# CRITICAL: Uses GLOBAL namespace for company-wide learning!
# =============================================================================

import os
import hashlib
import re
import logging
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, field, asdict


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
class ImportEpisode:
    """
    Represents a single import episode for memory storage.

    An episode captures all relevant information from one complete
    import interaction, including file structure, mappings learned,
    user corrections, and final success/failure status.

    SCHEMA-AWARE: Includes schema_version to track when mappings
    were learned. Stale mappings are filtered during retrieval.
    """
    episode_id: str
    filename_pattern: str  # Normalized pattern (dates → DATE, etc.)
    file_signature: str    # Hash of column structure for matching

    # File structure
    sheet_count: int
    total_rows: int
    sheets_info: List[Dict[str, Any]]

    # Learned mappings
    column_mappings: Dict[str, str]  # {file_column: target_field}
    user_corrections: Dict[str, Any]  # Corrections made by user

    # Outcome
    success: bool
    match_rate: float  # 0.0 to 1.0
    items_processed: int
    items_failed: int

    # Metadata
    user_id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    lessons: List[str] = field(default_factory=list)

    # Schema tracking
    schema_version: str = ""
    target_table: str = "pending_entry_items"


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_id(prefix: str = "EP") -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _extract_filename_pattern(filename: str) -> str:
    """Extract normalized pattern from filename."""
    # Remove date patterns
    pattern = re.sub(r'\d{4}[-_]\d{2}[-_]\d{2}', 'DATE', filename)
    pattern = re.sub(r'\d{2}[-_]\d{2}[-_]\d{4}', 'DATE', pattern)
    # Remove sequential numbers
    pattern = re.sub(r'_\d+\.', '_N.', pattern)
    # Remove random IDs/hashes
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


def _extract_lessons(
    column_mappings: Dict[str, str],
    user_corrections: Dict[str, Any],
) -> List[str]:
    """Extract natural language lessons from import."""
    lessons = []
    # Lessons from corrections
    for column, correction in user_corrections.items():
        if isinstance(correction, str):
            lessons.append(f"Coluna '{column}' deve mapear para '{correction}'")
    # Lessons from successful mappings
    for column, target_field in column_mappings.items():
        if target_field and column.lower() != target_field.lower():
            lessons.append(f"Coluna '{column}' corresponde ao campo '{target_field}'")
    return lessons[:10]


def _get_schema_version(target_table: str) -> str:
    """Get current schema version hash for a table."""
    try:
        from tools.schema_provider import SchemaProvider
        from tools.postgres_client import PostgresClient
        postgres_client = PostgresClient()
        provider = SchemaProvider(postgres_client)
        return provider.get_schema_version(target_table)
    except Exception as e:
        logger.warning(f"[create_episode] Schema version unavailable: {e}")
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
            logger.info("[create_episode] Memory client initialized")
        except ImportError:
            logger.warning("[create_episode] Memory SDK not available")
        except Exception as e:
            logger.error(f"[create_episode] Memory init failed: {e}")
    return _memory_client


# =============================================================================
# Tool Definition
# =============================================================================

@trace_memory_operation("create_episode")
async def create_episode_tool(
    user_id: str,
    filename: str,
    file_analysis: Dict[str, Any],
    column_mappings: Dict[str, str],
    user_corrections: Dict[str, Any],
    import_result: Dict[str, Any],
    target_table: str = "pending_entry_items",
) -> Dict[str, Any]:
    """
    Create and store an import episode in AgentCore Memory.

    Called after successful imports to capture learned patterns.
    Episodes are stored in GLOBAL namespace for company-wide learning.

    Args:
        user_id: User who performed the import
        filename: Original filename
        file_analysis: Analysis from sheet_analyzer
        column_mappings: Final column mappings used
        user_corrections: Any corrections made by user
        import_result: Result of the import execution
        target_table: Target PostgreSQL table for schema versioning

    Returns:
        Episode creation result with episode_id
    """
    session_id = import_result.get("session_id")

    # Emit audit event
    audit.learning(
        message=f"Criando episódio para: {filename}",
        session_id=session_id,
    )

    try:
        # Get current schema version
        schema_version = _get_schema_version(target_table)

        # Build episode
        episode = ImportEpisode(
            episode_id=_generate_id("EP"),
            filename_pattern=_extract_filename_pattern(filename),
            file_signature=_compute_file_signature(file_analysis),
            sheet_count=file_analysis.get("sheet_count", 1),
            total_rows=file_analysis.get("total_rows", 0),
            sheets_info=[
                {
                    "name": s.get("name"),
                    "purpose": s.get("purpose", s.get("detected_purpose")),
                    "column_count": s.get("column_count"),
                }
                for s in file_analysis.get("sheets", [])
            ],
            column_mappings=column_mappings,
            user_corrections=user_corrections,
            success=import_result.get("success", False),
            match_rate=import_result.get("match_rate", 0.0),
            items_processed=import_result.get("items_processed", 0),
            items_failed=import_result.get("items_failed", 0),
            user_id=user_id,
            lessons=_extract_lessons(column_mappings, user_corrections),
            schema_version=schema_version,
            target_table=target_table,
        )

        # Store in AgentCore Memory (GLOBAL namespace)
        memory_client = _get_memory_client()
        memory_stored = False

        if memory_client:
            try:
                # Create event in GLOBAL namespace (NOT per-user!)
                await memory_client.create_event(
                    event_type="import_completed",
                    data=asdict(episode),
                    namespace=MEMORY_NAMESPACE,  # GLOBAL!
                    role="TOOL",
                )
                memory_stored = True
                logger.info(f"[create_episode] Episode stored: {episode.episode_id}")
            except Exception as e:
                logger.error(f"[create_episode] Memory storage failed: {e}")

        # Emit completion event
        audit.completed(
            message=f"Episódio criado: {episode.episode_id}",
            session_id=session_id,
            details={
                "episode_id": episode.episode_id,
                "lessons_count": len(episode.lessons),
            },
        )

        return {
            "success": True,
            "episode_id": episode.episode_id,
            "filename_pattern": episode.filename_pattern,
            "lessons_count": len(episode.lessons),
            "memory_stored": memory_stored,
            "namespace": MEMORY_NAMESPACE,
        }

    except Exception as e:
        logger.error(f"[create_episode] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao criar episódio",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }
