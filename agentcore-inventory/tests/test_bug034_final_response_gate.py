# =============================================================================
# Tests for BUG-034: Final Response Gate Pattern
# =============================================================================
# Unit tests for the Final Response Gate that ensures Debug Agent is invoked
# for ALL error responses, including business logic errors.
#
# These tests verify:
# - Business logic errors (e.g., "File not found") trigger Debug Agent
# - Flash vs Pro heuristic correctly classifies errors
# - Timeout/failure gracefully returns response without analysis
# - Multiple errors are merged correctly
#
# Run: cd server/agentcore-inventory && python -m pytest tests/test_bug034_final_response_gate.py -v
# =============================================================================

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Import the functions under test
from swarm.response_utils import (
    _should_use_flash,
    _finalize_response,
    FLASH_ERROR_PATTERNS,
)


# =============================================================================
# Test: Flash vs Pro Heuristic
# =============================================================================

class TestFlashHeuristic:
    """Tests for _should_use_flash() function."""

    def test_file_not_found_uses_flash(self):
        """File not found errors are simple - use Flash."""
        assert _should_use_flash("File not found at S3 key 'imports/abc/file.csv'")
        assert _should_use_flash("FileNotFoundError: No such file or directory")
        assert _should_use_flash("NoSuchKey: The specified key does not exist")

    def test_s3_bucket_errors_use_flash(self):
        """S3 bucket-related errors are simple - use Flash."""
        assert _should_use_flash("NoSuchBucket: The bucket does not exist")
        assert _should_use_flash("Access denied to S3 bucket 'my-bucket'")
        assert _should_use_flash("Error uploading to S3: Connection timeout")

    def test_timeout_errors_use_flash(self):
        """Timeout errors are simple - use Flash."""
        assert _should_use_flash("Connection timed out after 30 seconds")
        assert _should_use_flash("TimeoutError: Operation exceeded deadline")
        assert _should_use_flash("Request timeout - please retry")

    def test_rate_limit_errors_use_flash(self):
        """Rate limit errors are simple - use Flash."""
        assert _should_use_flash("Rate limit exceeded: 429 Too Many Requests")
        assert _should_use_flash("Throttling: Request limit reached")
        assert _should_use_flash("Error 429: Too many requests")

    def test_validation_errors_use_flash(self):
        """Validation errors are simple - use Flash."""
        assert _should_use_flash("ValidationError: field 'name' is required")
        assert _should_use_flash("Invalid value for parameter 'count'")
        assert _should_use_flash("Missing field: 'email' is required")

    def test_auth_errors_use_flash(self):
        """Authentication errors are simple - use Flash."""
        assert _should_use_flash("Unauthorized: Invalid token")
        assert _should_use_flash("Error 401: Authentication required")
        assert _should_use_flash("Error 403: Forbidden - access denied")
        assert _should_use_flash("Token expired, please re-authenticate")

    def test_complex_errors_use_pro(self):
        """Complex errors require Pro with Thinking."""
        # Parsing errors (unclear format)
        assert not _should_use_flash("Failed to parse response from LLM")
        assert not _should_use_flash("Unexpected JSON structure in output")

        # Logic errors (complex reasoning needed)
        assert not _should_use_flash("Agent loop terminated unexpectedly")
        assert not _should_use_flash("Inconsistent state detected in workflow")

        # Integration errors (multi-system)
        assert not _should_use_flash("Memory namespace mismatch with runtime")
        assert not _should_use_flash("A2A protocol handshake failed")

    def test_empty_error_uses_pro(self):
        """Empty or unknown errors should use Pro for safety."""
        assert not _should_use_flash("")
        assert not _should_use_flash(None)

    def test_flash_patterns_are_lowercase(self):
        """Verify case-insensitive matching works."""
        assert _should_use_flash("FILE NOT FOUND")
        assert _should_use_flash("TIMEOUT ERROR")
        assert _should_use_flash("Rate Limit Exceeded")


# =============================================================================
# Test: Finalize Response Gate
# =============================================================================

