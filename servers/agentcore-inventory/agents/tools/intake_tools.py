# =============================================================================
# Intake Tools for Secure File Ingestion (Phase 1)
# =============================================================================
# Strands-compatible tools for the Inventory Hub orchestrator.
#
# These tools handle the secure file upload workflow:
# 1. request_file_upload_url - Generate presigned POST URL for browser uploads
# 2. verify_file_availability - Confirm file exists and validate content-type
#
# ARCHITECTURE (per CLAUDE.md):
# - LLM = Brain: Decides when to call tools based on user intent
# - Python = Hands: Deterministic execution (S3 operations, validation)
#
# SANDWICH PATTERN:
# - CODE (tools): Handle networking, validation, S3 operations
# - LLM (orchestrator): Analyze intent, decide actions, handle errors
# - CODE (tools): Return structured JSON for downstream processing
#
# VERSION: 2026-01-21T18:00:00Z - Phase 1 Secure File Ingestion
# =============================================================================

import importlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Optional

from strands import tool

# =============================================================================
# BUG-032 FIX (Part 4): Use __file__ to compute absolute path to tools/
# =============================================================================
# Previous fixes (Parts 1-3) relied on sys.path which doesn't work reliably
# in AgentCore runtime. This fix uses __file__ to compute the absolute path
# to the root tools/ directory from this file's location.
#
# File location: /var/task/agents/tools/intake_tools.py
# Target module: /var/task/tools/s3_client.py
# Path from here: ../../tools/s3_client.py (up 2 levels, then into tools/)
# =============================================================================
import importlib.util

# Get absolute path to this file's directory
_this_dir = os.path.dirname(os.path.abspath(__file__))
# Navigate up to /var/task (agents/tools/ → agents/ → root)
_root_dir = os.path.dirname(os.path.dirname(_this_dir))
# Target module path
_s3_client_path = os.path.join(_root_dir, "tools", "s3_client.py")

# Load module directly from file path using importlib.util
_spec = importlib.util.spec_from_file_location("tools.s3_client", _s3_client_path)
_s3_client_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_s3_client_module)

SGAS3Client = _s3_client_module.SGAS3Client
S3ClientError = _s3_client_module.S3ClientError
# =============================================================================

# Shared utilities
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Allowed file types for inventory import
# Maps file extension to MIME content-type
ALLOWED_FILE_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "pdf": "application/pdf",
    "xml": "application/xml",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "txt": "text/plain",
}

# Reverse mapping for content-type validation
CONTENT_TYPE_TO_EXTENSION = {v: k for k, v in ALLOWED_FILE_TYPES.items()}

# Maximum file size: 100 MB
MAX_FILE_SIZE_BYTES = 104857600

# URL expiration: 5 minutes
URL_EXPIRATION_SECONDS = 300


# =============================================================================
# Tool: request_file_upload_url
# =============================================================================


