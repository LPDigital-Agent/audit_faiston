# =============================================================================
# Shared Utilities for Faiston SGA Inventory Agents
# =============================================================================
# Common helpers used across all inventory management agents.
#
# Module: Gestao de Ativos -> Gestao de Estoque
# TEMPORARY: Using Gemini 2.5 (Strands SDK thoughtSignature issue #1199)
#
# API Key Note:
# GOOGLE_API_KEY is loaded from SSM Parameter Store at runtime (BUG-010 fix).
# SSM Path: /faiston-one/academy/google-api-key
# If env var is already set, SSM lookup is skipped.
# =============================================================================

import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
import os

# Strands Model Provider for Gemini (per CLAUDE.md - Gemini 2.5 Family ONLY)
from strands.models.gemini import GeminiModel

# A2A Protocol Types for Agent Card Discovery (100% A2A Architecture)
from a2a.types import AgentSkill

# =============================================================================
# Constants
# =============================================================================

# App name for Google ADK sessions
APP_NAME = "faiston-sga-inventory"

# Agent version for tracking
AGENT_VERSION = "2026.01.04.v1"

# =============================================================================
# Gemini 2.5 Model Configuration (TEMPORARY WORKAROUND)
# =============================================================================
# TEMPORARY: Using Gemini 2.5 instead of Gemini 3 due to Strands SDK not
# supporting the required thoughtSignature feature in Gemini 3 preview.
# Issue: https://github.com/strands-agents/sdk-python/issues/1199
# TODO: Revert to Gemini 3 when Strands SDK is updated
#
# Model selection based on agent type:
# - Pro: Import/analysis agents (complex file understanding)
# - Flash: Operational agents (speed-critical, simple tasks)
# =============================================================================

# Gemini 2.5 Model Family (Stable - January 2026)
# TEMPORARY WORKAROUND: Using Gemini 2.5 instead of 3 preview due to Strands SDK
# not supporting Gemini 3's required thoughtSignature feature.
# Issue: https://github.com/strands-agents/sdk-python/issues/1199
# TODO: Revert to gemini-3-*-preview once Strands SDK is updated
MODEL_GEMINI_FLASH = "gemini-2.5-flash"  # Fast, cost-effective (simple tasks)
MODEL_GEMINI_PRO = "gemini-2.5-pro"      # Complex reasoning

# Legacy constant (for backwards compatibility)
MODEL_GEMINI = MODEL_GEMINI_PRO

# =============================================================================
# Agent Model + Thinking Configuration (PERF-001: Import Performance Optimization)
# =============================================================================
# Agents are categorized into THREE tiers based on their reasoning needs:
#
# 1. PRO_NO_THINKING_AGENTS: Use Gemini 2.5 Pro WITHOUT thinking mode
#    - Fast path agents that need Pro's capabilities but not deep reasoning
#    - Optimized for speed in import/analysis workflows
#    - Decision: User-approved removal of Thinking to reduce 10+ min → 1-3 min imports
#
# 2. PRO_THINKING_AGENTS: Use Gemini 2.5 Pro WITH thinking mode enabled
#    - Deep reasoning agents for high-impact decisions
#    - Pattern learning, schema evolution, compliance, error analysis
#    - Thinking mode justified for accuracy over speed
#
# 3. FLASH_AGENTS (default): Use Gemini 2.5 Flash
#    - Simple operational agents (observation, etc.)
#    - Speed-critical, low complexity tasks
# =============================================================================

# ROLLBACK PERF-001: All import agents restored to use Thinking mode
# The PERF-001 optimization (removing thinking) caused response format errors.
# Gemini without Thinking returns inconsistent structured outputs.
# Decision: Prioritize functionality over speed.
PRO_NO_THINKING_AGENTS: set[str] = set()  # Empty - no agents without thinking for now

