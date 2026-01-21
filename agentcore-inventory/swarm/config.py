# =============================================================================
# Swarm Configuration - Faiston Inventory Management
# =============================================================================
# Configures the Strands Swarm for autonomous inventory import processing.
#
# Key Configuration:
# - entry_point: file_analyst (all imports start with file analysis)
# - max_handoffs: 30 (prevent infinite loops)
# - execution_timeout: 1800s (30 min for complex imports)
# - Meta-Tooling: Enabled for self-improvement
# =============================================================================

import logging
from dataclasses import dataclass
from typing import Optional

from strands.multiagent import Swarm


logger = logging.getLogger(__name__)


@dataclass
class SwarmConfig:
    """Configuration for Faiston Inventory Swarm."""

    # Swarm limits
    max_handoffs: int = 30
    max_iterations: int = 50

    # Timeouts (seconds)
    execution_timeout: float = 1800.0  # 30 minutes
    node_timeout: float = 300.0  # 5 minutes per agent

    # Anti-ping-pong protection
    repetitive_handoff_detection_window: int = 10
    repetitive_handoff_min_unique_agents: int = 3

    # Model configuration
    routing_model: str = "gemini-2.5-flash"  # Fast model for routing
    analysis_model: str = "gemini-2.5-pro"  # Pro model for analysis

    # Meta-Tooling
    enable_meta_tooling: bool = True


def create_inventory_swarm(config: Optional[SwarmConfig] = None) -> Swarm:
    """
    Create the Faiston Inventory Swarm.

    This creates a 5-agent swarm for autonomous inventory import processing:
    1. file_analyst - Entry point, file analysis
    2. schema_validator - Schema validation and mapping
    3. memory_agent - Episodic memory for patterns
    4. hil_agent - Human-in-the-loop clarification
    5. import_executor - Transaction execution

    Args:
        config: Optional SwarmConfig for customization

    Returns:
        Configured Swarm instance
    """
    if config is None:
        config = SwarmConfig()

    logger.info("[Swarm] Creating Faiston Inventory Swarm with config: %s", config)

    # Import agents (lazy import to avoid circular dependencies)
    from swarm.agents.file_analyst import create_file_analyst
    from swarm.agents.schema_validator import create_schema_validator
    from swarm.agents.memory_agent import create_memory_agent
    from swarm.agents.hil_agent import create_hil_agent
    from swarm.agents.import_executor import create_import_executor

    # Create agents (model selection is automatic via create_gemini_model)
    file_analyst = create_file_analyst()
    schema_validator = create_schema_validator()
    memory_agent = create_memory_agent()
    hil_agent = create_hil_agent()
    import_executor = create_import_executor()

    # Create the Swarm (Strands uses 'nodes' not 'agents')
    swarm = Swarm(
        nodes=[
            file_analyst,
            schema_validator,
            memory_agent,
            hil_agent,
            import_executor,
        ],
        entry_point=file_analyst,
        max_handoffs=config.max_handoffs,
        max_iterations=config.max_iterations,
        execution_timeout=config.execution_timeout,
        node_timeout=config.node_timeout,
        repetitive_handoff_detection_window=config.repetitive_handoff_detection_window,
        repetitive_handoff_min_unique_agents=config.repetitive_handoff_min_unique_agents,
    )

    logger.info(
        "[Swarm] Created Inventory Swarm with %d nodes, entry_point=%s",
        len(swarm.nodes),
        file_analyst.name,
    )

    return swarm


# =============================================================================
# Handoff Context Schema
# =============================================================================
# All agents share context via invocation_state. This schema defines the
# expected structure for consistent handoff communication.

HANDOFF_CONTEXT_SCHEMA = {
    # User/session context
    "user_id": "str - User performing the import",
    "session_id": "str - Session ID for continuity",
    "tenant_id": "str - Tenant identifier",
    # File context
    "file_path": "str - S3 path to import file",
    "file_type": "str - Detected file type (csv/xlsx/pdf/xml)",
    "target_table": "str - PostgreSQL target table",
    # Analysis results
    "file_analysis": "dict - Output from file_analyst",
    "memory_context": "dict - Patterns from memory_agent",
    # Validation results
    "proposed_mappings": "list - Column mappings from schema_validator",
    "unmapped_columns": "list - Columns without mapping",
    "validation_issues": "list - Type/format issues",
    # HIL state
    "hil_questions": "list - Pending questions for user",
    "user_responses": "dict - Accumulated user answers",
    "approval_status": "bool|None - Final approval state",
    # Import results
    "import_id": "str - Import transaction ID",
    "rows_imported": "int - Number of rows imported",
    "audit_trail_id": "str - DynamoDB audit record ID",
}


# =============================================================================
# Agent Names (for handoff_to_agent)
# =============================================================================
# These constants ensure consistent agent naming across the swarm.

AGENT_FILE_ANALYST = "file_analyst"
AGENT_SCHEMA_VALIDATOR = "schema_validator"
AGENT_MEMORY = "memory_agent"
AGENT_HIL = "hil_agent"
AGENT_IMPORT_EXECUTOR = "import_executor"

ALL_AGENTS = [
    AGENT_FILE_ANALYST,
    AGENT_SCHEMA_VALIDATOR,
    AGENT_MEMORY,
    AGENT_HIL,
    AGENT_IMPORT_EXECUTOR,
]
