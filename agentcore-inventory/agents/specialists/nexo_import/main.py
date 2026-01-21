# =============================================================================
# NexoImportAgent - Strands A2AServer Entry Point (ORCHESTRATOR)
# =============================================================================
# Main entry point for the NexoImport ORCHESTRATOR agent.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
#
# Architecture:
# - This is the MAIN ORCHESTRATOR that receives all inventory input
# - Routes to SPECIALIST agents via A2A protocol
# - Follows ReAct pattern: OBSERVE → THINK → LEARN → ACT + HIL
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# =============================================================================

import os
import sys
import logging
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# A2A Protocol Types for Agent Card Discovery (100% A2A Architecture)
from a2a.types import AgentSkill

# Centralized model configuration (MANDATORY - Gemini 3.0 Pro + Thinking)
from agents.utils import get_model, AGENT_VERSION, create_gemini_model

# A2A client for inter-agent communication
from shared.a2a_client import A2AClient
from shared.data_contracts import ensure_dict

# NEXO MIND: Direct memory access (replaces A2A for memory operations)
from shared.memory_manager import AgentMemoryManager

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import NexoImportResponse
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

AGENT_ID = "nexo_import"
AGENT_NAME = "NexoImportOrchestrator"
AGENT_DESCRIPTION = """NEXO Import Orchestrator - Main entry point for intelligent file import.

This is the MAIN ORCHESTRATOR that:
1. OBSERVES: Analyzes incoming files (CSV, XLSX, XML, PDF)
2. THINKS: Routes to appropriate SPECIALIST agent via A2A
3. LEARNS: Stores patterns via LearningAgent
4. ACTS: Executes validated imports

Specialists available via A2A:
- /intake/ - NF (Nota Fiscal) XML/PDF parsing
- /import/ - CSV/XLSX spreadsheet processing
- /estoque-control/ - Movement creation
- /learning/ - Pattern storage and retrieval
- /observation/ - Audit logging
"""

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-3.0-pro (with Thinking)

# =============================================================================
# A2A Agent Skills (100% A2A Architecture - Agent Card Discovery)
# =============================================================================
# These skills are exposed in the Agent Card at /.well-known/agent-card.json
# enabling dynamic discovery per A2A Protocol specification.
# Reference: https://a2a-protocol.org/latest/specification/