class TestFinalizeResponse:
    """Tests for _finalize_response() function."""

    @pytest.fixture
    def mock_session(self):
        """Mock session dict."""
        return {
            "session_id": "test-session-123",
            "user_id": "user-abc",
        }

    @pytest.fixture
    def mock_swarm_result(self):
        """Mock swarm result object."""
        result = MagicMock()
        result.results = {"key1": "value1"}
        result.message = "Test message"
        return result

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_business_logic_error_invokes_debug_agent(
        self, mock_capture, mock_session, mock_swarm_result
    ):
        """
        BUG-034: Business logic errors MUST invoke Debug Agent.
        Previously, errors with 'error' field were NOT analyzed.
        """
        response = {
            "success": False,
            "error": "File not found at S3 key 'imports/test/file.csv'. Check if the file was uploaded successfully.",
            "action": "nexo_analyze_file",
        }

        result = _finalize_response(
            response, "nexo_analyze_file", mock_session, mock_swarm_result
        )

        # Debug Agent should have been invoked
        mock_capture.assert_called_once()

        # Verify context was built correctly
        call_args = mock_capture.call_args
        context = call_args[0][2]  # Third positional arg is error_context
        assert context["error_type"] == "business_logic"
        assert context["action"] == "nexo_analyze_file"
        assert context["recommended_model"] == "flash"  # File not found is simple
        assert context["use_flash"] is True

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_extraction_failure_invokes_debug_agent(
        self, mock_capture, mock_session, mock_swarm_result
    ):
        """
        Extraction failures (no error message) MUST invoke Debug Agent.
        This was already working in BUG-033.
        """
        response = {
            "success": False,
            # No 'error' field - extraction failure
        }

        result = _finalize_response(
            response, "nexo_analyze_file", mock_session, mock_swarm_result
        )

        # Debug Agent should have been invoked
        mock_capture.assert_called_once()

        # Verify context indicates extraction failure
        call_args = mock_capture.call_args
        context = call_args[0][2]
        assert context["error_type"] == "extraction_failure"
        assert context["recommended_model"] == "pro"  # Unknown error uses Pro

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_success_response_skips_debug_agent(
        self, mock_capture, mock_session, mock_swarm_result
    ):
        """Success responses should NOT invoke Debug Agent."""
        response = {
            "success": True,
            "analysis": {"some": "data"},
        }

        result = _finalize_response(
            response, "nexo_analyze_file", mock_session, mock_swarm_result
        )

        # Debug Agent should NOT have been invoked
        mock_capture.assert_not_called()

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_already_has_debug_analysis_skips_reinvocation(
        self, mock_capture, mock_session, mock_swarm_result
    ):
        """Responses with existing debug_analysis should not be re-analyzed."""
        response = {
            "success": False,
            "error": "Some error",
            "debug_analysis": {
                "technical_explanation": "Already analyzed",
                "root_causes": [],
            },
        }

        result = _finalize_response(
            response, "nexo_analyze_file", mock_session, mock_swarm_result
        )

        # Debug Agent should NOT have been invoked (already has analysis)
        mock_capture.assert_not_called()

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_flash_recommendation_for_simple_errors(
        self, mock_capture, mock_session, mock_swarm_result
    ):
        """Simple errors should recommend Flash model."""
        simple_errors = [
            "Connection timeout after 30 seconds",
            "Rate limit exceeded: 429",
            "ValidationError: field 'name' is required",
            "File not found: /path/to/file",
        ]

        for error in simple_errors:
            mock_capture.reset_mock()
            response = {"success": False, "error": error}

            _finalize_response(
                response, "test_action", mock_session, mock_swarm_result
            )

            call_args = mock_capture.call_args
            context = call_args[0][2]
            assert context["use_flash"] is True, f"Failed for error: {error}"
            assert context["recommended_model"] == "flash"

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_pro_recommendation_for_complex_errors(
        self, mock_capture, mock_session, mock_swarm_result
    ):
        """Complex errors should recommend Pro model."""
        complex_errors = [
            "Agent loop terminated unexpectedly without completing task",
            "Memory consistency error in namespace resolution",
            "Failed to correlate swarm results with expected schema",
        ]

        for error in complex_errors:
            mock_capture.reset_mock()
            response = {"success": False, "error": error}

            _finalize_response(
                response, "test_action", mock_session, mock_swarm_result
            )

            call_args = mock_capture.call_args
            context = call_args[0][2]
            assert context["use_flash"] is False, f"Failed for error: {error}"
            assert context["recommended_model"] == "pro"


# =============================================================================
# Test: Graceful Degradation
# =============================================================================

class TestGracefulDegradation:
    """Tests for graceful handling when Debug Agent is unavailable."""

    @pytest.fixture
    def mock_session(self):
        return {"session_id": "test-session"}

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_debug_agent_failure_returns_response_without_analysis(
        self, mock_capture, mock_session
    ):
        """
        If Debug Agent fails, response should still be returned
        without debug_analysis (graceful degradation).
        """
        # Simulate _capture_debug_analysis not adding debug_analysis
        # (which happens on timeout or error)
        mock_capture.return_value = None

        response = {
            "success": False,
            "error": "Some error that needs analysis",
        }

        result = _finalize_response(response, "test_action", mock_session, None)

        # Response should still be returned
        assert result["success"] is False
        assert result["error"] == "Some error that needs analysis"
        # debug_analysis may or may not be present (depending on mock behavior)

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_null_session_handled_gracefully(self, mock_capture):
        """Null session should not cause crashes."""
        response = {"success": False, "error": "Test error"}

        # Should not raise
        result = _finalize_response(response, "test_action", None, None)

        assert result["success"] is False

    @patch("swarm.response_utils._capture_debug_analysis")
    def test_null_swarm_result_handled_gracefully(self, mock_capture, mock_session):
        """Null swarm_result should not cause crashes."""
        response = {"success": False, "error": "Test error"}

        # Should not raise
        result = _finalize_response(response, "test_action", mock_session, None)

        assert result["success"] is False


# =============================================================================
# Test: Flash Error Patterns Coverage
# =============================================================================

class TestFlashPatternsCoverage:
    """Verify all patterns in FLASH_ERROR_PATTERNS are tested."""

    def test_all_patterns_documented(self):
        """Ensure we have comprehensive pattern coverage."""
        # These are the key categories that should be covered
        categories = {
            "file/s3": ["file not found", "s3", "bucket", "key not found", "nosuchkey"],
            "network": ["timeout", "connection refused", "rate limit", "429", "503"],
            "validation": ["invalid", "required", "missing field", "validation error"],
            "auth": ["unauthorized", "401", "403", "forbidden", "token expired"],
        }

        for category, patterns in categories.items():
            for pattern in patterns:
                assert pattern in FLASH_ERROR_PATTERNS, (
                    f"Pattern '{pattern}' from category '{category}' "
                    f"not in FLASH_ERROR_PATTERNS"
                )

    def test_pattern_count_reasonable(self):
        """Ensure pattern set isn't too large (performance) or too small (coverage)."""
        # Should have between 20-50 patterns for good coverage without slowdown
        assert 20 <= len(FLASH_ERROR_PATTERNS) <= 50, (
            f"FLASH_ERROR_PATTERNS has {len(FLASH_ERROR_PATTERNS)} patterns. "
            f"Expected 20-50 for balanced coverage."
        )
