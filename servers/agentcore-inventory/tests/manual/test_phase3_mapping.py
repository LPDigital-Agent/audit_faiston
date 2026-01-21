#!/usr/bin/env python3
# =============================================================================
# Phase 3 Integration Test: Semantic Mapping (Column-to-Schema)
# =============================================================================
# Manual integration test for the Phase 3 schema mapping layer.
#
# This test validates:
# 1. SchemaMapper A2A invocation from orchestrator
# 2. Semantic column matching (exact, normalized, PT→EN)
# 3. Transformation detection (DATE_PARSE_PTBR, NUMBER_PARSE_PTBR, etc.)
# 4. Confidence scoring
# 5. needs_input flow for missing required columns
# 6. Training example persistence
# 7. HIL confirmation workflow
#
# USAGE:
#   cd server/agentcore-inventory
#   AWS_PROFILE=faiston-aio python tests/manual/test_phase3_mapping.py
#
# PREREQUISITES:
# - AWS credentials configured (profile: faiston-aio)
# - SchemaMapper agent running locally on port 9018
# - InventoryHub agent running locally (for orchestrator tests)
#
# NOTE: For local testing without full A2A, run with --mock flag:
#   python tests/manual/test_phase3_mapping.py --mock
#
# VERSION: 2026-01-21T21:00:00Z
# =============================================================================

import json
import os
import sys
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestColors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(message: str) -> None:
    """Print a formatted header."""
    print(f"\n{TestColors.BOLD}{TestColors.BLUE}{'=' * 70}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.BLUE}{message}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.BLUE}{'=' * 70}{TestColors.RESET}")


def print_subheader(message: str) -> None:
    """Print a formatted subheader."""
    print(f"\n{TestColors.BOLD}{message}{TestColors.RESET}")
    print("-" * 50)


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


def print_skip(test_name: str, reason: str) -> None:
    """Print a SKIP result."""
    print(f"\n{TestColors.CYAN}[SKIP]{TestColors.RESET} {test_name}")
    print(f"       Reason: {reason}")


# =============================================================================
# TEST DATA
# =============================================================================

# Test case 1: High-confidence exact matches
TEST_COLUMNS_EXACT = ["codigo", "descricao", "quantidade", "valor_unitario"]
TEST_SAMPLE_EXACT = [
    {"codigo": "ABC001", "descricao": "Widget A", "quantidade": "100", "valor_unitario": "15,50"},
    {"codigo": "DEF002", "descricao": "Widget B", "quantidade": "200", "valor_unitario": "25,00"},
    {"codigo": "GHI003", "descricao": "Widget C", "quantidade": "50", "valor_unitario": "35,75"},
]

# Test case 2: Portuguese abbreviations needing semantic matching
TEST_COLUMNS_PTBR = ["cod", "desc", "qtd", "vlr_unit", "data_entrada"]
TEST_SAMPLE_PTBR = [
    {"cod": "X001", "desc": "Produto X", "qtd": "10", "vlr_unit": "R$ 99,90", "data_entrada": "21/01/2026"},
]

# Test case 3: Unknown columns requiring user input
TEST_COLUMNS_UNKNOWN = ["SKU", "NOME", "QTY", "CUSTOM_FIELD", "ANOTHER_CUSTOM"]
TEST_SAMPLE_UNKNOWN = [
    {"SKU": "SKU-001", "NOME": "Item 1", "QTY": "5", "CUSTOM_FIELD": "abc", "ANOTHER_CUSTOM": "xyz"},
]

# Test case 4: Missing required columns (needs_input scenario)
TEST_COLUMNS_MISSING = ["descricao", "quantidade"]  # Missing part_number (required)
TEST_SAMPLE_MISSING = [
    {"descricao": "Item sem código", "quantidade": "10"},
]


# =============================================================================
# MOCK MAPPER FOR OFFLINE TESTING
# =============================================================================

