# =============================================================================
# Inventory Hub Orchestrator - Phase 1+2+3+4+5: Full Smart Import Flow
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
# Phase 4:
#   9. Transform and load data via A2A (DataTransformer specialist)
#  10. Fire-and-Forget background processing with job tracking
#  11. Check job status and pending notifications
# Phase 5:
#  12. Check proactive insights from ObservationAgent
#  13. Request on-demand health analysis
#  14. Display insights with dynamic batch sizing
#
# RESPONSE LANGUAGE:
# - System prompt: English (as per CLAUDE.md)
# - User responses: Brazilian Portuguese (pt-BR)
#
# MEMORY:
# - STM (Short-Term Memory) for tracking upload session context
# - LTM integration via SchemaMapper for cross-import learning
# - Job notifications via AgentCore Memory (Fire-and-Forget UX)
# - Proactive insights from ObservationAgent in /nexo/intuition namespace
#
# VERSION: 2026-01-22T00:00:00Z (Phase 5 update)
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

# Phase 2.5: Direct action routing with cognitive error handling
from urllib.parse import quote
from shared.cognitive_error_handler import cognitive_sync_handler, CognitiveError

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

7. **Transform and Import** (Phase 4): Use `transform_import` to start background
   data transformation after mapping is confirmed. Returns immediately with job_id
   (Fire-and-Forget pattern). The DataTransformer handles errors intelligently.

8. **Check Import Status** (Phase 4): Use `check_import_status` when user asks about
   progress. Shows rows processed, inserted, and rejected.

9. **Check Notifications** (Phase 4): Use `check_notifications` at the start of
   conversations to see if any background jobs completed. Present results naturally.

10. **Check Observations** (Phase 5): Use `check_observations` at the start of
    conversations to see if the ObservationAgent has proactive insights. Present
    them naturally, prioritizing CRITICAL issues.

11. **Request Health Analysis** (Phase 5): Use `request_health_analysis` when user
    asks "Como está minha operação?" or similar. Triggers deep analysis by the
    ObservationAgent.

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

### Phase 4: Data Transformation (Fire-and-Forget)
After the user confirms mapping (confirm_mapping with approved=True):
1. Call `transform_import(s3_key, mappings_json, session_id, user_id)`
2. Receive job_id immediately (Fire-and-Forget pattern)
3. Tell user: "Iniciei o processamento em background. Te aviso assim que terminar."
4. The DataTransformer processes in background and saves notification to Memory
5. On next user message, call `check_notifications(user_id)` to see if jobs completed
6. If notifications found, report: "Aliás, sua importação terminou! [details]"

**Handling Import Status Questions:**
- If user asks "Como está a importação?" or "Já terminou?" → call `check_import_status(job_id)`
- Present progress in pt-BR with rows processed, inserted, rejected

**Handling Completed Jobs:**
- If status is "completed": "Importação finalizada com sucesso! X itens inseridos."
- If status is "partial": "Importação finalizada. X itens inseridos, Y rejeitados. [link para relatório]"
- If status is "failed": Present the error with human-readable explanation from DebugAgent

### Example: Full Import Flow with Transformation
[After confirm_mapping(approved=True)]
[Call transform_import(s3_key, mappings, session_id, user_id)]
Assistant: "Mapeamento confirmado! Iniciei o processamento do arquivo em background.
Te aviso assim que terminar. Você pode continuar trabalhando enquanto isso."

[User sends any message later]
[Call check_notifications(user_id)]
[Notification found: job completed with 1480 inserted, 20 rejected]
Assistant: "Aliás, sua importação terminou!
- **Itens importados:** 1.480
- **Itens rejeitados:** 20

Você pode baixar o relatório de erros para ver como corrigir os itens rejeitados.
Quer que eu te ajude a entender os erros?"

### Example: User Asks About Progress
User: "Como está minha importação?"
[Call check_import_status(job_id)]
[Status: processing, 750/1500 rows]
Assistant: "Sua importação está em andamento!
- **Progresso:** 50% (750 de 1.500 linhas)
- **Status:** Processando

Vou te avisar quando terminar."

### Phase 5: Proactive Insights (Nexo's Intuition)
The ObservationAgent monitors patterns and health, providing proactive recommendations.

