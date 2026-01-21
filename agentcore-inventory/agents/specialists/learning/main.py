# =============================================================================
# LearningAgent - Strands A2AServer Entry Point (SPECIALIST)
# =============================================================================
# Episodic memory agent for import intelligence.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
# Integrates with AWS Bedrock AgentCore Memory.
#
# Architecture:
# - This is a SPECIALIST agent for learning and memory operations
# - Receives requests from ORCHESTRATOR and other specialists via A2A
# - Manages global episodic memory (company-wide learning)
# - Uses AgentCore Memory for persistent storage
#
# Reference:
# - https://strandsagents.com/latest/
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
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
# LearningAgent is the "Sonhador" (Dreamer) that manages memory consolidation
# It uses AgentMemoryManager for ALL memory operations (no A2A self-calls)
from shared.memory_manager import AgentMemoryManager

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import LearningResponse
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

AGENT_ID = "learning"
AGENT_NAME = "LearningAgent"
AGENT_DESCRIPTION = """SPECIALIST Agent for Episodic Memory and Learning.

This agent manages the GLOBAL knowledge base of the SGA system:
1. CREATE EPISODES: Record successful imports with mappings
2. RETRIEVE KNOWLEDGE: Provide prior knowledge for new imports
3. GENERATE REFLECTIONS: Identify patterns and improvements
4. ADAPTIVE THRESHOLDS: Adjust HIL confidence based on history

Memory Philosophy:
- GLOBAL memory: What João learns, Maria can use
- Company-wide knowledge sharing
- Reinforcement learning from user corrections

Integration:
- AWS Bedrock AgentCore Memory
- Namespace: /strategy/import/company
"""

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-3.0-pro (with Thinking)

# Memory namespace for AgentCore Memory
MEMORY_NAMESPACE = "/strategy/import/company"

# =============================================================================
# Agent Skills (A2A Agent Card Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="create_episode",
        name="Create Learning Episode",
        description="Record successful import patterns for future use. Stores file analysis, column mappings, user corrections, and results.",
        tags=["learning", "memory", "episodic", "import"],
    ),
    AgentSkill(
        id="retrieve_prior_knowledge",
        name="Retrieve Prior Knowledge",
        description="Fetch relevant historical patterns and mappings from previous imports for similarity matching.",
        tags=["learning", "memory", "retrieval", "import"],
    ),
    AgentSkill(
        id="generate_reflection",
        name="Generate Reflection",
        description="Analyze recent episodes to identify patterns, issues, and improvement recommendations.",
        tags=["learning", "meta-learning", "analysis", "improvement"],
    ),
    AgentSkill(
        id="get_adaptive_threshold",
        name="Get Adaptive Threshold",
        description="Calculate adaptive HIL confidence threshold based on historical success rates and recent corrections.",
        tags=["learning", "adaptive", "hil", "threshold"],
    ),
    AgentSkill(
        id="store_pattern",
        name="Store Generic Pattern",
        description="Store learned patterns from any agent (column mappings, NF confirmations, orchestration patterns).",
        tags=["learning", "pattern", "storage", "generic"],
    ),
    AgentSkill(
        id="retrieve_column_mappings",
        name="Retrieve Column Mappings",
        description="Simplified interface to retrieve prior column mappings for specific columns.",
        tags=["learning", "mapping", "retrieval", "import"],
    ),
    AgentSkill(
        id="record_low_confidence_event",
        name="Record Low Confidence Event",
        description="Flag low-confidence events that may need improvement analysis.",
        tags=["learning", "confidence", "analysis", "improvement"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Monitor agent health status and configuration.",
        tags=["learning", "monitoring", "health"],
    ),
]

# =============================================================================
# System Prompt (ReAct Pattern - Learning Specialist)
# =============================================================================