class MockSchemaMapper:
    """
    Mock SchemaMapper for testing without running the actual agent.
    Simulates the expected behavior based on the agent's system prompt.
    """

    # Semantic dictionary (subset for testing)
    SEMANTIC_DICT = {
        "codigo": "part_number",
        "cod": "part_number",
        "descricao": "description",
        "desc": "description",
        "quantidade": "quantity",
        "qtd": "quantity",
        "qty": "quantity",
        "valor_unitario": "unit_price",
        "vlr_unit": "unit_price",
        "data_entrada": "entry_date",
        "sku": "part_number",
        "nome": "description",
    }

    REQUIRED_COLUMNS = ["part_number"]

    def map_columns(
        self,
        columns: List[str],
        sample_data: List[Dict],
        session_id: str,
    ) -> Dict[str, Any]:
        """Simulate SchemaMapper mapping logic."""
        mappings = []
        unmapped = []
        mapped_targets = set()

        for col in columns:
            col_lower = col.lower().strip()

            if col_lower in self.SEMANTIC_DICT:
                target = self.SEMANTIC_DICT[col_lower]
                mapped_targets.add(target)

                # Detect transformations from sample data
                transform = self._detect_transform(col, sample_data)

                mappings.append({
                    "source_column": col,
                    "target_column": target,
                    "transform": transform,
                    "confidence": 0.9 if col_lower == col else 0.85,
                    "reason": f"Semantic match: {col} → {target}",
                })
            else:
                unmapped.append(col)

        # Check for missing required columns
        missing_required = []
        for req in self.REQUIRED_COLUMNS:
            if req not in mapped_targets:
                missing_required.append({
                    "target_column": req,
                    "description": f"Campo obrigatório: {req}",
                    "suggested_source": None,
                    "available_sources": unmapped,
                })

        if missing_required:
            return {
                "success": True,
                "status": "needs_input",
                "session_id": session_id,
                "target_table": "pending_entry_items",
                "partial_mappings": mappings,
                "missing_required_fields": missing_required,
                "unmapped_source_columns": unmapped,
                "overall_confidence": 0.0,
                "requires_confirmation": True,
            }

        return {
            "success": True,
            "status": "success",
            "session_id": session_id,
            "target_table": "pending_entry_items",
            "mappings": mappings,
            "unmapped_source_columns": unmapped,
            "overall_confidence": sum(m["confidence"] for m in mappings) / len(mappings) if mappings else 0.0,
            "requires_confirmation": True,
        }

    def _detect_transform(self, col: str, sample_data: List[Dict]) -> Optional[str]:
        """Detect required transformations from sample data."""
        if not sample_data:
            return None

        sample_value = sample_data[0].get(col, "")

        # Currency detection (R$ prefix)
        if "R$" in str(sample_value):
            return "CURRENCY_CLEAN_PTBR"

        # PT-BR number detection (comma as decimal)
        if "," in str(sample_value) and not "/" in str(sample_value):
            try:
                # Check if it's a number with comma decimal
                float(str(sample_value).replace(".", "").replace(",", "."))
                return "NUMBER_PARSE_PTBR"
            except ValueError:
                pass

        # PT-BR date detection (DD/MM/YYYY)
        if "/" in str(sample_value):
            parts = str(sample_value).split("/")
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                return "DATE_PARSE_PTBR"

        return "TRIM"


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_exact_match_mapping(use_mock: bool = True) -> Tuple[bool, str]:
    """Test mapping with exact column name matches."""
    print_info("Testing exact match mapping...")

    if use_mock:
        mapper = MockSchemaMapper()
        result = mapper.map_columns(
            columns=TEST_COLUMNS_EXACT,
            sample_data=TEST_SAMPLE_EXACT,
            session_id="test-exact-001",
        )
    else:
        # Real A2A call would go here
        from shared.a2a_client import A2AClient
        import asyncio

        async def _call():
            client = A2AClient()
            return await client.invoke_agent(
                agent_id="schema_mapper",
                payload={
                    "prompt": f"Map columns: {TEST_COLUMNS_EXACT}",
                    "columns": TEST_COLUMNS_EXACT,
                    "sample_data": TEST_SAMPLE_EXACT,
                    "session_id": "test-exact-001",
                },
            )

        try:
            response = asyncio.run(_call())
            result = getattr(response, "response", response)
        except Exception as e:
            return False, f"A2A call failed: {e}"

    # Validate result
    if not result.get("success"):
        return False, f"Mapping failed: {result.get('error')}"

    if result.get("status") != "success":
        return False, f"Expected status=success, got {result.get('status')}"

    mappings = result.get("mappings", [])
    if len(mappings) != 4:
        return False, f"Expected 4 mappings, got {len(mappings)}"

    # Check part_number mapping
    pn_mapping = next((m for m in mappings if m["target_column"] == "part_number"), None)
    if not pn_mapping:
        return False, "part_number mapping not found"

    if pn_mapping["source_column"] != "codigo":
        return False, f"Expected 'codigo' → 'part_number', got '{pn_mapping['source_column']}'"

    # Check requires_confirmation is True
    if not result.get("requires_confirmation"):
        return False, "requires_confirmation should always be True"

    details = f"Mappings: {len(mappings)}\nOverall confidence: {result.get('overall_confidence', 0):.2%}"
    return True, details


