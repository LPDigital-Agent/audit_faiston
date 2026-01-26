"""
Unit tests for BUG-022 Fix: NEXO Response Transformation

Tests the _transform_file_structure_to_nexo_response() function that standardizes
flat file structure output to nested structure matching TypeScript contract.

File: agents/orchestrators/inventory_hub/main.py:1534+
Models: shared/agent_schemas.py:347+ (NexoAnalyzeFileResponse, NexoAnalysisData, NexoSheetData)
TypeScript Contract: client/services/sgaAgentcore.ts:1461-1502
"""

import pytest
from datetime import datetime
from unittest.mock import patch

# Import the transformation function and models
# Note: Adjust import path if needed based on your test runner setup
import sys
from pathlib import Path

# Add parent directories to path for imports
server_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(server_root))

from agents.orchestrators.inventory_hub.main import _transform_file_structure_to_nexo_response
from shared.agent_schemas import (
    NexoAnalyzeFileResponse,
    NexoAnalysisData,
    NexoSheetData,
)


class TestNexoTransform:
    """Test suite for NEXO response transformation (BUG-022 fix)."""

    @pytest.fixture
    def sample_flat_structure(self):
        """Fixture: Flat structure from get_file_structure() tool."""
        return {
            "success": True,
            "columns": ["codigo", "descricao", "quantidade", "preco"],
            "sample_data": [
                {"codigo": "ABC123", "descricao": "Item 1", "quantidade": "10", "preco": "19.90"},
                {"codigo": "DEF456", "descricao": "Item 2", "quantidade": "20", "preco": "29.90"},
                {"codigo": "GHI789", "descricao": "Item 3", "quantidade": "30", "preco": "39.90"},
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

    def test_successful_transformation(self, sample_flat_structure, sample_s3_key):
        """Test successful transformation from flat to nested structure."""
        result = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )

        # Verify top-level fields
        assert result["success"] is True
        assert "import_session_id" in result
        assert result["import_session_id"].startswith("nexo_")
        assert result["filename"] == "SOLICITAÇÕES_DE_EXPEDIÇÃO.csv"
        assert result["detected_file_type"] == "csv_semicolon"

        # Verify nested analysis structure
        assert "analysis" in result
        analysis = result["analysis"]
        assert isinstance(analysis, dict)

        # Verify analysis fields
        assert analysis["sheet_count"] == 1
        assert analysis["total_rows"] == 1500
        assert analysis["recommended_strategy"] == "direct_import"

        # Verify sheets array
        assert "sheets" in analysis
        sheets = analysis["sheets"]
        assert isinstance(sheets, list)
        assert len(sheets) == 1

        # Verify sheet structure
        sheet = sheets[0]
        assert sheet["columns"] == ["codigo", "descricao", "quantidade", "preco"]
        assert len(sheet["sample_data"]) == 3
        assert sheet["row_count"] == 1500
        assert sheet["detected_format"] == "csv_semicolon"

        # Verify default empty fields (except confidence which is now calculated)
        assert result["column_mappings"] == []
        # BUG-022 FIX: Phase 2 now returns file quality confidence instead of 0.0
        # Sample data has 4 columns, 3 valid rows, known format → confidence = 1.0
        assert result["overall_confidence"] == 1.0
        assert result["questions"] == []

    def test_pydantic_validation(self, sample_flat_structure, sample_s3_key):
        """Test that transformation output passes Pydantic validation."""
        result = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )

        # Should not raise ValidationError
        validated = NexoAnalyzeFileResponse(**result)

        # Verify Pydantic model fields
        assert validated.success is True
        assert validated.analysis.sheet_count == 1
        assert len(validated.analysis.sheets) == 1
        assert validated.analysis.sheets[0].row_count == 1500

    def test_empty_columns_handling(self, sample_s3_key):
        """Test handling of empty columns list."""
        flat_structure = {
            "success": True,
            "columns": [],
            "sample_data": [],
            "row_count_estimate": 0,
            "detected_format": "csv_semicolon",
        }

        result = _transform_file_structure_to_nexo_response(flat_structure, sample_s3_key)

        assert result["analysis"]["sheets"][0]["columns"] == []
        assert result["analysis"]["sheets"][0]["sample_data"] == []
        assert result["analysis"]["sheets"][0]["row_count"] == 0

    def test_missing_optional_fields(self, sample_s3_key):
        """Test transformation with minimal required fields only."""
        flat_structure = {
            "success": True,
            # Missing: columns, sample_data, row_count_estimate, detected_format
        }

        result = _transform_file_structure_to_nexo_response(flat_structure, sample_s3_key)

        # Should use defaults
        sheet = result["analysis"]["sheets"][0]
        assert sheet["columns"] == []
        assert sheet["sample_data"] == []
        assert sheet["row_count"] == 0
        assert sheet["detected_format"] == "unknown"

    def test_import_session_id_generation(self, sample_flat_structure, sample_s3_key):
        """Test import_session_id includes timestamp and filename."""
        with patch('datetime.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 1, 22, 14, 30, 0)

            result = _transform_file_structure_to_nexo_response(
                sample_flat_structure, sample_s3_key
            )

            expected_prefix = "nexo_20260122_143000_SOLICITAÇÕES_DE_EXPEDIÇÃO.csv"
            assert result["import_session_id"] == expected_prefix

    def test_filename_extraction_from_s3_key(self, sample_flat_structure):
        """Test filename extraction from various S3 key formats."""
        test_cases = [
            ("uploads/user123/file.csv", "file.csv"),
            ("documents/2026/01/report.xlsx", "report.xlsx"),
            ("simple.txt", "simple.txt"),
            ("folder/subfolder/deep/nested/data.csv", "data.csv"),
        ]

        for s3_key, expected_filename in test_cases:
            result = _transform_file_structure_to_nexo_response(
                sample_flat_structure, s3_key
            )
            assert result["filename"] == expected_filename

    def test_backward_compatibility_fields_preserved(self, sample_flat_structure, sample_s3_key):
        """Test that original tool fields are preserved in sheet for backward compatibility."""
        result = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )

        sheet = result["analysis"]["sheets"][0]

        # Original flat fields should be in sheet
        assert "columns" in sheet
        assert "sample_data" in sheet
        assert "row_count" in sheet  # Note: renamed from row_count_estimate
        assert "detected_format" in sheet

    def test_transformation_idempotency(self, sample_flat_structure, sample_s3_key):
        """Test that running transformation twice produces consistent results (excluding timestamp)."""
        result1 = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )
        result2 = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )

        # Timestamps will differ, so exclude import_session_id
        result1_copy = {k: v for k, v in result1.items() if k != "import_session_id"}
        result2_copy = {k: v for k, v in result2.items() if k != "import_session_id"}

        assert result1_copy == result2_copy

    def test_sample_data_structure(self, sample_flat_structure, sample_s3_key):
        """Test that sample_data structure is preserved correctly."""
        result = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )

        sample_data = result["analysis"]["sheets"][0]["sample_data"]

        # Verify it's list of dicts
        assert isinstance(sample_data, list)
        assert len(sample_data) == 3
        assert all(isinstance(row, dict) for row in sample_data)

        # Verify first row structure
        first_row = sample_data[0]
        assert first_row["codigo"] == "ABC123"
        assert first_row["descricao"] == "Item 1"
        assert first_row["quantidade"] == "10"

    def test_recommended_strategy_default(self, sample_flat_structure, sample_s3_key):
        """Test that recommended_strategy defaults to 'direct_import' for Mode 2.5."""
        result = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )

        assert result["analysis"]["recommended_strategy"] == "direct_import"

    def test_sheet_count_and_total_rows_consistency(self, sample_flat_structure, sample_s3_key):
        """Test that sheet_count and total_rows are consistent."""
        result = _transform_file_structure_to_nexo_response(
            sample_flat_structure, sample_s3_key
        )

        analysis = result["analysis"]

        # For CSV/TXT, always 1 sheet
        assert analysis["sheet_count"] == 1
        assert len(analysis["sheets"]) == analysis["sheet_count"]

        # Total rows should match single sheet row_count
        assert analysis["total_rows"] == analysis["sheets"][0]["row_count"]


