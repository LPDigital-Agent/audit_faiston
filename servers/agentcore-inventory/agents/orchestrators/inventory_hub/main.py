# =============================================================================
# Inventory Hub Orchestrator - Phase 1+2+3: File Ingestion, Analysis & Mapping
# =============================================================================
# Central intelligence for SGA inventory file ingestion.
#
# ARCHITECTURE PRINCIPLES (per CLAUDE.md):
# 1. AI-FIRST / AGENTIC - Full Strands Agent with LLM reasoning
# 2. SANDWICH PATTERN - CODE → LLM → CODE
# 3. TOOL-FIRST - Deterministic tools handle S3 operations
# 4. NO RAW DATA IN CONTEXT - Files stay in S3, pass keys only
#
# CAPABILITIES:
# Phase 1:
#   1. Generate secure upload URLs (presigned POST)
#   2. Verify uploads completed (with retry logic)
#   3. Validate file types for inventory import
# Phase 2:
#   4. Analyze file structure via A2A (InventoryAnalyst specialist)
#   5. Extract columns, sample data, format without loading full file
# Phase 3:
#   6. Map columns to schema via A2A (SchemaMapper specialist)
#   7. Handle HIL confirmation and learning workflows
#   8. Save training examples for future imports
#
# RESPONSE LANGUAGE:
# - System prompt: English (as per CLAUDE.md)
# - User responses: Brazilian Portuguese (pt-BR)
#
# MEMORY:
# - STM (Short-Term Memory) for tracking upload session context
# - LTM integration via SchemaMapper for cross-import learning
#
# VERSION: 2026-01-21T21:00:00Z (Phase 3 update)
# =============================================================================

import json
import logging
import os
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool

# Agent utilities
from agents.utils import create_gemini_model, AGENT_VERSION

# Intake tools for file upload workflow
from agents.tools.intake_tools import (
    request_file_upload_url,
    verify_file_availability,
    ALLOWED_FILE_TYPES,
)

# Hooks (per ADR-002)
from shared.hooks.logging_hook import LoggingHook
from shared.hooks.metrics_hook import MetricsHook
from shared.hooks.debug_hook import DebugHook

# AUDIT-003: Global error capture for Debug Agent enrichment
from shared.debug_utils import debug_error

# Phase 2: A2A client for calling InventoryAnalyst specialist
from shared.a2a_client import A2AClient

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "inventory_hub"
AGENT_NAME = "FaistonInventoryHub"
AGENT_DESCRIPTION = """
Central intelligence for SGA inventory file ingestion.
Handles secure file uploads via presigned URLs and validates file types.
Phase 1 of the new inventory management architecture.
"""

# Runtime ID for AgentCore deployment (per plan)
RUNTIME_ID = "faiston_sga_inventory_hub"

# =============================================================================
# System Prompt (English with pt-BR Example Dialogues)
# =============================================================================