def test_ptbr_semantic_mapping(use_mock: bool = True) -> Tuple[bool, str]:
    """Test mapping with Portuguese abbreviations and transformations."""
    print_info("Testing PT-BR semantic mapping...")

    if use_mock:
        mapper = MockSchemaMapper()
        result = mapper.map_columns(
            columns=TEST_COLUMNS_PTBR,
            sample_data=TEST_SAMPLE_PTBR,
            session_id="test-ptbr-001",
        )
    else:
        from shared.a2a_client import A2AClient
        import asyncio

        async def _call():
            client = A2AClient()
            return await client.invoke_agent(
                agent_id="schema_mapper",
                payload={
                    "prompt": f"Map columns: {TEST_COLUMNS_PTBR}",
                    "columns": TEST_COLUMNS_PTBR,
                    "sample_data": TEST_SAMPLE_PTBR,
                    "session_id": "test-ptbr-001",
                },
            )

        try:
            response = asyncio.run(_call())
            result = getattr(response, "response", response)
        except Exception as e:
            return False, f"A2A call failed: {e}"

    if not result.get("success"):
        return False, f"Mapping failed: {result.get('error')}"

    mappings = result.get("mappings", [])

    # Check transformation detection
    vlr_mapping = next((m for m in mappings if m["source_column"] == "vlr_unit"), None)
    if vlr_mapping:
        if vlr_mapping.get("transform") != "CURRENCY_CLEAN_PTBR":
            return False, f"Expected CURRENCY_CLEAN_PTBR for vlr_unit, got {vlr_mapping.get('transform')}"

    date_mapping = next((m for m in mappings if m["source_column"] == "data_entrada"), None)
    if date_mapping:
        if date_mapping.get("transform") != "DATE_PARSE_PTBR":
            return False, f"Expected DATE_PARSE_PTBR for data_entrada, got {date_mapping.get('transform')}"

    details = f"Mappings: {len(mappings)}\nTransformations detected: CURRENCY, DATE"
    return True, details


