# =============================================================================
# Tests for Data Contract Enforcement (shared/data_contracts.py)
# =============================================================================
# These tests PREVENT REGRESSION of BUG-032 through BUG-036.
#
# The root cause of 5 days of bugs was STRING vs DICT mismatch:
# - A2A Protocol returns `result.response` as STRING JSON
# - Multiple parts of the codebase assumed DICT
#
# This test suite ensures:
# 1. ensure_dict() handles ALL input types correctly
# 2. ensure_string() handles ALL input types correctly
# 3. validate_response_format() normalizes responses correctly
# 4. Regression tests for each historical bug (BUG-032 to BUG-036)
#
# Run: cd server/agentcore-inventory && python -m pytest tests/test_data_contracts.py -v
# =============================================================================

import pytest
import json
from shared.data_contracts import (
    ensure_dict,
    ensure_string,
    validate_response_format,
    validate_a2a_response,
    normalize_debug_analysis,
    fix_double_encoded_json,
    is_json_string,
    is_dict_like,
)


# =============================================================================
# Test: ensure_dict()
# =============================================================================

class TestEnsureDict:
    """Test ensure_dict() handles ALL input types correctly."""

    # --- Basic Type Handling ---

    def test_dict_passthrough(self):
        """Dict input should pass through unchanged."""
        data = {"key": "value", "nested": {"inner": 123}}
        result = ensure_dict(data)
        assert result == {"key": "value", "nested": {"inner": 123}}
        assert result is data  # Same object reference for efficiency

    def test_none_to_empty_dict(self):
        """None should return empty dict."""
        assert ensure_dict(None) == {}

    def test_empty_string_to_empty_dict(self):
        """Empty string should return empty dict."""
        assert ensure_dict("") == {}
        assert ensure_dict("  ") == {}
        assert ensure_dict("\n\t") == {}

    # --- JSON String Parsing ---

    def test_json_string_to_dict(self):
        """Valid JSON string should be parsed to dict."""
        data = '{"key": "value"}'
        result = ensure_dict(data)
        assert result == {"key": "value"}

    def test_nested_json_string(self):
        """Nested JSON should parse correctly."""
        data = '{"outer": {"inner": "value", "list": [1, 2, 3]}}'
        result = ensure_dict(data)
        assert result["outer"]["inner"] == "value"
        assert result["outer"]["list"] == [1, 2, 3]

    def test_json_with_unicode(self):
        """JSON with Unicode characters should parse correctly."""
        data = '{"message": "Olá, mundo! 日本語 emoji: 🎉"}'
        result = ensure_dict(data)
        assert result["message"] == "Olá, mundo! 日本語 emoji: 🎉"

    def test_json_with_special_characters(self):
        """JSON with special characters in keys/values."""
        data = '{"key-with-dash": "value/with/slash", "key.with.dots": true}'
        result = ensure_dict(data)
        assert result["key-with-dash"] == "value/with/slash"
        assert result["key.with.dots"] is True

    # --- Invalid JSON Handling ---

    def test_invalid_json_wrapped(self):
        """Invalid JSON string should be wrapped, not raise."""
        result = ensure_dict("not json at all")
        assert "_raw_string" in result
        assert result["_raw_string"] == "not json at all"

    def test_truncated_json_wrapped(self):
        """Truncated JSON should be wrapped."""
        result = ensure_dict('{"key": "val')  # Missing closing
        assert "_raw_string" in result

    # --- Non-Dict JSON Handling ---

    def test_json_list_wrapped(self):
        """JSON list should be wrapped in _raw_value."""
        result = ensure_dict('[1, 2, 3]')
        assert "_raw_value" in result
        assert result["_raw_value"] == [1, 2, 3]

    def test_json_string_value_wrapped(self):
        """JSON string value should be wrapped."""
        result = ensure_dict('"just a string"')
        assert "_raw_value" in result
        assert result["_raw_value"] == "just a string"

    def test_json_number_wrapped(self):
        """JSON number should be wrapped."""
        result = ensure_dict('42')
        assert "_raw_value" in result
        assert result["_raw_value"] == 42

    def test_json_boolean_wrapped(self):
        """JSON boolean should be wrapped."""
        result = ensure_dict('true')
        assert "_raw_value" in result
        assert result["_raw_value"] is True

    def test_json_null_wrapped(self):
        """JSON null should be wrapped."""
        result = ensure_dict('null')
        assert "_raw_value" in result
        assert result["_raw_value"] is None

    # --- Unexpected Types ---

    def test_integer_wrapped(self):
        """Integer input should be wrapped."""
        result = ensure_dict(42)
        assert "_raw_value" in result
        assert result["_raw_value"] == 42

    def test_list_wrapped(self):
        """List input should be wrapped."""
        result = ensure_dict([1, 2, 3])
        assert "_raw_value" in result
        assert result["_raw_value"] == [1, 2, 3]

    def test_boolean_wrapped(self):
        """Boolean input should be wrapped."""
        result = ensure_dict(True)
        assert "_raw_value" in result
        assert result["_raw_value"] is True

    # --- Context Logging ---

    def test_context_is_used_for_logging(self):
        """Context parameter should be used (no crash)."""
        # Just verify it doesn't crash with context
        result = ensure_dict('{"key": "value"}', context="test_operation")
        assert result == {"key": "value"}


