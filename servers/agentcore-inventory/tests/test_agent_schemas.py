# =============================================================================
# Agent Schemas Tests - AUDIT-001 Compliance
# =============================================================================
# Tests to verify that all Pydantic response schemas for agents are valid,
# properly configured, and work correctly with Strands structured_output_model.
#
# Reference:
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/
# - ADR-005: Strands Structured Output Compliance
# =============================================================================

import pytest
from pydantic import ValidationError

from shared.agent_schemas import (
    # Enums
    SuggestedAction,
    AnalysisSource,
    OperationType,
    ImportStage,
    # Base
    AgentResponseBase,
    # Debug sub-models
    DebugRootCause,
    DebugDocumentationLink,
    DebugSimilarPattern,
    # Specialist responses
    ValidationResponse,
    EnrichmentResponse,
    ComplianceResponse,
    IntakeResponse,
    DebugAnalysisResponse,
    LearningResponse,
    ObservationResponse,
    SchemaEvolutionResponse,
    EquipmentResearchResponse,
    EstoqueControlResponse,
    DataImportResponse,
    # Orchestrator responses
    OrchestratorResponse,
    NexoImportResponse,
    # Swarm responses
    FileAnalystResponse,
    SchemaValidatorResponse,
    ImportExecutorResponse,
    MemoryAgentResponse,
    HILAgentResponse,
)


class TestEnums:
    """Test that enums have correct values."""

    def test_suggested_action_values(self):
        """SuggestedAction should have expected values."""
        assert SuggestedAction.RETRY == "retry"
        assert SuggestedAction.FALLBACK == "fallback"
        assert SuggestedAction.ESCALATE == "escalate"
        assert SuggestedAction.ABORT == "abort"
        assert SuggestedAction.INVESTIGATE == "investigate"

    def test_analysis_source_values(self):
        """AnalysisSource should have expected values."""
        assert AnalysisSource.MEMORY_PATTERN == "memory_pattern"
        assert AnalysisSource.DOCUMENTATION == "documentation"
        assert AnalysisSource.INFERENCE == "inference"

    def test_operation_type_values(self):
        """OperationType should have expected values."""
        assert OperationType.ENTRADA == "entrada"
        assert OperationType.SAIDA == "saida"
        assert OperationType.TRANSFERENCIA == "transferencia"
        assert OperationType.AJUSTE == "ajuste"
        assert OperationType.INVENTARIO == "inventario"

    def test_import_stage_values(self):
        """ImportStage should have expected values."""
        assert ImportStage.ANALYSIS == "analysis"
        assert ImportStage.MAPPING == "mapping"
        assert ImportStage.VALIDATION == "validation"
        assert ImportStage.CONFIRMATION == "confirmation"
        assert ImportStage.EXECUTION == "execution"
        assert ImportStage.COMPLETE == "complete"
        assert ImportStage.ERROR == "error"


class TestAgentResponseBase:
    """Test base response schema that all agents extend."""

    def test_minimal_instantiation(self):
        """Should create instance with only required fields."""
        response = AgentResponseBase(success=True)
        assert response.success is True
        assert response.error is None
        assert response.request_id is None

    def test_full_instantiation(self):
        """Should create instance with all fields."""
        response = AgentResponseBase(
            success=False, error="Something failed", request_id="req-123"
        )
        assert response.success is False
        assert response.error == "Something failed"
        assert response.request_id == "req-123"

    def test_extra_fields_allowed(self):
        """Should allow extra fields for backward compatibility."""
        response = AgentResponseBase(
            success=True, extra_field="extra_value", another_field=123
        )
        assert response.success is True
        assert response.extra_field == "extra_value"
        assert response.another_field == 123

    def test_serialization(self):
        """Should serialize to dict correctly."""
        response = AgentResponseBase(success=True, request_id="req-456")
        data = response.model_dump()
        assert data["success"] is True
        assert data["request_id"] == "req-456"


