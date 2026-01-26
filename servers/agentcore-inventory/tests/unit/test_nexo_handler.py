"""
Unit tests for _handle_nexo_analyze_file() handler (BUG-022 integration)

Tests that handler correctly calls transformation and returns nested structure.
File: agents/orchestrators/inventory_hub/main.py:1990-2065

Updated for BUG-045: Tests now mock ENABLE_AUTO_SCHEMA_MAPPING to skip Phase 3
and expect CognitiveError wrapping from @cognitive_sync_handler decorator.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


class TestHandleNexoAnalyzeFile:
    """Test suite for nexo_analyze_file handler function"""

    @pytest.fixture
    def sample_flat_result(self):
        """Fixture: Flat structure from get_file_structure() tool."""
        return {
            "success": True,
            "columns": ["codigo", "descricao", "quantidade", "preco"],
            "sample_data": [
                {"codigo": "ABC123", "descricao": "Item 1", "quantidade": "10", "preco": "19.90"},
                {"codigo": "DEF456", "descricao": "Item 2", "quantidade": "20", "preco": "29.90"},
            ],
            "row_count_estimate": 1500,
            "detected_format": "csv_semicolon",
            "separator": ";",
            "file_size_bytes": 45678,
            "has_header": True,
            "encoding": "utf-8",
        }

    @pytest.fixture
    def sample_s3_key(self):
        """Fixture: Sample S3 key."""
        return "uploads/user123/SOLICITAÇÕES_DE_EXPEDIÇÃO.csv"

    @patch('agents.orchestrators.inventory_hub.main.ENABLE_AUTO_SCHEMA_MAPPING', False)
    @patch('agents.tools.analysis_tools.get_file_structure')
    @patch('agents.orchestrators.inventory_hub.main._transform_file_structure_to_nexo_response')
    def test_successful_analysis_returns_nested_structure(
        self, mock_transform, mock_get_file_structure, sample_flat_result, sample_s3_key
    ):
        """Handler transforms flat structure to nested before returning"""
        from agents.orchestrators.inventory_hub.main import _handle_nexo_analyze_file

        # Mock get_file_structure to return flat structure
        mock_get_file_structure.return_value = json.dumps(sample_flat_result)

        # Mock transformation to return nested structure
        mock_transform.return_value = {
            "success": True,
            "import_session_id": "nexo_20260122_120000_SOLICITAÇÕES_DE_EXPEDIÇÃO.csv",
            "filename": "SOLICITAÇÕES_DE_EXPEDIÇÃO.csv",
            "detected_file_type": "csv_semicolon",
            "analysis": {
                "sheets": [
                    {
                        "columns": ["codigo", "descricao", "quantidade", "preco"],
                        "sample_data": sample_flat_result["sample_data"],
                        "row_count": 1500,
                        "detected_format": "csv_semicolon",
                    }
                ],
                "sheet_count": 1,
                "total_rows": 1500,
                "recommended_strategy": "direct_import",
            },
            "column_mappings": [],
            "overall_confidence": 0.0,
            "questions": [],
            "reasoning_trace": [],
        }

        # Call handler
        payload = {"s3_key": sample_s3_key}
        result = _handle_nexo_analyze_file(payload)

        # Verify response envelope structure
        assert result["success"] is True
        assert result["specialist_agent"] == "analyst"
        assert "response" in result

        # Verify response has nested analysis.sheets structure
        response = result["response"]
        assert "analysis" in response
        assert "sheets" in response["analysis"]
        assert isinstance(response["analysis"]["sheets"], list)
        assert response["analysis"]["sheet_count"] == 1
        assert response["analysis"]["total_rows"] == 1500
        assert response["analysis"]["recommended_strategy"] == "direct_import"

    @patch('agents.orchestrators.inventory_hub.main.ENABLE_AUTO_SCHEMA_MAPPING', False)
    @patch('agents.tools.analysis_tools.get_file_structure')
    @patch('agents.orchestrators.inventory_hub.main._transform_file_structure_to_nexo_response')
    def test_transformation_function_called(
        self, mock_transform, mock_get_file_structure, sample_flat_result, sample_s3_key
    ):
        """Handler calls _transform_file_structure_to_nexo_response()"""
        from agents.orchestrators.inventory_hub.main import _handle_nexo_analyze_file

        # Mock get_file_structure
        mock_get_file_structure.return_value = json.dumps(sample_flat_result)
        mock_transform.return_value = {"success": True, "analysis": {"sheets": []}}

        # Call handler
        payload = {"s3_key": sample_s3_key}
        _handle_nexo_analyze_file(payload)

        # Verify transformation was called with correct args
        mock_transform.assert_called_once()
        call_args = mock_transform.call_args
        assert call_args[0][0] == sample_flat_result  # First arg: flat result
        assert call_args[0][1] == sample_s3_key  # Second arg: s3_key

    def test_missing_s3_key_raises_error(self):
        """Handler validates required s3_key parameter (wrapped in CognitiveError)"""
        from agents.orchestrators.inventory_hub.main import _handle_nexo_analyze_file
        from shared.cognitive_error_handler import CognitiveError

        # Call with empty payload - expects CognitiveError wrapping ValueError
        with pytest.raises(CognitiveError) as exc_info:
            _handle_nexo_analyze_file({})

        # Verify error message is in Portuguese
        error_msg = str(exc_info.value)
        assert "s3_key" in error_msg
        assert "obrigatório" in error_msg

    @patch('agents.tools.analysis_tools.get_file_structure')
    def test_tool_failure_raises_runtime_error(self, mock_get_file_structure, sample_s3_key):
        """Handler propagates tool failures (wrapped in CognitiveError)"""
        from agents.orchestrators.inventory_hub.main import _handle_nexo_analyze_file
        from shared.cognitive_error_handler import CognitiveError

        # Mock get_file_structure to return failure
        mock_get_file_structure.return_value = json.dumps({
            "success": False,
            "error": "Arquivo não encontrado no S3",
            "error_type": "S3_NOT_FOUND",
        })

        # Call handler and expect CognitiveError wrapping RuntimeError
        payload = {"s3_key": sample_s3_key}
        with pytest.raises(CognitiveError) as exc_info:
            _handle_nexo_analyze_file(payload)

        # Verify error message contains error type and message
        error_msg = str(exc_info.value)
        assert "S3_NOT_FOUND" in error_msg
        assert "Arquivo não encontrado no S3" in error_msg

    @patch('agents.orchestrators.inventory_hub.main.ENABLE_AUTO_SCHEMA_MAPPING', False)
    @patch('agents.tools.analysis_tools.get_file_structure')
    @patch('agents.orchestrators.inventory_hub.main._transform_file_structure_to_nexo_response')
    def test_unicode_normalization_nfc(
        self, mock_transform, mock_get_file_structure, sample_flat_result
    ):
        """Handler normalizes Portuguese filenames to NFC (BUG-044)"""
        from agents.orchestrators.inventory_hub.main import _handle_nexo_analyze_file
        import unicodedata

        # Mock get_file_structure and transform
        mock_get_file_structure.return_value = json.dumps(sample_flat_result)
        mock_transform.return_value = {"success": True, "analysis": {"sheets": []}}

        # Call with NFD-decomposed Portuguese filename (e.g., from macOS)
        nfd_filename = "uploads/user123/SOLICITAC\u0327O\u0303ES_DE_EXPEDIC\u0327A\u0303O.csv"  # NFD form
        payload = {"s3_key": nfd_filename}
        _handle_nexo_analyze_file(payload)

        # Verify get_file_structure was called with NFC-normalized filename
        mock_get_file_structure.assert_called_once()
        called_s3_key = mock_get_file_structure.call_args[0][0]

        # Verify it's NFC normalized
        assert unicodedata.is_normalized("NFC", called_s3_key)
        assert called_s3_key == unicodedata.normalize("NFC", nfd_filename)


class TestHandleNexoAnalyzeFilePhase3:
    """Test suite for Phase 3 auto-trigger behavior (BUG-045)"""

    @pytest.fixture
    def sample_flat_result(self):
        """Fixture: Flat structure from get_file_structure() tool."""
        return {
            "success": True,
            "columns": ["codigo", "descricao", "quantidade"],
            "sample_data": [
                {"codigo": "ABC123", "descricao": "Item 1", "quantidade": "10"},
            ],
            "row_count_estimate": 100,
            "detected_format": "csv_semicolon",
        }

    @pytest.fixture
    def sample_s3_key(self):
        """Fixture: Sample S3 key."""
        return "uploads/user123/test.csv"

    @patch('agents.orchestrators.inventory_hub.main.ENABLE_AUTO_SCHEMA_MAPPING', True)
    @patch('agents.orchestrators.inventory_hub.main._invoke_schema_mapper_phase3')
    @patch('agents.orchestrators.inventory_hub.main._merge_phase3_results')
    @patch('agents.tools.analysis_tools.get_file_structure')
    @patch('agents.orchestrators.inventory_hub.main._transform_file_structure_to_nexo_response')
    def test_phase3_auto_triggered_when_enabled(
        self,
        mock_transform,
        mock_get_file_structure,
        mock_merge,
        mock_invoke_phase3,
        sample_flat_result,
        sample_s3_key,
    ):
        """Phase 3 SchemaMapper is auto-invoked when ENABLE_AUTO_SCHEMA_MAPPING=True"""
        from agents.orchestrators.inventory_hub.main import _handle_nexo_analyze_file

        # Mock get_file_structure
        mock_get_file_structure.return_value = json.dumps(sample_flat_result)

        # Mock transformation
        mock_transform.return_value = {
            "success": True,
            "import_session_id": "nexo_test",
            "analysis": {"sheets": []},
            "questions": [],
        }

        # Mock Phase 3 invoke
        mock_invoke_phase3.return_value = {
            "success": True,
            "status": "needs_input",
            "questions": [{"id": "q1", "question": "Test question?"}],
        }

        # Mock merge to return combined result
        mock_merge.return_value = {
            "success": True,
            "import_session_id": "nexo_test",
            "analysis": {"sheets": []},
            "questions": [{"id": "q1", "question": "Test question?"}],
        }

        # Call handler
        payload = {"s3_key": sample_s3_key}
        result = _handle_nexo_analyze_file(payload)

        # Verify Phase 3 was invoked
        mock_invoke_phase3.assert_called_once()
        mock_merge.assert_called_once()

        # Verify result has merged questions
        assert result["success"] is True
        assert len(result["response"]["questions"]) == 1

    @patch('agents.orchestrators.inventory_hub.main.ENABLE_AUTO_SCHEMA_MAPPING', True)
    @patch('agents.orchestrators.inventory_hub.main._invoke_schema_mapper_phase3')
    @patch('agents.tools.analysis_tools.get_file_structure')
    @patch('agents.orchestrators.inventory_hub.main._transform_file_structure_to_nexo_response')
    def test_phase3_failure_graceful_degradation(
        self,
        mock_transform,
        mock_get_file_structure,
        mock_invoke_phase3,
        sample_flat_result,
        sample_s3_key,
    ):
        """Phase 3 failure returns Phase 2 results with error marker"""
        from agents.orchestrators.inventory_hub.main import _handle_nexo_analyze_file

        # Mock get_file_structure
        mock_get_file_structure.return_value = json.dumps(sample_flat_result)

        # Mock transformation
        mock_transform.return_value = {
            "success": True,
            "import_session_id": "nexo_test",
            "analysis": {"sheets": []},
            "questions": [],
        }

        # Mock Phase 3 to fail
        mock_invoke_phase3.side_effect = Exception("SchemaMapper timeout")

        # Call handler - should NOT raise, should return Phase 2 with error marker
        payload = {"s3_key": sample_s3_key}
        result = _handle_nexo_analyze_file(payload)

        # Verify graceful degradation
        assert result["success"] is True
        assert "phase3_error" in result["response"]
        assert "SchemaMapper timeout" in result["response"]["phase3_error"]


class TestSchemaMappingResponseSerialization:
    """Test suite for BUG-045: Pydantic round-trip serialization of questions field"""

    def test_schema_mapping_response_preserves_questions(self):
        """
        CRITICAL TEST (BUG-045): Verify questions field survives Pydantic round-trip.

        Root Cause: When Strands SDK enforces structured_output_model, fields NOT in the
        Pydantic schema are silently dropped during .model_dump().

        This test catches:
        - Field presence after serialization
        - Content preservation (not just field existence)
        - Regression if someone accidentally removes the field
        """
        from shared.agent_schemas import SchemaMappingResponse, MappingStatus

        # ARRANGE: Create response with questions array (simulates LLM output)
        test_questions = [
            {
                "id": "q1",
                "question": "Which column represents the part number?",
                "options": ["col1", "val", "x"]
            },
            {
                "id": "q2",
                "question": "What is the unit of measurement for quantity?",
                "options": ["units", "kg", "liters"]
            }
        ]

        response_data = {
            "success": True,  # Required by AgentResponseBase
            "status": MappingStatus.NEEDS_INPUT,
            "session_id": "test_session_123",
            "mappings": [
                {
                    "source_column": "col1",
                    "target_column": "part_number",
                    "transform": "TRIM|UPPERCASE",
                    "confidence": 0.85,
                    "reason": "Exact match"
                }
            ],
            "questions": test_questions,  # <-- CRITICAL: This must survive
            "unmapped_source_columns": ["val", "x"],
            "overall_confidence": 0.65,
            "requires_confirmation": True,
            "memory_id": "mem_test_123",
            "patterns_used": ["exact_match", "prefix_match"]
        }

        # ACT: Create Pydantic model from dict (simulates Strands structured_output)
        response = SchemaMappingResponse(**response_data)

        # ASSERT 1: Field exists in model
        assert hasattr(response, 'questions'), \
            "BUG-045 REGRESSION: questions field missing from SchemaMappingResponse!"

        # ASSERT 2: Field has correct value
        assert response.questions == test_questions, \
            "questions field exists but content doesn't match!"

        # ACT: Serialize to dict (simulates .model_dump() in agent response)
        serialized = response.model_dump()

        # ASSERT 3: Field survives serialization
        assert 'questions' in serialized, \
            "BUG-045 REGRESSION: questions field dropped during model_dump()!"

        # ASSERT 4: Content preserved after round-trip
        assert serialized['questions'] == test_questions, \
            "questions field serialized but content corrupted!"

        # ASSERT 5: Verify array structure is intact
        assert len(serialized['questions']) == 2, \
            "questions array length changed during serialization!"
        assert serialized['questions'][0]['id'] == "q1", \
            "questions array content corrupted during serialization!"
        assert serialized['questions'][1]['question'] == "What is the unit of measurement for quantity?", \
            "questions array content corrupted during serialization!"

    def test_schema_mapping_response_empty_questions_default(self):
        """
        Verify questions field defaults to empty array (backward compatibility).

        When status=SUCCESS (no HIL needed), questions should be empty list.
        """
        from shared.agent_schemas import SchemaMappingResponse, MappingStatus

        # ARRANGE: Create response WITHOUT questions field
        response_data = {
            "success": True,  # Required by AgentResponseBase
            "status": MappingStatus.SUCCESS,
            "session_id": "test_session_456",
            "mappings": [],
            "unmapped_source_columns": [],
            "overall_confidence": 0.95,
            "requires_confirmation": True,
            "memory_id": None,
            "patterns_used": []
        }

        # ACT: Create model (should use default_factory=list)
        response = SchemaMappingResponse(**response_data)

        # ASSERT: Default to empty array
        assert response.questions == [], \
            "questions field should default to empty array when not provided!"

        # ASSERT: Serialization includes empty array
        serialized = response.model_dump()
        assert serialized['questions'] == [], \
            "questions field should serialize to empty array by default!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
