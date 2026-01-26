"""
InventoryHub Services - Modular service layer.

This package contains extracted services from the InventoryHub agent:
- intake_service: Phase 1-2 file intake and analysis logic
- validation_service: Request/response validation with cognitive error handling
- mapping_service: Phase 3 A2A schema mapping and HIL question generation
- job_service: Phase 4 fire-and-forget ETL job management
- insight_service: Phase 5 observations, health analysis, and notifications
"""

from .insight_service import (
    check_notifications,
    check_observations,
    request_health_analysis,
)
from .intake_service import (
    DIRECT_ACTIONS,
    calculate_file_quality_confidence,
    handle_direct_action,
    transform_file_structure_to_nexo_response,
)
from .job_service import check_import_job_status, invoke_transform_import
from .mapping_service import (
    generate_hil_questions,
    invoke_schema_mapper_phase3,
    _merge_phase3_results,
    _convert_missing_fields_to_questions,
)
from .validation_service import validate_llm_response, validate_payload

__all__ = [
    # Intake (Phase 1-2)
    "handle_direct_action",
    "calculate_file_quality_confidence",
    "transform_file_structure_to_nexo_response",
    "DIRECT_ACTIONS",
    # Validation
    "validate_payload",
    "validate_llm_response",
    # Mapping (Phase 3)
    "invoke_schema_mapper_phase3",
    "generate_hil_questions",
    "_merge_phase3_results",
    "_convert_missing_fields_to_questions",
    # Job Management (Phase 4)
    "invoke_transform_import",
    "check_import_job_status",
    # Insights (Phase 5)
    "check_observations",
    "request_health_analysis",
    "check_notifications",
]