class TestTypescriptContractAlignment:
    """Test alignment with TypeScript NexoAnalyzeFileResponse interface."""

    def test_all_required_typescript_fields_present(self):
        """Test that transformation output includes ALL required TypeScript fields."""
        flat_structure = {
            "success": True,
            "columns": ["col1"],
            "sample_data": [{"col1": "val1"}],
            "row_count_estimate": 10,
            "detected_format": "csv_comma",
        }
        s3_key = "test.csv"

        result = _transform_file_structure_to_nexo_response(flat_structure, s3_key)

        # Required fields from TypeScript interface (client/services/sgaAgentcore.ts:1461-1502)
        required_fields = [
            "success",
            "import_session_id",
            "filename",
            "detected_file_type",
            "analysis",
            "column_mappings",
            "overall_confidence",
            "questions",
        ]

        for field in required_fields:
            assert field in result, f"Missing required TypeScript field: {field}"

    def test_analysis_nested_structure_matches_typescript(self):
        """Test that analysis object structure matches TypeScript interface."""
        flat_structure = {
            "success": True,
            "columns": ["col1"],
            "sample_data": [{"col1": "val1"}],
            "row_count_estimate": 10,
            "detected_format": "csv_comma",
        }
        s3_key = "test.csv"

        result = _transform_file_structure_to_nexo_response(flat_structure, s3_key)
        analysis = result["analysis"]

        # Required analysis fields from TypeScript
        required_analysis_fields = ["sheets", "sheet_count", "total_rows", "recommended_strategy"]

        for field in required_analysis_fields:
            assert field in analysis, f"Missing required analysis field: {field}"

    def test_sheet_structure_matches_typescript(self):
        """Test that sheet structure matches TypeScript NexoSheetAnalysis interface."""
        flat_structure = {
            "success": True,
            "columns": ["col1"],
            "sample_data": [{"col1": "val1"}],
            "row_count_estimate": 10,
            "detected_format": "csv_comma",
        }
        s3_key = "test.csv"

        result = _transform_file_structure_to_nexo_response(flat_structure, s3_key)
        sheet = result["analysis"]["sheets"][0]

        # Required sheet fields
        required_sheet_fields = ["columns", "sample_data", "row_count", "detected_format"]

        for field in required_sheet_fields:
            assert field in sheet, f"Missing required sheet field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
