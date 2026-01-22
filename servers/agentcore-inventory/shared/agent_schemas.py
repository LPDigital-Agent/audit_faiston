# =============================================================================
# AUDIT-001: Strands Structured Output Pydantic Models
# =============================================================================
# This module defines Pydantic response models for ALL agents to enable
# type-safe structured output via Strands `structured_output_model` parameter.
#
# STRANDS STRUCTURED OUTPUT PATTERN:
# - Agent(structured_output_model=ResponseModel) → validates at runtime
# - result.structured_output → type-safe access (never use json.loads)
#
# Reference:
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/
#
# Before AUDIT-001: 17 of 19 agents used manual JSON parsing (anti-pattern)
# After AUDIT-001: 19 of 19 agents use structured_output_model (compliant)
#
# NOTE: These models are for AGENT RESPONSES only, not tool returns.
# Tools return dicts; structured_output_model validates final agent response.
# =============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# Enums for Type Safety
# =============================================================================

class SuggestedAction(str, Enum):
    """Suggested action for error handling."""
    RETRY = "retry"
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    ABORT = "abort"
    INVESTIGATE = "investigate"


class AnalysisSource(str, Enum):
    """Source of root cause analysis."""
    MEMORY_PATTERN = "memory_pattern"
    DOCUMENTATION = "documentation"
    INFERENCE = "inference"


class OperationType(str, Enum):
    """Type of stock operation."""
    ENTRADA = "entrada"
    SAIDA = "saida"
    TRANSFERENCIA = "transferencia"
    AJUSTE = "ajuste"
    INVENTARIO = "inventario"


class ImportStage(str, Enum):
    """Stage of import process."""
    ANALYSIS = "analysis"
    MAPPING = "mapping"
    VALIDATION = "validation"
    CONFIRMATION = "confirmation"
    EXECUTION = "execution"
    COMPLETE = "complete"
    ERROR = "error"


class MappingStatus(str, Enum):
    """Status of schema mapping operation (Phase 3)."""
    SUCCESS = "success"          # Complete mapping, ready for HIL
    NEEDS_INPUT = "needs_input"  # Agent needs help with required columns
    ERROR = "error"              # Mapping failed


class TransformationStatus(str, Enum):
    """Status of data transformation job (Phase 4)."""
    STARTED = "started"          # Job accepted, processing in background
    PROCESSING = "processing"    # Actively transforming rows
    COMPLETED = "completed"      # All rows processed successfully
    FAILED = "failed"            # Job failed (check error)
    PARTIAL = "partial"          # Some rows failed (rejection report available)


# =============================================================================
# Base Response Schema (ALL agents MUST extend this)
# =============================================================================

class AgentResponseBase(BaseModel):
    """
    Base response schema for all agents.

    Every agent response includes these fields for observability and tracing.
    Individual agents extend this with their specific fields.
    """
    success: bool = Field(
        description="Whether the operation succeeded"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request tracking ID for observability"
    )

    class Config:
        """Pydantic configuration for flexible validation."""
        extra = "allow"  # Allow extra fields for backward compatibility


# =============================================================================
# Debug Agent Sub-Models
# =============================================================================

class DebugRootCause(BaseModel):
    """Root cause analysis with confidence level."""
    cause: str = Field(description="Description of the potential cause")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level (0.0 - 1.0)"
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Evidence supporting this cause"
    )
    source: AnalysisSource = Field(
        default=AnalysisSource.INFERENCE,
        description="Source of the analysis"
    )


class DebugDocumentationLink(BaseModel):
    """Documentation link with relevance context."""
    title: str = Field(description="Document title")
    url: str = Field(description="Full URL to documentation")
    relevance: str = Field(description="Why this document is relevant")


class DebugSimilarPattern(BaseModel):
    """Similar error pattern from memory."""
    pattern_id: str = Field(description="Pattern identifier")
    similarity: float = Field(
        ge=0.0, le=1.0,
        description="Similarity score (0.0 - 1.0)"
    )
    resolution: str = Field(description="How this pattern was resolved")


# =============================================================================
# Schema Mapper Sub-Models (Phase 3)
# =============================================================================


class ColumnMapping(BaseModel):
    """
    Single column mapping proposal from SchemaMapper.

    Represents a semantic match between a source file column and
    a target PostgreSQL column with transformation and confidence.
    """
    source_column: str = Field(
        description="Column name as it appears in the source file"
    )
    target_column: str = Field(
        description="Target column name in pending_entry_items table"
    )
    transform: Optional[str] = Field(
        default=None,
        description="Transformation pipeline (e.g., 'TRIM|UPPERCASE', 'DATE_PARSE_PTBR')"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Match confidence score (0.0 - 1.0)"
    )
    reason: str = Field(
        default="",
        description="Explanation for the mapping decision"
    )


