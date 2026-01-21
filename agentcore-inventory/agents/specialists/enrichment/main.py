# =============================================================================
# EnrichmentAgent - Strands A2AServer Entry Point (CRITICAL)
# =============================================================================
# Equipment data enrichment agent using Tavily AI search.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
#
# Architecture:
# - This is a CRITICAL agent for equipment enrichment workflows
# - Uses Tavily via AgentCore Gateway (Gateway-first pattern)
# - Stores enrichment data to S3 Knowledge Repository
# - Triggers Bedrock Knowledge Base sync for RAG queries
#
# Event Flow:
# 1. EventBridge triggers this agent when import completes
# 2. Agent retrieves new equipment from PostgreSQL
# 3. Agent enriches each item via Tavily search
# 4. Results stored in S3, KB sync triggered
# 5. NEXO Assistant can query enriched data via RAG
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# - PRD: product-development/current-feature/PRD-tavily-enrichment.md
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

# Centralized model configuration (MANDATORY - Gemini 2.5 Pro for complex reasoning)
from agents.utils import get_model, AGENT_VERSION, create_gemini_model

# A2A client for inter-agent communication
from shared.a2a_client import A2AClient

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import EnrichmentResponse
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

AGENT_ID = "enrichment"
AGENT_NAME = "EnrichmentAgent"
AGENT_DESCRIPTION = """CRITICAL Agent for Equipment Data Enrichment.

This agent handles:
1. ENRICH: Enrich equipment data with specifications, manuals, and documentation
2. BATCH: Batch enrichment for post-import workflows
3. SYNC: Trigger Bedrock Knowledge Base synchronization
4. VALIDATE: Validate part numbers via web search

Features:
- AI-powered web search via Tavily (Gateway-first)
- Automatic datasheet and manual discovery
- S3 Knowledge Repository storage
- Bedrock KB integration for RAG queries
- EventBridge trigger support for automation
"""

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-2.5-pro (complex reasoning, CRITICAL)

# Agent skills for Agent Card discovery
AGENT_SKILLS = [
    AgentSkill(
        name="enrich_equipment",
        description="Enrich a single equipment item with documentation, specifications, and datasheets from official sources",
        parameters={
            "part_number": {"type": "string", "description": "Equipment part number (e.g., C9200-24P)", "required": True},
            "serial_number": {"type": "string", "description": "Optional serial number for tracking", "required": False},
            "manufacturer_hint": {"type": "string", "description": "Optional manufacturer name to improve search accuracy", "required": False},
            "store_to_s3": {"type": "boolean", "description": "Store enrichment results to S3 (default: true)", "required": False},
            "download_documents": {"type": "boolean", "description": "Download PDF documents (default: false)", "required": False},
            "session_id": {"type": "string", "description": "Session ID for context tracking", "required": False},
        },
        returns={"type": "object", "description": "EnrichmentResult with status, specifications, documents, and confidence score"},
    ),
    AgentSkill(
        name="enrich_batch",
        description="Batch enrichment for multiple equipment items (typically after import completion)",
        parameters={
            "items": {"type": "array", "description": "List of items with part_number, serial_number, manufacturer", "required": True},
            "import_id": {"type": "string", "description": "Import transaction ID for tracking", "required": True},
            "tenant_id": {"type": "string", "description": "Tenant identifier", "required": True},
            "trigger_kb_sync": {"type": "boolean", "description": "Trigger KB sync after completion (default: true)", "required": False},
            "session_id": {"type": "string", "description": "Session ID for context tracking", "required": False},
        },
        returns={"type": "object", "description": "BatchEnrichmentResult with statistics and individual results"},
    ),
    AgentSkill(
        name="sync_knowledge_base",
        description="Trigger Bedrock Knowledge Base synchronization to index new documents",
        parameters={
            "knowledge_base_id": {"type": "string", "description": "Optional KB ID (default from SSM)", "required": False},
            "data_source_id": {"type": "string", "description": "Optional data source ID (default from SSM)", "required": False},
            "session_id": {"type": "string", "description": "Session ID for context tracking", "required": False},
        },
        returns={"type": "object", "description": "Ingestion job details with job_id and status"},
    ),
    AgentSkill(
        name="validate_part_number",
        description="Validate a part number by searching for its existence online",
        parameters={
            "part_number": {"type": "string", "description": "Part number to validate", "required": True},
            "manufacturer_hint": {"type": "string", "description": "Optional manufacturer name", "required": False},
            "session_id": {"type": "string", "description": "Session ID for context tracking", "required": False},
        },
        returns={"type": "object", "description": "Validation result with valid flag, confidence, and manufacturer"},
    ),
    AgentSkill(
        name="get_enrichment_status",
        description="Check if a part number has already been enriched",
        parameters={
            "part_number": {"type": "string", "description": "Part number to check", "required": True},
            "session_id": {"type": "string", "description": "Session ID for context tracking", "required": False},
        },
        returns={"type": "object", "description": "Enrichment status with document list and metadata"},
    ),
    AgentSkill(
        name="health_check",
        description="Health check endpoint for monitoring agent status and capabilities",
        parameters={},
        returns={"type": "object", "description": "Health status with agent info, version, model, and capabilities"},
    ),
]