@tool
def request_file_upload_url(
    filename: str,
    content_type: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Generate a secure presigned POST URL for file upload to S3.

    This tool creates a presigned POST form that allows direct uploads
    from browsers with server-side validation of file size and content type.
    Files are stored in a temporary location and auto-deleted after 24 hours
    if not processed.

    IMPORTANT: Only inventory-related file types are allowed (CSV, Excel,
    PDF, XML, images, TXT). Other file types will be rejected with an error.

    Args:
        filename: Name of the file to upload (e.g., "inventory_2026.csv").
            The file extension is used to determine content-type.
        content_type: Optional MIME type override. If not provided, it will
            be inferred from the filename extension.
        user_id: Optional user identifier to attach as metadata for tracking.
        session_id: Optional session identifier to attach as metadata.

    Returns:
        JSON string with the following structure on success:
        {
            "success": true,
            "url": "https://bucket.s3.us-east-2.amazonaws.com",
            "fields": {"key": "...", "policy": "...", "x-amz-signature": "..."},
            "key": "temp/uploads/abc123_file.csv",
            "bucket": "faiston-one-sga-documents-prod",
            "expires_in": 300,
            "expires_at": "2026-01-21T11:05:00Z",
            "max_file_size_bytes": 104857600,
            "temp_cleanup_warning": "File will be auto-deleted after 24 hours if not processed"
        }

        On validation error (invalid file type):
        {
            "success": false,
            "error": "File type '.docx' not allowed for inventory import",
            "allowed_types": ["csv", "xlsx", "xls", "pdf", "xml", "jpg", "jpeg", "png", "txt"],
            "suggestion": "Please convert your file to CSV or Excel format"
        }
    """
    try:
        # Extract file extension
        if "." not in filename:
            return json.dumps({
                "success": False,
                "error": f"Filename '{filename}' has no extension",
                "allowed_types": list(ALLOWED_FILE_TYPES.keys()),
                "suggestion": "Please provide a filename with an extension (e.g., data.csv)",
            })

        extension = filename.rsplit(".", 1)[1].lower()

        # Validate file type
        if extension not in ALLOWED_FILE_TYPES:
            return json.dumps({
                "success": False,
                "error": f"File type '.{extension}' not allowed for inventory import",
                "allowed_types": list(ALLOWED_FILE_TYPES.keys()),
                "suggestion": "Please convert your file to CSV or Excel format",
            })

        # Determine content-type
        resolved_content_type = content_type or ALLOWED_FILE_TYPES[extension]

        # Build metadata
        metadata = {
            "original_filename": filename,
            "upload_timestamp": datetime.utcnow().isoformat() + "Z",
            "import_batch_id": str(uuid.uuid4()),
        }
        if user_id:
            metadata["user_id"] = user_id
        if session_id:
            metadata["session_id"] = session_id

        # Initialize S3 client
        s3_client = SGAS3Client()

        # Generate unique key in temp folder
        key = s3_client.get_temp_path(filename)

        # Generate presigned POST URL
        result = s3_client.generate_presigned_post(
            key=key,
            content_type=resolved_content_type,
            expires_in=URL_EXPIRATION_SECONDS,
            content_length_range=(1, MAX_FILE_SIZE_BYTES),
            metadata=metadata,
        )

        if not result.get("success"):
            return json.dumps({
                "success": False,
                "error": result.get("error", "Failed to generate upload URL"),
            })

        # Add metadata to response for tracking
        result["metadata"] = metadata
        result["allowed_content_type"] = resolved_content_type
        result["original_filename"] = filename

        logger.info(
            "[IntakeTool] Generated upload URL: key=%s, user=%s, session=%s",
            key, user_id, session_id
        )

        return json.dumps(result)

    except Exception as e:
        debug_error(e, "request_file_upload_url", {"filename": filename})
        return json.dumps({
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        })


# =============================================================================
# Tool: verify_file_availability
# =============================================================================


@tool
def verify_file_availability(s3_key: str) -> str:
    """
    Verify that a file has been uploaded and is ready for processing.

    This tool checks if a file exists in S3 after upload, validates its
    content-type against allowed inventory formats, and returns metadata
    about the file. Uses retry logic with exponential backoff to handle
    S3 eventual consistency.

    Use this tool after the user has uploaded a file to confirm it was
    successfully received before proceeding with processing.

    Args:
        s3_key: The S3 object key returned from request_file_upload_url.
            Format: "temp/uploads/{uuid}_{filename}"

    Returns:
        JSON string with the following structure on success:
        {
            "success": true,
            "exists": true,
            "key": "temp/uploads/abc123_file.csv",
            "content_type": "text/csv",
            "content_type_valid": true,
            "content_length": 12345,
            "file_size_human": "12.1 KB",
            "last_modified": "2026-01-21T10:30:00Z",
            "etag": "abc123...",
            "ready_for_processing": true
        }

        On file not found (after retries):
        {
            "success": true,
            "exists": false,
            "key": "temp/uploads/abc123_file.csv",
            "error": "File not found after 3 retries",
            "ready_for_processing": false,
            "suggestion": "The upload may have failed. Please try uploading again."
        }

        On invalid content-type:
        {
            "success": true,
            "exists": true,
            "key": "temp/uploads/abc123_file.docx",
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "content_type_valid": false,
            "ready_for_processing": false,
            "error": "Content type not allowed for inventory import",
            "allowed_types": ["csv", "xlsx", "xls", "pdf", "xml", "jpg", "jpeg", "png", "txt"]
        }
    """
    try:
        # Initialize S3 client
        s3_client = SGAS3Client()

        # Get file metadata with retry logic (3 retries, exponential backoff)
        result = s3_client.get_file_metadata(
            key=s3_key,
            retry_count=3,
            retry_delay=1.0,
        )

        if not result.get("success"):
            return json.dumps({
                "success": False,
                "error": result.get("error", "Failed to check file"),
                "key": s3_key,
            })

        # File not found after retries
        if not result.get("exists"):
            return json.dumps({
                "success": True,
                "exists": False,
                "key": s3_key,
                "error": result.get("error", "File not found"),
                "ready_for_processing": False,
                "suggestion": "The upload may have failed. Please try uploading again.",
            })

        # Validate content-type
        content_type = result.get("content_type", "application/octet-stream")
        content_type_valid = content_type in CONTENT_TYPE_TO_EXTENSION

        # Determine readiness for processing
        ready_for_processing = result["exists"] and content_type_valid

        response = {
            "success": True,
            "exists": True,
            "key": s3_key,
            "content_type": content_type,
            "content_type_valid": content_type_valid,
            "content_length": result.get("content_length", 0),
            "file_size_human": result.get("file_size_human", "Unknown"),
            "last_modified": result.get("last_modified"),
            "etag": result.get("etag"),
            "ready_for_processing": ready_for_processing,
        }

        # Add error info if content-type invalid
        if not content_type_valid:
            response["error"] = "Content type not allowed for inventory import"
            response["allowed_types"] = list(ALLOWED_FILE_TYPES.keys())

        # Include custom metadata if present
        if result.get("metadata"):
            response["upload_metadata"] = result["metadata"]

        logger.info(
            "[IntakeTool] Verified file: key=%s, exists=%s, ready=%s",
            s3_key, result["exists"], ready_for_processing
        )

        return json.dumps(response)

    except Exception as e:
        debug_error(e, "verify_file_availability", {"s3_key": s3_key})
        return json.dumps({
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "key": s3_key,
        })