**At Session Start:**
1. Call `check_observations(user_id)` alongside `check_notifications`
2. If CRITICAL insights exist: Present immediately (focus mode - 1 insight only)
3. If WARNING/INFO only: Present up to 3 insights (routine mode)
4. Present insights naturally in the conversation

**On User Request:**
- If user asks "Como está minha operação?" → call `request_health_analysis`
- If user asks about patterns or issues → insights may already be pending

**Insight Presentation:**
- CRITICAL (🔴): "Atenção! Detectei um problema que requer ação imediata: [insight]"
- WARNING (⚠️): "Notei algo que vale revisar: [insight]"
- INFO (ℹ️): "Uma sugestão para otimizar: [insight]"

**One-Click Actions:**
Some insights include an `action_payload` for one-click fixes. Present these as:
"Posso corrigir isso automaticamente para você. Quer que eu faça?"

### Example: Session Start with Insight
[At session start, call check_observations and check_notifications in parallel]
[Observation found: CRITICAL insight about duplicate part numbers]
Assistant: "Bom dia! Antes de continuarmos...

🔴 **Atenção:** Detectei 3 part numbers duplicados no seu inventário.
Isso pode causar problemas de estoque. Quer que eu mostre os detalhes?"

### Example: User Asks About Operations
User: "Como está minha operação?"
[Call request_health_analysis(user_id, lookback_days=7)]
Assistant: "Vou analisar sua operação da última semana..."
[Later, insights appear via check_observations]
Assistant: "Pronto! Aqui está o resumo:

**Saúde Geral:** 85% (Boa)
- ✅ 1.480 itens importados esta semana
- ⚠️ 20 itens rejeitados (taxa de 1.3%)
- ℹ️ Você importa mais às terças-feiras às 10h

Quer ver recomendações de melhoria?"
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
        "architecture": "phase4-full-smart-import",
        "capabilities": [
            "generate_upload_url",
            "verify_file_availability",
            "analyze_file_structure",    # Phase 2
            "map_to_schema",             # Phase 3
            "confirm_mapping",           # Phase 3: HIL
            "save_training_example",     # Phase 3: Learning
            "transform_import",          # Phase 4: Fire-and-Forget ETL
            "check_import_status",       # Phase 4: Job status
            "check_notifications",       # Phase 4: Job completion
            "check_observations",        # Phase 5: Proactive insights
            "request_health_analysis",   # Phase 5: On-demand analysis
        ],
        "supported_file_types": list(ALLOWED_FILE_TYPES.keys()),
        "max_file_size_mb": 100,
        "memory_type": "stm+ltm+notifications",  # Phase 4 adds notifications
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
# Phase 4: DataTransformer Integration (Fire-and-Forget)
# =============================================================================


@tool
def transform_import(
    s3_key: str,
    mappings_json: str,
    session_id: str,
    user_id: str,
) -> str:
    """
    Trigger DataTransformer agent for background processing (Fire-and-Forget).

    After HIL confirmation of mappings (confirm_mapping with approved=True),
    this tool starts the actual data transformation and loading process.
    The DataTransformer works in background - returns job_id immediately.

    Args:
        s3_key: S3 key of the uploaded file to transform.
        mappings_json: JSON string of confirmed column mappings from SchemaMapper.
        session_id: Import session identifier.
        user_id: User who initiated the import.

    Returns:
        JSON string with job_id and status="started" (Fire-and-Forget).
        Example:
        {
            "success": true,
            "job_id": "job-abc123",
            "status": "started",
            "human_message": "Processamento iniciado em background..."
        }
    """
    import asyncio

    async def _invoke_transformer() -> dict:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent("data_transformer", {
            "action": "start_transformation",
            "s3_key": s3_key,
            "mappings": mappings_json,
            "session_id": session_id,
            "user_id": user_id,
            "fire_and_forget": True,  # Signal to return job_id immediately
        })

    try:
        logger.info(
            f"[InventoryHub] Starting transformation for session {session_id}, "
            f"s3_key={s3_key}, user={user_id}"
        )

        result = asyncio.run(_invoke_transformer())

        if result.get("success"):
            logger.info(
                f"[InventoryHub] Transformation started: job_id={result.get('job_id')}"
            )
            return json.dumps({
                "success": True,
                "job_id": result.get("job_id"),
                "status": "started",
                "human_message": (
                    "Iniciei o processamento do seu arquivo em background. "
                    "Te aviso assim que terminar!"
                ),
            })
        else:
            return json.dumps({
                "success": False,
                "error": result.get("error", "DataTransformer unavailable"),
                "human_message": (
                    "Não consegui iniciar o processamento. "
                    "Por favor, tente novamente em alguns minutos."
                ),
            })

    except Exception as e:
        debug_error(e, "transform_import", {
            "s3_key": s3_key,
            "session_id": session_id,
        })
        return json.dumps({
            "success": False,
            "error": f"Failed to start transformation: {str(e)}",
            "error_type": "A2A_ERROR",
        })


