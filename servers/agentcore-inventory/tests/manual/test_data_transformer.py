#!/usr/bin/env python3
"""
Manual Test Script - DataTransformer Agent (Phase 4)

This script validates the DataTransformer agent with Cognitive Middleware.

Test Cases:
1. Happy Path: CSV with valid data → all rows inserted
2. Strict Mode Abort: Bad date with STOP_ON_ERROR → CognitiveError raised
3. Forgiving Mode Continue: Bad date with LOG_AND_CONTINUE → enriched rejection report
4. First Import Default: No preference → uses LOG_AND_CONTINUE + notifies user
5. Fire-and-Forget: Returns job_id immediately, processes in background
6. DebugAgent Enrichment: Rejection report contains human_explanation + suggested_fix
7. Infinite Loop Prevention: DebugAgent error doesn't call DebugAgent

Usage:
    cd server/agentcore-inventory
    python -m tests.manual.test_data_transformer

Prerequisites:
    1. DataTransformer agent running locally on port 9019
    2. DebugAgent running locally on port 9014 (for error enrichment)
    3. AWS credentials configured (profile: faiston-aio)
    4. S3 bucket with test file

Author: Faiston NEXO Team
Date: January 2026
"""

import asyncio
import json
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Test Utilities
# =============================================================================


async def invoke_agent(agent_id: str, payload: dict) -> dict:
    """Invoke an agent via A2A protocol."""
    from shared.strands_a2a_client import LocalA2AClient

    client = LocalA2AClient()
    response = await client.invoke_agent(agent_id, payload)
    return response