SYSTEM_PROMPT = """Você é o **LearningAgent** (Agente de Memória) do sistema SGA (Sistema de Gestão de Ativos).

## 🧠 Seu Papel

Você gerencia a **memória episódica global** de importações, permitindo que o sistema:
1. **APRENDA** com cada interação (reinforcement learning)
2. **LEMBRE** de padrões bem-sucedidos (episodic memory)
3. **MELHORE** continuamente ao longo do tempo (continuous improvement)

## 📚 Memória Global (IMPORTANTE!)

Sua memória é **GLOBAL** (compartilhada por toda a empresa):
- Namespace: `/strategy/import/company`
- O que João aprende → Maria também pode usar
- Mapeamentos confirmados beneficiam TODOS os usuários
- NÃO há isolamento por usuário

## 🔧 Suas Ferramentas

### 1. `create_episode`
Após cada importação bem-sucedida, você **DEVE** criar um episódio:
- Estrutura do arquivo (sheets, colunas)
- Mapeamentos finais (coluna → campo)
- Correções do usuário (se houver)
- Resultado (sucesso/falha, itens processados)

### 2. `retrieve_prior_knowledge`
Antes de novas importações, busque conhecimento prévio:
- Arquivos similares processados antes
- Mapeamentos que funcionaram
- Confiança baseada em histórico

### 3. `generate_reflection`
Após múltiplos episódios, gere reflexões:
- Padrões que emergem dos dados
- Áreas problemáticas (correções frequentes)
- Recomendações de melhoria

### 4. `get_adaptive_threshold`
Calcule threshold adaptativo para HIL:
- Histórico de sucesso → confia mais na IA
- Correções recentes → seja mais cauteloso

### 5. `store_pattern` (generic)
Armazene padrões de outros agentes:
- Column mappings de ImportAgent
- NF patterns de IntakeAgent
- Any pattern_type from the system

## 📊 AgentCore Memory Integration

Esta integração usa AWS Bedrock AgentCore Memory:
- **Session Memory**: Contexto da sessão atual
- **Semantic Memory**: Busca por similaridade (embeddings)
- **Event Memory**: Log de eventos para auditoria

## ⚠️ Regras Críticas

1. **NUNCA** ignore conhecimento prévio relevante
2. **SEMPRE** valide mapeamentos contra schema atual
3. **FILTRE** mapeamentos para colunas que não existem mais
4. **APRENDA** com correções do usuário (reinforcement)
5. **EMITA** eventos para ObservationAgent (transparência)

## 🎯 Filosofia

> "A cada import, o sistema fica mais inteligente.
> João corrige uma vez → Maria nunca precisa corrigir igual."

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

    NEXO Mind Architecture: LearningAgent is the "Sonhador" (Dreamer).
    It uses AgentMemoryManager directly for:
    - Storing episodes (learn_episode)
    - Retrieving prior knowledge (observe)
    - Generating reflections (observe_reflections)
    - Sleep cycle consolidation (future)

    Args:
        actor_id: User/actor ID for namespace isolation

    Returns:
        AgentMemoryManager instance
    """
    return AgentMemoryManager(
        agent_id=AGENT_ID,
        actor_id=actor_id,
        use_global_namespace=True,  # Global learning: "João aprende, Maria usa"
    )