class TestDebugSubModels:
    """Test Debug Agent sub-models."""

    def test_debug_root_cause_valid(self):
        """Should create valid DebugRootCause."""
        cause = DebugRootCause(
            cause="File not found",
            confidence=0.85,
            evidence=["Error message indicates missing file"],
            source=AnalysisSource.INFERENCE,
        )
        assert cause.cause == "File not found"
        assert cause.confidence == 0.85
        assert len(cause.evidence) == 1

    def test_debug_root_cause_confidence_range(self):
        """Confidence should be between 0.0 and 1.0."""
        # Valid
        DebugRootCause(cause="Test", confidence=0.0)
        DebugRootCause(cause="Test", confidence=1.0)
        DebugRootCause(cause="Test", confidence=0.5)

        # Invalid - too low
        with pytest.raises(ValidationError):
            DebugRootCause(cause="Test", confidence=-0.1)

        # Invalid - too high
        with pytest.raises(ValidationError):
            DebugRootCause(cause="Test", confidence=1.1)

    def test_debug_documentation_link(self):
        """Should create valid DebugDocumentationLink."""
        link = DebugDocumentationLink(
            title="S3 Error Guide",
            url="https://docs.aws.amazon.com/s3/errors",
            relevance="Covers S3 access denied errors",
        )
        assert link.title == "S3 Error Guide"
        assert "aws.amazon.com" in link.url

    def test_debug_similar_pattern(self):
        """Should create valid DebugSimilarPattern."""
        pattern = DebugSimilarPattern(
            pattern_id="pat-001", similarity=0.92, resolution="Retry with backoff"
        )
        assert pattern.pattern_id == "pat-001"
        assert pattern.similarity == 0.92


class TestSpecialistResponses:
    """Test specialist agent response schemas."""

    def test_validation_response_defaults(self):
        """ValidationResponse should have sensible defaults."""
        response = ValidationResponse(success=True)
        assert response.is_valid is False  # Default
        assert response.validation_score == 0.0
        assert response.issues == []
        assert response.warnings == []

    def test_validation_response_score_range(self):
        """Validation score should be 0.0 to 1.0."""
        ValidationResponse(success=True, validation_score=0.0)
        ValidationResponse(success=True, validation_score=1.0)

        with pytest.raises(ValidationError):
            ValidationResponse(success=True, validation_score=-0.1)
        with pytest.raises(ValidationError):
            ValidationResponse(success=True, validation_score=1.1)

    def test_enrichment_response_defaults(self):
        """EnrichmentResponse should have sensible defaults."""
        response = EnrichmentResponse(success=True)
        assert response.enriched_data == {}
        assert response.sources_used == []
        assert response.confidence == 0.0

    def test_compliance_response_full(self):
        """ComplianceResponse should accept full data."""
        response = ComplianceResponse(
            success=True,
            compliant=False,
            violations=["Missing serial number", "Invalid quantity"],
            recommendations=["Add serial number field"],
        )
        assert response.compliant is False
        assert len(response.violations) == 2

    def test_intake_response_defaults(self):
        """IntakeResponse should have sensible defaults."""
        response = IntakeResponse(success=True)
        assert response.movement_id is None
        assert response.items_processed == 0
        assert response.items_failed == 0
        assert response.details == {}

    def test_debug_analysis_response_full(self):
        """DebugAnalysisResponse should handle full analysis."""
        response = DebugAnalysisResponse(
            success=True,
            error_signature="sig_abc123",
            error_type="S3AccessDenied",
            technical_explanation="Acesso negado ao bucket S3",
            root_causes=[
                DebugRootCause(
                    cause="IAM policy missing",
                    confidence=0.9,
                    source=AnalysisSource.DOCUMENTATION,
                )
            ],
            debugging_steps=["Check IAM role", "Verify bucket policy"],
            recoverable=True,
            suggested_action=SuggestedAction.RETRY,
            llm_powered=True,
        )
        assert response.error_signature == "sig_abc123"
        assert len(response.root_causes) == 1
        assert response.suggested_action == SuggestedAction.RETRY

    def test_learning_response_defaults(self):
        """LearningResponse should have sensible defaults."""
        response = LearningResponse(success=True)
        assert response.pattern_learned is False
        assert response.pattern_id is None
        assert response.confidence_improvement == 0.0

    def test_observation_response_defaults(self):
        """ObservationResponse should have sensible defaults."""
        response = ObservationResponse(success=True)
        assert response.observations == []
        assert response.insights == []

    def test_schema_evolution_response_defaults(self):
        """SchemaEvolutionResponse should have sensible defaults."""
        response = SchemaEvolutionResponse(success=True)
        assert response.schema_change_proposed is False
        assert response.proposed_columns == []
        assert response.migration_script is None

    def test_equipment_research_response_defaults(self):
        """EquipmentResearchResponse should have sensible defaults."""
        response = EquipmentResearchResponse(success=True)
        assert response.equipment_info == {}
        assert response.manufacturer is None
        assert response.specifications == {}

    def test_estoque_control_response_with_operation(self):
        """EstoqueControlResponse should accept operation type."""
        response = EstoqueControlResponse(
            success=True,
            operation_type=OperationType.ENTRADA,
            quantity_affected=100,
            new_balance=500,
            location="WAREHOUSE-A",
        )
        assert response.operation_type == OperationType.ENTRADA
        assert response.quantity_affected == 100

    def test_data_import_response_defaults(self):
        """DataImportResponse should have sensible defaults."""
        response = DataImportResponse(success=True)
        assert response.rows_processed == 0
        assert response.rows_failed == 0
        assert response.preview_data is None
        assert response.column_mappings == []