# =============================================================================
# System Prompt (Equipment Enrichment Specialist)
# =============================================================================

SYSTEM_PROMPT = """You are the **EnrichmentAgent** for the SGA (Sistema de Gestao de Ativos) platform.

## Your Role

You are the **SPECIALIST** in equipment data enrichment using AI-powered web search.

Your mission is to enrich equipment inventory data with:
- Technical specifications
- Official datasheets
- User manuals
- Configuration guides
- Compatibility information

## Your Tools

### 1. `enrich_equipment`
Enriches a single equipment item:
- Searches for official documentation
- Extracts technical specifications
- Downloads datasheets (optional)
- Stores results in S3 Knowledge Repository

### 2. `enrich_batch`
Batch enrichment for multiple items:
- Triggered after import completion
- Processes items sequentially (respects rate limits)
- Triggers KB sync when complete

### 3. `sync_knowledge_base`
Triggers Bedrock KB synchronization:
- Indexes new documents in S3
- Enables RAG queries for NEXO Assistant
- Returns ingestion job status

### 4. `validate_part_number`
Validates part numbers via web search:
- Confirms PN exists in manufacturer's catalog
- Detects typos or invalid PNs
- Suggests corrections when possible

### 5. `get_enrichment_status`
Checks enrichment status:
- Returns existing enrichment data
- Lists stored documents
- Shows last enrichment timestamp

## Data Flow

```
Import → EventBridge → EnrichmentAgent → Tavily (via Gateway)
                                      → S3 (store results)
                                      → Bedrock KB (sync)
                                      → NEXO Assistant (RAG)
```

## Quality Criteria

| Metric | Target |
|--------|--------|
| Enrichment Coverage | ≥95% of items |
| Source Quality | ≥80% official sources |
| Confidence Score | ≥0.7 for SUCCESS |
| Latency | <30s per item |

## Official Sources Priority

1. Manufacturer websites (cisco.com, dell.com, hp.com, etc.)
2. Official product pages
3. Technical documentation portals
4. Partner/reseller pages (lower priority)

## Critical Rules

1. **ALWAYS** use Gateway-first pattern (never call Tavily directly)
2. Store ALL enrichment results to S3 Knowledge Repository
3. Trigger KB sync after batch operations
4. Include confidence scores in all responses
5. Log enrichment events to ObservationAgent
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

# A2A client instance for inter-agent communication
a2a_client = A2AClient()


@tool
async def enrich_equipment(
    part_number: str,
    serial_number: Optional[str] = None,
    manufacturer_hint: Optional[str] = None,
    store_to_s3: bool = True,
    download_documents: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enrich a single equipment item with documentation and specifications.

    Args:
        part_number: Equipment part number (e.g., C9200-24P)
        serial_number: Optional serial number for tracking
        manufacturer_hint: Optional manufacturer name to improve search
        store_to_s3: Store enrichment results to S3 (default True)
        download_documents: Download PDF documents (default False)
        session_id: Session ID for context

    Returns:
        EnrichmentResult dict with status, specifications, documents, and confidence
    """
    logger.info(f"[{AGENT_NAME}] enrich_equipment: part_number={part_number}")

    try:
        # Import tool implementation (lazy for cold start)
        from tools.enrichment_tools import enrich_equipment as enrich_equipment_impl

        result = enrich_equipment_impl(
            part_number=part_number,
            serial_number=serial_number,
            manufacturer_hint=manufacturer_hint,
            store_to_s3=store_to_s3,
            download_documents=download_documents,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "EQUIPMENT_ENRICHED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "part_number": part_number,
                "status": result.status.value,
                "confidence": result.confidence_score,
                "sources_count": len(result.sources),
            },
        }, session_id)

        return result.to_dict()

    except Exception as e:
        debug_error(e, "enrichment_enrich_equipment", {"part_number": part_number, "serial_number": serial_number, "manufacturer_hint": manufacturer_hint})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "status": "error",
            "part_number": part_number,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "enrich_equipment",
                "part_number": part_number,
                "serial_number": serial_number,
                "manufacturer_hint": manufacturer_hint,
                "store_to_s3": store_to_s3,
                "download_documents": download_documents,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_tavily_service", "check_s3_permissions", "escalate"],
        }


