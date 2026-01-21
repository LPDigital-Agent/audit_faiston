"""
Pydantic Schemas for FileAnalyzer A2A Agent

BUG-025 FIX: These schemas enforce structured output via Strands,
eliminating the JSON parsing issues that caused questions to be lost.

Limits increased to leverage Gemini's 65,536 output token capacity:
- columns: 30 -> 100
- hil_questions: 10 -> 25
- unmapped_questions: 10 -> 25
- unmapped_columns: 15 -> 50
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any


class HILQuestionOption(BaseModel):
    """Option for a Human-in-the-Loop question."""

    value: str = Field(description="Option value (for backend processing)")
    label: str = Field(description="Option label (for UI display)")
    warning: bool = Field(default=False, description="If true, show warning when selected")
    recommended: bool = Field(default=False, description="If true, highlight as recommended")


class HILQuestion(BaseModel):
    """Human-in-the-Loop question for column mapping clarification."""

    id: str = Field(description="Unique question ID (e.g., q1, q2)")
    field: str = Field(description="Related column/field name")
    question: str = Field(max_length=300, description="Question text for user")
    options: List[HILQuestionOption] = Field(
        default_factory=list,
        max_length=6,
        description="Available options for answer",
    )
    reason: str = Field(max_length=200, description="Why this question is being asked")
    priority: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Question priority - high for blocking issues",
    )
    topic: Literal["column_mapping", "sheet_selection", "data_validation", "unmapped", "format"] = Field(
        default="column_mapping",
        description="Question category",
    )
    default_value: Optional[str] = Field(default=None, description="Pre-selected default option")


class UnmappedQuestion(BaseModel):
    """Question about columns that don't map to any DB schema field."""

    id: str = Field(description="Unique question ID")
    field: str = Field(description="Source column name that is unmapped")
    question: str = Field(max_length=300, description="Question about what to do with this column")
    options: List[HILQuestionOption] = Field(
        default_factory=list,
        max_length=4,
        description="Options: ignore, store in metadata, request DB update",
    )
    reason: str = Field(max_length=200, description="Why this column couldn't be mapped")
    suggested_action: Literal["ignore", "metadata", "request_db_update"] = Field(
        default="metadata",
        description="Recommended action for this unmapped column",
    )


class ColumnAnalysis(BaseModel):
    """Analysis result for a single column in the source file."""

    source_name: str = Field(description="Original column name from file")
    normalized_name: str = Field(description="Normalized/cleaned column name")
    suggested_mapping: Optional[str] = Field(
        default=None,
        description="Suggested target DB column name",
    )
    mapping_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the mapping (0.0-1.0)",
    )
    data_type: Literal["string", "number", "date", "boolean", "mixed", "unknown"] = Field(
        default="string",
        description="Detected data type",
    )
    sample_values: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Sample values from this column",
    )
    is_unmapped: bool = Field(
        default=False,
        description="True if column doesn't match any DB field",
    )
    null_count: Optional[int] = Field(default=None, description="Count of null/empty values")
    unique_count: Optional[int] = Field(default=None, description="Count of unique values")


class InventoryAnalysisResponse(BaseModel):
    """
    Structured output for file analysis - enforced by Strands.

    BUG-025 FIX: This Pydantic model ensures ALL fields are properly
    validated before returning to the caller. No more silent failures
    or truncated questions.

    Limits increased to leverage Gemini max output (65,536 tokens).
    Supports complex inventory files with many columns and questions.
    """

    # Status fields
    success: bool = Field(description="Whether analysis completed successfully")
    error: Optional[str] = Field(default=None, description="Error message if success=false")

    # File metadata
    file_type: Literal["csv", "xlsx", "xls", "pdf", "image", "unknown"] = Field(
        description="Detected file type",
    )
    filename: Optional[str] = Field(default=None, description="Original filename")
    s3_key: Optional[str] = Field(default=None, description="S3 object key")

    # Analysis metadata
    analysis_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence in the analysis",
    )
    analysis_round: int = Field(
        ge=1,
        default=1,
        description="Current analysis round (1 = initial, 2+ = with user responses)",
    )

    # Data statistics
    row_count: int = Field(ge=0, default=0, description="Number of data rows")
    column_count: int = Field(ge=0, default=0, description="Number of columns")

    # Column analysis - increased limit for large files
    columns: List[ColumnAnalysis] = Field(
        default_factory=list,
        max_length=100,  # Increased from 30
        description="Analysis of each column",
    )

    # Mapping results
    suggested_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of source column to target DB column",
    )
    unmapped_columns: List[str] = Field(
        default_factory=list,
        max_length=50,  # Increased from 15
        description="Columns that don't map to any DB field",
    )

    # HIL Questions - increased limits for complex analysis
    hil_questions: List[HILQuestion] = Field(
        default_factory=list,
        max_length=25,  # Increased from 10
        description="Questions requiring user input for mapping decisions",
    )
    unmapped_questions: List[UnmappedQuestion] = Field(
        default_factory=list,
        max_length=25,  # Increased from 10
        description="Questions about unmapped columns",
    )

    # Status flags
    all_questions_answered: bool = Field(
        default=False,
        description="True if all HIL questions have been answered",
    )
    ready_for_import: bool = Field(
        default=False,
        description="True if file is ready for import (all mappings resolved)",
    )
    recommended_action: Literal["ready_for_import", "needs_user_input", "error"] = Field(
        default="needs_user_input",
        description="What should happen next",
    )

    # Optional detailed data
    sample_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        max_length=20,
        description="Preview of first N rows for user review",
    )
    validation_warnings: Optional[List[str]] = Field(
        default=None,
        max_length=20,
        description="Non-blocking warnings about data quality",
    )

    # Debug/tracking fields
    # BUG-028 FIX: Renamed from _debug_partial_recovery (Pydantic v2 forbids leading underscores)
    debug_partial_recovery: bool = Field(
        default=False,
        description="True if response was recovered via json-repair",
    )

    class Config:
        """Pydantic configuration."""

        extra = "ignore"  # Ignore extra fields from LLM response
        validate_assignment = True  # Validate on field assignment