class MissingRequiredField(BaseModel):
    """
    Required target field that could not be auto-mapped.

    Used in 'needs_input' response to request user clarification.
    Part of the Smart Learning System - agent asks for help.
    """
    target_column: str = Field(
        description="Required PostgreSQL column name"
    )
    description: str = Field(
        description="Human-readable description of the field (pt-BR)"
    )
    suggested_source: Optional[str] = Field(
        default=None,
        description="Agent's best guess source column (if any)"
    )
    available_sources: List[str] = Field(
        default_factory=list,
        description="File columns that could potentially match"
    )


# =============================================================================
# DataTransformer Sub-Models (Phase 4)
# =============================================================================


class RejectionReason(BaseModel):
    """
    Enriched rejection with DebugAgent diagnosis.

    Part of the Nexo Immune System: every rejected row includes
    human-readable explanation and suggested fix from DebugAgent.
    """
    row_number: int = Field(
        description="Row number in source file (1-indexed)"
    )
    column: str = Field(
        description="Column where the error occurred"
    )
    original_value: str = Field(
        description="Original value that caused the rejection"
    )
    error_type: str = Field(
        description="Error classification (e.g., DateParseError, NumberParseError)"
    )
    human_explanation: str = Field(
        description="DebugAgent-enriched explanation in pt-BR"
    )
    suggested_fix: str = Field(
        description="Actionable fix suggestion in pt-BR"
    )


class JobNotification(BaseModel):
    """
    Notification for completed background job.

    Stored in AgentCore Memory for retrieval on next user message.
    Part of Fire-and-Forget pattern - natural conversation UX.
    """
    job_id: str = Field(
        description="Unique job identifier"
    )
    job_type: str = Field(
        default="transformation",
        description="Type of background job"
    )
    status: TransformationStatus = Field(
        description="Final job status"
    )
    rows_inserted: int = Field(
        default=0,
        description="Number of successfully inserted rows"
    )
    rows_rejected: int = Field(
        default=0,
        description="Number of rejected rows"
    )
    rejection_report_url: Optional[str] = Field(
        default=None,
        description="S3 presigned URL for rejection report download"
    )
    human_message: str = Field(
        description="User-friendly completion message in pt-BR"
    )
    created_at: str = Field(
        description="ISO-8601 timestamp when job completed"
    )


# =============================================================================
# Specialist Agent Responses
# =============================================================================

class ValidationResponse(AgentResponseBase):
    """Response from ValidationAgent."""
    is_valid: bool = Field(
        default=False,
        description="Whether validation passed"
    )
    validation_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Validation confidence score"
    )
    issues: List[str] = Field(
        default_factory=list,
        description="Validation issues found"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-blocking warnings"
    )


class EnrichmentResponse(AgentResponseBase):
    """Response from EnrichmentAgent."""
    enriched_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Enriched data payload"
    )
    sources_used: List[str] = Field(
        default_factory=list,
        description="Data sources consulted for enrichment"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Enrichment confidence score"
    )


class ComplianceResponse(AgentResponseBase):
    """Response from ComplianceAgent."""
    compliant: bool = Field(
        default=False,
        description="Whether operation is compliant"
    )
    violations: List[str] = Field(
        default_factory=list,
        description="Compliance violations found"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for compliance"
    )


class IntakeResponse(AgentResponseBase):
    """Response from IntakeAgent."""
    movement_id: Optional[str] = Field(
        default=None,
        description="Created movement ID"
    )
    items_processed: int = Field(
        default=0,
        description="Number of items processed"
    )
    items_failed: int = Field(
        default=0,
        description="Number of items that failed"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Processing details"
    )