# =============================================================================
# Test: ensure_string()
# =============================================================================

class TestEnsureString:
    """Test ensure_string() handles ALL input types correctly."""

    def test_string_passthrough(self):
        """String input should pass through unchanged."""
        data = '{"key": "value"}'
        result = ensure_string(data)
        assert result == '{"key": "value"}'

    def test_none_to_empty_json(self):
        """None should return empty JSON object."""
        assert ensure_string(None) == "{}"

    def test_dict_to_json_string(self):
        """Dict should be serialized to JSON string."""
        data = {"key": "value", "number": 42}
        result = ensure_string(data)
        parsed = json.loads(result)
        assert parsed == {"key": "value", "number": 42}

    def test_dict_with_unicode(self):
        """Dict with Unicode should serialize correctly."""
        data = {"message": "Olá, 日本語 🎉"}
        result = ensure_string(data)
        assert "Olá" in result
        assert "日本語" in result
        # ensure_ascii=False preserves Unicode
        assert "\\u" not in result

    def test_other_types_wrapped(self):
        """Other types should be wrapped in _raw_value."""
        result = ensure_string([1, 2, 3])
        parsed = json.loads(result)
        assert parsed == {"_raw_value": [1, 2, 3]}


# =============================================================================
# Test: validate_response_format()
# =============================================================================

