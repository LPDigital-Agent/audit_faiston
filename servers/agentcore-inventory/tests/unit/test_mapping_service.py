# =============================================================================
# Unit Tests for BUG-028: Empty Mappings Handling in mapping_service.py
# =============================================================================
# Tests that column_mappings is ALWAYS set in the merged response, even when
# the mappings list is empty. This is a critical fix to ensure frontend
# TypeScript validation doesn't fail due to missing field.
# =============================================================================

import json
import pytest
from unittest.mock import MagicMock, patch

# Import the function under test
import sys
import os

# Add the agents path to sys.path for imports
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "../../agents/orchestrators/inventory_hub/services",
    ),
)


class TestMergePhase3Results:
    """Tests for _merge_phase3_results with focus on BUG-028 fix."""

    def test_empty_mappings_list_is_set_in_response(self):
        """
        BUG-028 FIX: Empty mappings list [] should still be set in response.

        When SchemaMapper returns status="success" with mappings=[], the
        merged response MUST include column_mappings=[] (not omit the key).
        """
        from mapping_service import _merge_phase3_results

        phase2 = {
            "success": True,
            "filename": "test.csv",
            "detected_file_type": "csv",
            "analysis": {},
        }
        phase3 = {
            "success": True,
            "status": "success",
            "mappings": [],  # Empty list - the BUG-028 scenario
            "overall_confidence": 0.0,
        }

        result = _merge_phase3_results(phase2, phase3)

        # BUG-028 FIX: column_mappings MUST be present in response
        assert "column_mappings" in result, "column_mappings field is missing!"
        assert result["column_mappings"] == [], "column_mappings should be empty list"
        assert result["phase3_status"] == "success"

    def test_non_empty_mappings_are_set_correctly(self):
        """Non-empty mappings should be set correctly in response."""
        from mapping_service import _merge_phase3_results

        phase2 = {"success": True, "filename": "test.csv"}
        phase3 = {
            "success": True,
            "status": "success",
            "mappings": [
                {
                    "source_column": "COD",
                    "target_column": "part_number",
                    "confidence": 0.95,
                }
            ],
            "overall_confidence": 0.95,
        }

        result = _merge_phase3_results(phase2, phase3)

        assert "column_mappings" in result
        assert len(result["column_mappings"]) == 1
        assert result["column_mappings"][0]["source_column"] == "COD"
        assert result["mapping_confidence"] == 0.95

    def test_needs_input_status_preserves_phase2_column_mappings(self):
        """status=needs_input should preserve phase2 column_mappings if present."""
        from mapping_service import _merge_phase3_results

        phase2 = {
            "success": True,
            "filename": "test.csv",
            "column_mappings": [],  # Phase 2 default
        }
        phase3 = {
            "success": True,
            "status": "needs_input",
            "missing_required_fields": [
                {
                    "target_column": "part_number",
                    "description": "Código do material",
                    "available_sources": ["COD", "SKU"],
                }
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question_text": "Qual coluna representa o código?",
                    "options": [],
                }
            ],
        }

        result = _merge_phase3_results(phase2, phase3)

        # Questions should be present
        assert "questions" in result
        assert len(result["questions"]) == 1
        # phase3_status should be "needs_input"
        assert result["phase3_status"] == "needs_input"

    def test_key_tolerant_extraction_mappings_key(self):
        """Test that 'mappings' key is extracted correctly."""
        from mapping_service import _merge_phase3_results

        phase2 = {"success": True}
        phase3 = {
            "success": True,
            "status": "success",
            "mappings": [{"source": "A", "target": "B"}],
        }

        result = _merge_phase3_results(phase2, phase3)

        assert "column_mappings" in result
        assert len(result["column_mappings"]) == 1

    def test_key_tolerant_extraction_column_mappings_key(self):
        """Test that 'column_mappings' key fallback works (Ghost Bug mitigation)."""
        from mapping_service import _merge_phase3_results

        phase2 = {"success": True}
        phase3 = {
            "success": True,
            "status": "success",
            # Using alternative key name that Gemini might generate
            "column_mappings": [{"source": "X", "target": "Y"}],
        }

        result = _merge_phase3_results(phase2, phase3)

        assert "column_mappings" in result
        assert len(result["column_mappings"]) == 1

    def test_phase3_error_returns_phase2_response(self):
        """When Phase 3 fails, should return Phase 2 response with error."""
        from mapping_service import _merge_phase3_results

        phase2 = {
            "success": True,
            "filename": "test.csv",
            "column_mappings": [],
        }
        phase3 = {
            "success": False,
            "error": "SchemaMapper timeout",
        }

        result = _merge_phase3_results(phase2, phase3)

        # Should have phase3_error but still return valid response
        assert "phase3_error" in result
        assert result["phase3_error"] == "SchemaMapper timeout"

    def test_requires_confirmation_always_true(self):
        """requires_confirmation should always be True per plan."""
        from mapping_service import _merge_phase3_results

        phase2 = {"success": True}
        phase3 = {
            "success": True,
            "status": "success",
            "mappings": [{"source": "A", "target": "B"}],
            "overall_confidence": 1.0,  # Even at 100% confidence
        }

        result = _merge_phase3_results(phase2, phase3)

        # Always require confirmation, even at 100% confidence
        assert result["requires_confirmation"] is True


class TestKeyTolerantExtraction:
    """Tests for Ghost Bug mitigation: key-tolerant mapping extraction."""

    def test_extracts_mappings_key(self):
        """Standard 'mappings' key is extracted."""
        from mapping_service import _merge_phase3_results

        phase3 = {"status": "success", "mappings": [{"a": "b"}]}
        result = _merge_phase3_results({}, phase3)

        assert "column_mappings" in result
        assert result["column_mappings"] == [{"a": "b"}]

    def test_extracts_columns_map_key(self):
        """Alternative 'columns_map' key is extracted."""
        from mapping_service import _merge_phase3_results

        phase3 = {"status": "success", "columns_map": [{"x": "y"}]}
        result = _merge_phase3_results({}, phase3)

        assert "column_mappings" in result
        assert result["column_mappings"] == [{"x": "y"}]

    def test_extracts_mapping_list_key(self):
        """Alternative 'mapping_list' key is extracted."""
        from mapping_service import _merge_phase3_results

        phase3 = {"status": "success", "mapping_list": [{"p": "q"}]}
        result = _merge_phase3_results({}, phase3)

        assert "column_mappings" in result
        assert result["column_mappings"] == [{"p": "q"}]

    def test_returns_empty_list_when_no_key_found(self):
        """Returns empty list when no mapping key is found."""
        from mapping_service import _merge_phase3_results

        phase3 = {"status": "success", "other_field": "value"}
        result = _merge_phase3_results({}, phase3)

        # BUG-028 FIX: column_mappings should exist (empty list)
        assert "column_mappings" in result
        assert result["column_mappings"] == []

    def test_first_non_empty_wins(self):
        """First non-empty result wins in the fallback chain."""
        from mapping_service import _merge_phase3_results

        phase3 = {
            "status": "success",
            "mappings": [],  # Empty, should fallback
            "column_mappings": [{"first": "wins"}],  # This should be used
        }

        result = _merge_phase3_results({}, phase3)

        # Empty list is falsy, so column_mappings wins in 'or' chain
        assert len(result["column_mappings"]) == 1
        assert result["column_mappings"][0] == {"first": "wins"}
