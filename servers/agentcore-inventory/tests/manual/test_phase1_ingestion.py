#!/usr/bin/env python3
# =============================================================================
# Phase 1 Integration Test: Secure File Ingestion
# =============================================================================
# Manual integration test for the Phase 1 file ingestion layer.
#
# This test validates the complete upload workflow:
# 1. Generate presigned POST URL
# 2. Upload a test file using the presigned URL
# 3. Verify the file exists in S3
# 4. Validate content-type
# 5. Cleanup
#
# USAGE:
#   cd server/agentcore-inventory
#   AWS_PROFILE=faiston-aio python tests/manual/test_phase1_ingestion.py
#
# PREREQUISITES:
# - AWS credentials configured (profile: faiston-aio)
# - Access to S3 bucket: faiston-one-sga-documents-prod
# - requests library installed (pip install requests)
#
# VERSION: 2026-01-21T18:00:00Z
# =============================================================================

import json
import os
import sys
from datetime import datetime
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests

from tools.s3_client import SGAS3Client


class TestColors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(message: str) -> None:
    """Print a formatted header."""
    print(f"\n{TestColors.BOLD}{TestColors.BLUE}{'=' * 60}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.BLUE}{message}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.BLUE}{'=' * 60}{TestColors.RESET}")


def print_pass(test_name: str, details: Optional[str] = None) -> None:
    """Print a PASS result."""
    print(f"\n{TestColors.GREEN}[PASS]{TestColors.RESET} {test_name}")
    if details:
        for line in details.split("\n"):
            print(f"       {line}")


def print_fail(test_name: str, error: str) -> None:
    """Print a FAIL result."""
    print(f"\n{TestColors.RED}[FAIL]{TestColors.RESET} {test_name}")
    print(f"       {TestColors.RED}Error: {error}{TestColors.RESET}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{TestColors.YELLOW}[INFO]{TestColors.RESET} {message}")


def run_phase1_integration_test() -> bool:
    """
    Run the complete Phase 1 integration test.

    Returns:
        True if all tests pass, False otherwise.
    """
    print_header("Phase 1 File Ingestion - Integration Test")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")

    # Initialize S3 client
    s3_client = SGAS3Client()
    print(f"Bucket: {s3_client.bucket}")

    all_passed = True
    uploaded_key: Optional[str] = None

    # Test data
    test_filename = "test_phase1_upload.csv"
    test_content = b"product_id,name,quantity\n001,Widget A,100\n002,Widget B,200\n"
    test_content_type = "text/csv"

    try:
        # -----------------------------------------------------------------
        # Test 1: Generate presigned POST URL
        # -----------------------------------------------------------------
        print_info("Testing presigned POST URL generation...")

        result = s3_client.generate_presigned_post(
            key=s3_client.get_temp_path(test_filename),
            content_type=test_content_type,
            expires_in=300,
            content_length_range=(1, 104857600),
            metadata={
                "test_run": "phase1_integration",
                "test_timestamp": datetime.utcnow().isoformat(),
            },
        )

        if not result.get("success"):
            print_fail("Generate presigned POST URL", result.get("error", "Unknown error"))
            return False

        uploaded_key = result["key"]
        print_pass(
            "Generate presigned POST URL",
            f"Key: {uploaded_key}\n"
            f"Expires at: {result.get('expires_at', 'N/A')}\n"
            f"Max file size: {result.get('max_file_size_bytes', 0) / (1024 * 1024):.0f} MB"
        )

        # -----------------------------------------------------------------
        # Test 2: Upload test file using presigned URL
        # -----------------------------------------------------------------
        print_info("Uploading test file to S3...")

        # Build multipart form data for POST
        files = {
            "file": (test_filename, test_content, test_content_type),
        }

        # Include all fields from presigned response
        upload_data = result["fields"].copy()

        # POST to S3
        response = requests.post(
            result["url"],
            data=upload_data,
            files=files,
            timeout=30,
        )

        # 204 No Content is the expected success response for S3 POST
        if response.status_code not in (200, 204):
            print_fail(
                "Upload test file to S3",
                f"Status: {response.status_code}\nResponse: {response.text[:500]}"
            )
            all_passed = False
        else:
            print_pass(
                "Upload test file to S3",
                f"Status: {response.status_code} {'No Content' if response.status_code == 204 else 'OK'}\n"
                f"File size: {len(test_content)} bytes"
            )

        # -----------------------------------------------------------------
        # Test 3: Verify file exists (with retry)
        # -----------------------------------------------------------------
        print_info("Verifying file exists in S3 (with retry)...")

        metadata_result = s3_client.get_file_metadata(
            key=uploaded_key,
            retry_count=3,
            retry_delay=1.0,
        )

        if not metadata_result.get("success") or not metadata_result.get("exists"):
            print_fail(
                "Verify file exists",
                metadata_result.get("error", "File not found after retries")
            )
            all_passed = False
        else:
            retry_info = "(retry 1/3)"  # First attempt succeeded
            print_pass(
                f"Verify file exists {retry_info}",
                f"Content-Type: {metadata_result.get('content_type', 'N/A')} "
                f"{'✓' if metadata_result.get('content_type') == test_content_type else '✗'}\n"
                f"Size: {metadata_result.get('file_size_human', 'N/A')}\n"
                f"Last Modified: {metadata_result.get('last_modified', 'N/A')}"
            )

        # -----------------------------------------------------------------
        # Test 4: Validate content-type
        # -----------------------------------------------------------------
        if metadata_result.get("exists"):
            actual_content_type = metadata_result.get("content_type", "")
            content_type_valid = actual_content_type == test_content_type

            if content_type_valid:
                print_pass(
                    "Validate content-type",
                    f"Expected: {test_content_type}\n"
                    f"Actual: {actual_content_type}\n"
                    f"Valid: True"
                )
            else:
                print_fail(
                    "Validate content-type",
                    f"Expected: {test_content_type}, Got: {actual_content_type}"
                )
                all_passed = False

    except Exception as e:
        print_fail("Integration test", str(e))
        all_passed = False

    finally:
        # -----------------------------------------------------------------
        # Cleanup: Delete test file
        # -----------------------------------------------------------------
        if uploaded_key:
            print_info(f"Cleaning up test file: {uploaded_key}")
            try:
                cleanup_success = s3_client.delete_file(uploaded_key)
                if cleanup_success:
                    print_pass("Cleanup test file", f"Deleted: {uploaded_key}")
                else:
                    print_fail("Cleanup test file", "Delete operation returned False")
            except Exception as e:
                print_fail("Cleanup test file", str(e))

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    print_header("Test Results Summary")
    if all_passed:
        print(f"\n{TestColors.GREEN}{TestColors.BOLD}=== SUCCESS: All Phase 1 tests passed! ==={TestColors.RESET}\n")
    else:
        print(f"\n{TestColors.RED}{TestColors.BOLD}=== FAILED: Some tests did not pass ==={TestColors.RESET}\n")

    return all_passed