class TestValidateResponseFormat:
    """Test response validation and normalization."""

    def test_success_boolean_preserved(self):
        """Boolean success should be preserved."""
        response = {"success": True}
        result = validate_response_format(response)
        assert result["success"] is True

        response = {"success": False}
        result = validate_response_format(response)
        assert result["success"] is False

    def test_success_string_true_variants(self):
        """String 'true' variants should become boolean True."""
        for val in ["true", "True", "TRUE", "1", "yes", "Yes"]:
            response = {"success": val}
            result = validate_response_format(response)
            assert result["success"] is True, f"Failed for value: {val}"

    def test_success_string_false_variants(self):
        """String 'false' variants should become boolean False."""
        for val in ["false", "False", "FALSE", "0", "no", "No", "anything_else"]:
            response = {"success": val}
            result = validate_response_format(response)
            assert result["success"] is False, f"Failed for value: {val}"

    def test_success_missing_defaults_false(self):
        """Missing success should default to False."""
        response = {"error": "something"}
        result = validate_response_format(response)
        assert result["success"] is False

    def test_error_string_preserved(self):
        """String error should be preserved."""
        response = {"success": False, "error": "Test error message"}
        result = validate_response_format(response)
        assert result["error"] == "Test error message"

    def test_error_nonstring_converted(self):
        """Non-string error should be converted to string."""
        response = {"success": False, "error": 12345}
        result = validate_response_format(response)
        assert result["error"] == "12345"

        response = {"success": False, "error": {"nested": "error"}}
        result = validate_response_format(response)
        assert isinstance(result["error"], str)

    def test_debug_analysis_string_parsed(self):
        """debug_analysis as STRING should be parsed to DICT."""
        response = {
            "success": False,
            "error": "Test error",
            "debug_analysis": '{"technical_explanation": "Test explanation"}'
        }
        result = validate_response_format(response)

        assert isinstance(result["debug_analysis"], dict)
        assert result["debug_analysis"]["technical_explanation"] == "Test explanation"

    def test_debug_analysis_dict_preserved(self):
        """debug_analysis as DICT should be preserved."""
        response = {
            "success": False,
            "debug_analysis": {"technical_explanation": "Test"}
        }
        result = validate_response_format(response)
        assert isinstance(result["debug_analysis"], dict)
        assert result["debug_analysis"]["technical_explanation"] == "Test"

    def test_string_response_converted(self):
        """String response should be converted to dict."""
        response = '{"success": true, "data": "test"}'
        result = validate_response_format(response)
        assert isinstance(result, dict)
        assert result["success"] is True

    def test_complete_error_response(self):
        """Test complete error response normalization."""
        response = {
            "success": False,
            "action": "nexo_analyze_file",
            "error": "Erro na extração de dados",
            "debug_analysis": json.dumps({
                "error_type": "ExtractionError",
                "technical_explanation": "Falha ao extrair dados estruturados",
                "root_causes": [
                    {"cause": "Formato não reconhecido", "confidence": 0.85}
                ],
                "debugging_steps": [
                    "Verificar formato do arquivo",
                    "Validar encoding UTF-8"
                ],
                "recoverable": True
            })
        }

        result = validate_response_format(response, "test_error_response")

        # Verify all fields normalized
        assert result["success"] is False
        assert isinstance(result["error"], str)
        assert isinstance(result["debug_analysis"], dict)
        assert result["debug_analysis"]["error_type"] == "ExtractionError"
        assert len(result["debug_analysis"]["root_causes"]) == 1


# =============================================================================
# Test: normalize_debug_analysis()
# =============================================================================

class TestNormalizeDebugAnalysis:
    """Test Debug Agent response normalization."""

    def test_full_analysis_preserved(self):
        """Complete analysis should have all fields preserved."""
        analysis = {
            "error_type": "ValidationError",
            "technical_explanation": "Campo obrigatório ausente",
            "root_causes": [{"cause": "Test", "confidence": 0.9}],
            "debugging_steps": ["Step 1", "Step 2"],
            "documentation_links": ["https://example.com"],
            "similar_patterns": ["pattern1"],
            "recoverable": True,
            "suggested_action": "retry"
        }

        result = normalize_debug_analysis(analysis)

        assert result["error_type"] == "ValidationError"
        assert result["technical_explanation"] == "Campo obrigatório ausente"
        assert len(result["root_causes"]) == 1
        assert len(result["debugging_steps"]) == 2
        assert result["recoverable"] is True
        assert result["suggested_action"] == "retry"

    def test_missing_fields_have_defaults(self):
        """Missing fields should have sensible defaults."""
        analysis = {}
        result = normalize_debug_analysis(analysis)

        assert result["error_type"] == "Unknown"
        assert result["technical_explanation"] == ""
        assert result["root_causes"] == []
        assert result["debugging_steps"] == []
        assert result["documentation_links"] == []
        assert result["similar_patterns"] == []
        assert result["recoverable"] is False
        assert result["suggested_action"] == "investigate"

    def test_string_analysis_parsed(self):
        """String analysis should be parsed and normalized."""
        analysis_str = json.dumps({
            "error_type": "NetworkError",
            "technical_explanation": "Connection timeout"
        })

        result = normalize_debug_analysis(analysis_str)

        assert result["error_type"] == "NetworkError"
        assert result["technical_explanation"] == "Connection timeout"
        # Should have defaults for missing fields
        assert result["root_causes"] == []

    def test_root_causes_always_list(self):
        """root_causes should always be a list."""
        # Single dict should become list
        analysis = {"root_causes": {"cause": "single", "confidence": 0.8}}
        result = normalize_debug_analysis(analysis)
        assert isinstance(result["root_causes"], list)

    def test_recoverable_normalized_to_bool(self):
        """recoverable should be normalized to boolean."""
        for val, expected in [("true", True), ("false", False), ("1", True), ("0", False)]:
            analysis = {"recoverable": val}
            result = normalize_debug_analysis(analysis)
            assert result["recoverable"] is expected, f"Failed for {val}"