SYSTEM_PROMPT = """
# Inventory Hub Orchestrator

You are the central intelligence for SGA (Sistema de Gestao de Ativos) file ingestion.
Your primary role is to help users upload inventory files securely.

## Your Capabilities

1. **Generate Upload URLs**: Use `request_file_upload_url` to create secure presigned URLs
   for browser-based file uploads. The URL is valid for 5 minutes.

2. **Verify Uploads**: Use `verify_file_availability` to confirm files have been uploaded
   successfully and are ready for processing.

3. **Analyze File Structure** (Phase 2): Use `analyze_file_structure` to inspect the
   uploaded file and extract columns, sample data, and format information without
   loading the full file into memory. Always use this AFTER verifying the upload.

4. **Map to Schema** (Phase 3): Use `map_to_schema` to propose column mappings to the
   database schema. This calls the SchemaMapper specialist which uses semantic matching
   and prior patterns from memory. Always use this AFTER the user confirms file structure.

5. **Confirm Mapping** (Phase 3): Use `confirm_mapping` for HIL approval of mappings.
   This is ALWAYS required before proceeding to data transformation.

6. **Save Training Example** (Phase 3): Use `save_training_example` when the user
   provides manual corrections. This teaches the system for future imports.

## Supported File Types

You can accept the following file types for inventory import:
- Spreadsheets: CSV, Excel (.xlsx, .xls)
- Documents: PDF, XML, TXT
- Images: JPG, PNG (for inventory photos/evidence)

Maximum file size: 100 MB

## Important Behaviors

1. **File Type Validation**: Always validate file extensions before generating upload URLs.
   Reject unsupported file types with a clear explanation.

2. **Temporary Storage**: Inform users that uploaded files are stored temporarily and
   will be auto-deleted after 24 hours if not processed.

3. **Error Handling**: If an upload verification fails after retries, suggest the user
   try uploading again.

4. **Session Context**: Remember files uploaded in the current session to provide
   continuity in multi-step workflows.

## Response Language

**CRITICAL**: Always respond to users in Brazilian Portuguese (pt-BR).
Your system instructions are in English, but all user-facing messages must be in Portuguese.

## Example Dialogues

### Example 1: User wants to upload a file
User: "Quero fazer upload de uma planilha"
Assistant: "Claro! Qual é o nome do arquivo que você deseja enviar?
Aceito os seguintes formatos: CSV, Excel (.xlsx, .xls), PDF, XML, TXT, ou imagens (JPG, PNG).
O tamanho máximo é 100 MB."

### Example 2: User provides filename
User: "O arquivo se chama estoque_2026.xlsx"
Assistant: [Calls request_file_upload_url with filename="estoque_2026.xlsx"]
"Perfeito! Aqui está o link para upload do arquivo 'estoque_2026.xlsx':
[Provides URL and upload instructions]
Este link é válido por 5 minutos. Após o upload, me avise para eu verificar se deu tudo certo."

### Example 3: User confirms upload
User: "Já fiz o upload"
Assistant: [Calls verify_file_availability with the s3_key]
"Ótimo! Verifiquei o arquivo e está tudo certo:
- Arquivo: estoque_2026.xlsx
- Tamanho: 2.5 MB
- Tipo: Excel (.xlsx)
O arquivo está pronto para processamento na próxima etapa."

### Example 4: Invalid file type
User: "Quero enviar um arquivo documento.docx"
Assistant: "Desculpe, o formato .docx não é suportado para importação de inventário.
Por favor, converta seu arquivo para um dos formatos aceitos:
- Excel: .xlsx ou .xls
- Planilha: .csv
- Documento: .pdf ou .txt
Posso ajudar com o upload assim que você tiver o arquivo no formato correto."

### Example 5: Upload failed
User: "Já fiz o upload" [but file not found]
Assistant: [After verify_file_availability returns exists=false]
"Parece que o upload não foi concluído com sucesso. Isso pode acontecer por:
- O link expirou (válido por 5 minutos)
- Problema de conexão durante o upload
- O arquivo excedeu 100 MB

Posso gerar um novo link de upload para você tentar novamente?"

## Workflow Guidance

### Phase 1: Upload Workflow
When a user wants to upload a file:
1. Ask for the filename if not provided
2. Call `request_file_upload_url` with the filename
3. Provide the upload URL and instructions
4. When user confirms upload, call `verify_file_availability`
5. Confirm success or suggest retry on failure

### Phase 2: Analysis Workflow (after upload verified)
After verifying the upload:
1. Call `analyze_file_structure` with the s3_key from verify_file_availability
2. Present the file structure to the user:
   - Number of columns detected
   - Column names (in their original format)
   - Sample data (first 3 rows)
   - Estimated total rows
   - File format and encoding
3. Ask the user to confirm if the structure looks correct
4. If user confirms, the file is ready for the next processing step

### Example: Full Upload + Analysis Flow
User: "Quero fazer upload de uma planilha"
[Phase 1: Upload workflow]
User: "Já fiz o upload"
[verify_file_availability confirms success]
Assistant: "Ótimo! Agora vou analisar a estrutura do arquivo..."
[Call analyze_file_structure with s3_key]
Assistant: "Encontrei a seguinte estrutura no arquivo:
- **Formato:** CSV com separador ponto-e-vírgula
- **Colunas:** codigo, descricao, quantidade, valor_unitario
- **Linhas estimadas:** ~1.500
- **Amostra dos dados:**
  | codigo | descricao | quantidade | valor_unitario |
  |--------|-----------|------------|----------------|
  | ABC123 | Item 1    | 10         | 15.50          |
  | DEF456 | Item 2    | 5          | 25.00          |

A estrutura está correta? Posso prosseguir com o mapeamento?"

### Phase 3: Schema Mapping Workflow (after file analysis confirmed)
After the user confirms the file structure is correct:
1. Call `map_to_schema` with columns and sample_data from Phase 2
2. **Handle the response based on `status` field:**

   **If `status="success"` (complete mapping):**
   - Present the mapping proposal to the user in pt-BR
   - Show matched columns with confidence scores
   - Show required transformations (DATE_PARSE_PTBR, NUMBER_PARSE_PTBR, etc.)
   - List unmapped columns (will be ignored during import)
   - **HIL ALWAYS REQUIRED**: Ask user to explicitly approve
   - On approval → call `confirm_mapping(approved=True)`
   - On rejection → call `confirm_mapping(approved=False)` and ask for corrections

   **If `status="needs_input"` (agent needs help):**
   - You are helping the agent learn! Present the question politely in pt-BR
   - Example: "Para importar corretamente, preciso saber: qual coluna contém o código do material?"
   - Show available options from `available_sources` list
   - When user answers → call `save_training_example(source_column=user_choice, target_column=required_field)`
   - After saving → call `map_to_schema` again (agent will use the new knowledge)
   - This creates a **learning loop** that improves with each import

3. After successful mapping + confirmation:
   - Inform user: "Mapeamento confirmado! Na próxima fase, o DataTransformer aplicará as transformações."

### Example: Mapping with Complete Success
[After file analysis confirmed]
Assistant: "Vou mapear as colunas para o banco de dados..."
[Call map_to_schema with columns and sample_data]
Assistant: "Encontrei o seguinte mapeamento:

| Coluna do Arquivo | Campo no Sistema | Confiança | Transformação |
|-------------------|------------------|-----------|---------------|
| codigo            | part_number      | 95%       | TRIM          |
| descricao         | description      | 90%       | TRIM          |
| quantidade        | quantity         | 98%       | -             |
| valor_unitario    | unit_price       | 85%       | NUMBER_PARSE_PTBR |

**Colunas ignoradas:** observacao (não mapeável)
**Confiança geral:** 92%

Este mapeamento está correto? Posso confirmar?"

User: "Sim, confirme"
[Call confirm_mapping(approved=True)]
Assistant: "Mapeamento confirmado! Na próxima fase, o DataTransformer aplicará as transformações."

### Example: Mapping Needs User Help
[After file analysis]
[Call map_to_schema]
[Response has status="needs_input"]
Assistant: "Para importar corretamente, preciso da sua ajuda:

**Qual coluna contém o código do material (part_number)?**

Opções disponíveis no arquivo:
1. SKU
2. CODIGO_PROD
3. REF_ITEM

Por favor, escolha uma das opções acima."

User: "É a coluna SKU"
[Call save_training_example(source_column="SKU", target_column="part_number")]
Assistant: "Ótimo! Aprendi que 'SKU' mapeia para 'part_number'. Deixa eu refazer o mapeamento..."
[Call map_to_schema again - now with learned pattern]
[Present complete mapping for confirmation]
"""