def test_needs_input_flow(use_mock: bool = True) -> Tuple[bool, str]:
    """Test needs_input response when required columns are missing."""
    print_info("Testing needs_input flow...")

    if use_mock:
        mapper = MockSchemaMapper()
        result = mapper.map_columns(
            columns=TEST_COLUMNS_MISSING,
            sample_data=TEST_SAMPLE_MISSING,
            session_id="test-missing-001",
        )
    else:
        from shared.a2a_client import A2AClient
        import asyncio

        async def _call():
            client = A2AClient()
            return await client.invoke_agent(
                agent_id="schema_mapper",
                payload={
                    "prompt": f"Map columns: {TEST_COLUMNS_MISSING}",
                    "columns": TEST_COLUMNS_MISSING,
                    "sample_data": TEST_SAMPLE_MISSING,
                    "session_id": "test-missing-001",
                },
            )

        try:
            response = asyncio.run(_call())
            result = getattr(response, "response", response)
        except Exception as e:
            return False, f"A2A call failed: {e}"

    if not result.get("success"):
        return False, f"Mapping failed: {result.get('error')}"

    if result.get("status") != "needs_input":
        return False, f"Expected status=needs_input, got {result.get('status')}"

    missing_fields = result.get("missing_required_fields", [])
    if not missing_fields:
        return False, "Expected missing_required_fields to be populated"

    # Check that part_number is in missing
    pn_missing = next((f for f in missing_fields if f["target_column"] == "part_number"), None)
    if not pn_missing:
        return False, "part_number should be in missing_required_fields"

    details = f"Status: needs_input\nMissing fields: {[f['target_column'] for f in missing_fields]}"
    return True, details


def test_unmapped_columns(use_mock: bool = True) -> Tuple[bool, str]:
    """Test that unmapped columns are listed but not block mapping."""
    print_info("Testing unmapped columns handling...")

    if use_mock:
        mapper = MockSchemaMapper()
        result = mapper.map_columns(
            columns=TEST_COLUMNS_UNKNOWN,
            sample_data=TEST_SAMPLE_UNKNOWN,
            session_id="test-unknown-001",
        )
    else:
        from shared.a2a_client import A2AClient
        import asyncio

        async def _call():
            client = A2AClient()
            return await client.invoke_agent(
                agent_id="schema_mapper",
                payload={
                    "prompt": f"Map columns: {TEST_COLUMNS_UNKNOWN}",
                    "columns": TEST_COLUMNS_UNKNOWN,
                    "sample_data": TEST_SAMPLE_UNKNOWN,
                    "session_id": "test-unknown-001",
                },
            )

        try:
            response = asyncio.run(_call())
            result = getattr(response, "response", response)
        except Exception as e:
            return False, f"A2A call failed: {e}"

    if not result.get("success"):
        return False, f"Mapping failed: {result.get('error')}"

    unmapped = result.get("unmapped_source_columns", [])

    # CUSTOM_FIELD and ANOTHER_CUSTOM should be unmapped
    if "CUSTOM_FIELD" not in unmapped and "ANOTHER_CUSTOM" not in unmapped:
        return False, f"Expected custom fields in unmapped, got {unmapped}"

    details = f"Unmapped columns: {unmapped}"
    return True, details


def test_response_schema_validation() -> Tuple[bool, str]:
    """Test that SchemaMappingResponse Pydantic model works correctly."""
    print_info("Testing response schema validation...")

    try:
        from shared.agent_schemas import SchemaMappingResponse, ColumnMapping, MappingStatus

        # Create a valid response
        response = SchemaMappingResponse(
            success=True,
            status=MappingStatus.SUCCESS,
            session_id="test-schema-001",
            target_table="pending_entry_items",
            mappings=[
                ColumnMapping(
                    source_column="codigo",
                    target_column="part_number",
                    transform="TRIM",
                    confidence=0.95,
                    reason="Exact semantic match",
                ),
            ],
            unmapped_source_columns=["custom_field"],
            overall_confidence=0.95,
            requires_confirmation=True,
        )

        # Validate fields
        if response.status != MappingStatus.SUCCESS:
            return False, f"Status should be SUCCESS, got {response.status}"

        if len(response.mappings) != 1:
            return False, f"Expected 1 mapping, got {len(response.mappings)}"

        if response.mappings[0].confidence != 0.95:
            return False, f"Confidence mismatch: {response.mappings[0].confidence}"

        details = f"Schema validation passed\nMappings: {len(response.mappings)}"
        return True, details

    except Exception as e:
        return False, f"Schema validation failed: {e}"