class DebugAnalysisResponse(AgentResponseBase):
    """
    Response from DebugAgent.

    Contains enriched error analysis including root causes,
    debugging steps, documentation links, and similar patterns.
    """
    error_signature: str = Field(
        default="",
        description="Unique error signature for deduplication"
    )
    error_type: str = Field(
        default="Unknown",
        description="Classification of error type"
    )
    technical_explanation: str = Field(
        default="",
        description="Technical explanation in pt-BR"
    )
    root_causes: List[DebugRootCause] = Field(
        default_factory=list,
        description="Root cause analysis with confidence levels"
    )
    debugging_steps: List[str] = Field(
        default_factory=list,
        description="Step-by-step debugging instructions"
    )
    documentation_links: List[DebugDocumentationLink] = Field(
        default_factory=list,
        description="Relevant documentation links"
    )
    similar_patterns: List[DebugSimilarPattern] = Field(
        default_factory=list,
        description="Similar error patterns from memory"
    )
    recoverable: bool = Field(
        default=False,
        description="Whether the error is recoverable (retry may succeed)"
    )
    suggested_action: SuggestedAction = Field(
        default=SuggestedAction.INVESTIGATE,
        description="Suggested action for the user"
    )
    llm_powered: bool = Field(
        default=True,
        description="Whether AI (Gemini) was used for analysis"
    )


class LearningResponse(AgentResponseBase):
    """Response from LearningAgent."""
    pattern_learned: bool = Field(
        default=False,
        description="Whether a new pattern was learned"
    )
    pattern_id: Optional[str] = Field(
        default=None,
        description="ID of learned pattern"
    )
    confidence_improvement: float = Field(
        default=0.0,
        description="Confidence improvement delta"
    )


class ObservationResponse(AgentResponseBase):
    """Response from ObservationAgent."""
    observations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Generated observations"
    )
    insights: List[str] = Field(
        default_factory=list,
        description="Key insights discovered"
    )


class SchemaEvolutionResponse(AgentResponseBase):
    """Response from SchemaEvolutionAgent."""
    schema_change_proposed: bool = Field(
        default=False,
        description="Whether schema change is proposed"
    )
    proposed_columns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="New columns proposed"
    )
    migration_script: Optional[str] = Field(
        default=None,
        description="SQL migration script if applicable"
    )


class EquipmentResearchResponse(AgentResponseBase):
    """Response from EquipmentResearchAgent."""
    equipment_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Equipment details"
    )
    manufacturer: Optional[str] = Field(
        default=None,
        description="Manufacturer name"
    )
    specifications: Dict[str, Any] = Field(
        default_factory=dict,
        description="Technical specifications"
    )


class EstoqueControlResponse(AgentResponseBase):
    """Response from EstoqueControlAgent."""
    operation_type: Optional[OperationType] = Field(
        default=None,
        description="Type of stock operation"
    )
    quantity_affected: int = Field(
        default=0,
        description="Quantity changed"
    )
    new_balance: Optional[int] = Field(
        default=None,
        description="New stock balance"
    )
    location: Optional[str] = Field(
        default=None,
        description="Stock location"
    )


class DataImportResponse(AgentResponseBase):
    """Response from DataImportAgent (legacy import agent)."""
    rows_processed: int = Field(
        default=0,
        description="Number of rows processed"
    )
    rows_failed: int = Field(
        default=0,
        description="Number of rows that failed"
    )
    preview_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Preview of imported data"
    )
    column_mappings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detected column mappings"
    )


class SchemaMappingResponse(AgentResponseBase):
    """
    Response from SchemaMapper specialist agent (Phase 3).

    This response supports two primary modes:
    1. SUCCESS: Complete mapping proposal, ready for HIL confirmation
    2. NEEDS_INPUT: Agent needs help with required columns (Smart Learning)

    The agent NEVER proceeds without HIL - requires_confirmation is always True.
    """
    # Status determines response interpretation
    status: MappingStatus = Field(
        default=MappingStatus.SUCCESS,
        description="Mapping operation status (success, needs_input, error)"
    )

    # Session tracking
    session_id: str = Field(
        default="",
        description="Import session identifier"
    )
    target_table: str = Field(
        default="pending_entry_items",
        description="Target PostgreSQL table for mapping"
    )

    # Complete mappings (when status=success)
    mappings: List[ColumnMapping] = Field(
        default_factory=list,
        description="Column mapping proposals with confidence scores"
    )

    # Unmapped columns (transparent ignore)
    unmapped_source_columns: List[str] = Field(
        default_factory=list,
        description="Source columns that don't map to any target (will be ignored)"
    )

    # Missing required fields (when status=needs_input)
    missing_required_fields: List[MissingRequiredField] = Field(
        default_factory=list,
        description="Required target columns that could not be auto-mapped"
    )

    # Partial mappings (for needs_input - what was successfully mapped)
    partial_mappings: List[ColumnMapping] = Field(
        default_factory=list,
        description="Successfully mapped columns (before asking for help)"
    )

    # Confidence scoring
    overall_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Overall mapping confidence (average of all mappings)"
    )

    # HIL flag (ALWAYS True per CLAUDE.md)
    requires_confirmation: bool = Field(
        default=True,
        description="Whether HIL approval is required (always True for Phase 3)"
    )

    # Memory tracking
    memory_id: Optional[str] = Field(
        default=None,
        description="AgentCore Memory ID for the stored proposal"
    )
    patterns_used: List[str] = Field(
        default_factory=list,
        description="Prior patterns retrieved from memory that influenced mapping"
    )