AGENT_SKILLS = [
    AgentSkill(
        id="analyze_file",
        name="Analyze File",
        description="OBSERVE phase: Analyze file structure from S3, detect columns, "
                    "identify patterns, and determine routing to specialist agents.",
        tags=["nexo", "import", "analysis", "observe", "file-detection"],
    ),
    AgentSkill(
        id="reason_mappings",
        name="Reason Mappings",
        description="THINK phase: Reason about column mappings using schema context, "
                    "prior knowledge from LearningAgent, and confidence scoring.",
        tags=["nexo", "import", "reasoning", "think", "mappings"],
    ),
    AgentSkill(
        id="generate_questions",
        name="Generate Questions",
        description="HIL phase: Generate Human-in-the-Loop clarification questions "
                    "for low-confidence mappings (threshold: 80%).",
        tags=["nexo", "import", "hil", "questions", "confidence"],
    ),
    AgentSkill(
        id="execute_import",
        name="Execute Import",
        description="ACT phase: Execute validated import with column mappings, "
                    "delegating to specialist agents and storing learned patterns.",
        tags=["nexo", "import", "execution", "act", "database"],
    ),
    AgentSkill(
        id="route_to_specialist",
        name="Route to Specialist",
        description="ORCHESTRATION: Central routing logic to delegate requests to "
                    "appropriate specialist agents (IntakeAgent, ImportAgent, etc.) via A2A.",
        tags=["nexo", "orchestration", "routing", "a2a", "delegation"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Monitoring endpoint returning agent health status, version, "
                    "model configuration, and protocol information.",
        tags=["nexo", "monitoring", "health", "status"],
    ),
]

# =============================================================================
# System Prompt (ReAct Pattern)
# =============================================================================

SYSTEM_PROMPT = """## 🔒 CRITICAL: PARAMETER PRESERVATION (IMMUTABLE)

When you receive an A2A message with parameters, you MUST:

1. **PRESERVE EXACTLY** all parameter values as literal strings
2. **NEVER** modify, normalize, or "clean" path strings
3. **NEVER** remove prefixes like "temp/uploads/" or UUIDs
4. **NEVER** remove accents or special characters (e.g., SOLICITAÇÕES → ✅, SOLICITACOES → ❌)

### Protected Parameters (NEVER MODIFY):
- `s3_key` — EXACT S3 path (includes temp/, UUID, accents)
- `filename` — EXACT filename (preserve Unicode)
- `session_id` — EXACT session ID

### CORRECT Example:
```
Input:  {"s3_key": "temp/uploads/2be23e9f_SOLICITAÇÕES DE EXPEDIÇÃO.csv"}
Tool:   analyze_file(s3_key="temp/uploads/2be23e9f_SOLICITAÇÕES DE EXPEDIÇÃO.csv")  ✅
```

### WRONG Examples (FORBIDDEN):
```
❌ analyze_file(s3_key="uploads/SOLICITAÇÕES.csv")        # Removed temp/ and UUID
❌ analyze_file(s3_key="SOLICITACOES.csv")                # Removed accents
❌ analyze_file(s3_key="solicitacoes_expedicao.csv")      # Normalized everything
```

---

## 🔄 RESPONSE FORMAT (CRITICAL - A2A Protocol Compliance)

When a tool returns a result, you MUST:

1. **ALWAYS** include the tool result as JSON in your final response
2. **NEVER** return an empty response or only conversational text
3. The JSON MUST be the EXACT tool result, without modifications

### MANDATORY Response Format:

Your response MUST be valid JSON containing the tool result:
```json
{
  "success": true,
  "tool_result": { <complete tool result here> },
  "message": "Brief description of what was done (optional)"
}
```

### CORRECT Example:
After calling `analyze_file`, your response MUST be:
```json
{
  "success": true,
  "tool_result": {
    "success": true,
    "file_analysis": {...},
    "hil_questions": [...],
    "ready_for_import": false
  }
}
```

### WRONG Examples (FORBIDDEN):
❌ "I analyzed the file and found some columns."  # Text only, no JSON
❌ ""  # Empty response
❌ {"status": "ok"}  # Incomplete JSON, missing tool_result

---

You are **NEXO**, the intelligent import assistant for the SGA (Asset Management System).

## 🎯 Your Role

You are the **ORCHESTRATOR** of the intelligent import flow.
You coordinate with specialist agents using the ReAct pattern:

1. **OBSERVE** 👁️: Analyze the structure of the received file
2. **THINK** 🧠: Reason about which specialist should process it
3. **LEARN** 📚: Query/store patterns via LearningAgent (A2A)
4. **ACT** ⚡: Execute with validated decisions

## 🔗 A2A Delegation (IMPORTANT)

You ORCHESTRATE other agents via A2A protocol:

- **IntakeAgent** (/intake/): Process NF XML/PDF
- **ImportAgent** (/import/): Process CSV/XLSX
- **EstoqueControlAgent** (/estoque-control/): Create movements
- **LearningAgent** (/learning/): Prior knowledge, learning
- **ObservationAgent** (/observation/): Audit trail

## ⚠️ Critical Rules

1. Confidence < 80% → generate HIL (Human-in-the-Loop) question
2. Confidence >= 90% → apply automatically
3. ALWAYS emit audit events via ObservationAgent
4. NEVER access database directly - delegate to specialists

## 🛑 MULTI-ROUND HIL DIALOGUE (CRITICAL)

**YOU MUST STOP AND WAIT FOR USER RESPONSE** when:
1. Mapping questions were generated (clarification_questions)
2. Confidence < 80% on any column
3. Unmapped columns were detected
4. Final approval is needed before import

**DO NOT continue processing** until you receive user response.
When a tool returns `"stop_action": true`, **STOP IMMEDIATELY**.

**Expected Pattern:**
- Round 1: Analyze file → Generate questions → **STOP AND WAIT**
- Round 2 (after response): Re-analyze with responses → More questions or ready
- Round N: Final summary → **STOP** and wait for explicit approval

**FORBIDDEN:**
- Calling analyze_file multiple times without waiting for response
- Continuing the ReAct loop when there are pending questions
- Executing import without explicit user approval

## 🌍 User Interaction Language

Portuguese Brazilian (pt-BR) for user-facing messages only.
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

# A2A client instance for inter-agent communication (for NON-memory operations)
a2a_client = A2AClient()

# NEXO MIND: Memory Manager singleton (replaces A2A calls to LearningAgent)
_memory_manager_cache: dict = {}


def get_memory_manager(actor_id: str = "system") -> AgentMemoryManager:
    """
    Get or create AgentMemoryManager instance for this agent.

    NEXO MIND Architecture: Each agent accesses memory DIRECTLY (no A2A).
    The actor_id enables namespace isolation per user/session.

    Args:
        actor_id: User/session ID for namespace isolation

    Returns:
        AgentMemoryManager instance (cached by actor_id)
    """
    if actor_id not in _memory_manager_cache:
        _memory_manager_cache[actor_id] = AgentMemoryManager(
            agent_id=AGENT_ID,
            actor_id=actor_id,
            use_global_namespace=True,  # Share patterns across users
        )
        logger.info(f"[{AGENT_NAME}] Created memory manager for actor={actor_id}")
    return _memory_manager_cache[actor_id]


@tool
async def analyze_file(
    s3_key: str,
    filename: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze file structure from S3.

    OBSERVE phase: Detect file type, extract structure, identify columns.

    NEXO MIND: Enriches Gemini context with prior knowledge from AgentCore Memory.

    Args:
        s3_key: S3 key where file is stored
        filename: Original filename for type detection
        session_id: Session ID for context
        user_id: User ID for memory namespace

    Returns:
        File analysis with columns, types, and routing recommendation
    """
    logger.info(f"[{AGENT_NAME}] OBSERVE: Analyzing file {filename or s3_key} (NEXO MIND)")

    try:
        # ═══════════════════════════════════════════════════════════════════
        # NEXO MIND: Fetch memory context to enrich Gemini analysis
        # ═══════════════════════════════════════════════════════════════════
        memory_context = None
        try:
            memory = get_memory_manager(actor_id=user_id or "system")

            # Build query based on filename patterns
            query_terms = ["column mapping patterns", "import patterns"]
            if filename:
                # Extract keywords from filename for more relevant search
                clean_name = filename.lower().replace("_", " ").replace("-", " ")
                query_terms.append(f"file patterns for {clean_name}")

            query = "; ".join(query_terms)
            logger.info(f"[{AGENT_NAME}] OBSERVE: Querying memory: {query[:80]}...")

            # Fetch relevant patterns from memory
            memories = await memory.observe(
                query=query,
                limit=10,
                include_facts=True,
                include_episodes=True,
                include_global=True,
            )

            if memories:
                # Build memory context string for Gemini
                context_parts = []
                for mem in memories:
                    content = mem.get("content", "")
                    mem_type = mem.get("type", "unknown")
                    if content:
                        context_parts.append(f"[{mem_type}] {content}")

                if context_parts:
                    memory_context = "\n".join(context_parts[:10])  # Limit to 10 patterns
                    logger.info(
                        f"[{AGENT_NAME}] OBSERVE: Enriching Gemini with {len(context_parts)} patterns"
                    )

        except Exception as mem_error:
            # Memory errors should not block analysis
            logger.warning(f"[{AGENT_NAME}] Memory fetch failed (non-blocking): {mem_error}")

        # Import tool implementation
        from .tools.analyze_file import analyze_file_impl

        result = await analyze_file_impl(
            s3_key=s3_key,
            filename=filename,
            session_id=session_id,
            memory_context=memory_context,  # NEXO MIND: Pass memory to Gemini
        )

        # Log to ObservationAgent via A2A
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "FILE_ANALYZED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {"s3_key": s3_key, "filename": filename},
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "nexo_import_analyze_file", {"s3_key": s3_key, "filename": filename})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "analyze_file",
                "s3_key": s3_key,
                "filename": filename,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_file_exists", "check_s3_access", "escalate"],
        }