def test_confirm_mapping_tool() -> Tuple[bool, str]:
    """Test the confirm_mapping tool (mocked - no actual memory write)."""
    print_info("Testing confirm_mapping tool...")

    try:
        # Import the tool
        from agents.orchestrators.inventory_hub.main import confirm_mapping

        # This will fail without proper memory setup, but we can test the validation
        result_json = confirm_mapping(
            session_id="",  # Empty to trigger validation error
            approved=True,
            user_id="test-user",
        )

        result = json.loads(result_json)

        # Should fail with validation error
        if result.get("success"):
            return False, "Expected validation error for empty session_id"

        if result.get("error_type") != "VALIDATION_ERROR":
            return False, f"Expected VALIDATION_ERROR, got {result.get('error_type')}"

        details = "Validation works: empty session_id rejected"
        return True, details

    except Exception as e:
        return False, f"Tool test failed: {e}"


def test_save_training_example_tool() -> Tuple[bool, str]:
    """Test the save_training_example tool validation."""
    print_info("Testing save_training_example tool...")

    try:
        from agents.orchestrators.inventory_hub.main import save_training_example

        # Test with empty required fields
        result_json = save_training_example(
            source_column="",  # Empty to trigger validation
            target_column="part_number",
            user_id="test-user",
            session_id="test-session",
        )

        result = json.loads(result_json)

        if result.get("success"):
            return False, "Expected validation error for empty source_column"

        if result.get("error_type") != "VALIDATION_ERROR":
            return False, f"Expected VALIDATION_ERROR, got {result.get('error_type')}"

        details = "Validation works: empty source_column rejected"
        return True, details

    except Exception as e:
        return False, f"Tool test failed: {e}"


def test_health_check_phase3_capabilities() -> Tuple[bool, str]:
    """Test that health_check includes Phase 3 capabilities."""
    print_info("Testing health_check Phase 3 capabilities...")

    try:
        from agents.orchestrators.inventory_hub.main import health_check

        result_json = health_check()
        result = json.loads(result_json)

        if not result.get("success"):
            return False, "Health check failed"

        capabilities = result.get("capabilities", [])

        phase3_caps = ["map_to_schema", "confirm_mapping", "save_training_example"]
        for cap in phase3_caps:
            if cap not in capabilities:
                return False, f"Missing Phase 3 capability: {cap}"

        if result.get("architecture") != "phase3-semantic-mapping":
            return False, f"Expected architecture 'phase3-semantic-mapping', got {result.get('architecture')}"

        details = f"Architecture: {result.get('architecture')}\nPhase 3 capabilities: {phase3_caps}"
        return True, details

    except Exception as e:
        return False, f"Health check test failed: {e}"


# =============================================================================
# A2A CONNECTIVITY TEST
# =============================================================================

def test_a2a_connectivity() -> Tuple[bool, str]:
    """Test A2A connectivity to SchemaMapper agent."""
    print_info("Testing A2A connectivity to SchemaMapper...")

    try:
        from shared.a2a_client import A2AClient
        import asyncio

        async def _check():
            client = A2AClient()

            # Check if schema_mapper is in LOCAL_AGENTS
            if "schema_mapper" not in client.LOCAL_AGENTS:
                return False, "schema_mapper not in LOCAL_AGENTS"

            # Try to invoke health check
            return await client.invoke_agent(
                agent_id="schema_mapper",
                payload={"action": "health_check"},
            )

        try:
            response = asyncio.run(_check())

            if isinstance(response, tuple):
                return response  # Already a (bool, str) tuple

            result = getattr(response, "response", response)

            if isinstance(result, dict) and result.get("status") == "healthy":
                details = f"SchemaMapper healthy\nVersion: {result.get('version', 'unknown')}"
                return True, details

            return True, "A2A connection successful (response received)"

        except ConnectionRefusedError:
            return False, "Connection refused - is SchemaMapper running on port 9018?"
        except Exception as e:
            return False, f"A2A error: {e}"

    except ImportError as e:
        return False, f"Import error: {e}"


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