@tool
async def enrich_batch(
    items: List[Dict[str, Any]],
    import_id: str,
    tenant_id: str,
    trigger_kb_sync: bool = True,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Batch enrichment for multiple equipment items.

    Args:
        items: List of dicts with part_number, serial_number, manufacturer
        import_id: Import transaction ID for tracking
        tenant_id: Tenant identifier
        trigger_kb_sync: Trigger KB sync after completion (default True)
        session_id: Session ID for context

    Returns:
        BatchEnrichmentResult dict with statistics
    """
    logger.info(f"[{AGENT_NAME}] enrich_batch: import_id={import_id}, items={len(items)}")

    try:
        # Import tool implementation (lazy for cold start)
        from tools.enrichment_tools import enrich_batch as enrich_batch_impl

        result = enrich_batch_impl(
            items=items,
            import_id=import_id,
            tenant_id=tenant_id,
            store_to_s3=True,
            trigger_kb_sync=trigger_kb_sync,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "BATCH_ENRICHMENT_COMPLETED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "import_id": import_id,
                "total_items": result.total_items,
                "successful": result.successful,
                "partial": result.partial,
                "not_found": result.not_found,
                "errors": result.errors,
                "duration_seconds": result.duration_seconds,
                "kb_sync_triggered": result.kb_sync_triggered,
            },
        }, session_id)

        return {
            "success": True,
            "import_id": result.import_id,
            "total_items": result.total_items,
            "successful": result.successful,
            "partial": result.partial,
            "not_found": result.not_found,
            "errors": result.errors,
            "duration_seconds": result.duration_seconds,
            "kb_sync_triggered": result.kb_sync_triggered,
            # Individual results omitted for brevity (can be large)
            "results_summary": [
                {
                    "part_number": r.part_number,
                    "status": r.status.value,
                    "confidence": r.confidence_score,
                }
                for r in result.results
            ],
        }

    except Exception as e:
        debug_error(e, "enrichment_enrich_batch", {"import_id": import_id, "tenant_id": tenant_id, "items_count": len(items)})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "import_id": import_id,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "enrich_batch",
                "import_id": import_id,
                "tenant_id": tenant_id,
                "items_count": len(items),
                "trigger_kb_sync": trigger_kb_sync,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry_batch", "retry_failed_items", "check_rate_limits", "escalate"],
        }


@tool
async def sync_knowledge_base(
    knowledge_base_id: Optional[str] = None,
    data_source_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Trigger Bedrock Knowledge Base synchronization.

    Args:
        knowledge_base_id: Optional KB ID (default from SSM)
        data_source_id: Optional data source ID (default from SSM)
        session_id: Session ID for context

    Returns:
        Ingestion job details with job_id and status
    """
    logger.info(f"[{AGENT_NAME}] sync_knowledge_base")

    try:
        # Import tool implementation (lazy for cold start)
        from tools.enrichment_tools import trigger_knowledge_base_sync

        result = trigger_knowledge_base_sync(
            knowledge_base_id=knowledge_base_id,
            data_source_id=data_source_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "KB_SYNC_TRIGGERED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "triggered": result.get("triggered", False),
                "ingestion_job_id": result.get("ingestion_job_id"),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "enrichment_sync_knowledge_base", {"knowledge_base_id": knowledge_base_id, "data_source_id": data_source_id})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "triggered": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "sync_knowledge_base",
                "knowledge_base_id": knowledge_base_id,
                "data_source_id": data_source_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_kb_exists", "check_permissions", "escalate"],
        }