# Agents that require Pro + Thinking (deep reasoning for consistent outputs)
# ROLLBACK PERF-001: Import agents moved back here - they need Thinking for correct JSON structure
PRO_THINKING_AGENTS = {
    # Import agents (ROLLBACK - need Thinking for consistent structured outputs)
    "nexo_import",      # Main orchestrator - needs Thinking for response structure
    "intake",           # Document intake - needs Thinking for NF parsing
    "import",           # Data import - needs Thinking for file structure
    "file_analyzer",    # FileAnalyzer A2A agent - needs Thinking for analysis
    "vision_analyzer",  # VisionAnalyzer A2A agent - needs Thinking for OCR
    "file_analyst",     # FileAnalyst A2A agent - needs Thinking for NEXO imports
    # Phase 2+3+4: Smart Import specialist agents (critical inventory per CLAUDE.md)
    "inventory_analyst",  # Phase 2 - File structure analysis
    "schema_mapper",      # Phase 3 - Semantic column mapping with learning
    "data_transformer",   # Phase 4 - Cognitive ETL with error enrichment
    # Reasoning agents (always used Thinking)
    "learning",         # Memory extraction - NEEDS thinking for pattern recognition
    "schema_evolution", # Schema analysis - NEEDS thinking for SQL generation
    "enrichment",       # Equipment enrichment - NEEDS thinking for Tavily data reasoning
    "debug",            # Error analysis - NEEDS thinking for root cause identification
    "compliance",       # Audit, regulatory - NEEDS thinking for compliance rules
}

# Agents that require Pro (complex reasoning but no thinking needed)
# NOTE: Currently empty - all Pro agents use Thinking for consistent outputs
PRO_AGENTS: set[str] = set()


def get_model(agent_type: str = "default") -> str:
    """
    Get appropriate Gemini 2.5 model for agent type.

    TEMPORARY: Using Gemini 2.5 due to Strands SDK not supporting Gemini 3 thoughtSignature.
    See: https://github.com/strands-agents/sdk-python/issues/1199

    Model selection (PERF-001 updated):
    - PRO_THINKING_AGENTS → gemini-2.5-pro (with thinking enabled in LazyGeminiModel)
    - PRO_NO_THINKING_AGENTS → gemini-2.5-pro (WITHOUT thinking - optimized for speed)
    - PRO_AGENTS → gemini-2.5-pro (legacy, currently empty)
    - All others → gemini-2.5-flash

    Args:
        agent_type: Agent identifier (e.g., "nexo_import", "observation")

    Returns:
        Model ID string
    """
    if agent_type in PRO_THINKING_AGENTS or agent_type in PRO_NO_THINKING_AGENTS or agent_type in PRO_AGENTS:
        return os.environ.get("GEMINI_MODEL_PRO", MODEL_GEMINI_PRO)
    return os.environ.get("GEMINI_MODEL", MODEL_GEMINI_FLASH)


def get_thinking_config(agent_type: str = "default"):
    """
    Get thinking configuration for agents requiring deep reasoning.

    Per Google Gemini 3.0 docs (https://ai.google.dev/gemini-api/docs/thinking):
    - thinking_level="high": Maximizes reasoning depth (default for Pro)
    - thinking_level="medium": Balanced (Flash only)
    - thinking_level="low": Simple tasks, minimizes latency

    IMPORTANT: This returns a dict for use with generate_content() calls.
    Google ADK Agent class doesn't directly accept thinkingConfig, but tools
    that call generate_content() can use this configuration.

    Args:
        agent_type: Agent identifier

    Returns:
        Dict with thinking config for Pro+Thinking agents, None otherwise
    """
    if agent_type in PRO_THINKING_AGENTS:
        return {
            "thinking_config": {
                "thinking_level": "high"  # Maximize reasoning for file analysis
            }
        }
    return None


def requires_thinking(agent_type: str) -> bool:
    """
    Check if agent requires thinking mode.

    Args:
        agent_type: Agent identifier

    Returns:
        True if agent requires thinking mode
    """
    return agent_type in PRO_THINKING_AGENTS


