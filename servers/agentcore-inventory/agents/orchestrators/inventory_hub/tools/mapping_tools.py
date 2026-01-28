"""
Mapping tools for InventoryHub orchestrator.

Tools for column mapping via SchemaMapper A2A, HIL confirmation,
and training example storage.
"""

import asyncio
import json
import logging
import os
from typing import Optional

from strands import tool

from shared.debug_utils import debug_error
from shared.memory_manager import AgentMemoryManager
from shared.strands_a2a_client import A2AClient

__all__ = ["map_to_schema", "confirm_mapping", "save_training_example"]

logger = logging.getLogger(__name__)


@tool
def map_to_schema(
    columns: list,
    sample_data: list,
    session_id: Optional[str] = None,
    user_answers: Optional[dict] = None,
) -> str:
    """
    Map file columns to target PostgreSQL schema via SchemaMapper agent (A2A).

    Call this AFTER analyze_file_structure returns successfully.
    The SchemaMapper uses semantic matching and prior patterns from memory
    to propose column mappings.

    IMPORTANT: The response may have two statuses:
    - "success": Complete mapping ready for HIL confirmation
    - "needs_input": Agent needs help with required columns

    Args:
        columns: List of column names from file analysis.
            Example: ["codigo", "descricao", "quantidade", "valor"]
        sample_data: First 3 rows of sample data for context.
            Example: [{"codigo": "ABC", "quantidade": "10"}, ...]
        session_id: Optional session ID override. Defaults to AgentCore context.
        user_answers: Optional dict of user answers to HIL questions.
            Example: {"quantity_column": "QTD", "category": "entrada"}
            SchemaMapper uses these to refine mapping decisions.

    Returns:
        JSON string with mapping proposal:
        {
            "success": true,
            "status": "success" | "needs_input",
            "mappings": [...],  # When status=success
            "missing_required_fields": [...],  # When status=needs_input
            "overall_confidence": 0.87,
            "requires_confirmation": true  # ALWAYS true
        }
    """

    async def _invoke_mapper() -> dict:
        """Async wrapper for A2A invocation."""
        a2a_client = A2AClient()
        effective_session_id = session_id or os.environ.get("SESSION_ID", "default")

        payload = {
            "prompt": f"Map these columns to pending_entry_items schema: {columns}",
            "session_id": effective_session_id,
            "columns": columns,
            "sample_data": sample_data[:3] if sample_data else [],
            "target_table": "pending_entry_items",
        }

        if user_answers:
            payload["user_answers"] = user_answers
            payload["prompt"] = (
                f"Re-analyze column mapping using user answers: {user_answers}. "
                f"Map these columns to pending_entry_items schema: {columns}"
            )
            logger.info(f"[map_to_schema] Re-analysis with {len(user_answers)} user answers")

        return await a2a_client.invoke_agent(
            agent_id="schema_mapper",
            payload=payload,
        )

    try:
        if not columns:
            return json.dumps({
                "success": False,
                "error": "columns list is required",
                "error_type": "VALIDATION_ERROR",
            })

        result = asyncio.run(_invoke_mapper())
        response_str = getattr(result, "response", "")

        # BUG-046 FIX: A2AResponse.response is a JSON STRING, not a dict.
        # Parse it so we return the actual response structure, not a wrapper.
        try:
            final_result = json.loads(response_str) if response_str else {}
        except json.JSONDecodeError:
            final_result = {"success": False, "error": "Invalid JSON from schema_mapper", "raw": response_str[:500]}

        return json.dumps(final_result)

    except Exception as e:
        debug_error(e, "map_to_schema", {"columns": columns})
        return json.dumps({
            "success": False,
            "error": f"A2A call to SchemaMapper failed: {str(e)}",
            "error_type": "A2A_ERROR",
        })


