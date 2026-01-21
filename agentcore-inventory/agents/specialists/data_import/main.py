# =============================================================================
# ImportAgent - Strands A2AServer Entry Point (SPECIALIST)
# =============================================================================
# Bulk CSV/Excel importer specialist agent.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
#
# Architecture:
# - This is a SPECIALIST agent for spreadsheet imports
# - Receives requests from ORCHESTRATOR (NexoImportAgent) via A2A
# - Handles CSV, XLSX, XLS file processing
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# =============================================================================

import os
import sys
import logging
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill
from fastapi import FastAPI
import uvicorn

# Centralized model configuration (MANDATORY - Gemini 3.0 Pro + Thinking)
from agents.utils import get_model, AGENT_VERSION, create_gemini_model

# A2A client for inter-agent communication
from shared.a2a_client import A2AClient

# NEXO Mind - Direct Memory Access (Hippocampus)
from shared.memory_manager import AgentMemoryManager

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import DataImportResponse
from shared.debug_utils import debug_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "data_import"
AGENT_NAME = "ImportAgent"
AGENT_DESCRIPTION = """SPECIALIST Agent for Bulk Spreadsheet Imports.

This agent processes inventory data from CSV/Excel files:
1. PREVIEW: Analyze file structure, detect columns, suggest mappings
2. DETECT: Auto-detect delimiters, encoding, and column purposes
3. MATCH: Match rows to existing part numbers
4. EXECUTE: Process validated imports, create movements

Features:
- Auto-detect CSV delimiters (comma, semicolon, tab)
- Excel support (XLSX, XLS)
- Intelligent column mapping with AI
- Part number fuzzy matching (≥80% similarity)
- Memory integration for learning patterns
"""