class LazyGeminiModel:
    """
    Lazy-loading wrapper for GeminiModel to enable fast A2A server startup.

    BUG-008 FIX: AgentCore requires the A2A server to respond to health checks
    within 5-10 seconds. GeminiModel's constructor makes a blocking HTTP call
    to Google's API (generativelanguage.googleapis.com) to validate credentials,
    which can exceed this timeout on cold starts.

    This wrapper defers the actual GeminiModel initialization until the first
    inference call, allowing the A2A server to start instantly and respond to
    AgentCore's health probes.

    Usage:
        model = LazyGeminiModel(agent_type="nexo_import")
        agent = Agent(model=model, ...)  # Server starts immediately
        # First actual request triggers GeminiModel initialization

    Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/gemini/
    """

    def __init__(self, agent_type: str = "default"):
        """
        Initialize lazy wrapper without connecting to Google API.

        Args:
            agent_type: Agent identifier for model selection (Pro vs Flash)
        """
        self._agent_type = agent_type
        self._model: GeminiModel | None = None
        self._model_id = get_model(agent_type)
        # Log immediately so CloudWatch shows server started
        import logging
        logging.getLogger(__name__).info(
            f"[LazyGeminiModel] Initialized for {agent_type} (model: {self._model_id}) - "
            f"actual connection deferred to first request"
        )

    def _ensure_model(self) -> GeminiModel:
        """
        Ensure GeminiModel is initialized, creating it on first call.

        Returns:
            Initialized GeminiModel instance
        """
        if self._model is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("[LazyGeminiModel] First request - initializing GeminiModel...")

            # BUG-010 FIX: Load GOOGLE_API_KEY from SSM if not in environment
            # SSM Parameter: /faiston-one/academy/google-api-key
            if not os.environ.get("GOOGLE_API_KEY"):
                logger.info("[LazyGeminiModel] GOOGLE_API_KEY not in env, loading from SSM...")
                try:
                    import boto3
                    ssm = boto3.client("ssm", region_name="us-east-2")
                    response = ssm.get_parameter(
                        Name="/faiston-one/academy/google-api-key",
                        WithDecryption=True
                    )
                    api_key = response["Parameter"]["Value"]
                    os.environ["GOOGLE_API_KEY"] = api_key
                    logger.info("[LazyGeminiModel] GOOGLE_API_KEY loaded from SSM successfully")
                except Exception as e:
                    logger.error(f"[LazyGeminiModel] Failed to load GOOGLE_API_KEY from SSM: {e}")
                    raise RuntimeError(
                        "GOOGLE_API_KEY not found in environment and SSM lookup failed. "
                        f"SSM path: /faiston-one/academy/google-api-key. Error: {e}"
                    )

            # Build params
            # BUG-011 FIX: Increased max_output_tokens from 4096 to 16384
            # The file analysis response includes: structure, mappings, confidence scores,
            # HIL questions, unmapped columns, and full JSON output. With the new
            # RESPONSE FORMAT requirement (commit 09caf83), responses can easily exceed
            # 4096 tokens, causing MaxTokensReachedException in Strands A2A.
            # Gemini 2.5 Pro supports up to 65,536 output tokens.
            # Reference: https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.5-pro
            #
            # BUG-021 v7 FIX: REMOVED response_mime_type: "application/json"
            # Gemini API does NOT support response_mime_type when tools (function calling)
            # are enabled. The error was: "Function calling with a response mime type:
            # 'application/json' is unsupported"
            # Reference: https://ai.google.dev/gemini-api/docs/function-calling
            # JSON output is enforced via system prompt instead.
            params = {
                "temperature": 0.7,
                "max_output_tokens": 16384,  # 4x increase to handle detailed analysis
            }

            # BUG-009 CORRECT FIX: Different thinking parameters per Gemini version
            # - Gemini 2.5: Uses "thinking_budget" (integer: 128-32768, or -1 for dynamic)
            # - Gemini 3: Uses "thinking_level" (string: "high", "medium", "low")
            # Reference: https://ai.google.dev/gemini-api/docs/thinking
            is_gemini_3 = "gemini-3" in self._model_id
            if requires_thinking(self._agent_type):
                if is_gemini_3:
                    params["thinking_config"] = {
                        "thinking_level": "high"  # Max reasoning for Gemini 3
                    }
                    logger.info("[LazyGeminiModel] Thinking mode enabled (Gemini 3 - thinking_level: high)")
                else:
                    # Gemini 2.5 uses thinking_budget instead of thinking_level
                    params["thinking_config"] = {
                        "thinking_budget": -1  # Dynamic allocation for Gemini 2.5
                    }
                    logger.info("[LazyGeminiModel] Thinking mode enabled (Gemini 2.5 - thinking_budget: dynamic)")

            # NOW make the actual connection to Google
            self._model = GeminiModel(
                model_id=self._model_id,
                params=params,
            )
            logger.info("[LazyGeminiModel] GeminiModel initialized successfully")

        return self._model

    def __getattr__(self, name: str):
        """
        Proxy all attribute access to the underlying GeminiModel.

        This makes LazyGeminiModel a transparent wrapper - any method call
        or attribute access triggers model initialization and then delegates
        to the real GeminiModel.
        """
        return getattr(self._ensure_model(), name)

    @property
    def model_id(self) -> str:
        """Return model ID without initializing the model."""
        return self._model_id