# =============================================================================
# Health Check Tool
# =============================================================================


@tool
def health_check() -> str:
    """
    Check the health status of the Inventory Hub orchestrator.

    This tool returns system information useful for debugging and monitoring.

    Returns:
        JSON string with health status, version, and capabilities.
    """
    return json.dumps({
        "success": True,
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "runtime_id": RUNTIME_ID,
        "architecture": "phase3-semantic-mapping",
        "capabilities": [
            "generate_upload_url",
            "verify_file_availability",
            "analyze_file_structure",  # Phase 2
            "map_to_schema",           # Phase 3
            "confirm_mapping",         # Phase 3: HIL
            "save_training_example",   # Phase 3: Learning
        ],
        "supported_file_types": list(ALLOWED_FILE_TYPES.keys()),
        "max_file_size_mb": 100,
        "memory_type": "stm+ltm",  # Phase 3 adds LTM via SchemaMapper
    })


# =============================================================================
# Phase 2: File Structure Analysis Tool (A2A)
# =============================================================================


@tool
def analyze_file_structure(s3_key: str) -> str:
    """
    Analyze the structure of an uploaded inventory file.

    This tool invokes the InventoryAnalyst specialist agent via A2A protocol
    to inspect the file structure without loading the full content.

    Use this AFTER verifying the file exists with verify_file_availability.

    The analysis returns:
    - Column names exactly as they appear in the file
    - First 3 rows of sample data
    - Detected file format (CSV/Excel) and encoding
    - Estimated total row count
    - Whether the file has a header row

    Args:
        s3_key: The S3 object key returned from verify_file_availability.
            Example: "temp/uploads/abc123_inventory.csv"

    Returns:
        JSON string with file structure analysis:
        {
            "success": true,
            "columns": ["codigo", "descricao", "quantidade"],
            "sample_data": [{"codigo": "ABC", "descricao": "Item 1", "quantidade": "10"}, ...],
            "row_count_estimate": 1500,
            "detected_format": "csv_semicolon",
            "has_header": true,
            "encoding": "utf-8"
        }

        On error:
        {
            "success": false,
            "error": "Error description",
            "error_type": "ERROR_TYPE"
        }
    """
    import asyncio

    async def _invoke_analyst() -> dict:
        """Async wrapper for A2A invocation."""
        a2a_client = A2AClient()
        prompt = f"Analyze the file structure at s3_key: {s3_key}"
        return await a2a_client.invoke_agent(
            agent_id="inventory_analyst",  # BUG-FIX: was agent_name
            payload={
                "prompt": prompt,
                "s3_key": s3_key,
            },
        )

    try:
        if not s3_key:
            return json.dumps({
                "success": False,
                "error": "s3_key is required",
                "error_type": "VALIDATION_ERROR",
            })

        # BUG-FIX: Use asyncio.run() to bridge sync tool with async A2A client
        result = asyncio.run(_invoke_analyst())

        # A2AResponse has .response attribute with the actual data
        response_data = getattr(result, "response", result)
        if isinstance(response_data, dict):
            if response_data.get("success"):
                return json.dumps(response_data)
            # Handle error from analyst
            debug_error(
                Exception(response_data.get("error", "Unknown error")),
                "analyze_file_structure",
                {"s3_key": s3_key, "error_type": response_data.get("error_type")},
            )
            return json.dumps(response_data)

        # Fallback: return raw response
        return json.dumps({"success": True, "response": str(response_data)})

    except Exception as e:
        debug_error(e, "analyze_file_structure", {"s3_key": s3_key})
        return json.dumps({
            "success": False,
            "error": f"A2A call failed: {str(e)}",
            "error_type": "A2A_ERROR",
        })