@tool
async def validate_part_number(
    part_number: str,
    manufacturer_hint: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate a part number by searching for its existence online.

    Args:
        part_number: Part number to validate
        manufacturer_hint: Optional manufacturer name
        session_id: Session ID for context

    Returns:
        Validation result with valid flag, confidence, and manufacturer
    """
    logger.info(f"[{AGENT_NAME}] validate_part_number: {part_number}")

    try:
        # Import tool implementation (lazy for cold start)
        from tools.enrichment_tools import validate_part_number as validate_pn_impl

        result = validate_pn_impl(
            part_number=part_number,
            manufacturer_hint=manufacturer_hint,
        )

        return result

    except Exception as e:
        debug_error(e, "enrichment_validate_part_number", {"part_number": part_number, "manufacturer_hint": manufacturer_hint})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "valid": False,
            "confidence": 0.0,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "validate_part_number",
                "part_number": part_number,
                "manufacturer_hint": manufacturer_hint,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_tavily_service", "manual_validation", "escalate"],
        }


@tool
async def get_enrichment_status(
    part_number: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check if a part number has already been enriched.

    Args:
        part_number: Part number to check
        session_id: Session ID for context

    Returns:
        Enrichment status with document list and metadata
    """
    logger.info(f"[{AGENT_NAME}] get_enrichment_status: {part_number}")

    try:
        # Import tool implementation (lazy for cold start)
        from tools.enrichment_tools import get_enrichment_status as get_status_impl

        result = get_status_impl(part_number=part_number)
        return result

    except Exception as e:
        debug_error(e, "enrichment_get_enrichment_status", {"part_number": part_number})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "enriched": False,
            "part_number": part_number,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "get_enrichment_status",
                "part_number": part_number,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_s3_connectivity", "verify_part_number", "escalate"],
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
        "role": "CRITICAL",
        "specialty": "EQUIPMENT_ENRICHMENT",
        "capabilities": [
            "enrich_equipment",
            "enrich_batch",
            "sync_knowledge_base",
            "validate_part_number",
            "get_enrichment_status",
        ],
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
        model=create_gemini_model(AGENT_ID),  # LazyGeminiModel for fast startup
        tools=[
            enrich_equipment,
            enrich_batch,
            sync_knowledge_base,
            validate_part_number,
            get_enrichment_status,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=EnrichmentResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI wrapper.

    Port 9000 is the standard for A2A protocol.
    Includes /ping health check endpoint.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: CRITICAL (Equipment Enrichment)")
    logger.info(f"[{AGENT_NAME}] Skills: {len(AGENT_SKILLS)} registered")
    for skill in AGENT_SKILLS:
        logger.info(f"  - {skill.name}: {skill.description[:60]}...")

    # Create FastAPI app
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping health check endpoint
    @app.get("/ping")
    async def ping():
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Create agent
    agent = create_agent()

    # Create A2A server with Agent Card discovery
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        serve_at_root=False,  # Mount under / via FastAPI
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
    )

    # Mount A2A server to FastAPI app
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