def create_gemini_model(agent_type: str = "default") -> LazyGeminiModel:
    """
    Create lazy-loading GeminiModel wrapper for Strands Agent.

    BUG-008 FIX: Returns LazyGeminiModel instead of GeminiModel to enable
    fast A2A server startup. The actual Google API connection is deferred
    until the first inference request.

    TEMPORARY: Using Gemini 2.5 due to Strands SDK thoughtSignature issue.
    See: https://github.com/strands-agents/sdk-python/issues/1199
    Uses GOOGLE_API_KEY from environment (set at deploy time via --env).

    This function centralizes model configuration to:
    1. Apply correct model ID based on agent type (Pro vs Flash)
    2. Configure thinking mode for complex reasoning agents
    3. Ensure consistent parameters across all agents
    4. Enable lazy loading for fast AgentCore startup (BUG-008)

    Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/gemini/

    Args:
        agent_type: Agent identifier for model selection

    Returns:
        LazyGeminiModel wrapper that initializes on first use
    """
    return LazyGeminiModel(agent_type=agent_type)


# =============================================================================
# A2A Agent Skills Helper (100% A2A Architecture)
# =============================================================================


def create_agent_skill(
    skill_id: str,
    name: str,
    description: str,
    agent_id: str,
    extra_tags: Optional[List[str]] = None,
) -> AgentSkill:
    """
    Create an AgentSkill for A2A Agent Card discovery.

    This helper ensures consistent skill creation across all agents,
    following the A2A Protocol specification.

    Args:
        skill_id: Unique identifier for the skill (e.g., "analyze_file")
        name: Human-readable skill name (e.g., "Analyze File")
        description: Detailed description of what the skill does
        agent_id: Agent identifier for tagging (e.g., "nexo_import")
        extra_tags: Additional tags for categorization

    Returns:
        AgentSkill instance ready for A2AServer configuration

    Reference: https://a2a-protocol.org/latest/specification/
    """
    base_tags = [agent_id, "sga", "inventory"]
    if extra_tags:
        base_tags.extend(extra_tags)

    return AgentSkill(
        id=skill_id,
        name=name,
        description=description,
        tags=base_tags,
    )


# Environment variables
INVENTORY_TABLE = os.environ.get("INVENTORY_TABLE", "faiston-one-sga-inventory-prod")
HIL_TASKS_TABLE = os.environ.get("HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod")
AUDIT_LOG_TABLE = os.environ.get("AUDIT_LOG_TABLE", "faiston-one-sga-audit-log-prod")
DOCUMENTS_BUCKET = os.environ.get("DOCUMENTS_BUCKET", "faiston-one-sga-documents-prod")

# =============================================================================
# Entity Prefixes (Single-Table Design)
# =============================================================================

class EntityPrefix:
    """DynamoDB entity type prefixes for single-table design."""
    PART_NUMBER = "PN#"
    ASSET = "ASSET#"
    LOCATION = "LOC#"
    BALANCE = "BALANCE#"
    MOVEMENT = "MOVE#"
    RESERVATION = "RESERVE#"
    TASK = "TASK#"
    DIVERGENCE = "DIV#"
    DOCUMENT = "DOC#"
    PROJECT = "PROJ#"


# =============================================================================
# Movement Types
# =============================================================================

class MovementType:
    """Inventory movement types."""
    ENTRY = "ENTRY"           # Entrada (Internalizacao)
    EXIT = "EXIT"             # Saida (Expedicao)
    TRANSFER = "TRANSFER"     # Transferencia
    ADJUSTMENT = "ADJUSTMENT" # Ajuste (HIL required)
    RESERVATION = "RESERVATION"  # Reserva
    UNRESERVATION = "UNRESERVATION"  # Desreserva
    RETURN = "RETURN"         # Reversa
    DISCARD = "DISCARD"       # Descarte (HIL required)
    LOSS = "LOSS"             # Extravio (HIL required)


# =============================================================================
# HIL Task Types
# =============================================================================

class HILTaskType:
    """Human-in-the-Loop task types."""
    APPROVAL_NEW_PN = "APPROVAL_NEW_PN"
    APPROVAL_ENTRY = "APPROVAL_ENTRY"
    APPROVAL_ADJUSTMENT = "APPROVAL_ADJUSTMENT"
    APPROVAL_DISCARD = "APPROVAL_DISCARD"
    APPROVAL_TRANSFER = "APPROVAL_TRANSFER"
    REVIEW_ENTRY = "REVIEW_ENTRY"
    ESCALATION = "ESCALATION"
    # Project Gate - For entries without project_id
    NEW_PROJECT_REQUEST = "NEW_PROJECT_REQUEST"


