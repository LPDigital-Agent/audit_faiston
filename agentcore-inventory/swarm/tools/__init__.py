# =============================================================================
# Swarm Tools - Faiston Inventory Management
# =============================================================================
# This module contains all tools used by the Inventory Swarm agents.
#
# Tool Categories:
# - analysis_tools: File parsing (CSV, XLSX, PDF, XML)
# - schema_tools: PostgreSQL schema validation and mapping
# - memory_tools: AgentCore Memory integration
# - hil_tools: Human-in-the-loop question generation
# - import_tools: Import execution and audit
# - meta_tools: Meta-Tooling for self-improvement
# =============================================================================

from swarm.tools.analysis_tools import (
    detect_file_type,
    analyze_csv,
    analyze_xlsx,
    analyze_pdf,
    analyze_xml,
)

from swarm.tools.schema_tools import (
    get_target_schema,
    propose_mappings,
    validate_types,
    check_constraints,
)

from swarm.tools.memory_tools import (
    retrieve_episodes,
    store_episode,
    get_adaptive_threshold,
    similarity_search,
    update_pattern_success,
)

from swarm.tools.hil_tools import (
    generate_questions,
    process_answers,
    request_approval,
    format_summary,
)

from swarm.tools.import_tools import (
    verify_approval,
    execute_import,
    generate_audit,
    rollback_import,
    apply_quantity_rule,
)

from swarm.tools.meta_tools import get_meta_tools

__all__ = [
    # Analysis tools
    "detect_file_type",
    "analyze_csv",
    "analyze_xlsx",
    "analyze_pdf",
    "analyze_xml",
    # Schema tools
    "get_target_schema",
    "propose_mappings",
    "validate_types",
    "check_constraints",
    # Memory tools
    "retrieve_episodes",
    "store_episode",
    "get_adaptive_threshold",
    "similarity_search",
    "update_pattern_success",
    # HIL tools
    "generate_questions",
    "process_answers",
    "request_approval",
    "format_summary",
    # Import tools
    "verify_approval",
    "execute_import",
    "generate_audit",
    "rollback_import",
    "apply_quantity_rule",
    # Meta tools
    "get_meta_tools",
]