def test_intake_tools() -> bool:
    """
    Test the intake tools directly (without orchestrator).

    This tests the Strands tool functions in isolation.

    Returns:
        True if all tests pass, False otherwise.
    """
    print_header("Intake Tools - Direct Test")

    try:
        from agents.tools.intake_tools import (
            request_file_upload_url,
            verify_file_availability,
            ALLOWED_FILE_TYPES,
        )

        all_passed = True

        # Test 1: Valid file type
        print_info("Testing request_file_upload_url with valid file type...")
        result = json.loads(request_file_upload_url(
            filename="test_inventory.csv",
            user_id="test-user",
            session_id="test-session",
        ))

        if result.get("success"):
            print_pass(
                "request_file_upload_url (valid)",
                f"Key: {result.get('key', 'N/A')}\n"
                f"Content-Type: {result.get('allowed_content_type', 'N/A')}"
            )
        else:
            print_fail("request_file_upload_url (valid)", result.get("error", "Unknown"))
            all_passed = False

        # Test 2: Invalid file type
        print_info("Testing request_file_upload_url with invalid file type...")
        result = json.loads(request_file_upload_url(
            filename="document.docx",
            user_id="test-user",
        ))

        if not result.get("success") and "not allowed" in result.get("error", "").lower():
            print_pass(
                "request_file_upload_url (invalid type rejection)",
                f"Error: {result.get('error', 'N/A')}\n"
                f"Allowed types: {result.get('allowed_types', [])}"
            )
        else:
            print_fail(
                "request_file_upload_url (invalid type rejection)",
                "Should have rejected .docx file type"
            )
            all_passed = False

        # Test 3: Verify non-existent file
        print_info("Testing verify_file_availability with non-existent file...")
        result = json.loads(verify_file_availability(
            s3_key="temp/uploads/nonexistent_file_12345.csv"
        ))

        if result.get("exists") is False:
            print_pass(
                "verify_file_availability (non-existent)",
                f"Exists: {result.get('exists', 'N/A')}\n"
                f"Error: {result.get('error', 'N/A')}"
            )
        else:
            print_fail(
                "verify_file_availability (non-existent)",
                "Should have returned exists=False"
            )
            all_passed = False

        # Summary
        print_header("Intake Tools Test Summary")
        if all_passed:
            print(f"\n{TestColors.GREEN}{TestColors.BOLD}=== SUCCESS: All intake tool tests passed! ==={TestColors.RESET}\n")
        else:
            print(f"\n{TestColors.RED}{TestColors.BOLD}=== FAILED: Some intake tool tests failed ==={TestColors.RESET}\n")

        return all_passed

    except ImportError as e:
        print_fail("Import intake tools", str(e))
        return False


if __name__ == "__main__":
    print(f"\n{TestColors.BOLD}Phase 1 Secure File Ingestion - Manual Integration Test{TestColors.RESET}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("-" * 60)

    # Check AWS profile
    aws_profile = os.environ.get("AWS_PROFILE", "default")
    print(f"AWS Profile: {aws_profile}")

    if aws_profile != "faiston-aio":
        print(f"\n{TestColors.YELLOW}WARNING: Expected AWS_PROFILE=faiston-aio, got {aws_profile}{TestColors.RESET}")
        print("Run with: AWS_PROFILE=faiston-aio python tests/manual/test_phase1_ingestion.py\n")

    # Run tests
    results = []

    # Test 1: Intake tools (direct)
    print("\n" + "=" * 60)
    print("PART 1: Intake Tools Direct Test")
    print("=" * 60)
    results.append(("Intake Tools", test_intake_tools()))

    # Test 2: Full S3 integration
    print("\n" + "=" * 60)
    print("PART 2: Full S3 Integration Test")
    print("=" * 60)
    results.append(("S3 Integration", run_phase1_integration_test()))

    # Final summary
    print("\n" + "=" * 60)
    print(f"{TestColors.BOLD}FINAL SUMMARY{TestColors.RESET}")
    print("=" * 60)
    for test_name, passed in results:
        status = f"{TestColors.GREEN}PASS{TestColors.RESET}" if passed else f"{TestColors.RED}FAIL{TestColors.RESET}"
        print(f"  {test_name}: {status}")

    all_passed = all(passed for _, passed in results)
    exit_code = 0 if all_passed else 1

    print(f"\n{TestColors.BOLD}Exit code: {exit_code}{TestColors.RESET}\n")
    sys.exit(exit_code)
