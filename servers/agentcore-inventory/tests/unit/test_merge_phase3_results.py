"""
Unit tests for BUG-045 Fix: _merge_phase3_results AI question preference

Tests that _merge_phase3_results correctly:
1. Prefers AI-generated questions from SchemaMapper when available
2. Falls back to template-based questions when SchemaMapper returns none
3. Includes questions even on status="success" for low-confidence mappings

File: agents/orchestrators/inventory_hub/main.py:1871-1950

Note: strands SDK mocking is handled by tests/conftest.py (module-level mocks)
"""

import pytest
import sys
from pathlib import Path

# Add parent directories to path for imports
server_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(server_root))

from agents.orchestrators.inventory_hub.main import _merge_phase3_results


class TestMergePhase3ResultsBUG045:
    """Test suite for BUG-045: AI-generated question preference."""

    @pytest.fixture
    def sample_phase2_response(self):
        """Fixture: Phase 2 response with nested structure."""
        return {
            "success": True,
            "import_session_id": "nexo_20260122_120000_test.csv",
            "filename": "test.csv",
            "detected_file_type": "csv_semicolon",
            "analysis": {
                "sheets": [
                    {
                        "columns": ["codigo", "descricao", "quantidade"],
                        "sample_data": [
                            {"codigo": "ABC123", "descricao": "Item 1", "quantidade": "10"},
                        ],
                        "row_count": 100,
                        "detected_format": "csv_semicolon",
                    }
                ],
                "sheet_count": 1,
                "total_rows": 100,
                "recommended_strategy": "direct_import",
            },
            "column_mappings": [],
            "overall_confidence": 0.85,
            "questions": [],
            "reasoning_trace": [],
        }

    @pytest.fixture
    def ai_generated_questions(self):
        """Fixture: AI-generated questions from SchemaMapper (BUG-045 format)."""
        return [
            {
                "id": "q_part_number_abc123",
                "question": "Identificamos valores como 'ABC123', 'DEF456' na coluna 'codigo'. Isso é o código do produto (Part Number)?",
                "context": "O campo part_number é obrigatório para importação no sistema de inventário.",
                "hint": "Baseado nos valores observados, esta coluna parece conter códigos alfanuméricos no formato de Part Number.",
                "importance": "critical",
                "topic": "column_mapping",
                "target_column": "part_number",
                "options": [
                    {"value": "codigo", "label": "codigo", "recommended": True},
                    {"value": "_none_", "label": "Nenhuma dessas colunas", "warning": True},
                ],
            },
            {
                "id": "q_quantity_def456",
                "question": "Vemos valores numéricos como '10', '20' na coluna 'quantidade'. Isso representa a quantidade em estoque?",
                "context": "A quantidade é necessária para rastrear níveis de inventário.",
                "hint": "Padrão numérico inteiro detectado, consistente com contagem de estoque.",
                "importance": "high",
                "topic": "column_mapping",
                "target_column": "quantity",
                "options": [
                    {"value": "quantidade", "label": "quantidade", "recommended": True},
                    {"value": "_none_", "label": "Nenhuma dessas colunas", "warning": True},
                ],
            },
        ]

    @pytest.fixture
    def template_based_missing_fields(self):
        """Fixture: missing_required_fields for template-based question generation."""
        return [
            {
                "field": "part_number",
                "description": "Código do produto (Part Number)",
                "required": True,
            },
            {
                "field": "quantity",
                "description": "Quantidade em estoque",
                "required": True,
            },
        ]

    # =========================================================================
    # BUG-045: AI-generated questions preference
    # =========================================================================

    def test_prefers_ai_questions_when_available(
        self, sample_phase2_response, ai_generated_questions
    ):
        """BUG-045: Should use AI-generated questions from SchemaMapper when available."""
        phase3_response = {
            "success": True,
            "status": "needs_input",
            "missing_required_fields": [{"field": "part_number"}],  # Fallback data
            "questions": ai_generated_questions,  # AI-generated (preferred)
            "overall_confidence": 0.65,
        }

        result = _merge_phase3_results(sample_phase2_response, phase3_response)

        # Should use AI-generated questions, not template-based
        assert len(result["questions"]) == 2
        assert result["questions"][0]["id"] == "q_part_number_abc123"
        assert "Identificamos valores" in result["questions"][0]["question"]
        assert result["questions"][0].get("hint") is not None

    def test_fallback_to_template_when_no_ai_questions(
        self, sample_phase2_response, template_based_missing_fields
    ):
        """BUG-045: Should fallback to template-based questions when SchemaMapper returns none."""
        phase3_response = {
            "success": True,
            "status": "needs_input",
            "missing_required_fields": template_based_missing_fields,
            # No "questions" key - triggers fallback
            "overall_confidence": 0.65,
        }

        result = _merge_phase3_results(sample_phase2_response, phase3_response)

        # Should generate template-based questions from missing_required_fields
        assert len(result["questions"]) == 2
        # Template questions don't have AI-generated fields like "hint"
        # They have simpler structure from _convert_missing_fields_to_questions

    def test_fallback_when_ai_questions_empty(
        self, sample_phase2_response, template_based_missing_fields
    ):
        """BUG-045: Should fallback when SchemaMapper returns empty questions array."""
        phase3_response = {
            "success": True,
            "status": "needs_input",
            "missing_required_fields": template_based_missing_fields,
            "questions": [],  # Empty array - should trigger fallback
            "overall_confidence": 0.65,
        }

        result = _merge_phase3_results(sample_phase2_response, phase3_response)

        # Should generate template-based questions
        assert len(result["questions"]) == 2

    def test_success_status_with_ai_questions(
        self, sample_phase2_response, ai_generated_questions
    ):
        """BUG-045: Should include AI questions even on status=success for low-confidence mappings."""
        phase3_response = {
            "success": True,
            "status": "success",
            "mappings": [
                {"source": "codigo", "target": "part_number", "confidence": 0.6},
            ],
            "questions": ai_generated_questions[:1],  # 1 question for low-confidence
            "overall_confidence": 0.60,
        }

        result = _merge_phase3_results(sample_phase2_response, phase3_response)

        # Should include the AI questions even on success
        assert len(result["questions"]) == 1
        assert result["questions"][0]["id"] == "q_part_number_abc123"

        # Should also have the mappings
        assert len(result["column_mappings"]) == 1
        assert result["column_mappings"][0]["target"] == "part_number"

    # =========================================================================
    # Existing behavior preservation
    # =========================================================================

    def test_phase3_failure_returns_phase2_only(self, sample_phase2_response):
        """Phase 3 failure should return Phase 2 response with error."""
        phase3_response = {
            "success": False,
            "error": "SchemaMapper timeout",
        }

        result = _merge_phase3_results(sample_phase2_response, phase3_response)

        # Should include phase3_error
        assert "phase3_error" in result
        assert result["phase3_error"] == "SchemaMapper timeout"

        # Should preserve Phase 2 questions (empty)
        assert result["questions"] == []

    def test_mapping_confidence_merged(self, sample_phase2_response, ai_generated_questions):
        """Should merge mapping_confidence from Phase 3."""
        phase3_response = {
            "success": True,
            "status": "needs_input",
            "questions": ai_generated_questions,
            "overall_confidence": 0.72,
        }

        result = _merge_phase3_results(sample_phase2_response, phase3_response)

        # Should have mapping_confidence from Phase 3
        assert result.get("mapping_confidence") == 0.72

    def test_phase3_status_marked(self, sample_phase2_response, ai_generated_questions):
        """Should mark phase3_status in merged response."""
        phase3_response = {
            "success": True,
            "status": "needs_input",
            "questions": ai_generated_questions,
            "overall_confidence": 0.65,
        }

        result = _merge_phase3_results(sample_phase2_response, phase3_response)

        assert result.get("phase3_status") == "needs_input"


class TestMergePhase3ResultsEdgeCases:
    """Edge cases for _merge_phase3_results."""

    @pytest.fixture
    def minimal_phase2_response(self):
        """Fixture: Minimal Phase 2 response."""
        return {
            "success": True,
            "import_session_id": "nexo_test",
            "questions": [],
        }

    def test_no_questions_no_missing_fields(self, minimal_phase2_response):
        """Should handle case where neither questions nor missing_fields exist."""
        phase3_response = {
            "success": True,
            "status": "success",
            "mappings": [],
            "overall_confidence": 1.0,
        }

        result = _merge_phase3_results(minimal_phase2_response, phase3_response)

        # Should have empty questions (from Phase 2)
        assert result["questions"] == []

    def test_unknown_status(self, minimal_phase2_response):
        """Should handle unknown status gracefully."""
        phase3_response = {
            "success": True,
            "status": "unknown_status",
            "overall_confidence": 0.5,
        }

        result = _merge_phase3_results(minimal_phase2_response, phase3_response)

        # Should not crash, status recorded
        assert result.get("phase3_status") == "unknown_status"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