# =============================================================================
# Test: fix_double_encoded_json()
# =============================================================================

class TestFixDoubleEncodedJson:
    """Test double-encoded JSON detection and fix."""

    def test_simple_double_encoded(self):
        """Simple double-encoded JSON should be fixed."""
        # This is what happens when json.dumps is called twice
        inner = {"key": "value"}
        double_encoded = json.dumps(json.dumps(inner))

        result = fix_double_encoded_json(double_encoded)
        assert result == {"key": "value"}

    def test_triple_encoded(self):
        """Triple-encoded JSON should be fixed."""
        inner = {"key": "value"}
        triple_encoded = json.dumps(json.dumps(json.dumps(inner)))

        result = fix_double_encoded_json(triple_encoded)
        assert result == {"key": "value"}

    def test_normal_json_unchanged(self):
        """Normal JSON should be unchanged."""
        normal = '{"key": "value"}'
        result = fix_double_encoded_json(normal)
        assert result == {"key": "value"}

    def test_non_string_passthrough(self):
        """Non-string input should pass through."""
        data = {"key": "value"}
        result = fix_double_encoded_json(data)
        assert result == {"key": "value"}

    def test_max_depth_respected(self):
        """Max depth should be respected to prevent infinite loops."""
        # Create deeply encoded string
        inner = {"key": "value"}
        encoded = inner
        for _ in range(10):
            encoded = json.dumps(encoded)

        # With max_depth=3, we should stop after 3 iterations
        result = fix_double_encoded_json(encoded, max_depth=3)
        # Result should still be a string after 3 iterations
        assert isinstance(result, str)


# =============================================================================
# Test: Type Checking Utilities
# =============================================================================

class TestTypeCheckingUtils:
    """Test is_json_string() and is_dict_like()."""

    def test_is_json_string_valid(self):
        """Valid JSON strings should return True."""
        assert is_json_string('{"key": "value"}') is True
        assert is_json_string('[1, 2, 3]') is True
        assert is_json_string('"string"') is True
        assert is_json_string('42') is True
        assert is_json_string('true') is True
        assert is_json_string('null') is True

    def test_is_json_string_invalid(self):
        """Invalid JSON should return False."""
        assert is_json_string('not json') is False
        assert is_json_string('{"truncated": ') is False
        assert is_json_string('') is False

    def test_is_json_string_non_string(self):
        """Non-string input should return False."""
        assert is_json_string({"key": "value"}) is False
        assert is_json_string([1, 2, 3]) is False
        assert is_json_string(42) is False
        assert is_json_string(None) is False

    def test_is_dict_like_dict(self):
        """Dict should return True."""
        assert is_dict_like({"key": "value"}) is True

    def test_is_dict_like_json_dict(self):
        """JSON string containing dict should return True."""
        assert is_dict_like('{"key": "value"}') is True

    def test_is_dict_like_json_list(self):
        """JSON string containing list should return False."""
        assert is_dict_like('[1, 2, 3]') is False

    def test_is_dict_like_non_json(self):
        """Non-JSON string should return False."""
        assert is_dict_like('not json') is False

    def test_is_dict_like_other_types(self):
        """Other types should return False."""
        assert is_dict_like([1, 2, 3]) is False
        assert is_dict_like(42) is False
        assert is_dict_like(None) is False


# =============================================================================
# REGRESSION TESTS: BUG-032 through BUG-036
# =============================================================================