# =============================================================================
# Phase 3: Schema Mapping Tools (A2A + HIL)
# =============================================================================


@tool
def map_to_schema(
    columns: list,
    sample_data: list,
    session_id: Optional[str] = None,
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
    import asyncio

    async def _invoke_mapper() -> dict:
        """Async wrapper for A2A invocation."""
        a2a_client = A2AClient()
        effective_session_id = session_id or os.environ.get("SESSION_ID", "default")

        return await a2a_client.invoke_agent(
            agent_id="schema_mapper",
            payload={
                "prompt": f"Map these columns to pending_entry_items schema: {columns}",
                "session_id": effective_session_id,
                "columns": columns,
                "sample_data": sample_data[:3] if sample_data else [],
                "target_table": "pending_entry_items",
            },
        )

    try:
        if not columns:
            return json.dumps({
                "success": False,
                "error": "columns list is required",
                "error_type": "VALIDATION_ERROR",
            })

        # Bridge sync tool with async A2A client
        result = asyncio.run(_invoke_mapper())

        # Extract response from A2AResponse
        response_data = getattr(result, "response", result)
        if isinstance(response_data, dict):
            return json.dumps(response_data)

        return json.dumps({"success": True, "response": str(response_data)})

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
    import asyncio
    from shared.memory_manager import AgentMemoryManager

    async def _confirm() -> dict:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="inventory_hub", actor_id=user_id)

        if approved:
            # Promote INFERENCE → FACT (enables global learning)
            await memory.learn_fact(
                fact=f"Mapping approved by {user_id} for session {session_id}",
                category="column_mapping_confirmed",
                session_id=session_id,
                use_global=True,  # Share with other users for cross-learning
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
) -> str:
    """
    Save user's manual column mapping as a Training Example.

    Use this when SchemaMapper returns status="needs_input" and the user
    provides a correction. This teaches the system for future imports.

    The mapping is stored as a FACT in AgentCore Memory with use_global=True
    for cross-learning across all users and imports.

    Args:
        source_column: The column name from the file (user's selection).
            Example: "SKU" or "CODIGO_MATERIAL"
        target_column: The required target column that needed mapping.
            Example: "part_number"
        user_id: The user providing the correction (for audit).
        session_id: The active import session.

    Returns:
        JSON confirmation of saved training example:
        {
            "success": true,
            "message": "Aprendi! 'SKU' agora mapeia para 'part_number'.",
            "learned_mapping": {"source": "SKU", "target": "part_number"}
        }
    """
    import asyncio
    from shared.memory_manager import AgentMemoryManager

    async def _save_training() -> dict:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="inventory_hub", actor_id=user_id)

        # Store as FACT with global visibility (cross-learning)
        await memory.learn_fact(
            fact=f"Column '{source_column}' maps to '{target_column}'",
            category="column_mapping_training_example",
            session_id=session_id,
            use_global=True,  # Enable learning across all users/imports
            metadata={
                "source_column": source_column,
                "target_column": target_column,
                "taught_by": user_id,
            }
        )

        return {
            "success": True,
            "message": f"Aprendi! '{source_column}' agora mapeia para '{target_column}'.",
            "learned_mapping": {"source": source_column, "target": target_column}
        }

    try:
        if not source_column or not target_column:
            return json.dumps({
                "success": False,
                "error": "source_column and target_column are required",
                "error_type": "VALIDATION_ERROR",
            })

        result = asyncio.run(_save_training())
        logger.info(
            f"[InventoryHub] Training example saved: {source_column} → {target_column} "
            f"by {user_id} in session {session_id}"
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


# =============================================================================
# Orchestrator Factory
# =============================================================================


def create_inventory_hub() -> Agent:
    """
    Create the Inventory Hub orchestrator as a full Strands Agent.

    This agent handles Phase 1 file ingestion workflow with:
    - File upload URL generation (presigned POST)
    - Upload verification with retry logic
    - File type validation
    - STM memory for session context

    Returns:
        Strands Agent configured for inventory file ingestion.
    """
    hooks = [
        LoggingHook(log_level=logging.INFO),
        MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        DebugHook(timeout_seconds=30.0),
    ]

    agent = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model("inventory_hub"),  # Gemini Flash for speed
        tools=[
            # Phase 1: File upload workflow
            request_file_upload_url,
            verify_file_availability,
            # Phase 2: File analysis (A2A)
            analyze_file_structure,
            # Phase 3: Schema mapping (A2A + HIL)
            map_to_schema,
            confirm_mapping,
            save_training_example,
            # System
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
    )

    logger.info(f"[InventoryHub] Created {AGENT_NAME} with {len(hooks)} hooks")
    return agent


# =============================================================================
# BedrockAgentCoreApp Entrypoint
# =============================================================================

app = BedrockAgentCoreApp()


# =============================================================================
# CONCURRENCY FIX: No cached orchestrator instance
# =============================================================================
# Strands Agents are STATEFUL and do NOT support concurrent invocations.
# The SDK raises ConcurrencyException if the same Agent instance is invoked
# while already processing a request.
#
# AgentCore Runtime may send concurrent requests to the same container,
# so we MUST create a NEW Agent instance per request.
#
# Reference: Strands SDK AWS Lambda deployment pattern
# https://strandsagents.com/latest/user-guide/deploy/deploy_to_aws_lambda/
# =============================================================================


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """
    Main entrypoint for AgentCore Runtime.

    Handles:
    1. Health check requests
    2. Natural language file upload requests

    Args:
        payload: Request with either:
            - action: "health_check" for system status
            - prompt: Natural language request for file operations
        context: AgentCore context with session_id, identity

    Returns:
        Response dict with operation results
    """
    try:
        # Extract context
        session_id = getattr(context, "session_id", "default-session")
        user_id = getattr(context, "user_id", None) or payload.get("user_id", "anonymous")
        action = payload.get("action")
        prompt = payload.get("prompt", payload.get("message", ""))

        logger.info(
            f"[InventoryHub] Invoke: action={action}, session={session_id}, "
            f"user={user_id}, prompt_len={len(prompt)}"
        )

        # Mode 1: Health check (direct response, no LLM)
        if action == "health_check":
            return json.loads(health_check())

        # Mode 2: Natural language processing via LLM
        if not prompt:
            return {
                "success": False,
                "error": "Missing 'prompt' or 'action' in request",
                "usage": {
                    "prompt": "Natural language request (e.g., 'Quero fazer upload de um arquivo CSV')",
                    "action": "Action name (health_check)",
                },
                "agent_id": AGENT_ID,
            }

        # Create fresh agent instance (concurrency fix)
        agent = create_inventory_hub()

        # Invoke agent with prompt
        result = agent(
            prompt,
            user_id=user_id,
            session_id=session_id,
        )

        # Extract response
        if hasattr(result, "message"):
            message = result.message
            # Try to parse as JSON if structured
            if isinstance(message, str) and message.strip().startswith("{"):
                try:
                    return json.loads(message)
                except json.JSONDecodeError:
                    pass
            return {
                "success": True,
                "response": message,
                "agent_id": AGENT_ID,
            }

        return {
            "success": True,
            "response": str(result),
            "agent_id": AGENT_ID,
        }

    except Exception as e:
        debug_error(e, "inventory_hub_invoke", {
            "action": payload.get("action"),
            "prompt_len": len(payload.get("prompt", "")),
        })
        return {
            "success": False,
            "error": str(e),
            "agent_id": AGENT_ID,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "inventory_hub_invoke",
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
        }


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "app",
    "create_inventory_hub",
    "invoke",
    "AGENT_ID",
    "AGENT_NAME",
    "RUNTIME_ID",
]


# =============================================================================
# Main (for local testing)
# =============================================================================

if __name__ == "__main__":
    app.run()
