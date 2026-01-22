#!/usr/bin/env python3
"""
Manual Test Script - MCP Gateway Batch Insert Tool

Tests the sga_insert_pending_items_batch tool via MCP Gateway.

Test Cases:
1. Direct client test: Call postgres_client.insert_pending_items_batch directly
2. MCP Gateway test: Call via MCP Gateway (requires deployed Lambda)

Usage:
    cd server/agentcore-inventory
    python -m tests.manual.test_batch_insert

Prerequisites:
    1. AWS credentials configured (profile: faiston-aio)
    2. RDS Proxy accessible (via VPC or direct)
    3. For MCP test: Lambda deployed via GitHub Actions

Author: Faiston NEXO Team
Date: January 2026
"""

import json
import logging
import os
import sys
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_result(test_name: str, success: bool, details: str = ""):
    """Print test result with formatting."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status} | {test_name}")
    if details:
        print(f"    Details: {details}")


def test_direct_client():
    """
    Test 1: Direct PostgreSQL Client Test

    Calls insert_pending_items_batch directly on the postgres_client.
    Requires RDS Proxy access (VPC or bastion).
    """
    print("\n" + "=" * 60)
    print("TEST 1: Direct PostgreSQL Client Test")
    print("=" * 60)

    try:
        from tools.postgres_client import SGAPostgresClient

        client = SGAPostgresClient()

        # First, we need to create a test pending_entry record
        # to satisfy the FK constraint
        test_entry_id = str(uuid.uuid4())

        # Create parent entry
        logger.info(f"Creating test pending_entry with ID: {test_entry_id}")

        conn = client._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sga.pending_entries
                (entry_id, source_type, status, metadata)
                VALUES (%s, 'NF', 'PENDING', '{"test": true}')
            """, (test_entry_id,))
            conn.commit()

        logger.info("Parent entry created successfully")

        # Now test batch insert
        test_rows = [
            {
                "line_number": 1,
                "part_number": "TEST-BATCH-001",
                "description": "Test item 1 for batch insert",
                "quantity": 10,
                "unit_value": 100.00,
                "total_value": 1000.00,
            },
            {
                "line_number": 2,
                "part_number": "TEST-BATCH-002",
                "description": "Test item 2 for batch insert",
                "quantity": 5,
                "unit_value": 200.00,
                "total_value": 1000.00,
            },
            {
                "line_number": 3,
                "part_number": "TEST-BATCH-003",
                "description": "Test item 3 for batch insert",
                "quantity": 20,
                "unit_value": 50.00,
                "total_value": 1000.00,
                "serial_numbers": ["SN001", "SN002", "SN003"],
            },
        ]

        logger.info(f"Inserting {len(test_rows)} test rows...")

        result = client.insert_pending_items_batch(
            rows=test_rows,
            entry_id=test_entry_id,
        )

        logger.info(f"Result: {json.dumps(result, indent=2)}")

        success = result.get("success", False)
        inserted = result.get("inserted_count", 0)
        errors = result.get("errors", [])

        print_result(
            "Direct Client Batch Insert",
            success and inserted == 3,
            f"Inserted: {inserted}, Errors: {len(errors)}"
        )

        # Cleanup: Delete test data
        logger.info("Cleaning up test data...")
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sga.pending_entry_items WHERE entry_id = %s",
                (test_entry_id,)
            )
            cur.execute(
                "DELETE FROM sga.pending_entries WHERE entry_id = %s",
                (test_entry_id,)
            )
            conn.commit()

        logger.info("Cleanup complete")
        return success

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        print_result("Direct Client Batch Insert", False, str(e))
        return False


def test_invalid_entry_id():
    """
    Test 2: Invalid Entry ID Test

    Verifies that batch insert fails gracefully when entry_id doesn't exist.
    """
    print("\n" + "=" * 60)
    print("TEST 2: Invalid Entry ID Test")
    print("=" * 60)

    try:
        from tools.postgres_client import SGAPostgresClient

        client = SGAPostgresClient()

        # Use a non-existent entry_id
        fake_entry_id = str(uuid.uuid4())

        test_rows = [
            {"line_number": 1, "part_number": "FAKE-001", "quantity": 1},
        ]

        logger.info(f"Testing with non-existent entry_id: {fake_entry_id}")

        result = client.insert_pending_items_batch(
            rows=test_rows,
            entry_id=fake_entry_id,
        )

        logger.info(f"Result: {json.dumps(result, indent=2)}")

        # Should fail with FK error
        success = result.get("success", True) is False
        errors = result.get("errors", [])

        has_fk_error = any(
            "does not exist" in str(e.get("error", "")).lower()
            for e in errors
        )

        print_result(
            "Invalid Entry ID Rejection",
            success and has_fk_error,
            f"Correctly rejected: {has_fk_error}"
        )

        return success and has_fk_error

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        print_result("Invalid Entry ID Rejection", False, str(e))
        return False


def test_mcp_gateway():
    """
    Test 3: MCP Gateway Test

    Calls the batch insert tool via the deployed MCP Gateway.
    Requires the Lambda to be deployed.
    """
    print("\n" + "=" * 60)
    print("TEST 3: MCP Gateway Test (Deployed Lambda)")
    print("=" * 60)

    try:
        from tools.mcp_gateway_client import MCPGatewayClientFactory

        client = MCPGatewayClientFactory.create_from_env()

        # First create a test entry via direct client
        from tools.postgres_client import SGAPostgresClient
        pg_client = SGAPostgresClient()

        test_entry_id = str(uuid.uuid4())

        # Create parent entry
        logger.info(f"Creating test pending_entry with ID: {test_entry_id}")

        conn = pg_client._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sga.pending_entries
                (entry_id, source_type, status, metadata)
                VALUES (%s, 'NF', 'PENDING', '{"test": "mcp_gateway"}')
            """, (test_entry_id,))
            conn.commit()

        # Now test via MCP Gateway
        test_rows = [
            {
                "line_number": 1,
                "part_number": "MCP-TEST-001",
                "description": "MCP Gateway test item",
                "quantity": 100,
            },
        ]

        logger.info("Calling MCP Gateway sga_insert_pending_items_batch...")

        result = client.invoke_tool(
            tool_name="sga_insert_pending_items_batch",
            parameters={
                "rows": test_rows,
                "session_id": test_entry_id,
            },
        )

        logger.info(f"MCP Gateway Result: {json.dumps(result, indent=2)}")

        success = result.get("success", False)
        inserted = result.get("inserted_count", 0)

        print_result(
            "MCP Gateway Batch Insert",
            success and inserted == 1,
            f"Inserted: {inserted}"
        )

        # Cleanup
        logger.info("Cleaning up test data...")
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sga.pending_entry_items WHERE entry_id = %s",
                (test_entry_id,)
            )
            cur.execute(
                "DELETE FROM sga.pending_entries WHERE entry_id = %s",
                (test_entry_id,)
            )
            conn.commit()

        return success

    except Exception as e:
        logger.error(f"MCP Gateway test failed: {e}")
        print_result("MCP Gateway Batch Insert", False, str(e))
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("BATCH INSERT TOOL - MANUAL TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1: Direct client
    results.append(("Direct Client", test_direct_client()))

    # Test 2: Invalid entry_id
    results.append(("Invalid Entry ID", test_invalid_entry_id()))

    # Test 3: MCP Gateway (only if Lambda is deployed)
    if os.environ.get("TEST_MCP_GATEWAY", "false").lower() == "true":
        results.append(("MCP Gateway", test_mcp_gateway()))
    else:
        print("\n⏭️  Skipping MCP Gateway test (set TEST_MCP_GATEWAY=true to enable)")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