# Agent Skills for A2A Discovery
AGENT_SKILLS = [
    AgentSkill(
        id="preview_import",
        name="Preview Import File",
        description="Analyze file structure before import: detect format (CSV/XLSX/XLS), identify delimiters and encoding, suggest column mappings, calculate preview statistics. OBSERVE phase of ReAct pattern.",
        tags=["import", "spreadsheet", "preview", "csv", "excel", "observe"],
    ),
    AgentSkill(
        id="detect_columns",
        name="Detect Column Purposes",
        description="Detect column purposes using AI and prior learning: map source columns to target fields (part_number, description, quantity, serial_number, location, project_id, unit_price). THINK phase of ReAct pattern.",
        tags=["import", "spreadsheet", "column-mapping", "ai", "think"],
    ),
    AgentSkill(
        id="match_rows_to_pn",
        name="Match Rows to Part Numbers",
        description="Match import rows to existing part numbers: exact match by code, fuzzy match by description (≥80% similarity), return matched and unmatched rows with confidence scores. MATCH phase of ReAct pattern.",
        tags=["import", "spreadsheet", "matching", "part-number", "fuzzy-match"],
    ),
    AgentSkill(
        id="execute_import",
        name="Execute Validated Import",
        description="Execute validated import: process file, create inventory entries, handle serialized items, update balances, generate statistics, learn successful patterns. ACT phase of ReAct pattern.",
        tags=["import", "spreadsheet", "execute", "inventory", "act"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Health check endpoint for monitoring agent status, version, model, protocol, and specialty.",
        tags=["import", "health", "monitoring", "status"],
    ),
]

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-3.0-pro (with Thinking)

# =============================================================================
# System Prompt (ReAct Pattern - Import Specialist)
# =============================================================================

SYSTEM_PROMPT = """Você é o **ImportAgent** do sistema Faiston SGA (Sistema de Gestão de Ativos).

## 🎯 Seu Papel

Você é o **ESPECIALISTA** em importação de planilhas (CSV/Excel).
Segue o padrão ReAct para processar arquivos tabulares:

1. **OBSERVE** 👁️: Analise estrutura do arquivo (colunas, delimitadores)
2. **THINK** 🧠: Mapeie colunas para campos do sistema
3. **MATCH** 🔗: Associe linhas a part numbers existentes
4. **ACT** ⚡: Execute importação ou route para HIL

## 🔧 Suas Ferramentas

### 1. `preview_import`
Analisa arquivo antes da importação:
- Detecta formato (CSV, XLSX, XLS)
- Identifica delimitadores e encoding
- Sugere mapeamento de colunas
- Calcula estatísticas prévias

### 2. `detect_columns`
Detecção inteligente de colunas:
- "codigo", "part_number", "pn" → part_number
- "descricao", "description", "nome" → description
- "quantidade", "qty", "qtd" → quantity
- "serial", "ns", "sn" → serial_number
- "localizacao", "location" → location
- "projeto", "project" → project_id

### 3. `match_rows_to_pn`
Associação de linhas a part numbers:
- Match exato por código
- Match fuzzy por descrição (≥80% similaridade)
- Mapeamento manual para não-encontrados

### 4. `execute_import`
Executa importação validada:
- Cria movimentações por linha
- Trata itens serializados
- Atualiza saldos de inventário
- Gera estatísticas de importação

## 📊 Regras de Negócio

### Quantidade
- Positivo = entrada (ENTRY)
- Negativo = saída (EXIT)
- Zero = ignorar linha

### Serialização
- Um serial por linha se serializado
- Múltiplos seriais separados por vírgula/ponto-vírgula
- Auto-geração se configurado

### Localização
- Deve existir na tabela de localizações
- Default: ESTOQUE_CENTRAL se não especificado

## ⚠️ Regras Críticas

1. **SEMPRE** valide encoding UTF-8/Latin-1
2. **SEMPRE** detecte delimitador antes de processar
3. Linhas com erro → log e continuar (não abortar)
4. Para movimentações → delegar ao EstoqueControlAgent via A2A
5. Após sucesso → registrar padrão no LearningAgent

## 🌍 Linguagem

Português brasileiro (pt-BR) para interações com usuário.
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

# A2A client instance for inter-agent communication
a2a_client = A2AClient()


def _get_memory(actor_id: str = "system") -> AgentMemoryManager:
    """
    Get AgentMemoryManager instance for direct memory access.

    NEXO Mind Architecture: Each agent has its own "hippocampal" connection
    to the shared brain (AgentCore Memory). No A2A gargalo!

    Args:
        actor_id: User/actor ID for namespace isolation

    Returns:
        AgentMemoryManager instance
    """
    return AgentMemoryManager(
        agent_id=AGENT_ID,
        actor_id=actor_id,
        use_global_namespace=True,  # Share patterns across users
    )


@tool
async def preview_import(
    s3_key: str,
    filename: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Preview file before import.

    OBSERVE phase: Analyze file structure without modifying data.

    Args:
        s3_key: S3 key where file is stored
        filename: Original filename for type detection
        session_id: Session ID for context

    Returns:
        Preview with columns, sample rows, and suggested mappings
    """
    logger.info(f"[{AGENT_NAME}] OBSERVE: Previewing {filename or s3_key}")

    try:
        # Import tool implementation
        from agents.data_import.tools.preview_import import preview_import_tool

        result = await preview_import_tool(
            s3_key=s3_key,
            filename=filename,
            session_id=session_id,
        )

        # Log to ObservationAgent via A2A
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "FILE_PREVIEWED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "s3_key": s3_key,
                "filename": filename,
                "columns_detected": len(result.get("columns", [])),
                "rows_count": result.get("total_rows", 0),
            },
        }, session_id)

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] preview_import failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "preview_import",
                "s3_key": s3_key,
                "filename": filename,
                "session_id": session_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError, FileNotFoundError)),
            },
            "suggested_actions": ["retry", "check_s3_permissions", "verify_file_format", "escalate"],
        }