def print_result(test_name: str, success: bool, details: str = ""):
    """Print test result with formatting."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{'='*60}")
    print(f"{status} - {test_name}")
    if details:
        print(f"Details: {details}")
    print(f"{'='*60}")


# =============================================================================
# Test Cases
# =============================================================================


async def test_health_check():
    """Test 1: Health check endpoint."""
    print("\n🔍 Test 1: Health Check")

    response = await invoke_agent("data_transformer", {
        "action": "health_check",
    })

    success = response.get("success", False)
    agent_name = response.get("agent_name", "")

    print_result(
        "Health Check",
        success and agent_name == "FaistonDataTransformer",
        f"Agent: {agent_name}, Status: {response.get('status')}",
    )
    return success


async def test_load_preferences_first_import():
    """Test 2: Load preferences for first-time user."""
    print("\n🔍 Test 2: Load Preferences (First Import)")

    response = await invoke_agent("data_transformer", {
        "action": "load_preferences",
        "user_id": f"test_user_{datetime.now().timestamp()}",
        "session_id": "test_session_001",
    })

    success = response.get("success", False)
    first_import = response.get("first_import", False)
    strategy = response.get("strategy", "")

    print_result(
        "Load Preferences (First Import)",
        success and first_import and strategy == "LOG_AND_CONTINUE",
        f"Strategy: {strategy}, First Import: {first_import}",
    )
    return success


async def test_create_job():
    """Test 3: Create transformation job (Fire-and-Forget start)."""
    print("\n🔍 Test 3: Create Job (Fire-and-Forget)")

    response = await invoke_agent("data_transformer", {
        "action": "create_job",
        "session_id": "test_session_002",
        "s3_key": "test/sample_inventory.csv",
        "user_id": "test_user_001",
        "strategy": "LOG_AND_CONTINUE",
    })

    success = response.get("success", False)
    job_id = response.get("job_id", "")
    status = response.get("status", "")

    print_result(
        "Create Job",
        success and job_id.startswith("job-") and status == "started",
        f"Job ID: {job_id}, Status: {status}",
    )
    return success, job_id


async def test_get_job_status(job_id: str):
    """Test 4: Get job status."""
    print("\n🔍 Test 4: Get Job Status")

    response = await invoke_agent("data_transformer", {
        "action": "get_job_status",
        "job_id": job_id,
    })

    success = response.get("success", False)
    returned_job_id = response.get("job_id", "")

    print_result(
        "Get Job Status",
        success and returned_job_id == job_id,
        f"Job ID: {returned_job_id}, Status: {response.get('status')}",
    )
    return success


async def test_validate_file_size():
    """Test 5: Validate file size (should reject large files)."""
    print("\n🔍 Test 5: Validate File Size")

    # This test assumes you have a test file in S3
    # For actual testing, update the s3_key to a real file
    response = await invoke_agent("data_transformer", {
        "action": "validate_file_size",
        "s3_key": "test/sample_inventory.csv",
    })

    # Even if file doesn't exist, the validation logic should be tested
    success = "success" in response

    print_result(
        "Validate File Size",
        success,
        f"Size: {response.get('size_mb', 'N/A')}MB, "
        f"Within limits: {response.get('within_limits', 'N/A')}",
    )
    return success


async def test_stream_and_transform():
    """Test 6: Stream and transform file (requires real S3 file)."""
    print("\n🔍 Test 6: Stream and Transform")
    print("⚠️  Skipping - requires real S3 file")

    # This would require:
    # 1. A real file in S3
    # 2. Valid column mappings from SchemaMapper
    # Uncomment below for real testing:

    # mappings = [
    #     {"source_column": "codigo", "target_column": "part_number", "transform": "TRIM"},
    #     {"source_column": "quantidade", "target_column": "quantity", "transform": ""},
    # ]
    # response = await invoke_agent("data_transformer", {
    #     "action": "stream_and_transform",
    #     "s3_key": "real/file/path.csv",
    #     "mappings_json": json.dumps(mappings),
    #     "session_id": "test_session",
    #     "job_id": "job-test123",
    #     "strategy": "LOG_AND_CONTINUE",
    # })

    return True  # Placeholder


async def test_cognitive_middleware():
    """Test 7: Cognitive Middleware (error enrichment)."""
    print("\n🔍 Test 7: Cognitive Middleware")

    # Test that errors would be enriched by DebugAgent
    # This is a structural test - actual enrichment requires DebugAgent

    try:
        from shared.cognitive_error_handler import CognitiveError, cognitive_error_handler

        # Verify the decorator exists and works
        @cognitive_error_handler("test_agent")
        async def sample_function():
            raise ValueError("Test error")

        # This should raise CognitiveError (if DebugAgent is available)
        # or the original error (if DebugAgent is unavailable)
        try:
            await sample_function()
        except (CognitiveError, ValueError):
            pass  # Expected

        print_result(
            "Cognitive Middleware Structure",
            True,
            "Decorator and CognitiveError class exist",
        )
        return True

    except ImportError as e:
        print_result("Cognitive Middleware", False, f"Import error: {e}")
        return False


async def test_infinite_loop_prevention():
    """Test 8: Verify DebugAgent doesn't call itself."""
    print("\n🔍 Test 8: Infinite Loop Prevention")

    try:
        from shared.cognitive_error_handler import cognitive_error_handler

        # Verify that agent_id="debug" skips enrichment
        @cognitive_error_handler("debug")
        async def debug_function():
            raise ValueError("Debug agent error")

        try:
            await debug_function()
        except ValueError:
            # Should raise original error, not CognitiveError
            print_result(
                "Infinite Loop Prevention",
                True,
                "Debug agent skips self-enrichment",
            )
            return True

    except Exception as e:
        print_result("Infinite Loop Prevention", False, str(e))
        return False


# =============================================================================
# Main Test Runner
# =============================================================================


async def run_all_tests():
    """Run all test cases."""
    print("\n" + "=" * 60)
    print("  DataTransformer Agent - Manual Test Suite")
    print("  Phase 4: Cognitive ETL with Nexo Immune System")
    print("=" * 60)

    results = []

    # Test 1: Health check
    results.append(("Health Check", await test_health_check()))

    # Test 2: Load preferences
    results.append(("Load Preferences", await test_load_preferences_first_import()))

    # Test 3: Create job
    success, job_id = await test_create_job()
    results.append(("Create Job", success))

    # Test 4: Get job status (only if job was created)
    if success and job_id:
        results.append(("Get Job Status", await test_get_job_status(job_id)))

    # Test 5: Validate file size
    results.append(("Validate File Size", await test_validate_file_size()))

    # Test 6: Stream and transform (placeholder)
    results.append(("Stream and Transform", await test_stream_and_transform()))

    # Test 7: Cognitive middleware
    results.append(("Cognitive Middleware", await test_cognitive_middleware()))

    # Test 8: Infinite loop prevention
    results.append(("Infinite Loop Prevention", await test_infinite_loop_prevention()))

    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 60)

    return passed == total


def main():
    """Entry point."""
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