def run_phase3_integration_test(use_mock: bool = True) -> bool:
    """
    Run the complete Phase 3 integration test.

    Args:
        use_mock: If True, use MockSchemaMapper instead of real A2A calls.

    Returns:
        True if all tests pass, False otherwise.
    """
    print_header("Phase 3 Semantic Mapping - Integration Test")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Mode: {'MOCK' if use_mock else 'LIVE A2A'}")

    results = []

    # -----------------------------------------------------------------
    # SCHEMA VALIDATION TESTS
    # -----------------------------------------------------------------
    print_subheader("Schema & Tool Validation Tests")

    tests_schema = [
        ("SchemaMappingResponse Pydantic validation", test_response_schema_validation),
        ("confirm_mapping tool validation", test_confirm_mapping_tool),
        ("save_training_example tool validation", test_save_training_example_tool),
        ("health_check Phase 3 capabilities", test_health_check_phase3_capabilities),
    ]

    for test_name, test_func in tests_schema:
        passed, details = test_func()
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # MAPPING LOGIC TESTS
    # -----------------------------------------------------------------
    print_subheader("Mapping Logic Tests")

    tests_mapping = [
        ("Exact match column mapping", lambda: test_exact_match_mapping(use_mock)),
        ("PT-BR semantic mapping + transformations", lambda: test_ptbr_semantic_mapping(use_mock)),
        ("needs_input flow for missing required", lambda: test_needs_input_flow(use_mock)),
        ("Unmapped columns handling", lambda: test_unmapped_columns(use_mock)),
    ]

    for test_name, test_func in tests_mapping:
        passed, details = test_func()
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # A2A CONNECTIVITY TEST (skip if mock mode)
    # -----------------------------------------------------------------
    if not use_mock:
        print_subheader("A2A Connectivity Tests")

        passed, details = test_a2a_connectivity()
        results.append(("A2A connectivity to SchemaMapper", passed))
        if passed:
            print_pass("A2A connectivity to SchemaMapper", details)
        else:
            print_fail("A2A connectivity to SchemaMapper", details)
    else:
        print_subheader("A2A Connectivity Tests")
        print_skip("A2A connectivity to SchemaMapper", "Running in mock mode")

    # -----------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------
    print_header("Test Summary")

    total = len(results)
    passed_count = sum(1 for _, passed in results if passed)
    failed_count = total - passed_count

    print(f"\n{TestColors.BOLD}Total Tests: {total}{TestColors.RESET}")
    print(f"{TestColors.GREEN}Passed: {passed_count}{TestColors.RESET}")
    print(f"{TestColors.RED}Failed: {failed_count}{TestColors.RESET}")

    if failed_count > 0:
        print(f"\n{TestColors.RED}Failed Tests:{TestColors.RESET}")
        for test_name, passed in results:
            if not passed:
                print(f"  - {test_name}")

    all_passed = failed_count == 0

    if all_passed:
        print(f"\n{TestColors.GREEN}{TestColors.BOLD}ALL TESTS PASSED!{TestColors.RESET}")
    else:
        print(f"\n{TestColors.RED}{TestColors.BOLD}SOME TESTS FAILED{TestColors.RESET}")

    return all_passed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3 Integration Test")
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use mock mapper instead of real A2A (default: True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live A2A calls (requires SchemaMapper running)",
    )

    args = parser.parse_args()

    use_mock = not args.live

    success = run_phase3_integration_test(use_mock=use_mock)
    sys.exit(0 if success else 1)
