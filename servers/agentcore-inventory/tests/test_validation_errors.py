"""
Test validation errors are enriched via DebugAgent.

This module tests that validation errors in InventoryHub Mode 2.5 and Mode 2
are properly caught by @cognitive_sync_handler and enriched via DebugAgent.

Tests verify:
1. Validation errors raise CognitiveError (not return dict)
2. CognitiveError contains enriched fields (human_explanation, suggested_fix)
3. Error type is preserved for debugging
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_debug_agent_response():
    """Mock DebugAgent A2A response for error enrichment."""
    return MagicMock(
        success=True,
        response='{"human_explanation": "Parece que você esqueceu de informar o nome do arquivo.", "suggested_fix": "Informe o nome do arquivo com extensão (ex: planilha.xlsx).", "error_type": "ValueError", "recoverable": true}',
    )


@pytest.fixture
def mock_a2a_client(mock_debug_agent_response):
    """Mock A2A client to avoid real DebugAgent calls."""
    mock_client = MagicMock()
    mock_client.invoke_agent = AsyncMock(return_value=mock_debug_agent_response)
    return mock_client


@pytest.fixture(autouse=True)
def mock_cognitive_middleware(mock_a2a_client):
    """
    Mock the cognitive error handler middleware to use our mocked A2A client.

    This prevents real network calls to DebugAgent during tests while still
    exercising the full error enrichment flow.
    """
    # Patch A2AClient at source module (it's imported locally in functions)
    with patch(
        "shared.a2a_client.A2AClient",
        return_value=mock_a2a_client,
    ):
        # Also patch the circuit breaker to always allow execution
        with patch(
            "shared.cognitive_error_handler._debug_circuit.can_execute",
            return_value=True,
        ):
            yield


# =============================================================================
# Test: _validate_payload
# =============================================================================


class TestValidatePayload:
    """Tests for the _validate_payload helper function."""

    def test_empty_payload_raises_cognitive_error(self, mock_cognitive_middleware):
        """Verify empty payload triggers DebugAgent enrichment."""
        from agents.orchestrators.inventory_hub.main import _validate_payload
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _validate_payload({})

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "human_explanation" in error.to_dict()
        assert error.recoverable is True

    def test_payload_with_only_action_returns_empty_string(self):
        """Verify payload with action but no prompt raises error."""
        from agents.orchestrators.inventory_hub.main import _validate_payload
        from shared.cognitive_error_handler import CognitiveError

        # Action alone is not enough - we need prompt for Mode 2 LLM path
        with pytest.raises(CognitiveError):
            _validate_payload({"action": "some_action"})

    def test_valid_prompt_returns_string(self):
        """Verify valid payload returns the prompt string."""
        from agents.orchestrators.inventory_hub.main import _validate_payload

        prompt = _validate_payload({"prompt": "Upload arquivo.csv"})
        assert prompt == "Upload arquivo.csv"

    def test_message_field_also_accepted(self):
        """Verify 'message' field is accepted as prompt alternative."""
        from agents.orchestrators.inventory_hub.main import _validate_payload

        prompt = _validate_payload({"message": "Upload arquivo.csv"})
        assert prompt == "Upload arquivo.csv"


# =============================================================================
# Test: _handle_get_nf_upload_url
# =============================================================================


class TestHandleGetNfUploadUrl:
    """Tests for file upload URL validation."""

    def test_missing_filename_raises_cognitive_error(self, mock_cognitive_middleware):
        """Verify missing filename triggers DebugAgent enrichment."""
        from agents.orchestrators.inventory_hub.main import _handle_get_nf_upload_url
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _handle_get_nf_upload_url({}, "user123", "session456")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "filename" in error.technical_message.lower() or "arquivo" in error.technical_message.lower()

    def test_filename_without_extension_raises_cognitive_error(self, mock_cognitive_middleware):
        """Verify filename without extension triggers DebugAgent enrichment."""
        from agents.orchestrators.inventory_hub.main import _handle_get_nf_upload_url
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _handle_get_nf_upload_url({"filename": "testfile"}, "user123", "session456")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "extensão" in error.technical_message.lower() or "extension" in error.technical_message.lower()

    def test_invalid_extension_raises_cognitive_error(self, mock_cognitive_middleware):
        """Verify invalid extension triggers DebugAgent enrichment."""
        from agents.orchestrators.inventory_hub.main import _handle_get_nf_upload_url
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _handle_get_nf_upload_url({"filename": "malware.exe"}, "user123", "session456")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert ".exe" in error.technical_message or "permitido" in error.technical_message.lower()


# =============================================================================
# Test: _handle_verify_file
# =============================================================================


class TestHandleVerifyFile:
    """Tests for file verification validation."""

    def test_missing_s3_key_raises_cognitive_error(self, mock_cognitive_middleware):
        """Verify missing s3_key triggers DebugAgent enrichment."""
        from agents.orchestrators.inventory_hub.main import _handle_verify_file
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _handle_verify_file({})

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "s3_key" in error.technical_message.lower()


# =============================================================================
# Test: _handle_direct_action
# =============================================================================


class TestHandleDirectAction:
    """Tests for direct action routing validation."""

    def test_unknown_action_raises_cognitive_error(self, mock_cognitive_middleware):
        """Verify unknown action triggers DebugAgent enrichment."""
        from agents.orchestrators.inventory_hub.main import _handle_direct_action
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _handle_direct_action("invalid_action", {}, "user123", "session456")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "invalid_action" in error.technical_message


# =============================================================================
# Test: CognitiveError structure
# =============================================================================


class TestCognitiveErrorStructure:
    """Tests for CognitiveError response format."""

    def test_cognitive_error_has_required_fields(self, mock_cognitive_middleware):
        """Verify CognitiveError contains all required fields for frontend."""
        from agents.orchestrators.inventory_hub.main import _validate_payload
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _validate_payload({})

        error = exc_info.value
        error_dict = error.to_dict()

        # Required fields for frontend display
        assert "human_explanation" in error_dict
        assert "suggested_fix" in error_dict
        assert "technical_message" in error_dict
        assert "error_type" in error_dict
        assert "recoverable" in error_dict

    def test_cognitive_error_is_recoverable_for_validation(self, mock_cognitive_middleware):
        """Verify validation errors are marked as recoverable."""
        from agents.orchestrators.inventory_hub.main import _validate_payload
        from shared.cognitive_error_handler import CognitiveError

        with pytest.raises(CognitiveError) as exc_info:
            _validate_payload({})

        error = exc_info.value
        # User can fix validation errors and retry
        assert error.recoverable is True


# =============================================================================
# Test: _validate_llm_response (BUG-020: Output Validation)
# =============================================================================


class TestOutputValidation:
    """
    BUG-020: Output validation for LLM responses.

    Tests verify that incomplete LLM responses trigger validation errors
    which are enriched via DebugAgent (same pattern as input validation).
    """

    def test_incomplete_file_analysis_raises_error(self, mock_cognitive_middleware):
        """Verify missing sheets/columns triggers validation error."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response
        from shared.cognitive_error_handler import CognitiveError

        response = {"status": "success"}  # Missing sheets/columns
        with pytest.raises(CognitiveError) as exc_info:
            _validate_llm_response(response, "nexo_analyze_file")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "incompleta" in error.technical_message.lower()

    def test_empty_sheets_raises_error(self, mock_cognitive_middleware):
        """Verify empty sheets array triggers validation error."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response
        from shared.cognitive_error_handler import CognitiveError

        response = {"status": "success", "sheets": []}  # Empty array
        with pytest.raises(CognitiveError) as exc_info:
            _validate_llm_response(response, "nexo_analyze_file")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "zero abas" in error.technical_message.lower()

    def test_valid_file_analysis_passes(self):
        """Verify valid response passes validation."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {"status": "success", "sheets": [{"name": "Sheet1"}]}
        result = _validate_llm_response(response, "nexo_analyze_file")
        assert result == response

    def test_columns_also_accepted_for_file_analysis(self):
        """Verify 'columns' field is accepted as alternative to 'sheets'."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {"status": "success", "columns": ["col_a", "col_b"]}
        result = _validate_llm_response(response, "nexo_analyze_file")
        assert result == response

    def test_incomplete_mapping_raises_error(self, mock_cognitive_middleware):
        """Verify missing mappings triggers validation error."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response
        from shared.cognitive_error_handler import CognitiveError

        response = {"status": "success", "overall_confidence": 0.87}
        with pytest.raises(CognitiveError) as exc_info:
            _validate_llm_response(response, "map_to_schema")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "mappings" in error.technical_message.lower()

    def test_empty_mappings_raises_error(self, mock_cognitive_middleware):
        """Verify empty mappings array triggers validation error."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response
        from shared.cognitive_error_handler import CognitiveError

        response = {"status": "success", "mappings": []}
        with pytest.raises(CognitiveError) as exc_info:
            _validate_llm_response(response, "map_to_schema")

        error = exc_info.value
        assert error.error_type == "ValueError"
        assert "nenhuma coluna" in error.technical_message.lower()

    def test_valid_mapping_passes(self):
        """Verify valid mapping response passes validation."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {
            "status": "success",
            "mappings": [{"source": "codigo", "target": "part_number"}],
        }
        result = _validate_llm_response(response, "map_to_schema")
        assert result == response

    def test_schema_mapper_action_also_validated(self, mock_cognitive_middleware):
        """Verify 'schema_mapper' action is validated same as 'map_to_schema'."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response
        from shared.cognitive_error_handler import CognitiveError

        response = {"status": "success"}  # Missing mappings
        with pytest.raises(CognitiveError):
            _validate_llm_response(response, "schema_mapper")

    def test_unknown_action_skips_validation(self):
        """Verify unknown actions pass through without validation."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {"status": "success"}  # Would fail for known actions
        result = _validate_llm_response(response, "unknown_action")
        assert result == response  # Passes through unchanged

    def test_empty_action_skips_validation(self):
        """Verify empty action (chat mode) skips validation."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {"status": "success"}
        result = _validate_llm_response(response, "")
        assert result == response

    def test_error_response_passes_through(self):
        """Verify error responses are not blocked by validation."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {"status": "error", "error": "File not found"}
        result = _validate_llm_response(response, "nexo_analyze_file")
        assert result["error"] == "File not found"

    def test_success_false_passes_through(self):
        """Verify success=False responses pass through without validation."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {"success": False, "error": "Processing failed"}
        result = _validate_llm_response(response, "nexo_analyze_file")
        assert result["success"] is False

    def test_mapping_with_needs_input_status_passes(self):
        """Verify mapping with needs_input status passes without mappings check."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response

        response = {
            "status": "needs_input",
            "missing_required_fields": [{"target_column": "part_number"}],
        }
        result = _validate_llm_response(response, "map_to_schema")
        assert result["status"] == "needs_input"

    def test_output_validation_error_is_recoverable(self, mock_cognitive_middleware):
        """Verify output validation errors are marked as recoverable for Frontend retry."""
        from agents.orchestrators.inventory_hub.main import _validate_llm_response
        from shared.cognitive_error_handler import CognitiveError

        response = {"status": "success"}  # Missing required fields
        with pytest.raises(CognitiveError) as exc_info:
            _validate_llm_response(response, "nexo_analyze_file")

        error = exc_info.value
        # BUG-020: Critical for Frontend "Tentar Novamente" button
        assert error.recoverable is True