@tool
async def detect_columns(
    columns: List[str],
    sample_data: Optional[List[Dict[str, Any]]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect column purposes using AI.

    THINK phase: Map source columns to target fields.

    Args:
        columns: List of column names from file
        sample_data: Optional sample rows for context
        session_id: Session ID for context

    Returns:
        Column mapping suggestions with confidence scores
    """
    logger.info(f"[{AGENT_NAME}] THINK: Detecting column purposes")

    try:
        # NEXO Mind: Direct memory access for prior column mappings
        memory = _get_memory()
        prior_mappings = {}

        # OBSERVE: Query memory for patterns on these column names
        for col in columns:
            prior_patterns = await memory.observe(
                query=f"column mapping for '{col}'",
                limit=3,
                include_facts=True,
                include_episodes=False,
                include_global=True,  # Company-wide patterns
            )

            # Extract mapping from prior knowledge
            for pattern in prior_patterns:
                content = pattern.get("content", "")
                # Parse patterns like "Column 'SERIAL' → 'serial_number'"
                if "→" in content and col.lower() in content.lower():
                    parts = content.split("→")
                    if len(parts) == 2:
                        target = parts[1].strip().strip("'\"")
                        prior_mappings[col.lower()] = target
                        logger.info(f"[{AGENT_NAME}] Memory found: {col} → {target}")
                        break

        # Import tool implementation (if exists)
        try:
            from agents.data_import.tools.detect_columns import detect_columns_tool
            result = await detect_columns_tool(
                columns=columns,
                sample_data=sample_data,
                prior_mappings=prior_mappings,
                session_id=session_id,
            )
        except ImportError:
            # Fallback: Basic detection
            result = _basic_column_detection(columns, prior_mappings)

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] detect_columns failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "mappings": {},
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "detect_columns",
                "columns": columns,
                "session_id": session_id,
                "has_sample_data": sample_data is not None,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "use_basic_mapping", "request_manual_mapping", "escalate"],
        }


def _basic_column_detection(
    columns: List[str],
    prior_mappings: Dict[str, str]
) -> Dict[str, Any]:
    """Basic column detection fallback."""
    mappings = {}
    confidence = {}

    column_patterns = {
        "part_number": ["codigo", "part_number", "pn", "code", "cod", "partnumber"],
        "description": ["descricao", "description", "nome", "name", "desc"],
        "quantity": ["quantidade", "qty", "qtd", "quant", "quantity"],
        "serial_number": ["serial", "ns", "sn", "serial_number", "serialnumber"],
        "location": ["localizacao", "location", "local", "loc"],
        "project_id": ["projeto", "project", "proj", "project_id"],
        "unit_price": ["preco", "price", "valor", "value", "unit_price"],
    }

    for col in columns:
        col_lower = col.lower().strip()

        # Check prior mappings first
        if col_lower in prior_mappings:
            mappings[col] = prior_mappings[col_lower]
            confidence[col] = 0.95
            continue

        # Pattern matching
        matched = False
        for target, patterns in column_patterns.items():
            if col_lower in patterns or any(p in col_lower for p in patterns):
                mappings[col] = target
                confidence[col] = 0.85
                matched = True
                break

        if not matched:
            mappings[col] = None
            confidence[col] = 0.0

    return {
        "success": True,
        "mappings": mappings,
        "confidence": confidence,
        "unmapped": [c for c, m in mappings.items() if m is None],
    }


@tool
async def match_rows_to_pn(
    rows: List[Dict[str, Any]],
    column_mappings: Dict[str, str],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Match import rows to existing part numbers.

    MATCH phase: Associate each row with inventory part numbers.

    Args:
        rows: List of row data from file
        column_mappings: Validated column mappings
        session_id: Session ID for context

    Returns:
        Match results with part number associations
    """
    logger.info(f"[{AGENT_NAME}] MATCH: Associating {len(rows)} rows to part numbers")

    try:
        # Import tool implementation (if exists)
        try:
            from agents.data_import.tools.match_rows import match_rows_to_pn_tool
            result = await match_rows_to_pn_tool(
                rows=rows,
                column_mappings=column_mappings,
                session_id=session_id,
            )
        except ImportError:
            # Fallback: Return rows as-is with no matches
            result = {
                "success": True,
                "matched_rows": [],
                "unmatched_rows": rows,
                "match_rate": 0.0,
            }

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] match_rows_to_pn failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "matched_rows": [],
            "unmatched_rows": rows,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "match_rows_to_pn",
                "row_count": len(rows),
                "column_mappings": column_mappings,
                "session_id": session_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "skip_matching", "manual_review", "escalate"],
        }