class EntryStatus:
    """NF Entry processing status values."""
    PENDING_UPLOAD = "PENDING_UPLOAD"         # Awaiting file upload
    PROCESSING = "PROCESSING"                 # Being extracted
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"  # Awaiting user confirmation
    PENDING_APPROVAL = "PENDING_APPROVAL"     # Awaiting HIL approval (unmatched items)
    PENDING_PROJECT = "PENDING_PROJECT"       # Awaiting project assignment (no project_id)
    CONFIRMED = "CONFIRMED"                   # User confirmed, ready for movement
    COMPLETED = "COMPLETED"                   # Movements created
    FAILED = "FAILED"                         # Processing failed
    CANCELLED = "CANCELLED"                   # Entry cancelled


class HILAssignedRole:
    """Roles for HIL task assignment routing."""
    OPERATOR = "OPERATOR"           # Warehouse operators
    SUPERVISOR = "SUPERVISOR"       # Floor supervisors
    MANAGER = "MANAGER"             # Area managers
    FINANCE_OPERATOR = "FINANCE_OPERATOR"   # Finance team for project creation
    DIRECTOR = "DIRECTOR"           # Directors for high-value approvals


class HILTaskStatus:
    """HIL task status values."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# =============================================================================
# Confidence Scoring
# =============================================================================

class RiskLevel:
    """Risk level indicators for AI decisions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# JSON Parsing Utilities
# =============================================================================


def extract_json(response: str) -> str:
    """
    Extract JSON from a response that may contain markdown code blocks.

    Args:
        response: Raw response text from LLM

    Returns:
        Extracted JSON string
    """
    # Try to find JSON in markdown code block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
    if json_match:
        return json_match.group(1).strip()

    # Try to find raw JSON object or array
    json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", response)
    if json_match:
        return json_match.group(1).strip()

    # Return as-is if no JSON found
    return response.strip()


def parse_json_safe(response: str) -> Dict[str, Any]:
    """
    Safely parse JSON from response with fallback.

    Args:
        response: Raw response text from LLM

    Returns:
        Parsed JSON dict or error dict
    """
    try:
        json_str = extract_json(response)
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse JSON: {e}", "raw_response": response}


# =============================================================================
# Date/Time Utilities
# =============================================================================


def now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def now_yyyymm() -> str:
    """Return current UTC date in YYYY-MM format for GSI5 partitioning."""
    return datetime.utcnow().strftime("%Y-%m")


def now_yyyymmdd() -> str:
    """Return current UTC date in YYYY-MM-DD format for audit log partitioning."""
    return datetime.utcnow().strftime("%Y-%m-%d")


# =============================================================================
# ID Generation
# =============================================================================


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID with optional prefix.

    Args:
        prefix: Optional prefix (e.g., "MOVE", "TASK")

    Returns:
        Unique ID string
    """
    import uuid
    unique = str(uuid.uuid4())[:12]
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    if prefix:
        return f"{prefix}-{timestamp}-{unique}"
    return f"{timestamp}-{unique}"


# =============================================================================
# Logging Utilities (Secure - No PII)
# =============================================================================


def log_agent_action(
    agent_name: str,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    status: str = "started",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log agent action for observability.

    SECURITY: Never log PII, credentials, or sensitive data.
    Only log action metadata for debugging and audit.

    Args:
        agent_name: Name of the agent performing the action
        action: Action being performed
        entity_type: Type of entity being operated on
        entity_id: ID of entity (safe to log, not PII)
        status: Action status (started, completed, failed)
        details: Additional safe-to-log details
    """
    log_entry = {
        "timestamp": now_iso(),
        "agent": agent_name,
        "action": action,
        "status": status,
    }
    if entity_type:
        log_entry["entity_type"] = entity_type
    if entity_id:
        log_entry["entity_id"] = entity_id
    if details:
        # Filter out any potentially sensitive keys
        safe_keys = {"count", "batch_size", "duration_ms", "confidence", "risk_level", "error"}
        # Defensive: handle both dict and string (callers may pass str(e) by mistake)
        if isinstance(details, dict):
            safe_details = {k: v for k, v in details.items() if k in safe_keys}
            if safe_details:
                log_entry["details"] = safe_details
        elif isinstance(details, str):
            # Convert string to error dict for backwards compatibility
            log_entry["details"] = {"error": details[:200]}  # Truncate for safety

    print(json.dumps(log_entry))