class TransformationResult(AgentResponseBase):
    """
    Response from DataTransformer agent (Phase 4).

    Supports Fire-and-Forget pattern:
    - STARTED: Job accepted, processing in background (immediate return)
    - PROCESSING: Mid-execution status check
    - COMPLETED/PARTIAL/FAILED: Final status with full details

    Part of Nexo Immune System: all errors enriched by DebugAgent.
    """
    # Job tracking
    job_id: str = Field(
        description="Unique job identifier for status tracking"
    )
    session_id: str = Field(
        default="",
        description="Import session this job belongs to"
    )
    status: TransformationStatus = Field(
        default=TransformationStatus.STARTED,
        description="Current job status"
    )

    # Progress metrics
    rows_total: int = Field(
        default=0,
        description="Total rows in source file"
    )
    rows_processed: int = Field(
        default=0,
        description="Rows processed so far"
    )
    rows_inserted: int = Field(
        default=0,
        description="Rows successfully inserted to pending_entry_items"
    )
    rows_rejected: int = Field(
        default=0,
        description="Rows that failed transformation/validation"
    )

    # Strategy used (from Memory preferences)
    strategy_used: str = Field(
        default="LOG_AND_CONTINUE",
        description="Error handling strategy: STOP_ON_ERROR or LOG_AND_CONTINUE"
    )
    strategy_source: str = Field(
        default="system_default",
        description="Where strategy came from: memory, user_explicit, system_default"
    )

    # Rejection report (when status is PARTIAL or FAILED)
    rejection_report_url: Optional[str] = Field(
        default=None,
        description="S3 presigned URL for detailed rejection report download"
    )
    rejection_summary: List[RejectionReason] = Field(
        default_factory=list,
        description="First 10 rejections with DebugAgent enrichment (preview)"
    )

    # User-facing message
    human_message: str = Field(
        default="",
        description="User-friendly status message in pt-BR"
    )

    # Timing
    started_at: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp when job started"
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp when job completed"
    )

    # Debug enrichment (if FAILED or PARTIAL)
    debug_analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="DebugAgent analysis for pattern detection across rejections"
    )


# =============================================================================
# Orchestrator Responses
# =============================================================================

class OrchestratorResponse(AgentResponseBase):
    """Response from EstoqueOrchestrator."""
    action_taken: str = Field(
        default="",
        description="Action performed by orchestrator"
    )
    specialist_invoked: Optional[str] = Field(
        default=None,
        description="Specialist agent called"
    )
    result: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operation result payload"
    )
    requires_hil: bool = Field(
        default=False,
        description="Whether HIL approval is needed"
    )
    # AUDIT-002: Debug analysis from DebugHook error enrichment
    # This ensures debug_analysis is preserved through Strands serialization
    debug_analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Debug analysis from error enrichment (DebugHook)"
    )


class NexoImportResponse(AgentResponseBase):
    """
    Response from NexoImportOrchestrator.

    Handles the multi-stage NEXO import workflow.
    """
    import_session_id: str = Field(
        default="",
        description="Import session identifier"
    )
    stage: ImportStage = Field(
        default=ImportStage.ANALYSIS,
        description="Current import stage"
    )
    analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="File analysis result"
    )
    questions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Clarification questions for user"
    )
    column_mappings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Column mapping proposals"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Overall confidence score"
    )

    # AUDIT-002: Debug analysis from DebugHook error enrichment
    # This ensures debug_analysis is preserved through Strands serialization
    debug_analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Debug analysis from error enrichment (DebugHook)"
    )


# =============================================================================
# Swarm Agent Responses
# =============================================================================