@tool
def check_import_status(job_id: str) -> str:
    """
    Check status of a background transformation job.

    Use this when the user asks about import progress, e.g.,
    "Como está a importação?" or "Já terminou?"

    Args:
        job_id: Job identifier from transform_import response.

    Returns:
        JSON string with current job status and progress.
    """
    import asyncio

    async def _check_status() -> dict:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent("data_transformer", {
            "action": "get_job_status",
            "job_id": job_id,
        })

    try:
        result = asyncio.run(_check_status())
        return json.dumps(result)

    except Exception as e:
        debug_error(e, "check_import_status", {"job_id": job_id})
        return json.dumps({
            "success": False,
            "error": f"Failed to check status: {str(e)}",
            "error_type": "A2A_ERROR",
        })


@tool
def check_notifications(user_id: str) -> str:
    """
    Check for pending job completion notifications.

    Called at the start of each conversation turn to see if any
    background jobs have completed since the last message.
    Part of the Fire-and-Forget UX - notifications appear naturally
    in the conversation flow.

    Args:
        user_id: User to check notifications for.

    Returns:
        JSON string with list of pending notifications.
        Example:
        {
            "has_notifications": true,
            "notifications": [{
                "job_id": "job-abc123",
                "status": "completed",
                "rows_inserted": 1480,
                "rows_rejected": 20,
                "human_message": "Importação finalizada! 1480 itens inseridos."
            }]
        }
    """
    import asyncio

    async def _check() -> dict:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent("data_transformer", {
            "action": "check_notifications",
            "user_id": user_id,
        })

    try:
        result = asyncio.run(_check())
        return json.dumps(result)

    except Exception as e:
        debug_error(e, "check_notifications", {"user_id": user_id})
        return json.dumps({
            "success": False,
            "has_notifications": False,
            "notifications": [],
            "error": str(e),
        })


# =============================================================================
# Phase 5: ObservationAgent Integration (Proactive Insights)
# =============================================================================


