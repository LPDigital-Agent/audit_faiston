"""
Unit Tests for Lambda Invoker.

Tests cover:
- Successful Lambda invocations with response transformation
- Error handling and CognitiveError generation
- X-Ray tracing integration
- Audit logging integration

Coverage target: 80%+ per CLAUDE.md mandate
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch, ANY

import pytest

# Set environment variables BEFORE importing the module
os.environ["INTAKE_TOOLS_LAMBDA"] = "test-intake-tools"
os.environ["FILE_ANALYZER_LAMBDA"] = "test-file-analyzer"
os.environ["AWS_REGION_NAME"] = "us-east-2"
os.environ["AUDIT_LOG_TABLE"] = "test-audit-table"

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.lambda_invoker import (
    LambdaInvoker,
    invoke_intake_tools,
    invoke_file_analyzer,
)
from shared.cognitive_error_handler import CognitiveError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_lambda_client():
    """Create a mock Lambda client."""
    with patch("shared.lambda_invoker._get_lambda_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_audit():
    """Mock the audit emitter."""
    with patch("shared.lambda_invoker.AgentAuditEmitter") as mock:
        audit = MagicMock()
        mock.return_value = audit
        yield audit


@pytest.fixture
def mock_xray():
    """Mock X-Ray tracing."""
    with patch("shared.lambda_invoker.trace_subsegment") as mock:
        # Create a mock context manager
        subsegment = MagicMock()
        mock.return_value.__enter__ = MagicMock(return_value=subsegment)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        yield mock


@pytest.fixture
def invoker(mock_audit):
    """Create a Lambda invoker instance with mocked audit."""
    return LambdaInvoker(audit_agent_id="test_agent")


@pytest.fixture
def success_response():
    """Create a successful Lambda response."""
    return {
        "success": True,
        "data": {
            "upload_url": "https://s3.amazonaws.com/presigned-url",
            "s3_key": "uploads/user-123/session-456/file.xlsx",
            "expires_in": 300,
        },
        "error": None,
        "error_type": None,
    }


@pytest.fixture
def error_response():
    """Create an error Lambda response."""
    return {
        "success": False,
        "data": None,
        "error": "Validation failed: filename is required",
        "error_type": "VALIDATION_ERROR",
    }


# =============================================================================
# Invoke Intake Tests
# =============================================================================


class TestInvokeIntake:
    """Tests for invoke_intake method."""

    def test_success_returns_orchestrator_envelope(
        self, mock_lambda_client, mock_xray, invoker, success_response
    ):
        """Successful invocation should return Orchestrator envelope."""
        # Setup mock
        payload_bytes = json.dumps(success_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call
        result = invoker.invoke_intake(
            action="get_nf_upload_url",
            payload={"filename": "test.xlsx"},
            user_id="user-123",
            session_id="session-456",
        )

        # Assert
        assert result["success"] is True
        assert result["specialist_agent"] == "intake"
        assert result["response"]["upload_url"] == "https://s3.amazonaws.com/presigned-url"
        assert result["response"]["s3_key"] == "uploads/user-123/session-456/file.xlsx"

    def test_invokes_correct_function(
        self, mock_lambda_client, mock_xray, invoker, success_response
    ):
        """Should invoke the configured intake tools function."""
        # Setup mock
        payload_bytes = json.dumps(success_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call
        invoker.invoke_intake(
            action="get_nf_upload_url",
            payload={"filename": "test.xlsx"},
            user_id="user-123",
            session_id="session-456",
        )

        # Assert
        mock_lambda_client.invoke.assert_called_once()
        call_args = mock_lambda_client.invoke.call_args
        assert call_args[1]["FunctionName"] == "test-intake-tools"
        assert call_args[1]["InvocationType"] == "RequestResponse"

        # Verify payload
        payload = json.loads(call_args[1]["Payload"])
        assert payload["action"] == "get_nf_upload_url"
        assert payload["user_id"] == "user-123"
        assert payload["session_id"] == "session-456"

    def test_validation_error_raises_cognitive_error(
        self, mock_lambda_client, mock_xray, invoker, error_response
    ):
        """Validation errors should raise CognitiveError."""
        # Setup mock
        payload_bytes = json.dumps(error_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call and assert
        with pytest.raises(CognitiveError) as exc_info:
            invoker.invoke_intake(
                action="get_nf_upload_url",
                payload={},  # Missing filename
                user_id="user-123",
                session_id="session-456",
            )

        error = exc_info.value
        assert error.error_type == "VALIDATION_ERROR"
        assert error.recoverable is True
        assert "filename" in error.technical_message.lower()

    def test_function_error_raises_cognitive_error(
        self, mock_lambda_client, mock_xray, invoker
    ):
        """Lambda function errors should raise CognitiveError."""
        # Setup mock with FunctionError
        error_payload = json.dumps({"errorMessage": "Out of memory"}).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=error_payload)),
            "StatusCode": 200,
            "FunctionError": "Unhandled",
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call and assert
        with pytest.raises(CognitiveError) as exc_info:
            invoker.invoke_intake(
                action="get_nf_upload_url",
                payload={"filename": "test.xlsx"},
                user_id="user-123",
                session_id="session-456",
            )

        error = exc_info.value
        assert error.error_type == "LAMBDA_FUNCTION_ERROR"
        assert "Out of memory" in error.technical_message

    def test_file_not_found_is_returned_not_raised(
        self, mock_lambda_client, mock_xray, invoker
    ):
        """FILE_NOT_FOUND errors should be returned, not raised."""
        # Setup mock
        not_found_response = {
            "success": True,
            "data": {
                "exists": False,
                "s3_key": "uploads/user-123/session-456/missing.xlsx",
            },
            "error": "File not found after 3 retries",
            "error_type": "FILE_NOT_FOUND",
        }
        payload_bytes = json.dumps(not_found_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call - should NOT raise
        result = invoker.invoke_intake(
            action="verify_file",
            payload={"s3_key": "uploads/user-123/session-456/missing.xlsx"},
            user_id="user-123",
            session_id="session-456",
        )

        # Assert - file not found is returned, not raised
        assert result["success"] is True
        assert result["response"]["exists"] is False


# =============================================================================
# Invoke File Analyzer Tests
# =============================================================================


class TestInvokeFileAnalyzer:
    """Tests for invoke_file_analyzer method."""

    def test_success_with_mcp_format(self, mock_lambda_client, mock_xray, invoker):
        """Should handle MCP format responses from file analyzer."""
        # Setup mock with MCP format
        mcp_response = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "columns": ["name", "quantity"],
                        "row_count_estimate": 100,
                    }),
                }
            ],
            "isError": False,
        }
        payload_bytes = json.dumps(mcp_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call
        result = invoker.invoke_file_analyzer(
            action="analyze_file_structure",
            payload={"s3_key": "uploads/user-123/file.csv"},
            session_id="session-456",
        )

        # Assert
        assert result["success"] is True
        assert result["specialist_agent"] == "file_analyzer"
        assert result["response"]["columns"] == ["name", "quantity"]

    def test_invokes_correct_function(
        self, mock_lambda_client, mock_xray, invoker
    ):
        """Should invoke the configured file analyzer function."""
        # Setup mock
        response = {"success": True, "data": {"columns": []}}
        payload_bytes = json.dumps(response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call
        invoker.invoke_file_analyzer(
            action="analyze_file_structure",
            payload={"s3_key": "uploads/test.csv"},
        )

        # Assert
        call_args = mock_lambda_client.invoke.call_args
        assert call_args[1]["FunctionName"] == "test-file-analyzer"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_invocation_exception_raises_cognitive_error(
        self, mock_lambda_client, mock_xray, invoker
    ):
        """Lambda client exceptions should raise CognitiveError."""
        # Setup mock to raise exception
        mock_lambda_client.invoke.side_effect = Exception("Network timeout")

        # Call and assert
        with pytest.raises(CognitiveError) as exc_info:
            invoker.invoke_intake(
                action="get_nf_upload_url",
                payload={"filename": "test.xlsx"},
                user_id="user-123",
                session_id="session-456",
            )

        error = exc_info.value
        assert error.error_type == "INVOCATION_ERROR"
        assert error.recoverable is True

    def test_json_parse_error_raises_cognitive_error(
        self, mock_lambda_client, mock_xray, invoker
    ):
        """Invalid JSON response should raise CognitiveError."""
        # Setup mock with invalid JSON
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=b"not valid json")),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call and assert
        with pytest.raises(CognitiveError) as exc_info:
            invoker.invoke_intake(
                action="get_nf_upload_url",
                payload={"filename": "test.xlsx"},
                user_id="user-123",
                session_id="session-456",
            )

        error = exc_info.value
        assert error.error_type == "PARSE_ERROR"
        assert error.recoverable is False


# =============================================================================
# Translation and Suggestion Tests
# =============================================================================


class TestTranslationAndSuggestions:
    """Tests for error translation and fix suggestions."""

    def test_translate_filename_error(self, invoker):
        """Should translate filename validation errors."""
        # The pattern checks for "filename" AND "obrigat" (obrigatorio)
        result = invoker._translate_error("filename is obrigatorio para upload")
        assert "arquivo" in result.lower()

    def test_translate_extension_error(self, invoker):
        """Should translate extension errors."""
        result = invoker._translate_error("Extensao nao permitida")
        assert "tipo" in result.lower() or "arquivo" in result.lower()

    def test_translate_unknown_error(self, invoker):
        """Unknown errors should get generic translation."""
        result = invoker._translate_error("Some random error")
        assert "erro" in result.lower()

    def test_suggest_fix_validation(self, invoker):
        """Should suggest fix for validation errors."""
        result = invoker._suggest_fix("VALIDATION_ERROR")
        assert "verifique" in result.lower()

    def test_suggest_fix_unknown(self, invoker):
        """Unknown error types should get generic suggestion."""
        result = invoker._suggest_fix("UNKNOWN_TYPE")
        assert "tente" in result.lower() or "suporte" in result.lower()


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_invoke_intake_tools_function(self, mock_lambda_client, mock_xray):
        """invoke_intake_tools should create invoker and call method."""
        # Setup mock
        success_response = {
            "success": True,
            "data": {"upload_url": "https://example.com"},
            "error": None,
            "error_type": None,
        }
        payload_bytes = json.dumps(success_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call
        with patch("shared.lambda_invoker.AgentAuditEmitter"):
            result = invoke_intake_tools(
                action="get_nf_upload_url",
                payload={"filename": "test.xlsx"},
                user_id="user-123",
                session_id="session-456",
            )

        # Assert
        assert result["success"] is True
        assert result["specialist_agent"] == "intake"

    def test_invoke_file_analyzer_function(self, mock_lambda_client, mock_xray):
        """invoke_file_analyzer should create invoker and call method."""
        # Setup mock
        response = {"success": True, "data": {"columns": ["a", "b"]}}
        payload_bytes = json.dumps(response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Call
        with patch("shared.lambda_invoker.AgentAuditEmitter"):
            result = invoke_file_analyzer(
                action="analyze",
                payload={"s3_key": "test.csv"},
                session_id="session-456",
            )

        # Assert
        assert result["success"] is True
        assert result["specialist_agent"] == "file_analyzer"


# =============================================================================
# Audit Logging Tests
# =============================================================================


class TestAuditLogging:
    """Tests for audit logging integration."""

    def test_emits_working_event_on_start(
        self, mock_lambda_client, mock_xray, mock_audit
    ):
        """Should emit working event when starting invocation."""
        # Setup mock
        success_response = {"success": True, "data": {}}
        payload_bytes = json.dumps(success_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Create invoker with mocked audit
        invoker = LambdaInvoker()
        invoker.audit = mock_audit

        # Call
        invoker.invoke_intake(
            action="get_nf_upload_url",
            payload={"filename": "test.xlsx"},
            user_id="user-123",
            session_id="session-456",
        )

        # Assert - should have called working()
        mock_audit.working.assert_called()
        call_args = mock_audit.working.call_args
        assert "session-456" in str(call_args)

    def test_emits_completed_event_on_success(
        self, mock_lambda_client, mock_xray, mock_audit
    ):
        """Should emit completed event on successful invocation."""
        # Setup mock
        success_response = {"success": True, "data": {}}
        payload_bytes = json.dumps(success_response).encode("utf-8")
        mock_response = {
            "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
            "StatusCode": 200,
        }
        mock_lambda_client.invoke.return_value = mock_response

        # Create invoker with mocked audit
        invoker = LambdaInvoker()
        invoker.audit = mock_audit

        # Call
        invoker.invoke_intake(
            action="get_nf_upload_url",
            payload={"filename": "test.xlsx"},
            user_id="user-123",
            session_id="session-456",
        )

        # Assert - should have called completed()
        mock_audit.completed.assert_called()

    def test_emits_error_event_on_failure(
        self, mock_lambda_client, mock_xray, mock_audit
    ):
        """Should emit error event on invocation failure."""
        # Setup mock to raise
        mock_lambda_client.invoke.side_effect = Exception("Connection failed")

        # Create invoker with mocked audit
        invoker = LambdaInvoker()
        invoker.audit = mock_audit

        # Call
        with pytest.raises(CognitiveError):
            invoker.invoke_intake(
                action="get_nf_upload_url",
                payload={"filename": "test.xlsx"},
                user_id="user-123",
                session_id="session-456",
            )

        # Assert - should have called error()
        mock_audit.error.assert_called()