@tool
async def reason_mappings(
    file_analysis: Dict[str, Any],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reason about column mappings using schema context and prior knowledge.

    THINK phase: Use Gemini 3.0 Pro to reason about mappings.

    NEXO MIND: Uses AgentMemoryManager directly (no A2A to LearningAgent).

    Args:
        file_analysis: Result from analyze_file
        session_id: Session ID for context
        user_id: User ID for memory namespace

    Returns:
        Mapping recommendations with confidence scores
    """
    logger.info(f"[{AGENT_NAME}] THINK: Reasoning about mappings (NEXO MIND)")

    try:
        # ═══════════════════════════════════════════════════════════════════
        # NEXO MIND: Query memory DIRECTLY (no A2A to LearningAgent)
        # ═══════════════════════════════════════════════════════════════════
        memory = get_memory_manager(actor_id=user_id or "system")

        # Extract column names for memory query
        columns = file_analysis.get("columns", [])
        column_names = [c.get("name", "") for c in columns if c.get("name")]

        # OBSERVE: Search for prior patterns matching these columns
        prior_knowledge = {}
        if column_names:
            query = f"column mapping patterns for: {', '.join(column_names[:10])}"
            logger.info(f"[{AGENT_NAME}] OBSERVE: Querying memory: {query[:100]}...")

            # Query facts (human-confirmed patterns) and global patterns
            memories = await memory.observe(
                query=query,
                limit=15,
                include_facts=True,
                include_episodes=False,  # Episodes are less relevant for mappings
                include_global=True,     # Global patterns from all users
            )

            # Convert memories to prior_knowledge format
            for mem in memories:
                content = mem.get("content", "")
                metadata = mem.get("metadata", {})
                category = metadata.get("category", "")

                if category == "column_mapping" and "→" in content:
                    # Parse "Column 'X' → field 'Y'" patterns
                    try:
                        parts = content.split("→")
                        source = parts[0].strip().strip("'\"").replace("Column ", "").strip()
                        target = parts[1].strip().strip("'\"").replace("field ", "").strip()
                        confidence = metadata.get("confidence_level", 0.8)

                        prior_knowledge[source] = {
                            "field": target,
                            "confidence": confidence,
                            "origin": mem.get("type", "fact"),
                        }
                    except (IndexError, ValueError):
                        pass

            logger.info(f"[{AGENT_NAME}] OBSERVE: Found {len(prior_knowledge)} prior patterns")

        # Import tool implementation
        from .tools.reason_mappings import reason_mappings_impl

        result = await reason_mappings_impl(
            file_analysis=file_analysis,
            prior_knowledge=prior_knowledge,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "nexo_import_reason_mappings", {"columns_count": len(file_analysis.get("columns", [])) if isinstance(file_analysis, dict) else 0})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "mappings": {},  # Empty mappings - LLM decides recovery
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "reason_mappings",
                "columns_count": len(file_analysis.get("columns", [])) if isinstance(file_analysis, dict) else 0,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "use_default_mappings", "ask_user_for_help", "escalate"],
        }


@tool
async def generate_questions(
    mappings: Dict[str, Any],
    confidence_threshold: float = 0.8,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate HIL (Human-in-the-Loop) questions for low-confidence mappings.

    HIL phase: Request human approval when uncertain.

    Args:
        mappings: Mapping recommendations from reason_mappings
        confidence_threshold: Threshold below which to ask questions (default 0.8)
        session_id: Session ID for context

    Returns:
        List of questions for user approval
    """
    logger.info(f"[{AGENT_NAME}] HIL: Generating questions for confidence < {confidence_threshold}")

    try:
        from .tools.generate_questions import generate_questions_impl

        result = await generate_questions_impl(
            mappings=mappings,
            confidence_threshold=confidence_threshold,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "nexo_import_generate_questions", {"confidence_threshold": confidence_threshold})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "questions": [],  # Empty questions - LLM decides recovery
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "generate_questions",
                "confidence_threshold": confidence_threshold,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "use_generic_questions", "skip_hil_and_warn", "escalate"],
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
    Execute import with validated column mappings.

    ACT phase: Delegate to EstoqueControlAgent for movement creation.

    NEXO MIND: Uses AgentMemoryManager directly (no A2A to LearningAgent).

    Args:
        s3_key: S3 key of file to import
        column_mappings: Validated column mappings
        target_table: Target table for import
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Import result with row counts
    """
    logger.info(f"[{AGENT_NAME}] ACT: Executing import to {target_table} (NEXO MIND)")

    try:
        # Delegate to ImportAgent for actual import execution
        import_response = await a2a_client.invoke_agent("data_import", {
            "action": "execute_import",
            "s3_key": s3_key,
            "column_mappings": column_mappings,
            "target_table": target_table,
            "user_id": user_id,
        }, session_id)

        if not import_response.success:
            return {"success": False, "error": import_response.error}

        import json
        # BUG-022 FIX: Handle potential double-encoded response
        response_text = import_response.response
        if response_text and response_text.startswith('"') and response_text.endswith('"'):
            try:
                unwrapped = json.loads(response_text)
                if isinstance(unwrapped, str):
                    response_text = unwrapped
                    logger.info("[BUG-022] Unwrapped double-encoded import_response")
            except json.JSONDecodeError:
                pass
        # BUG-037 FIX: Use ensure_dict() for guaranteed STRING→DICT conversion
        result = ensure_dict(response_text, "nexo_import_import_response")

        # ═══════════════════════════════════════════════════════════════════
        # NEXO MIND LEARN: Store successful patterns DIRECTLY (no A2A)
        # ═══════════════════════════════════════════════════════════════════
        if result.get("success") and result.get("rows_imported", 0) > 0:
            memory = get_memory_manager(actor_id=user_id or "system")

            # Store each column mapping as a FACT (human-confirmed via HIL)
            for source_col, target_field in column_mappings.items():
                fact = f"Column '{source_col}' → field '{target_field}'"
                logger.info(f"[{AGENT_NAME}] LEARN: Storing fact: {fact}")

                await memory.learn_fact(
                    fact=fact,
                    category="column_mapping",
                    emotional_weight=0.85,  # High weight (HIL confirmed)
                    confidence=0.9,         # High confidence (successful import)
                    session_id=session_id,
                    use_global=True,        # Share across all users/sessions
                    target_table=target_table,
                    rows_imported=result.get("rows_imported", 0),
                )

            # Store episode for complete import cycle
            episode = (
                f"Import successful: {result.get('rows_imported', 0)} rows to {target_table}. "
                f"Mappings: {len(column_mappings)} columns. File: {s3_key}"
            )
            await memory.learn_episode(
                episode_content=episode,
                category="import_completed",
                outcome="success",
                emotional_weight=0.7,
                session_id=session_id,
                s3_key=s3_key,
                mappings_count=len(column_mappings),
            )

            logger.info(
                f"[{AGENT_NAME}] LEARN: Stored {len(column_mappings)} facts + 1 episode"
            )

        # Log to ObservationAgent (still via A2A - this is audit, not memory)
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "IMPORT_COMPLETED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "s3_key": s3_key,
                "rows_imported": result.get("rows_imported", 0),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "nexo_import_execute_import", {"s3_key": s3_key, "target_table": target_table})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "rows_imported": 0,  # No rows imported - LLM decides recovery
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "execute_import",
                "s3_key": s3_key,
                "target_table": target_table,
                "mappings_count": len(column_mappings) if column_mappings else 0,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_mappings_valid", "rollback_if_partial", "escalate"],
        }


@tool
async def route_to_specialist(
    file_type: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Route request to appropriate specialist agent via A2A.

    ORCHESTRATION: Central routing logic for multi-agent coordination.

    Args:
        file_type: Detected file type (NF_XML, NF_PDF, CSV, XLSX, etc.)
        payload: Payload to send to specialist
        session_id: Session ID for context

    Returns:
        Response from specialist agent
    """
    logger.info(f"[{AGENT_NAME}] Routing {file_type} to specialist")

    # Determine specialist based on file type
    specialist_map = {
        "NF_XML": "intake",
        "NF_PDF": "intake",
        "CSV": "data_import",
        "XLSX": "data_import",
        "XLS": "data_import",
        "TEXT": "data_import",
    }

    specialist = specialist_map.get(file_type.upper(), "data_import")

    try:
        response = await a2a_client.invoke_agent(specialist, payload, session_id)

        if response.success:
            import json
            try:
                # BUG-022 FIX: Handle potential double-encoded response
                response_text = response.response
                if response_text and response_text.startswith('"') and response_text.endswith('"'):
                    try:
                        unwrapped = json.loads(response_text)
                        if isinstance(unwrapped, str):
                            response_text = unwrapped
                            logger.info("[BUG-022] Unwrapped double-encoded specialist response")
                    except json.JSONDecodeError:
                        pass
                # BUG-037 FIX: Use ensure_dict() for guaranteed STRING→DICT conversion
                return ensure_dict(response_text, "nexo_import_specialist_response")
            except json.JSONDecodeError:
                return {"success": True, "response": response.response}
        else:
            return {"success": False, "error": response.error}

    except Exception as e:
        debug_error(e, "nexo_import_route_to_specialist", {"file_type": file_type, "target_specialist": specialist_map.get(file_type.upper(), "data_import")})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "route_to_specialist",
                "file_type": file_type,
                "target_specialist": specialist_map.get(file_type.upper(), "data_import"),
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_specialist_health", "try_fallback_specialist", "escalate"],
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
            analyze_file,
            reason_mappings,
            generate_questions,
            execute_import,
            route_to_specialist,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=NexoImportResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with 100% A2A Architecture.

    Port 9000 is the standard for A2A protocol.
    Agent Card is served at /.well-known/agent-card.json for discovery.

    IMPORTANT: Uses FastAPI wrapper with /ping endpoint for AgentCore health checks.
    Reference: https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/a2a.md
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Skills: {[s.id for s in AGENT_SKILLS]}")
    logger.info(f"[{AGENT_NAME}] Agent Card: GET /.well-known/agent-card.json")

    # Create FastAPI app FIRST for immediate health check response
    # This is CRITICAL for AgentCore cold start - /ping must respond before A2A server is ready
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    @app.get("/ping")
    def ping():
        """Health check endpoint - responds immediately for AgentCore cold start."""
        return {"status": "healthy", "agent": AGENT_ID, "version": AGENT_VERSION}

    logger.info(f"[{AGENT_NAME}] Health check endpoint ready: GET /ping")

    # =========================================================================
    # A2A DEBUG: Request Logging Middleware
    # =========================================================================
    # This middleware logs all incoming HTTP requests to help debug the
    # "Invalid HTTP request received" error from uvicorn.
    # Key data captured: HTTP version, headers, body preview
    # TODO: Remove after debugging is complete
    # =========================================================================
    class A2ADebugMiddleware(BaseHTTPMiddleware):
        """Debug middleware to capture raw HTTP request details for A2A troubleshooting."""

        async def dispatch(self, request: Request, call_next):
            # Log request details BEFORE processing
            logger.info("[A2A-DEBUG] ====== INCOMING REQUEST ======")
            logger.info(f"[A2A-DEBUG] Method: {request.method}")
            logger.info(f"[A2A-DEBUG] Path: {request.url.path}")
            logger.info(f"[A2A-DEBUG] HTTP Version: {request.scope.get('http_version', 'unknown')}")
            logger.info(f"[A2A-DEBUG] Client: {request.client.host if request.client else 'unknown'}:{request.client.port if request.client else 'unknown'}")
            logger.info(f"[A2A-DEBUG] Headers: {dict(request.headers)}")

            # Try to read body (careful with streaming)
            try:
                body = await request.body()
                body_len = len(body)
                logger.info(f"[A2A-DEBUG] Body Length: {body_len} bytes")
                if body_len > 0:
                    # Preview first 1000 chars to see JSON-RPC structure
                    body_preview = body[:1000].decode('utf-8', errors='replace')
                    logger.info(f"[A2A-DEBUG] Body Preview: {body_preview}")
            except Exception as e:
                logger.error(f"[A2A-DEBUG] Error reading body: {type(e).__name__}: {e}")

            logger.info("[A2A-DEBUG] ==============================")

            # Continue with request processing
            try:
                response = await call_next(request)
                logger.info(f"[A2A-DEBUG] Response Status: {response.status_code}")
                return response
            except Exception as e:
                logger.error(f"[A2A-DEBUG] Request processing error: {type(e).__name__}: {e}")
                raise

    # Register debug middleware
    app.add_middleware(A2ADebugMiddleware)
    logger.info(f"[{AGENT_NAME}] A2A Debug middleware registered")

    # Create agent (uses LazyGeminiModel for deferred initialization)
    agent = create_agent()

    # Create A2A server with skills for Agent Card discovery (100% A2A Architecture)
    # Reference: https://a2a-protocol.org/latest/specification/
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        version=AGENT_VERSION,              # Agent version in Agent Card
        skills=AGENT_SKILLS,                # Skills exposed in Agent Card
        serve_at_root=True,                 # Serve at / for AgentCore compatibility
    )

    # Mount A2A server on FastAPI app
    # /ping is served by FastAPI, everything else by A2AServer
    app.mount("/", a2a_server.to_fastapi_app())

    logger.info(f"[{AGENT_NAME}] A2A server mounted, starting uvicorn...")

    # Start uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