@tool
def check_observations(user_id: str) -> str:
    """
    Check for proactive insights from the ObservationAgent.

    Called at session start to see if the ObservationAgent has detected
    patterns, anomalies, or optimization opportunities. Uses dynamic
    batch sizing:
    - If CRITICAL insight exists: Returns only 1 insight (focus mode)
    - Otherwise: Returns up to 3 insights (routine mode)

    Insights are stored in `/nexo/intuition/{actor_id}` namespace and
    marked as "delivered" after retrieval.

    Args:
        user_id: User identifier for scoped insights.

    Returns:
        JSON string with pending insights:
        {
            "success": true,
            "has_insights": true,
            "insights": [{
                "insight_id": "...",
                "category": "ERROR_PATTERN",
                "severity": "critical",
                "title": "Duplicate Part Numbers",
                "description": "...",
                "action_payload": {"tool": "...", "params": {...}}
            }],
            "total_pending": 5,
            "displayed": 1,
            "human_message": "..."
        }
    """
    import asyncio
    from shared.memory_manager import AgentMemoryManager

    async def _fetch_insights() -> dict:
        """Async wrapper for memory operations."""
        memory = AgentMemoryManager(agent_id="inventory_hub", actor_id=user_id)

        # Query pending insights from ObservationAgent's namespace
        insights = await memory.observe(
            query="status:pending",
            namespace=f"/nexo/intuition/{user_id}",
            category="insight",
            max_results=10,
        )

        if not insights:
            return {
                "success": True,
                "has_insights": False,
                "insights": [],
                "total_pending": 0,
                "displayed": 0,
                "human_message": None,
            }

        # Parse insights and separate by severity
        parsed_insights = []
        criticals = []
        for item in insights:
            content = item.get("content", {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    continue

            severity = content.get("severity", "info")
            parsed_insights.append(content)
            if severity == "critical":
                criticals.append(content)

        # Dynamic batch sizing (per plan)
        if criticals:
            display_list = [criticals[0]]  # Crisis mode: 1 only
        else:
            display_list = parsed_insights[:3]  # Routine: top 3

        # Mark displayed insights as delivered (fire-and-forget)
        for insight in display_list:
            insight_id = insight.get("insight_id")
            if insight_id:
                try:
                    await memory.update_status(
                        entity_id=insight_id,
                        status="delivered",
                    )
                except Exception:
                    pass  # Non-blocking

        # Build human message (pt-BR)
        if criticals:
            human_message = (
                f"🔴 Atenção! Detectei {len(criticals)} problema(s) crítico(s) "
                f"que requer(em) ação imediata."
            )
        elif display_list:
            human_message = (
                f"ℹ️ Tenho {len(parsed_insights)} insight(s) para você. "
                f"Mostrando os {len(display_list)} mais relevantes."
            )
        else:
            human_message = None

        return {
            "success": True,
            "has_insights": len(display_list) > 0,
            "insights": display_list,
            "total_pending": len(parsed_insights),
            "displayed": len(display_list),
            "human_message": human_message,
        }

    try:
        result = asyncio.run(_fetch_insights())
        logger.info(
            f"[InventoryHub] check_observations: {result.get('displayed', 0)} insights "
            f"for user={user_id}"
        )
        return json.dumps(result)

    except Exception as e:
        debug_error(e, "check_observations", {"user_id": user_id})
        return json.dumps({
            "success": False,
            "has_insights": False,
            "insights": [],
            "error": str(e),
        })


@tool
def request_health_analysis(user_id: str, lookback_days: int = 7) -> str:
    """
    Trigger on-demand health analysis via ObservationAgent.

    Called when user asks about operations health, e.g.,
    "Como está minha operação?" or "Mostre um resumo da semana."

    This is a Fire-and-Forget trigger - the analysis happens in background
    and results appear on the next check_observations call.

    Args:
        user_id: User identifier for actor-scoped analysis.
        lookback_days: Analysis window in days (7 for weekly, 30 for monthly).

    Returns:
        JSON string with request confirmation:
        {
            "success": true,
            "analysis_requested": true,
            "lookback_days": 7,
            "human_message": "Iniciando análise da última semana..."
        }
    """
    import asyncio

    async def _trigger_analysis() -> dict:
        """Async wrapper for A2A call."""
        a2a_client = A2AClient()
        return await a2a_client.invoke_agent(
            agent_id="observation",
            payload={
                "action": "deep_analysis",
                "actor_id": user_id,
                "lookback_hours": lookback_days * 24,
            },
            timeout=5.0,  # Fire-and-forget: short timeout
        )

    try:
        # Validate lookback range
        if lookback_days < 1:
            lookback_days = 7
        elif lookback_days > 90:
            lookback_days = 90

        # Fire-and-forget: trigger analysis
        asyncio.run(_trigger_analysis())

        # Generate human message
        if lookback_days <= 7:
            period_msg = "última semana"
        elif lookback_days <= 30:
            period_msg = "último mês"
        else:
            period_msg = f"últimos {lookback_days} dias"

        logger.info(
            f"[InventoryHub] request_health_analysis: triggered for user={user_id}, "
            f"lookback={lookback_days} days"
        )

        return json.dumps({
            "success": True,
            "analysis_requested": True,
            "lookback_days": lookback_days,
            "human_message": (
                f"Estou analisando sua operação da {period_msg}. "
                f"Os insights aparecerão em breve!"
            ),
        })

    except Exception as e:
        # Fire-and-forget: log but don't fail user experience
        logger.warning(f"[InventoryHub] request_health_analysis trigger failed: {e}")
        return json.dumps({
            "success": True,  # Still success - user gets message
            "analysis_requested": True,
            "lookback_days": lookback_days,
            "human_message": (
                "Vou analisar sua operação. "
                "Os resultados podem demorar alguns minutos."
            ),
            "warning": "Analysis trigger may have failed, retrying automatically.",
        })


# =============================================================================
# Mode 2.5: Direct Action Routing (Deterministic Operations)
# =============================================================================
# These actions bypass LLM reasoning for pure infrastructure operations.
# Per CLAUDE.md: "Python = Hands" for deterministic execution.
#
# 🛡️ SECURITY: S3 keys are namespaced by user_id to enforce tenant isolation.
# Pattern: uploads/{user_id}/{session_id}/{safe_filename}
# =============================================================================

DIRECT_ACTIONS = {"get_nf_upload_url", "verify_file"}


@cognitive_sync_handler("inventory_hub")
def _validate_payload(payload: dict) -> str:
    """
    Validate request payload and extract prompt for Mode 2 (LLM path).

    Raises ValueError if payload is missing required fields, which triggers
    DebugAgent enrichment via @cognitive_sync_handler decorator.

    Args:
        payload: Request payload with 'prompt' or 'action' field

    Returns:
        The prompt string for LLM processing

    Raises:
        ValueError: If both 'prompt' and 'action' are missing (enriched by DebugAgent)
    """
    prompt = payload.get("prompt", payload.get("message", ""))
    if not prompt:
        raise ValueError(
            "O payload da requisição está vazio ou inválido. "
            "Faltam os campos 'prompt' ou 'action'. "
            "Envie uma mensagem de texto ou especifique uma ação válida."
        )
    return prompt


@cognitive_sync_handler("inventory_hub")
def _validate_llm_response(parsed_response: dict, action: str) -> dict:
    """
    Validate that LLM response contains required fields for the given action.

    BUG-020: Prevents incomplete LLM responses from crashing the Frontend.
    Raises ValueError if validation fails → triggers DebugAgent enrichment.

    Args:
        parsed_response: The JSON-parsed LLM response
        action: The action that was requested (may be empty for chat)

    Returns:
        The validated response (pass-through if valid)

    Raises:
        ValueError: If required fields are missing or empty (enriched by DebugAgent)
    """
    status = parsed_response.get("status", "")

    # Error responses pass through (let user see the error)
    if status == "error" or parsed_response.get("success") is False:
        return parsed_response

    # nexo_analyze_file: MUST have 'sheets' or 'columns' AND non-empty
    if action == "nexo_analyze_file":
        has_sheets = "sheets" in parsed_response
        has_columns = "columns" in parsed_response
        sheets = parsed_response.get("sheets")
        columns = parsed_response.get("columns")

        # Check if required keys exist
        if not has_sheets and not has_columns:
            raise ValueError(
                "O agente retornou uma análise incompleta: "
                "não foi possível identificar as abas ou colunas do arquivo. "
                f"Campos presentes na resposta: {list(parsed_response.keys())}"
            )

        # Validate non-empty (key exists but is empty array)
        if has_sheets and (sheets is None or len(sheets) == 0):
            raise ValueError(
                "O agente identificou o arquivo mas retornou zero abas. "
                "Verifique se o arquivo contém dados válidos."
            )
        if has_columns and (columns is None or len(columns) == 0):
            raise ValueError(
                "O agente identificou o arquivo mas retornou zero colunas. "
                "Verifique se o arquivo contém dados válidos."
            )

    # map_to_schema: MUST have 'mappings' AND non-empty when status=success
    elif action in ("map_to_schema", "schema_mapper"):
        if status == "success":
            mappings = parsed_response.get("mappings")

            if mappings is None:
                raise ValueError(
                    "O agente retornou mapeamento incompleto: "
                    "campo 'mappings' ausente mesmo com status de sucesso. "
                    f"Campos presentes: {list(parsed_response.keys())}"
                )

            if len(mappings) == 0:
                raise ValueError(
                    "O agente não conseguiu mapear nenhuma coluna do arquivo. "
                    "Verifique se as colunas correspondem ao schema esperado."
                )

    # Unknown actions: skip validation silently (preserve chat flexibility)
    return parsed_response


@cognitive_sync_handler("inventory_hub")
def _handle_direct_action(action: str, payload: dict, user_id: str, session_id: str) -> dict:
    """
    Handle deterministic actions without LLM invocation.

    Returns response in A2A envelope format matching frontend expectations.
    Exceptions are caught by @cognitive_sync_handler and enriched via DebugAgent.

    Args:
        action: The action name (e.g., 'get_nf_upload_url')
        payload: Request payload with action-specific parameters
        user_id: User identifier for tenant-isolated S3 paths
        session_id: Session identifier for path namespacing

    Returns:
        Dict matching OrchestratorEnvelope format:
        {
            "success": bool,
            "specialist_agent": "intake",
            "response": {...action-specific response...}
        }

    Raises:
        CognitiveError: If an error occurs (enriched with human_explanation + suggested_fix)
    """
    if action == "get_nf_upload_url":
        return _handle_get_nf_upload_url(payload, user_id, session_id)
    elif action == "verify_file":
        return _handle_verify_file(payload)
    else:
        raise ValueError(f"Ação desconhecida: '{action}'. Ações válidas: {', '.join(DIRECT_ACTIONS)}")


@cognitive_sync_handler("inventory_hub")
def _handle_get_nf_upload_url(payload: dict, user_id: str, session_id: str) -> dict:
    """
    Generate presigned PUT URL for file upload.

    🛡️ SECURITY: S3 keys are namespaced by user_id to enforce tenant isolation.
    Pattern: uploads/{user_id}/{session_id}/{safe_filename}

    Args:
        payload: {filename: str, content_type?: str}
        user_id: User identifier for S3 metadata and path namespacing
        session_id: Session identifier for S3 metadata and path namespacing

    Returns:
        {
            "success": true,
            "specialist_agent": "intake",
            "response": {
                "upload_url": "https://...",
                "s3_key": "uploads/{user_id}/{session_id}/...",
                "expires_in": 300
            }
        }

    Raises:
        CognitiveError: If an error occurs (enriched with human_explanation + suggested_fix)
    """
    from agents.tools.intake_tools import ALLOWED_FILE_TYPES
    from tools.s3_client import SGAS3Client

    filename = payload.get("filename")
    if not filename:
        raise ValueError("O nome do arquivo é obrigatório para gerar o link de upload")

    # Validate extension
    if "." not in filename:
        raise ValueError(f"O arquivo '{filename}' não possui extensão. Informe o nome completo (ex: planilha.xlsx)")

    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_FILE_TYPES:
        raise ValueError(f"Tipo de arquivo '.{extension}' não permitido. Formatos aceitos: {', '.join(ALLOWED_FILE_TYPES.keys())}")

    content_type = payload.get("content_type") or ALLOWED_FILE_TYPES.get(
        extension, "application/octet-stream"
    )

    # 🛡️ SECURITY ENFORCEMENT: Actor-Isolated Path
    # Prevent directory traversal by sanitizing filename
    safe_filename = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
    s3_key = f"uploads/{user_id}/{session_id}/{safe_filename}"

    # URL-encode filename to ensure ASCII compliance (S3 metadata RFC 2616)
    # CRITICAL: This encoded value MUST be sent by frontend as x-amz-meta-original_filename header
    encoded_filename = quote(filename, safe="")

    # Build metadata dict (these values are signed into the presigned URL)
    metadata = {
        "user_id": user_id,
        "session_id": session_id,
        "original_filename": encoded_filename,
    }

    # Generate presigned PUT URL
    s3_client = SGAS3Client()
    result = s3_client.generate_upload_url(
        key=s3_key,
        content_type=content_type,
        expires_in=300,  # 5 minutes
        metadata=metadata,
    )

    if not result.get("success"):
        raise RuntimeError(f"Falha ao gerar URL de upload no S3: {result.get('error', 'erro desconhecido')}")

    # Verify tenant isolation (defense in depth)
    if not s3_key.startswith(f"uploads/{user_id}/"):
        logger.error(f"[InventoryHub] Security violation: s3_key={s3_key} not namespaced to user={user_id}")
        raise PermissionError("Violação de segurança: caminho de upload não autorizado para este usuário")

    logger.info(f"[InventoryHub] Mode 2.5 upload URL generated: s3_key={s3_key}")

    # CRITICAL: Return required_headers so frontend sends EXACT values that were signed
    # S3 presigned URLs validate that headers match the signature - any mismatch = 403 Forbidden
    return {
        "success": True,
        "specialist_agent": "intake",
        "response": {
            "upload_url": result["upload_url"],
            "s3_key": result["key"],
            "expires_in": result["expires_in"],
            # Frontend MUST send these exact headers with these exact values
            "required_headers": {
                "Content-Type": content_type,
                "x-amz-meta-original_filename": encoded_filename,
                "x-amz-meta-user_id": user_id,
                "x-amz-meta-session_id": session_id,
            },
        },
    }


@cognitive_sync_handler("inventory_hub")
def _handle_verify_file(payload: dict) -> dict:
    """
    Verify file exists and is ready for processing.

    Args:
        payload: {s3_key: str}

    Returns:
        {
            "success": true,
            "specialist_agent": "intake",
            "response": {
                "exists": true,
                "s3_key": "...",
                "content_type": "...",
                "ready_for_processing": true
            }
        }
    """
    from tools.s3_client import SGAS3Client

    s3_key = payload.get("s3_key")
    if not s3_key:
        raise ValueError("O parâmetro 's3_key' é obrigatório para verificar o arquivo")

    s3_client = SGAS3Client()
    result = s3_client.get_file_metadata(key=s3_key, retry_count=3, retry_delay=1.0)

    if not result.get("success"):
        raise RuntimeError(f"Falha ao verificar arquivo no S3: {result.get('error', 'arquivo não encontrado')}")

    return {
        "success": True,
        "specialist_agent": "intake",
        "response": {
            "exists": result.get("exists", False),
            "s3_key": s3_key,
            "content_type": result.get("content_type"),
            "ready_for_processing": result.get("exists", False),
        },
    }


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
            # Phase 4: Data transformation (Fire-and-Forget)
            transform_import,
            check_import_status,
            check_notifications,
            # Phase 5: Proactive insights (ObservationAgent)
            check_observations,
            request_health_analysis,
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

        # Mode 2.5: Direct action routing (deterministic, no LLM)
        # 🛡️ SECURITY: user_id is passed for tenant-isolated S3 paths
        # CognitiveError handling: exceptions enriched by DebugAgent via @cognitive_sync_handler
        if action in DIRECT_ACTIONS:
            logger.info(
                f"[InventoryHub] Mode 2.5 direct action: action={action}, "
                f"user={user_id}, session={session_id}"
            )
            try:
                return _handle_direct_action(action, payload, user_id, session_id)
            except CognitiveError as e:
                # Error enriched by DebugAgent - return structured response with user-friendly message
                logger.warning(f"[InventoryHub] CognitiveError in Mode 2.5: {e.technical_message}")
                return {
                    "success": False,
                    "error": e.human_explanation,
                    "technical_error": e.technical_message,
                    "suggested_fix": e.suggested_fix,
                    "specialist_agent": "intake",
                    "agent_id": AGENT_ID,
                }

        # Mode 2: Natural language processing via LLM
        # Validate payload with DebugAgent enrichment for user-friendly error messages
        try:
            prompt = _validate_payload(payload)
        except CognitiveError as e:
            # Error enriched by DebugAgent - return structured response with user-friendly message
            logger.warning(f"[InventoryHub] CognitiveError in payload validation: {e.technical_message}")
            return {
                "success": False,
                "error": e.human_explanation,
                "technical_error": e.technical_message,
                "suggested_fix": e.suggested_fix,
                "usage": {
                    "prompt": "Natural language request (e.g., 'Quero fazer upload de um arquivo CSV')",
                    "action": f"Action name (health_check, {', '.join(DIRECT_ACTIONS)})",
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
                    parsed = json.loads(message)
                    # BUG-020: Validate required fields before returning
                    action = payload.get("action", "")
                    validated = _validate_llm_response(parsed, action)
                    # BUG-020 v7 FIX: Wrap in OrchestratorEnvelope format
                    # Frontend expects: { success, specialist_agent, response }
                    # Without this wrapper, extractAgentCoreResponse() doesn't unwrap
                    # and hasValidAnalysisData() checks the outer envelope instead of inner response
                    return {
                        "success": True,
                        "specialist_agent": "llm",
                        "response": validated,
                        "agent_id": AGENT_ID,
                    }
                except json.JSONDecodeError:
                    pass
                except ValueError:
                    # Validation failed - re-raise to be caught by outer except
                    raise
            # =======================================================================
            # BUG-039 FIX: Detect tool failure in LLM text responses
            # =======================================================================
            # When a tool fails, the LLM often generates apologetic text like:
            # "Desculpe, não consegui analisar..." instead of passing the error.
            # This causes "Erro desconhecido" on frontend because success=True.
            #
            # Solution: Detect failure indicators and return proper error envelope.
            # =======================================================================
            failure_indicators = [
                "não consegui",
                "não foi possível",
                "houve um problema",
                "houve um erro",
                "falhou",
                "failed",
                "error occurred",
                "A2A call failed",
            ]
            message_lower = message.lower() if isinstance(message, str) else ""
            is_failure_message = any(indicator in message_lower for indicator in failure_indicators)

            if is_failure_message:
                logger.warning(f"[InventoryHub] BUG-039: LLM text indicates tool failure: {message[:200]}")
                return {
                    "success": False,
                    "error": message,  # Use LLM's explanation as the error message
                    "error_type": "TOOL_FAILURE",
                    "specialist_agent": "llm",
                    "agent_id": AGENT_ID,
                }

            # BUG-020 v8: Envelope for non-JSON text responses (success case)
            return {
                "success": True,
                "specialist_agent": "llm",
                "response": message,
                "agent_id": AGENT_ID,
            }

        # BUG-020 v8: Envelope for fallback (result without .message)
        return {
            "success": True,
            "specialist_agent": "llm",
            "response": str(result),
            "agent_id": AGENT_ID,
        }

    except CognitiveError as e:
        # =======================================================================
        # AUDIT-028 FIX: Preserve DebugAgent enrichment for all CognitiveErrors
        # =======================================================================
        # CognitiveError contains enriched data from DebugAgent:
        # - human_explanation: User-friendly message in pt-BR
        # - suggested_fix: Actionable fix suggestion in pt-BR
        # - error_type: Classification for analytics
        # - recoverable: Whether retry may succeed
        #
        # This catch block ensures enriched errors bubble up to frontend
        # with full context, enabling DebugAnalysisPanel display.
        # =======================================================================
        logger.warning(
            f"[InventoryHub] CognitiveError in invoke: "
            f"type={e.error_type}, recoverable={e.recoverable}, "
            f"message={e.technical_message[:100]}"
        )
        return {
            "success": False,
            "error": e.human_explanation,
            "technical_error": e.technical_message,
            "suggested_fix": e.suggested_fix,
            "specialist_agent": "inventory_hub",
            "agent_id": AGENT_ID,
            # AUDIT-028: Include debug_analysis for DebugAnalysisPanel
            "debug_analysis": {
                "error_signature": f"inventory_hub_{e.error_type}",
                "error_type": e.error_type,
                "technical_explanation": e.technical_message,
                "root_causes": [],  # DebugAgent would populate this
                "debugging_steps": [e.suggested_fix] if e.suggested_fix else [],
                "documentation_links": [],
                "similar_patterns": [],
                "recoverable": e.recoverable,
                "suggested_action": "retry" if e.recoverable else "escalate",
                "llm_powered": True,  # Came from DebugAgent enrichment
            },
            "error_context": {
                "error_type": e.error_type,
                "operation": "inventory_hub_invoke",
                "recoverable": e.recoverable,
            },
        }

    except Exception as e:
        # =======================================================================
        # Fallback for non-enriched exceptions
        # =======================================================================
        # These are exceptions that bypassed the @cognitive_sync_handler
        # (e.g., errors in the agent invocation itself).
        # We still provide structured error but without LLM enrichment.
        # =======================================================================
        debug_error(e, "inventory_hub_invoke", {
            "action": payload.get("action"),
            "prompt_len": len(payload.get("prompt", "")),
        })
        error_type = type(e).__name__
        is_recoverable = isinstance(e, (ValueError, TimeoutError, ConnectionError, OSError))
        return {
            "success": False,
            "error": str(e),
            "technical_error": str(e),
            "agent_id": AGENT_ID,
            # AUDIT-028: Include minimal debug_analysis for consistency
            "debug_analysis": {
                "error_signature": f"inventory_hub_{error_type}",
                "error_type": error_type,
                "technical_explanation": str(e),
                "root_causes": [],
                "debugging_steps": [],
                "documentation_links": [],
                "similar_patterns": [],
                "recoverable": is_recoverable,
                "suggested_action": "retry" if is_recoverable else "escalate",
                "llm_powered": False,  # Not enriched by DebugAgent
            },
            "error_context": {
                "error_type": error_type,
                "operation": "inventory_hub_invoke",
                # BUG-020: ValueError (validation errors) are recoverable - user can retry
                # CRITICAL: Enables "Tentar Novamente" button in Frontend
                "recoverable": is_recoverable,
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