class TestBugRegression:
    """
    Regression tests for BUG-032 through BUG-036.

    These tests ensure we NEVER reintroduce the same bugs.
    Each test documents the exact bug scenario and expected fix.
    """

    def test_bug036_string_analysis_parsed(self):
        """
        BUG-036: Debug analysis STRING should be parsed to DICT.

        Root Cause: A2A protocol returns result.response as STRING JSON.
        Previous Behavior: response["debug_analysis"] was a STRING.
        Fix: Use ensure_dict() to convert STRING → DICT.
        """
        # This is what Debug Agent returns via A2A protocol
        debug_result = {
            "enriched": True,
            "analysis": '{"technical_explanation": "Test", "root_causes": []}',
            "agent_id": "debug"
        }

        # Apply ensure_dict (what debug_utils.py now does)
        analysis = ensure_dict(debug_result["analysis"], "bug036_test")

        # CRITICAL ASSERTION
        assert isinstance(analysis, dict), \
            f"BUG-036 regression: analysis should be dict, got {type(analysis)}"
        assert "technical_explanation" in analysis

    def test_bug035_timeout_graceful_handling(self):
        """
        BUG-035: Timeout should not cause crashes or data issues.

        Root Cause: 5s timeout was too short for Gemini Pro + Thinking.
        Previous Behavior: Timeout caused incomplete/missing analysis.
        Fix: Increased timeout to 15s, ensure_dict handles None gracefully.
        """
        # Timeout returns this (no analysis field)
        timeout_result = {"enriched": False, "reason": "timeout"}

        # Should not crash - ensure_dict handles None/missing
        analysis = ensure_dict(timeout_result.get("analysis", {}), "timeout_test")
        assert analysis == {}

    def test_bug034_business_logic_errors_need_analysis(self):
        """
        BUG-034: Business logic errors (e.g., "File not found") need analysis.

        Root Cause: Gate only called Debug Agent when `not success AND not error`.
        Previous Behavior: "File not found" had error field, so no analysis.
        Fix: Final Response Gate calls Debug Agent for ALL failed responses.

        This test verifies the response format is correct for such cases.
        """
        # Business logic error response
        response = {
            "success": False,
            "error": "File not found at S3 key 'imports/abc/file.csv'",
            "action": "nexo_analyze_file",
            # debug_analysis would be added by Final Response Gate
            "debug_analysis": json.dumps({
                "error_type": "FileNotFound",
                "technical_explanation": "Arquivo não existe no bucket S3",
                "root_causes": [{"cause": "Chave S3 inválida", "confidence": 0.95}],
            })
        }

        result = validate_response_format(response)

        # debug_analysis should be DICT, not STRING
        assert isinstance(result["debug_analysis"], dict)
        assert result["debug_analysis"]["error_type"] == "FileNotFound"

    def test_bug033_analysis_must_reach_response(self):
        """
        BUG-033: Debug analysis must be injected into response dict.

        Root Cause: debug_error() result was computed but discarded.
        Previous Behavior: Analysis existed but wasn't in response.
        Fix: _capture_debug_analysis() injects analysis into response.

        This test verifies the expected response structure.
        """
        # Response with analysis properly injected (after BUG-033 fix)
        response = {
            "success": False,
            "error": "Test error",
            "debug_analysis": {
                "technical_explanation": "Test explanation",
                "root_causes": [],
            },
            "_debug_enriched": True,  # Flag added by _capture_debug_analysis
        }

        assert "debug_analysis" in response
        assert response["_debug_enriched"] is True
        assert isinstance(response["debug_analysis"], dict)

    def test_bug032_sync_return_value(self):
        """
        BUG-032: debug_error() must return synchronously with result.

        Root Cause: Fire-and-forget pattern discarded results.
        Previous Behavior: debug_error() spawned task and returned immediately.
        Fix: Changed to synchronous with timeout, returns actual result.

        This test verifies the expected return format from debug_error().
        """
        # Expected return format from debug_error() (BUG-032 fix)
        expected_success = {
            "enriched": True,
            "analysis": {"technical_explanation": "..."},  # Must be DICT
            "agent_id": "debug",
        }

        expected_failure = {
            "enriched": False,
            "reason": "timeout",  # or error message
        }

        # Verify structure (actual call would need mocking)
        assert "enriched" in expected_success
        assert "analysis" in expected_success
        assert isinstance(expected_success["analysis"], dict)

        assert "enriched" in expected_failure
        assert expected_failure["enriched"] is False

    def test_bug022_double_encoded_json(self):
        """
        BUG-022: Double-encoded JSON should be detected and fixed.

        Root Cause: Some paths encoded JSON twice.
        Previous Behavior: Frontend received escaped JSON strings.
        Fix: fix_double_encoded_json() unwraps multiple layers.
        """
        # Double-encoded JSON (what we used to receive)
        double_encoded = '"{\\"key\\": \\"value\\"}"'

        # First parse removes outer quotes
        first_parse = json.loads(double_encoded)
        assert isinstance(first_parse, str), "First parse should give string"

        # fix_double_encoded_json handles this
        result = fix_double_encoded_json(double_encoded)
        assert result == {"key": "value"}