@tool
async def execute_import(
    s3_key: str,
    column_mappings: Dict[str, str],
    target_table: str = "pending_entry_items",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute validated import.

    ACT phase: Process file and create inventory entries.

    Args:
        s3_key: S3 key of file to import
        column_mappings: Validated column mappings
        target_table: Target table for import
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Import result with statistics
    """
    logger.info(f"[{AGENT_NAME}] ACT: Executing import to {target_table}")

    try:
        # Import tool implementation
        from agents.data_import.tools.execute_import import execute_import_tool

        result = await execute_import_tool(
            s3_key=s3_key,
            column_mappings=column_mappings,
            target_table=target_table,
            session_id=session_id,
            user_id=user_id,
        )

        # NEXO Mind: LEARN - Store successful patterns directly in memory
        if result.get("success") and result.get("rows_imported", 0) > 0:
            memory = _get_memory(actor_id=user_id or "system")

            # Store each column mapping as a confirmed FACT
            for source_col, target_field in column_mappings.items():
                if target_field:  # Only store successful mappings
                    await memory.learn_fact(
                        fact=f"Column '{source_col}' → '{target_field}'",
                        category="column_mapping",
                        emotional_weight=0.8,  # Confirmed by successful import
                        session_id=session_id,
                    )

            # Store the overall import episode
            await memory.learn_episode(
                episode_content=(
                    f"Import successful: {result.get('rows_imported', 0)} rows "
                    f"to {target_table} with mappings: {column_mappings}"
                ),
                category="import_completed",
                outcome="success",
                emotional_weight=0.7,
                session_id=session_id,
            )
            logger.info(f"[{AGENT_NAME}] LEARNED: Stored {len(column_mappings)} patterns in memory")

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "IMPORT_COMPLETED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "s3_key": s3_key,
                "rows_imported": result.get("rows_imported", 0),
                "rows_failed": result.get("rows_failed", 0),
            },
        }, session_id)

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] execute_import failed: {e}", exc_info=True)
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "rows_imported": 0,
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "execute_import",
                "s3_key": s3_key,
                "target_table": target_table,
                "column_mappings": column_mappings,
                "session_id": session_id,
                "user_id": user_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "validate_mappings", "check_database", "rollback", "escalate"],
        }


@tool
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring.

    Returns:
        Health status with agent info
    """
    return {
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "model": MODEL_ID,
        "protocol": "A2A",
        "port": 9000,
        "role": "SPECIALIST",
        "specialty": "SPREADSHEET_IMPORT",
    }


# =============================================================================
# Strands Agent Configuration
# =============================================================================

def create_agent() -> Agent:
    """
    Create Strands Agent with all tools.

    Returns:
        Configured Strands Agent with hooks (ADR-002)
    """
    return Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # GeminiModel via Google AI Studio
        tools=[
            preview_import,
            detect_columns,
            match_rows_to_pn,
            execute_import,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=DataImportResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI wrapper.

    Port 9000 is the standard for A2A protocol.
    Includes /ping endpoint for health checks.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: SPECIALIST (Spreadsheet Import)")
    logger.info(f"[{AGENT_NAME}] Skills: {len(AGENT_SKILLS)} registered")
    for skill in AGENT_SKILLS:
        logger.info(f"[{AGENT_NAME}]   - {skill.id}: {skill.name}")

    # Create FastAPI app
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping endpoint for health checks
    @app.get("/ping")
    async def ping():
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Create agent
    agent = create_agent()

    # Create A2A server with version and skills
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        serve_at_root=False,  # We'll mount it at / manually
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
    )

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[{AGENT_NAME}] Health check available at /ping")
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
