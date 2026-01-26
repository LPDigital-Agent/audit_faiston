"""System tools for InventoryHub orchestrator.

This module contains system-level tools for health checks and monitoring.
These tools are used for debugging, observability, and system status reporting.

Architecture Note:
    InventoryHub is the central orchestrator for SGA file ingestion.
    System tools support monitoring and operational visibility.
"""

import json

from strands import tool

# NOTE: DO NOT import from config at module level - causes circular import!
# config.py → tools/__init__.py → system_tools.py → config.py = CRASH!
# Instead, we use lazy import inside health_check() function.
from agents.utils import AGENT_VERSION
from agents.tools.intake_tools import ALLOWED_FILE_TYPES

__all__ = ["health_check"]


@tool
def health_check() -> str:
    """
    Check the health status of the Inventory Hub orchestrator.

    This tool returns system information useful for debugging and monitoring.

    Returns:
        JSON string with health status, version, and capabilities.
    """
    # Lazy import to break circular dependency (BUG-031 fix)
    # config.py imports tools/__init__.py which imports system_tools.py
    # If we import config at module level, we get circular import crash
    from agents.orchestrators.inventory_hub.config import AGENT_ID, AGENT_NAME, RUNTIME_ID

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
