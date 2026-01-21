# =============================================================================
# SGA Inventory Agent Tools
# =============================================================================
# Strands-compatible tools for agent orchestrators.
#
# This package contains deterministic Python tools that follow the
# "LLM = Brain / Python = Hands" principle from CLAUDE.md.
#
# Tools handle:
# - HTTP requests/responses (networking)
# - File validation (deterministic)
# - S3 operations (presigned URLs, metadata)
#
# LLM orchestrators handle:
# - Decision-making (when to call tools)
# - Intent extraction (user requests)
# - Error recovery strategy
#
# VERSION: 2026-01-21T18:00:00Z - Phase 1 Secure File Ingestion
# =============================================================================

from .intake_tools import (
    ALLOWED_FILE_TYPES,
    request_file_upload_url,
    verify_file_availability,
)

__all__ = [
    "ALLOWED_FILE_TYPES",
    "request_file_upload_url",
    "verify_file_availability",
]