class TestOrchestratorResponses:
    """Test orchestrator response schemas."""

    def test_orchestrator_response_defaults(self):
        """OrchestratorResponse should have sensible defaults."""
        response = OrchestratorResponse(success=True)
        assert response.action_taken == ""
        assert response.specialist_invoked is None
        assert response.result == {}
        assert response.requires_hil is False

    def test_orchestrator_response_full(self):
        """OrchestratorResponse should accept full data."""
        response = OrchestratorResponse(
            success=True,
            action_taken="route_to_validation",
            specialist_invoked="validation",
            result={"items_validated": 10},
            requires_hil=True,
        )
        assert response.action_taken == "route_to_validation"
        assert response.requires_hil is True

    def test_nexo_import_response_defaults(self):
        """NexoImportResponse should have sensible defaults."""
        response = NexoImportResponse(success=True)
        assert response.import_session_id == ""
        assert response.stage == ImportStage.ANALYSIS
        assert response.analysis is None
        assert response.questions == []
        assert response.column_mappings == []
        assert response.confidence == 0.0

    def test_nexo_import_response_with_stage(self):
        """NexoImportResponse should accept stage enum."""
        response = NexoImportResponse(
            success=True,
            import_session_id="nexo-123",
            stage=ImportStage.VALIDATION,
            confidence=0.85,
        )
        assert response.stage == ImportStage.VALIDATION
        assert response.confidence == 0.85