@tool
def confirm_mapping(session_id: str, approved: bool, user_id: str) -> str:
    """
    Confirm or reject a mapping proposal (Human-in-the-Loop action).

    This is the HIL confirmation step required for ALL mapping proposals.
    If approved, the mapping is promoted from INFERENCE to FACT in
    AgentCore Memory, enabling cross-learning for future imports.

    Args:
        session_id: The session containing the mapping proposal.
        approved: True to confirm, False to reject.
        user_id: The user confirming (for audit trail).

    Returns:
        JSON string with confirmation status and next steps:
        {
            "success": true,
            "status": "APPROVED" | "REJECTED",
            "message": "...",  # pt-BR message
            "next_action": "call_data_transformer" | "request_manual_mapping"
        }
    """

    async def _confirm() -> dict:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="inventory_hub", actor_id=user_id)

        if approved:
            await memory.learn_fact(
                fact=f"Mapping approved by {user_id} for session {session_id}",
                category="column_mapping_confirmed",
                session_id=session_id,
                use_global=True,
            )
            return {
                "success": True,
                "status": "APPROVED",
                "message": "Mapeamento confirmado. Pronto para Phase 4: DataTransformer.",
                "next_action": "call_data_transformer",
            }
        else:
            return {
                "success": True,
                "status": "REJECTED",
                "message": "Mapeamento rejeitado. Por favor, forneça correções.",
                "next_action": "request_manual_mapping",
            }

    try:
        if not session_id or not user_id:
            return json.dumps({
                "success": False,
                "error": "session_id and user_id are required",
                "error_type": "VALIDATION_ERROR",
            })

        result = asyncio.run(_confirm())
        return json.dumps(result)

    except Exception as e:
        debug_error(e, "confirm_mapping", {"session_id": session_id, "approved": approved})
        return json.dumps({
            "success": False,
            "error": f"HIL confirmation failed: {str(e)}",
            "error_type": "MEMORY_ERROR",
        })


@tool
def save_training_example(
    source_column: str,
    target_column: str,
    user_id: str,
    session_id: str,
    update_current_session: bool = True,
) -> str:
    """
    Save user's manual column mapping as a Training Example (DUAL-WRITE PATTERN).

    Use this when SchemaMapper returns status="needs_input" and the user
    provides a correction. This teaches the system for future imports.

    **DUAL-WRITE PATTERN:**
    1. **LTM (Long-Term Memory):** Saves as a FACT in AgentCore Memory with use_global=True
       for cross-learning across all users and imports (future imports).
    2. **STM (Short-Term Memory):** When update_current_session=True, also writes an event
       to the current session so the agent remembers the correction (current import).

    Args:
        source_column: The column name from the file (user's selection).
            Example: "SKU" or "CODIGO_MATERIAL"
        target_column: The required target column that needed mapping.
            Example: "part_number"
        user_id: The user providing the correction (for audit).
        session_id: The active import session.
        update_current_session: If True (default), also updates STM for the current
            session so the mapping correction is applied immediately. Set to False
            only if you want to save for future imports without affecting current session.

    Returns:
        JSON confirmation of saved training example:
        {
            "success": true,
            "message": "Aprendi! 'SKU' agora mapeia para 'part_number'.",
            "learned_mapping": {"source": "SKU", "target": "part_number"},
            "ltm_saved": true,
            "stm_updated": true,
            "apply_to_current_mapping": true
        }
    """

    async def _save_training_dual_write() -> dict:
        """Async wrapper for dual-write memory operations (LTM + STM)."""
        memory = AgentMemoryManager(agent_id="inventory_hub", actor_id=user_id)

        # 1. SAVE TO LTM (Long-Term Memory) - for future imports
        await memory.learn_fact(
            fact=f"Column '{source_column}' maps to '{target_column}'",
            category="column_mapping_training_example",
            session_id=session_id,
            use_global=True,
            metadata={
                "source_column": source_column,
                "target_column": target_column,
                "taught_by": user_id,
            }
        )
        ltm_saved = True

        # 2. UPDATE STM (Short-Term Memory) - for current session
        stm_updated = False
        if update_current_session:
            await memory.learn(
                content=f"User corrected mapping: '{source_column}' → '{target_column}'. "
                        f"Apply this correction to the current import session.",
                category="mapping_correction",
                session_id=session_id,
                use_global=False,  # Session-scoped, not global
                confidence=1.0,  # User correction = high confidence
                source_column=source_column,
                target_column=target_column,
                correction_type="user_override",
            )
            stm_updated = True

        return {
            "success": True,
            "message": f"Aprendi! '{source_column}' agora mapeia para '{target_column}'.",
            "learned_mapping": {"source": source_column, "target": target_column},
            "ltm_saved": ltm_saved,
            "stm_updated": stm_updated,
            "apply_to_current_mapping": update_current_session,
        }

    try:
        if not source_column or not target_column:
            return json.dumps({
                "success": False,
                "error": "source_column and target_column are required",
                "error_type": "VALIDATION_ERROR",
            })

        result = asyncio.run(_save_training_dual_write())
        logger.info(
            f"[InventoryHub] Training example saved (dual-write): {source_column} → {target_column} "
            f"by {user_id} in session {session_id}, stm_updated={result['stm_updated']}"
        )
        return json.dumps(result)

    except Exception as e:
        debug_error(e, "save_training_example", {
            "source_column": source_column,
            "target_column": target_column,
        })
        return json.dumps({
            "success": False,
            "error": f"Failed to save training example: {str(e)}",
            "error_type": "MEMORY_ERROR",
        })