class FileAnalystResponse(AgentResponseBase):
    """
    Response from Swarm FileAnalyst.

    SCHEMA-FIX: Expanded to match unified_analyze_file tool output.
    This ensures Strands structured_output validation works correctly.
    """
    # Original fields (basic analysis metadata)
    file_type: str = Field(
        default="unknown",
        description="Detected file type"
    )
    sheet_count: int = Field(
        default=1,
        description="Number of sheets (for Excel)"
    )
    total_rows: int = Field(
        default=0,
        description="Total data rows"
    )
    columns: List[str] = Field(
        default_factory=list,
        description="Column names detected"
    )
    recommended_strategy: str = Field(
        default="",
        description="Import strategy recommendation"
    )

    # SCHEMA-FIX: New fields to match unified_analyze_file output
    import_session_id: str = Field(
        default="",
        description="Import session identifier"
    )
    detected_file_type: str = Field(
        default="",
        description="Detected file type from analysis"
    )
    filename: str = Field(
        default="",
        description="Original filename"
    )
    analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Nested analysis object with sheets, columns, confidence"
    )
    column_mappings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Column mapping proposals"
    )
    questions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="HIL questions for user clarification"
    )
    overall_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Overall confidence score"
    )
    ready_for_import: bool = Field(
        default=False,
        description="Whether file is ready for import execution"
    )
    stop_action: bool = Field(
        default=False,
        description="Whether to stop and wait for user response"
    )
    session_state: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Session state for frontend storage"
    )
    reasoning_trace: Optional[List[str]] = Field(
        default=None,
        description="Agent reasoning trace for transparency"
    )
    analysis_round: int = Field(
        default=1,
        description="Current analysis round number"
    )
    pending_questions_count: int = Field(
        default=0,
        description="Number of pending HIL questions"
    )
    unmapped_questions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Questions for unmapped columns"
    )


class SchemaValidatorResponse(AgentResponseBase):
    """Response from Swarm SchemaValidator."""
    schema_valid: bool = Field(
        default=False,
        description="Whether schema matches expectations"
    )
    matched_columns: List[str] = Field(
        default_factory=list,
        description="Columns that matched schema"
    )
    unmatched_columns: List[str] = Field(
        default_factory=list,
        description="Columns that did not match"
    )
    type_mismatches: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Type mismatch details"
    )


class ImportExecutorResponse(AgentResponseBase):
    """Response from Swarm ImportExecutor."""
    rows_imported: int = Field(
        default=0,
        description="Successfully imported rows"
    )
    rows_failed: int = Field(
        default=0,
        description="Rows that failed to import"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Import errors encountered"
    )
    transaction_id: Optional[str] = Field(
        default=None,
        description="Database transaction ID"
    )


class MemoryAgentResponse(AgentResponseBase):
    """Response from Swarm MemoryAgent."""
    memories_retrieved: int = Field(
        default=0,
        description="Number of memories retrieved"
    )
    memories_stored: int = Field(
        default=0,
        description="Number of memories stored"
    )
    relevant_patterns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Relevant patterns found"
    )


class HILAgentResponse(AgentResponseBase):
    """Response from Swarm HILAgent (Human-in-the-Loop)."""
    approval_required: bool = Field(
        default=False,
        description="Whether human approval is required"
    )
    approval_reason: Optional[str] = Field(
        default=None,
        description="Why approval is needed"
    )
    confidence_level: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Agent's confidence level"
    )
    suggested_options: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Options for human to choose from"
    )


# =============================================================================
# Export All Models (for easy importing)
# =============================================================================

__all__ = [
    # Enums
    "SuggestedAction",
    "AnalysisSource",
    "OperationType",
    "ImportStage",
    "MappingStatus",  # Phase 3
    "TransformationStatus",  # Phase 4
    # Base
    "AgentResponseBase",
    # Debug sub-models
    "DebugRootCause",
    "DebugDocumentationLink",
    "DebugSimilarPattern",
    # Schema Mapper sub-models (Phase 3)
    "ColumnMapping",
    "MissingRequiredField",
    # DataTransformer sub-models (Phase 4)
    "RejectionReason",
    "JobNotification",
    # Specialist responses
    "ValidationResponse",
    "EnrichmentResponse",
    "ComplianceResponse",
    "IntakeResponse",
    "DebugAnalysisResponse",
    "LearningResponse",
    "ObservationResponse",
    "SchemaEvolutionResponse",
    "EquipmentResearchResponse",
    "EstoqueControlResponse",
    "DataImportResponse",
    "SchemaMappingResponse",  # Phase 3
    "TransformationResult",  # Phase 4
    # Orchestrator responses
    "OrchestratorResponse",
    "NexoImportResponse",
    # Swarm responses
    "FileAnalystResponse",
    "SchemaValidatorResponse",
    "ImportExecutorResponse",
    "MemoryAgentResponse",
    "HILAgentResponse",
]