class TestImportResponses:
    """Test import agent response schemas (FileAnalyst, SchemaValidator, etc.)."""

    def test_file_analyst_response_defaults(self):
        """FileAnalystResponse should have sensible defaults."""
        response = FileAnalystResponse(success=True)
        assert response.file_type == "unknown"
        assert response.sheet_count == 1
        assert response.total_rows == 0
        assert response.columns == []
        assert response.recommended_strategy == ""

    def test_file_analyst_response_full(self):
        """FileAnalystResponse should accept full data."""
        response = FileAnalystResponse(
            success=True,
            file_type="xlsx",
            sheet_count=3,
            total_rows=500,
            columns=["PART_NUMBER", "QUANTITY", "SERIAL"],
            recommended_strategy="auto_import",
        )
        assert response.file_type == "xlsx"
        assert len(response.columns) == 3

    def test_schema_validator_response_defaults(self):
        """SchemaValidatorResponse should have sensible defaults."""
        response = SchemaValidatorResponse(success=True)
        assert response.schema_valid is False
        assert response.matched_columns == []
        assert response.unmatched_columns == []
        assert response.type_mismatches == []

    def test_import_executor_response_defaults(self):
        """ImportExecutorResponse should have sensible defaults."""
        response = ImportExecutorResponse(success=True)
        assert response.rows_imported == 0
        assert response.rows_failed == 0
        assert response.errors == []
        assert response.transaction_id is None

    def test_import_executor_response_full(self):
        """ImportExecutorResponse should accept full data."""
        response = ImportExecutorResponse(
            success=True,
            rows_imported=150,
            rows_failed=5,
            errors=["Row 45: Invalid quantity", "Row 67: Missing serial"],
            transaction_id="txn-abc123",
        )
        assert response.rows_imported == 150
        assert len(response.errors) == 2

    def test_memory_agent_response_defaults(self):
        """MemoryAgentResponse should have sensible defaults."""
        response = MemoryAgentResponse(success=True)
        assert response.memories_retrieved == 0
        assert response.memories_stored == 0
        assert response.relevant_patterns == []

    def test_hil_agent_response_defaults(self):
        """HILAgentResponse should have sensible defaults."""
        response = HILAgentResponse(success=True)
        assert response.approval_required is False
        assert response.approval_reason is None
        assert response.confidence_level == 0.0
        assert response.suggested_options == []

    def test_hil_agent_response_full(self):
        """HILAgentResponse should accept full data."""
        response = HILAgentResponse(
            success=True,
            approval_required=True,
            approval_reason="Low confidence mapping",
            confidence_level=0.65,
            suggested_options=[
                {"value": "map_to_quantity", "label": "Map to quantity field"},
                {"value": "ignore", "label": "Ignore column"},
            ],
        )
        assert response.approval_required is True
        assert len(response.suggested_options) == 2


class TestSerialization:
    """Test JSON serialization/deserialization for all schemas."""

    @pytest.mark.parametrize(
        "schema_class",
        [
            ValidationResponse,
            EnrichmentResponse,
            ComplianceResponse,
            IntakeResponse,
            DebugAnalysisResponse,
            LearningResponse,
            ObservationResponse,
            SchemaEvolutionResponse,
            EquipmentResearchResponse,
            EstoqueControlResponse,
            DataImportResponse,
            OrchestratorResponse,
            NexoImportResponse,
            FileAnalystResponse,
            SchemaValidatorResponse,
            ImportExecutorResponse,
            MemoryAgentResponse,
            HILAgentResponse,
        ],
    )
    def test_roundtrip_serialization(self, schema_class):
        """All schemas should serialize and deserialize correctly."""
        # Create instance with minimal data
        original = schema_class(success=True)

        # Serialize to JSON string
        json_str = original.model_dump_json()

        # Deserialize back
        restored = schema_class.model_validate_json(json_str)

        # Verify
        assert restored.success == original.success
        assert restored.error == original.error

    @pytest.mark.parametrize(
        "schema_class",
        [
            ValidationResponse,
            EnrichmentResponse,
            ComplianceResponse,
            IntakeResponse,
            LearningResponse,
            ObservationResponse,
            SchemaEvolutionResponse,
            EquipmentResearchResponse,
            EstoqueControlResponse,
            DataImportResponse,
            OrchestratorResponse,
            NexoImportResponse,
            FileAnalystResponse,
            SchemaValidatorResponse,
            ImportExecutorResponse,
            MemoryAgentResponse,
            HILAgentResponse,
        ],
    )
    def test_from_dict(self, schema_class):
        """All schemas should instantiate from dict."""
        data = {"success": True, "error": None}
        instance = schema_class(**data)
        assert instance.success is True


class TestBackwardCompatibility:
    """Test that schemas maintain backward compatibility."""

    def test_extra_fields_preserved_in_output(self):
        """Extra fields should be preserved when serializing."""
        response = ValidationResponse(
            success=True,
            is_valid=True,
            legacy_field="should_be_kept",  # Unknown field
        )
        data = response.model_dump()
        assert data.get("legacy_field") == "should_be_kept"

    def test_missing_optional_fields_use_defaults(self):
        """Missing optional fields should use defaults."""
        # Simulate partial data from older version
        data = {"success": True}
        response = DebugAnalysisResponse(**data)

        # All optional fields should have defaults
        assert response.error_signature == ""
        assert response.error_type == "Unknown"
        assert response.root_causes == []
        assert response.llm_powered is True
