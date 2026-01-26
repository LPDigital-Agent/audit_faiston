"""
InventoryHub Tools - Modular @tool implementations (Facade Pattern).

This package contains all @tool functions for the InventoryHub orchestrator.
Tools are thin wrappers that delegate to services/ for business logic.

Architecture:
    tools/           → @tool decorated functions (Interface Layer)
    services/        → Business logic classes (Service Layer)

The ALL_TOOLS list is used by create_inventory_hub() to register tools
with the Strands Agent. 10 local tools total.

Note: 2 additional tools (request_file_upload_url, verify_file_availability)
are imported separately from agents.tools.intake_tools in create_inventory_hub().
"""

# System tools (1 tool)
from .system_tools import health_check

# Intake tools (1 tool)
from .intake_tools import analyze_file_structure

# Mapping tools (3 tools)
from .mapping_tools import (
    confirm_mapping,
    map_to_schema,
    save_training_example,
)

# Execution tools (3 tools)
from .execution_tools import (
    check_import_status,
    check_notifications,
    transform_import,
)

# Insight tools (2 tools)
from .insight_tools import (
    check_observations,
    request_health_analysis,
)

# ALL_TOOLS list for agent registration (10 local tools)
# Used by create_inventory_hub() in main.py
ALL_TOOLS = [
    # System
    health_check,
    # Intake (Phase 1-2)
    analyze_file_structure,
    # Mapping (Phase 3)
    map_to_schema,
    confirm_mapping,
    save_training_example,
    # Execution (Phase 4)
    transform_import,
    check_import_status,
    check_notifications,
    # Insights (Phase 5)
    check_observations,
    request_health_analysis,
]

__all__ = [
    # List for agent registration
    "ALL_TOOLS",
    # System
    "health_check",
    # Intake
    "analyze_file_structure",
    # Mapping
    "map_to_schema",
    "confirm_mapping",
    "save_training_example",
    # Execution
    "transform_import",
    "check_import_status",
    "check_notifications",
    # Insights
    "check_observations",
    "request_health_analysis",
]
