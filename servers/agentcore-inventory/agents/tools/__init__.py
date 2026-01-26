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

# =============================================================================
# BUG-032 FIX (Part 2): Ensure deployment root is in sys.path
# =============================================================================
# This module imports from intake_tools.py which imports from root tools/s3_client.py
# The sys.path fix MUST happen BEFORE that import chain executes.
#
# NOTE: This is a DUPLICATE of the fix in agents/__init__.py because Python
# import chain for nested packages doesn't guarantee parent __init__.py runs first.
# =============================================================================
import os
import sys

_deployment_root = os.environ.get("LAMBDA_TASK_ROOT", os.getcwd())
if _deployment_root not in sys.path:
    sys.path.insert(0, _deployment_root)
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