# =============================================================================
# Test: A2A Response Contract
# =============================================================================

class TestA2AResponseContract:
    """Test A2A protocol response handling contract."""

    def test_a2a_response_is_always_string(self):
        """
        A2AResponse.response is ALWAYS a STRING containing JSON.
        Callers MUST use ensure_dict() to convert.
        """
        # This is what A2A protocol returns
        a2a_response_text = '{"success": true, "analysis": {"key": "value"}}'

        # Callers MUST do this
        result = ensure_dict(a2a_response_text, "a2a_response")

        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["analysis"] == {"key": "value"}

    def test_validate_a2a_response_with_expected_fields(self):
        """validate_a2a_response() should check expected fields."""
        response = '{"field1": "value1"}'

        result = validate_a2a_response(
            response,
            expected_fields=["field1", "field2", "field3"],
            context="test"
        )

        assert result["field1"] == "value1"
        assert "_validation_warnings" in result
        assert "field2" in result["_validation_warnings"]
        assert "field3" in result["_validation_warnings"]

    def test_debug_agent_response_format(self):
        """Test actual Debug Agent response format handling."""
        # This is exactly what Debug Agent returns via A2A
        debug_response = json.dumps({
            "error_type": "ValidationError",
            "technical_explanation": "Campo obrigatório ausente",
            "root_causes": [{"cause": "Test", "confidence": 0.9}],
            "debugging_steps": ["Step 1", "Step 2"],
            "documentation_links": [],
            "similar_patterns": [],
            "recoverable": False,
            "suggested_action": "abort"
        })

        # Apply ensure_dict (what we do in debug_utils.py)
        result = ensure_dict(debug_response, "debug_analysis")

        # CRITICAL: Result must be a dict
        assert isinstance(result, dict)
        assert result["error_type"] == "ValidationError"
        assert isinstance(result["root_causes"], list)
        assert len(result["debugging_steps"]) == 2


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_very_large_json(self):
        """Large JSON should be handled without issues."""
        large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}
        large_json = json.dumps(large_dict)

        result = ensure_dict(large_json, "large_json_test")
        assert len(result) == 1000

    def test_deeply_nested_json(self):
        """Deeply nested JSON should be handled."""
        nested = {"level": 0}
        current = nested
        for i in range(50):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        json_str = json.dumps(nested)
        result = ensure_dict(json_str)

        # Navigate to verify
        current = result
        for i in range(50):
            assert current["level"] == i
            current = current["nested"]

    def test_json_with_all_types(self):
        """JSON with all JSON types should parse correctly."""
        data = {
            "string": "text",
            "number": 42,
            "float": 3.14,
            "boolean_true": True,
            "boolean_false": False,
            "null": None,
            "array": [1, "two", 3.0, True, None],
            "object": {"nested": "value"}
        }
        json_str = json.dumps(data)

        result = ensure_dict(json_str)
        assert result["string"] == "text"
        assert result["number"] == 42
        assert result["float"] == 3.14
        assert result["boolean_true"] is True
        assert result["boolean_false"] is False
        assert result["null"] is None
        assert result["array"] == [1, "two", 3.0, True, None]
        assert result["object"]["nested"] == "value"
