"""
DataTransformer Tools - Phase 4.

These tools implement the Sandwich Pattern (CODE → LLM → CODE):
- preference_loader: Load/save user preferences from AgentCore Memory
- job_manager: Fire-and-forget job tracking
- etl_stream: S3 streaming + transformation (batched)
- batch_loader: MCP Gateway batch insert + rejection reports

All tools follow CLAUDE.md Tool Quality Standards:
- Google-style docstrings
- Type hints on all arguments
- JSON return format documented
"""

from agents.specialists.data_transformer.tools.preference_loader import (
    load_import_preferences,
    save_import_preference,
)
from agents.specialists.data_transformer.tools.job_manager import (
    create_job,
    get_job_status,
    update_job_status,
    save_job_notification,
    check_pending_notifications,
)
from agents.specialists.data_transformer.tools.etl_stream import (
    validate_file_size,
    stream_and_transform,
    enrich_errors_with_debug,
)
from agents.specialists.data_transformer.tools.batch_loader import (
    insert_pending_items_batch,
    insert_all_batches,
    generate_rejection_report,
)

__all__ = [
    # Preference loading
    "load_import_preferences",
    "save_import_preference",
    # Job management
    "create_job",
    "get_job_status",
    "update_job_status",
    "save_job_notification",
    "check_pending_notifications",
    # ETL streaming
    "validate_file_size",
    "stream_and_transform",
    "enrich_errors_with_debug",
    # Batch loading
    "insert_pending_items_batch",
    "insert_all_batches",
    "generate_rejection_report",
]