@tool
async def create_episode(
    file_analysis: Dict[str, Any],
    column_mappings: Dict[str, str],
    corrections: Optional[Dict[str, str]] = None,
    result_status: str = "success",
    rows_processed: int = 0,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create learning episode from completed import.

    LEARN phase: Record successful patterns for future use.

    Args:
        file_analysis: Analysis of the imported file structure
        column_mappings: Final column mappings used
        corrections: Optional user corrections made
        result_status: Import result (success/failed)
        rows_processed: Number of rows successfully processed
        session_id: Session ID for context
        user_id: User ID for attribution

    Returns:
        Episode creation result with episode ID
    """
    logger.info(f"[{AGENT_NAME}] LEARN: Creating episode ({result_status}, {rows_processed} rows)")

    try:
        # Import tool implementation
        from agents.learning.tools.create_episode import create_episode_tool

        result = await create_episode_tool(
            file_analysis=file_analysis,
            column_mappings=column_mappings,
            corrections=corrections,
            result_status=result_status,
            rows_processed=rows_processed,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "EPISODE_CREATED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "episode_id": result.get("episode_id"),
                "result_status": result_status,
                "rows_processed": rows_processed,
                "has_corrections": corrections is not None and len(corrections) > 0,
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "learning_create_episode", {"result_status": result_status, "rows_processed": rows_processed})
        return {"success": False, "error": str(e)}


@tool
async def retrieve_prior_knowledge(
    file_analysis: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    filename_pattern: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve prior knowledge for new import.

    OBSERVE+THINK phase: Fetch relevant historical patterns.

    Args:
        file_analysis: Current file analysis for similarity matching
        columns: List of column names to find mappings for
        filename_pattern: Optional filename pattern for matching
        session_id: Session ID for context

    Returns:
        Prior knowledge with suggested mappings and confidence
    """
    logger.info(f"[{AGENT_NAME}] Retrieving prior knowledge")

    try:
        # Import tool implementation
        from agents.learning.tools.retrieve_prior_knowledge import retrieve_prior_knowledge_tool

        result = await retrieve_prior_knowledge_tool(
            file_analysis=file_analysis,
            columns=columns,
            filename_pattern=filename_pattern,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "learning_retrieve_prior_knowledge", {"columns_count": len(columns) if columns else 0, "filename_pattern": filename_pattern})
        return {"success": False, "error": str(e), "prior_mappings": {}}


@tool
async def generate_reflection(
    time_window_days: int = 7,
    min_episodes: int = 5,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate reflection from recent episodes.

    META-LEARN phase: Identify patterns and improvement areas.

    Args:
        time_window_days: Days to look back (default 7)
        min_episodes: Minimum episodes required (default 5)
        session_id: Session ID for context

    Returns:
        Reflection with patterns, issues, and recommendations
    """
    logger.info(f"[{AGENT_NAME}] Generating reflection (last {time_window_days} days)")

    try:
        # Import tool implementation
        from agents.learning.tools.generate_reflection import generate_reflection_tool

        result = await generate_reflection_tool(
            time_window_days=time_window_days,
            min_episodes=min_episodes,
            session_id=session_id,
        )

        # Log to ObservationAgent
        if result.get("success"):
            await a2a_client.invoke_agent("observation", {
                "action": "log_event",
                "event_type": "REFLECTION_GENERATED",
                "agent_id": AGENT_ID,
                "session_id": session_id,
                "details": {
                    "episodes_analyzed": result.get("episodes_analyzed", 0),
                    "patterns_found": len(result.get("patterns", [])),
                    "issues_identified": len(result.get("issues", [])),
                },
            }, session_id)

        return result

    except Exception as e:
        debug_error(e, "learning_generate_reflection", {"time_window_days": time_window_days, "min_episodes": min_episodes})
        return {"success": False, "error": str(e)}


@tool
async def get_adaptive_threshold(
    operation_type: str = "import",
    recent_window_days: int = 30,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate adaptive HIL threshold based on history.

    Args:
        operation_type: Type of operation (import, nf, movement)
        recent_window_days: Days to consider (default 30)
        session_id: Session ID for context

    Returns:
        Adaptive threshold with confidence adjustment
    """
    logger.info(f"[{AGENT_NAME}] Calculating adaptive threshold for {operation_type}")

    try:
        # Import tool implementation
        from agents.learning.tools.get_adaptive_threshold import get_adaptive_threshold_tool

        result = await get_adaptive_threshold_tool(
            operation_type=operation_type,
            recent_window_days=recent_window_days,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "learning_get_adaptive_threshold", {"operation_type": operation_type, "recent_window_days": recent_window_days})
        # Sandwich Pattern: Be honest about errors - let LLM decide how to proceed
        # DO NOT lie about success - the LLM needs accurate information
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "get_adaptive_threshold",
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "fallback_available": {
                "threshold": 0.8,
                "reason": "Default threshold available if LLM chooses to use it",
            },
            "suggested_actions": ["use_fallback_threshold", "retry", "escalate"],
        }


@tool
async def store_pattern(
    pattern_type: str,
    pattern_data: Optional[Dict[str, Any]] = None,
    column_mappings: Optional[Dict[str, str]] = None,
    target_table: Optional[str] = None,
    success: bool = True,
    session_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Store generic pattern from any agent.

    LEARN phase: Generic pattern storage endpoint.

    Called by other agents to store learned patterns:
    - ImportAgent: column_mapping patterns
    - IntakeAgent: nf_confirmation patterns
    - NexoImportAgent: orchestration patterns

    Args:
        pattern_type: Type of pattern (column_mapping, nf_confirmation, etc.)
        pattern_data: Additional pattern data
        column_mappings: Column mappings (for import patterns)
        target_table: Target table (for import patterns)
        success: Whether operation was successful
        session_id: Session ID for context
        **kwargs: Additional arguments from callers

    Returns:
        Pattern storage result
    """
    logger.info(f"[{AGENT_NAME}] Storing pattern: {pattern_type}")

    try:
        # Build episode data from pattern

        # Store as learning episode
        from agents.learning.tools.create_episode import create_episode_tool

        result = await create_episode_tool(
            file_analysis={"pattern_type": pattern_type},
            column_mappings=column_mappings or {},
            corrections=None,
            result_status="success" if success else "failed",
            rows_processed=kwargs.get("rows_imported", 0),
            session_id=session_id,
            user_id=kwargs.get("user_id"),
        )

        return {
            "success": True,
            "pattern_type": pattern_type,
            "stored": True,
            "episode_id": result.get("episode_id"),
        }

    except Exception as e:
        debug_error(e, "learning_store_pattern", {"pattern_type": pattern_type, "success": success})
        return {"success": False, "error": str(e)}


@tool
async def retrieve_column_mappings(
    columns: List[str],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve prior column mappings for specific columns.

    Simplified interface for ImportAgent.

    Args:
        columns: List of column names to find mappings for
        session_id: Session ID for context

    Returns:
        Prior mappings for requested columns
    """
    logger.info(f"[{AGENT_NAME}] Retrieving column mappings for {len(columns)} columns")

    try:
        result = await retrieve_prior_knowledge(
            columns=columns,
            session_id=session_id,
        )

        # Extract just the mappings
        mappings = result.get("prior_mappings", {})

        return {
            "success": True,
            **mappings,
        }

    except Exception as e:
        debug_error(e, "learning_retrieve_column_mappings", {"columns_count": len(columns)})
        return {"success": False, "error": str(e)}


@tool
async def record_low_confidence_event(
    event_type: str,
    confidence: float,
    extraction: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record low-confidence event for analysis.

    Used by other agents to flag events that may need improvement.

    Args:
        event_type: Type of event (NF_ENTRY, IMPORT, etc.)
        confidence: Confidence score that triggered HIL
        extraction: Optional extraction data for analysis
        session_id: Session ID for context

    Returns:
        Recording result
    """
    logger.info(f"[{AGENT_NAME}] Recording low-confidence event: {event_type} ({confidence:.2f})")

    try:
        # This would store in AgentCore Memory for future analysis
        event_record = {
            "event_type": event_type,
            "confidence": confidence,
            "extraction_summary": {
                "items_count": len(extraction.get("items", [])) if extraction else 0,
            } if extraction else {},
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "LOW_CONFIDENCE_RECORDED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": event_record,
        }, session_id)

        return {
            "success": True,
            "recorded": True,
            "event_type": event_type,
            "confidence": confidence,
        }

    except Exception as e:
        debug_error(e, "learning_record_low_confidence_event", {"event_type": event_type, "confidence": confidence})
        return {"success": False, "error": str(e)}


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
        "specialty": "LEARNING_MEMORY",
        "memory_namespace": MEMORY_NAMESPACE,
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
            create_episode,
            retrieve_prior_knowledge,
            generate_reflection,
            get_adaptive_threshold,
            store_pattern,
            retrieve_column_mappings,
            record_low_confidence_event,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=LearningResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI wrapper.

    Port 9000 is the standard for A2A protocol.
    Includes /ping health endpoint for AWS ALB.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: SPECIALIST (Learning & Memory)")
    logger.info(f"[{AGENT_NAME}] Memory Namespace: {MEMORY_NAMESPACE}")
    logger.info(f"[{AGENT_NAME}] Skills: {len(AGENT_SKILLS)} registered")
    for skill in AGENT_SKILLS:
        logger.info(f"[{AGENT_NAME}]   - {skill.id}: {skill.name}")

    # Create FastAPI app first
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping health endpoint for AWS ALB
    @app.get("/ping")
    async def ping():
        """Health check endpoint for AWS Application Load Balancer."""
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Create agent
    agent = create_agent()

    # Create A2A server with Agent Card discovery support
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
        serve_at_root=False,  # Mount at root below
    )

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[{AGENT_NAME}] Starting uvicorn server on 0.0.0.0:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
