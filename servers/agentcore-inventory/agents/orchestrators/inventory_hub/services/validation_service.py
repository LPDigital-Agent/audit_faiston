# =============================================================================
# Validation Service - InventoryHub Request/Response Validation
# =============================================================================
# Handles validation of incoming request payloads and LLM responses.
# Integrated with Cognitive Error Handler for AI-powered error enrichment.
#
# ARCHITECTURE (per CLAUDE.md):
# - AI-FIRST: Validation errors enriched by DebugAgent
# - SANDWICH PATTERN: Code validates -> Error enriched by LLM -> Code returns
# - HIL FRIENDLY: Error messages are user-facing in pt-BR
#
# Author: Faiston NEXO Team
# Date: January 2026
# =============================================================================
"""
Validation service for InventoryHub request/response validation.

This module provides validation functions for:
- Request payloads (Mode 2 LLM path)
- LLM responses (action-specific validation)

All validation errors are enriched by DebugAgent via the
@cognitive_sync_handler decorator for user-friendly error messages.
"""

from typing import Any

from shared.cognitive_error_handler import cognitive_sync_handler

__all__ = ["validate_payload", "validate_llm_response"]


@cognitive_sync_handler("inventory_hub")
def validate_payload(payload: dict[str, Any]) -> str:
    """
    Validate request payload and extract prompt for Mode 2 (LLM path).

    Raises ValueError if payload is missing required fields, which triggers
    DebugAgent enrichment via @cognitive_sync_handler decorator.

    Args:
        payload: Request payload with 'prompt' or 'action' field.

    Returns:
        The prompt string for LLM processing.

    Raises:
        ValueError: If both 'prompt' and 'action' are missing
            (enriched by DebugAgent).
    """
    prompt = payload.get("prompt", payload.get("message", ""))
    if not prompt:
        raise ValueError(
            "O payload da requisicao esta vazio ou invalido. "
            "Faltam os campos 'prompt' ou 'action'. "
            "Envie uma mensagem de texto ou especifique uma acao valida."
        )
    return prompt


@cognitive_sync_handler("inventory_hub")
def validate_llm_response(parsed_response: dict[str, Any], action: str) -> dict[str, Any]:
    """
    Validate that LLM response contains required fields for the given action.

    Raises ValueError if validation fails, triggering DebugAgent enrichment.
    Different actions have different validation rules:

    - nexo_analyze_file: MUST have 'sheets' or 'columns' AND non-empty
    - map_to_schema, schema_mapper: MUST have 'mappings' when status=success
    - Error responses (status="error") pass through without validation
    - Unknown actions skip validation silently (preserve chat flexibility)

    Args:
        parsed_response: The JSON-parsed LLM response.
        action: The action that was requested (may be empty for chat).

    Returns:
        The validated response (pass-through if valid).

    Raises:
        ValueError: If required fields are missing or empty
            (enriched by DebugAgent).
    """
    status = parsed_response.get("status", "")

    # Error responses pass through (let user see the error)
    if status == "error" or parsed_response.get("success") is False:
        return parsed_response

    # nexo_analyze_file: MUST have 'sheets' or 'columns' AND non-empty
    if action == "nexo_analyze_file":
        _validate_analyze_file_response(parsed_response)

    # map_to_schema: MUST have 'mappings' AND non-empty when status=success
    elif action in ("map_to_schema", "schema_mapper"):
        _validate_schema_mapper_response(parsed_response, status)

    # Unknown actions: skip validation silently (preserve chat flexibility)
    return parsed_response


def _validate_analyze_file_response(parsed_response: dict[str, Any]) -> None:
    """
    Validate nexo_analyze_file response has required structure.

    Args:
        parsed_response: The JSON-parsed LLM response.

    Raises:
        ValueError: If 'sheets' or 'columns' are missing or empty.
    """
    has_sheets = "sheets" in parsed_response
    has_columns = "columns" in parsed_response
    sheets = parsed_response.get("sheets")
    columns = parsed_response.get("columns")

    # Check if required keys exist
    if not has_sheets and not has_columns:
        raise ValueError(
            "O agente retornou uma analise incompleta: "
            "nao foi possivel identificar as abas ou colunas do arquivo. "
            f"Campos presentes na resposta: {list(parsed_response.keys())}"
        )

    # Validate non-empty (key exists but is empty array)
    if has_sheets and (sheets is None or len(sheets) == 0):
        raise ValueError(
            "O agente identificou o arquivo mas retornou zero abas. "
            "Verifique se o arquivo contem dados validos."
        )
    if has_columns and (columns is None or len(columns) == 0):
        raise ValueError(
            "O agente identificou o arquivo mas retornou zero colunas. "
            "Verifique se o arquivo contem dados validos."
        )


def _validate_schema_mapper_response(
    parsed_response: dict[str, Any],
    status: str,
) -> None:
    """
    Validate schema mapper response has required mappings.

    Args:
        parsed_response: The JSON-parsed LLM response.
        status: The status field from the response.

    Raises:
        ValueError: If 'mappings' is missing or empty when status=success.
    """
    if status != "success":
        return

    mappings = parsed_response.get("mappings")

    if mappings is None:
        raise ValueError(
            "O agente retornou mapeamento incompleto: "
            "campo 'mappings' ausente mesmo com status de sucesso. "
            f"Campos presentes: {list(parsed_response.keys())}"
        )

    if len(mappings) == 0:
        raise ValueError(
            "O agente nao conseguiu mapear nenhuma coluna do arquivo. "
            "Verifique se as colunas correspondem ao schema esperado."
        )
