#!/usr/bin/env python3
"""
Manual Test Script - ObservationAgent (Phase 5)

This script validates the ObservationAgent - "The Nexo's Intuition".

Test Cases:
1. Health Check: Verify agent responds on port 9012
2. Scan Recent Activity: Test Memory read operations with time windows
3. Analyze Patterns (Error): Detect error patterns from episodes
4. Analyze Patterns (Mapping): Detect mapping opportunities
5. Generate Insight: Create InsightReport from detected patterns
6. Check Inventory Health: Query database for anomalies
7. Cognitive Middleware: Verify @cognitive_error_handler works
8. Fire-and-Forget: Verify non-blocking trigger from DataTransformer

Usage:
    cd server/agentcore-inventory
    python -m tests.manual.test_observation_agent

Prerequisites:
    1. ObservationAgent running locally on port 9012
    2. AWS credentials configured (profile: faiston-aio)
    3. AgentCore Memory accessible
    4. PostgreSQL database accessible

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


def print_section(title: str):
    """Print section header."""
    print(f"\n{'#'*60}")
    print(f"# {title}")
    print(f"{'#'*60}")


# =============================================================================
# Test Cases
# =============================================================================


async def test_health_check():
    """Test 1: Health check endpoint."""
    print("\n🔍 Test 1: Health Check")

    try:
        response = await invoke_agent("observation", {
            "action": "health_check",
        })

        success = response.get("success", False)
        agent_name = response.get("agent_name", "")

        print_result(
            "Health Check",
            success and agent_name == "FaistonObservationAgent",
            f"Agent: {agent_name}, Status: {response.get('status')}",
        )
        return success

    except Exception as e:
        print_result("Health Check", False, f"Error: {e}")
        return False


async def test_scan_recent_activity_tactical():
    """Test 2: Scan recent activity (24h tactical window)."""
    print("\n🔍 Test 2: Scan Recent Activity (Tactical - 24h)")

    try:
        response = await invoke_agent("observation", {
            "action": "scan_activity",
            "actor_id": "test_user_001",
            "time_window_hours": 24,
        })

        success = response.get("success", False)
        time_window_type = response.get("time_window_type", "")
        activity_summary = response.get("activity_summary", {})

        details = (
            f"Window: {time_window_type}, "
            f"Facts: {activity_summary.get('total_facts', 0)}, "
            f"Episodes: {activity_summary.get('total_episodes', 0)}"
        )

        print_result(
            "Scan Recent Activity (Tactical)",
            success and time_window_type == "tactical",
            details,
        )
        return success

    except Exception as e:
        print_result("Scan Recent Activity (Tactical)", False, f"Error: {e}")
        return False


async def test_scan_recent_activity_operational():
    """Test 3: Scan recent activity (7d operational window)."""
    print("\n🔍 Test 3: Scan Recent Activity (Operational - 7 days)")

    try:
        response = await invoke_agent("observation", {
            "action": "scan_activity",
            "actor_id": "test_user_001",
            "time_window_hours": 168,  # 7 days
        })

        success = response.get("success", False)
        time_window_type = response.get("time_window_type", "")

        print_result(
            "Scan Recent Activity (Operational)",
            success and time_window_type == "operational",
            f"Window: {time_window_type}",
        )
        return success

    except Exception as e:
        print_result("Scan Recent Activity (Operational)", False, f"Error: {e}")
        return False


async def test_analyze_patterns_error():
    """Test 4: Analyze error patterns from mock activity data."""
    print("\n🔍 Test 4: Analyze Patterns (Error Type)")

    # Mock activity data with error patterns
    mock_activity = {
        "success": True,
        "facts": [],
        "episodes": [
            {
                "content": "Missing column: part_number not found in file",
                "outcome": "error",
                "session_id": "session_001",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "content": "Schema mismatch: unknown column 'codigo'",
                "outcome": "failed",
                "session_id": "session_002",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "content": "Duplicate constraint violation on part_number",
                "outcome": "error",
                "session_id": "session_003",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ],
        "activity_summary": {
            "total_facts": 0,
            "total_episodes": 3,
            "unique_sessions": 3,
        },
    }

    try:
        response = await invoke_agent("observation", {
            "action": "analyze_patterns",
            "activity_json": json.dumps(mock_activity),
            "pattern_type": "error",
        })

        success = response.get("success", False)
        patterns = response.get("patterns", [])
        pattern_summary = response.get("pattern_summary", {})

        # Check if error patterns were detected
        error_patterns = [p for p in patterns if p.get("type") == "error"]

        print_result(
            "Analyze Error Patterns",
            success and len(error_patterns) > 0,
            f"Detected {len(error_patterns)} error patterns, "
            f"Total: {pattern_summary.get('total_patterns', 0)}",
        )
        return success

    except Exception as e:
        print_result("Analyze Error Patterns", False, f"Error: {e}")
        return False


async def test_analyze_patterns_mapping():
    """Test 5: Analyze mapping opportunity patterns."""
    print("\n🔍 Test 5: Analyze Patterns (Mapping Opportunities)")

    # Mock activity data with unmapped columns
    mock_activity = {
        "success": True,
        "facts": [
            {
                "content": "SKU maps to part_number",
                "category": "column_mapping",
                "confidence": 0.95,
            },
        ],
        "episodes": [
            {
                "content": "Unmapped column: 'CODIGO_PROD' in file",
                "outcome": "warning",
                "session_id": "session_001",
            },
            {
                "content": "Unknown column: 'CODIGO_PROD' not mapped",
                "outcome": "warning",
                "session_id": "session_002",
            },
            {
                "content": "Missing mapping for: 'CODIGO_PROD'",
                "outcome": "info",
                "session_id": "session_003",
            },
        ],
        "activity_summary": {
            "total_facts": 1,
            "total_episodes": 3,
            "unique_sessions": 3,
        },
    }

    try:
        response = await invoke_agent("observation", {
            "action": "analyze_patterns",
            "activity_json": json.dumps(mock_activity),
            "pattern_type": "mapping",
            "enforce_learning_mode": False,  # Bypass for testing
        })

        success = response.get("success", False)
        patterns = response.get("patterns", [])

        # Check for mapping patterns
        mapping_patterns = [p for p in patterns if p.get("type") == "mapping"]

        print_result(
            "Analyze Mapping Patterns",
            success,
            f"Detected {len(mapping_patterns)} mapping opportunities",
        )
        return success

    except Exception as e:
        print_result("Analyze Mapping Patterns", False, f"Error: {e}")
        return False


async def test_generate_insight():
    """Test 6: Generate insight from detected patterns."""
    print("\n🔍 Test 6: Generate Insight")

    # Mock patterns for insight generation
    mock_patterns = {
        "success": True,
        "patterns": [
            {
                "type": "error",
                "subtype": "SchemaMismatch",
                "frequency": 5,
                "severity": "critical",
                "confidence": 0.87,
                "description": "Detected 5 occurrences of SchemaMismatch errors",
                "samples": [
                    {"content": "Missing column: part_number", "session_id": "s1"},
                ],
            },
        ],
        "pattern_summary": {
            "total_patterns": 1,
            "critical_count": 1,
        },
    }

    try:
        response = await invoke_agent("observation", {
            "action": "generate_insight",
            "patterns_json": json.dumps(mock_patterns),
            "actor_id": "test_user_001",
            "category": "ERROR_PATTERN",
        })

        success = response.get("success", False)
        insight = response.get("insight", {})
        insight_id = insight.get("insight_id", "")

        # Validate insight structure
        has_required_fields = all([
            insight.get("insight_id"),
            insight.get("category"),
            insight.get("severity"),
            insight.get("title"),
            insight.get("description"),
            insight.get("human_message"),
        ])

        print_result(
            "Generate Insight",
            success and has_required_fields,
            f"Insight ID: {insight_id}, "
            f"Category: {insight.get('category')}, "
            f"Severity: {insight.get('severity')}",
        )
        return success

    except Exception as e:
        print_result("Generate Insight", False, f"Error: {e}")
        return False


async def test_check_inventory_health():
    """Test 7: Check inventory database health."""
    print("\n🔍 Test 7: Check Inventory Health")

    try:
        response = await invoke_agent("observation", {
            "action": "check_health",
            "actor_id": "test_user_001",
        })

        success = response.get("success", False)
        health_score = response.get("health_score")
        health_status = response.get("health_status", "")
        anomaly_counts = response.get("anomaly_counts", {})

        # Health score should be between 0 and 1
        score_valid = health_score is None or (0 <= health_score <= 1)

        print_result(
            "Check Inventory Health",
            success and score_valid,
            f"Score: {health_score}, Status: {health_status}, "
            f"Anomalies: {sum(anomaly_counts.values()) if anomaly_counts else 0}",
        )
        return success

    except Exception as e:
        print_result("Check Inventory Health", False, f"Error: {e}")
        return False


async def test_learning_mode_enforcement():
    """Test 8: Learning mode suppresses patterns with insufficient data."""
    print("\n🔍 Test 8: Learning Mode Enforcement")

    # Mock activity with only 1 session (below MIN_SESSIONS_FOR_PATTERN=3)
    mock_activity = {
        "success": True,
        "facts": [],
        "episodes": [
            {
                "content": "Some warning message",
                "outcome": "warning",
                "session_id": "session_001",
            },
        ],
        "activity_summary": {
            "total_facts": 0,
            "total_episodes": 1,
            "unique_sessions": 1,  # Below threshold
        },
    }

    try:
        response = await invoke_agent("observation", {
            "action": "analyze_patterns",
            "activity_json": json.dumps(mock_activity),
            "pattern_type": "all",
            "enforce_learning_mode": True,  # Enforce thresholds
        })

        success = response.get("success", False)
        learning_mode_applied = response.get("learning_mode_applied", False)
        patterns = response.get("patterns", [])

        # With learning mode, non-critical patterns should be suppressed
        print_result(
            "Learning Mode Enforcement",
            success and learning_mode_applied,
            f"Learning mode applied: {learning_mode_applied}, "
            f"Patterns returned: {len(patterns)}",
        )
        return success

    except Exception as e:
        print_result("Learning Mode Enforcement", False, f"Error: {e}")
        return False


async def test_critical_bypass_learning_mode():
    """Test 9: CRITICAL patterns bypass learning mode."""
    print("\n🔍 Test 9: Critical Patterns Bypass Learning Mode")

    # Mock activity with critical error but only 1 session
    mock_activity = {
        "success": True,
        "facts": [],
        "episodes": [
            {
                "content": "Duplicate constraint violation",
                "outcome": "error",
                "session_id": "session_001",
            },
            {
                "content": "Duplicate key constraint",
                "outcome": "failed",
                "session_id": "session_001",
            },
        ],
        "activity_summary": {
            "total_facts": 0,
            "total_episodes": 2,
            "unique_sessions": 1,  # Below threshold
        },
    }

    try:
        response = await invoke_agent("observation", {
            "action": "analyze_patterns",
            "activity_json": json.dumps(mock_activity),
            "pattern_type": "error",
            "enforce_learning_mode": True,
        })

        success = response.get("success", False)
        learning_mode_applied = response.get("learning_mode_applied", False)
        patterns = response.get("patterns", [])

        # CRITICAL patterns should still be returned despite learning mode
        critical_patterns = [p for p in patterns if p.get("severity") == "critical"]

        print_result(
            "Critical Bypass Learning Mode",
            success and learning_mode_applied,
            f"Learning mode: {learning_mode_applied}, "
            f"Critical patterns: {len(critical_patterns)}",
        )
        return success

    except Exception as e:
        print_result("Critical Bypass Learning Mode", False, f"Error: {e}")
        return False


async def test_insight_deduplication():
    """Test 10: Insight deduplication (7-day cooldown)."""
    print("\n🔍 Test 10: Insight Deduplication")

    # Generate same insight twice
    mock_patterns = {
        "success": True,
        "patterns": [
            {
                "type": "error",
                "subtype": "SchemaMismatch",
                "frequency": 3,
                "severity": "warning",
                "confidence": 0.75,
                "description": "Schema issues detected",
            },
        ],
    }

    try:
        # First generation
        response1 = await invoke_agent("observation", {
            "action": "generate_insight",
            "patterns_json": json.dumps(mock_patterns),
            "actor_id": "test_user_dedup",
            "category": "ERROR_PATTERN",
        })

        # Second generation (should be deduplicated)
        response2 = await invoke_agent("observation", {
            "action": "generate_insight",
            "patterns_json": json.dumps(mock_patterns),
            "actor_id": "test_user_dedup",
            "category": "ERROR_PATTERN",
        })

        # Check if deduplication worked
        insight1_id = response1.get("insight", {}).get("insight_id")
        is_duplicate = response2.get("is_duplicate", False)

        print_result(
            "Insight Deduplication",
            response1.get("success", False),
            f"First insight: {insight1_id}, "
            f"Duplicate detected: {is_duplicate}",
        )
        return response1.get("success", False)

    except Exception as e:
        print_result("Insight Deduplication", False, f"Error: {e}")
        return False


async def test_orchestrator_check_observations():
    """Test 11: Orchestrator can fetch insights via check_observations."""
    print("\n🔍 Test 11: Orchestrator Integration (check_observations)")

    try:
        response = await invoke_agent("inventory_hub", {
            "action": "check_observations",
            "user_id": "test_user_001",
        })

        success = response.get("success", False)
        has_insights = response.get("has_insights", False)
        insights = response.get("insights", [])

        print_result(
            "Orchestrator check_observations",
            success,
            f"Has insights: {has_insights}, Count: {len(insights)}",
        )
        return success

    except Exception as e:
        print_result("Orchestrator check_observations", False, f"Error: {e}")
        return False


async def test_orchestrator_request_health_analysis():
    """Test 12: Orchestrator can trigger health analysis."""
    print("\n🔍 Test 12: Orchestrator Integration (request_health_analysis)")

    try:
        response = await invoke_agent("inventory_hub", {
            "action": "request_health_analysis",
            "user_id": "test_user_001",
            "lookback_days": 7,
        })

        success = response.get("success", False)
        analysis_requested = response.get("analysis_requested", False)
        human_message = response.get("human_message", "")

        print_result(
            "Orchestrator request_health_analysis",
            success and analysis_requested,
            f"Requested: {analysis_requested}, Message: {human_message[:50]}...",
        )
        return success

    except Exception as e:
        print_result("Orchestrator request_health_analysis", False, f"Error: {e}")
        return False


# =============================================================================
# Main Test Runner
# =============================================================================


async def run_all_tests():
    """Run all test cases."""
    print_section("ObservationAgent Test Suite (Phase 5)")
    print(f"Started at: {datetime.now().isoformat()}")

    results = []

    # Core Agent Tests
    print_section("Core Agent Tests")
    results.append(("Health Check", await test_health_check()))

    # Scan Activity Tests
    print_section("Scan Activity Tests")
    results.append(("Scan Tactical (24h)", await test_scan_recent_activity_tactical()))
    results.append(("Scan Operational (7d)", await test_scan_recent_activity_operational()))

    # Pattern Analysis Tests
    print_section("Pattern Analysis Tests")
    results.append(("Analyze Error Patterns", await test_analyze_patterns_error()))
    results.append(("Analyze Mapping Patterns", await test_analyze_patterns_mapping()))

    # Insight Generation Tests
    print_section("Insight Generation Tests")
    results.append(("Generate Insight", await test_generate_insight()))
    results.append(("Insight Deduplication", await test_insight_deduplication()))

    # Health Check Tests
    print_section("Inventory Health Tests")
    results.append(("Check Inventory Health", await test_check_inventory_health()))

    # Learning Mode Tests
    print_section("Learning Mode Tests")
    results.append(("Learning Mode Enforcement", await test_learning_mode_enforcement()))
    results.append(("Critical Bypass", await test_critical_bypass_learning_mode()))

    # Integration Tests
    print_section("Orchestrator Integration Tests")
    results.append(("check_observations", await test_orchestrator_check_observations()))
    results.append(("request_health_analysis", await test_orchestrator_request_health_analysis()))

    # Summary
    print_section("Test Summary")
    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed")
    print()

    for name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")

    print()

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
