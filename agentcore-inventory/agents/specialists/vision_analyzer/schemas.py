"""
VisionAnalyzer Pydantic Schemas - Maximum Scope

BUG-025 FIX: Comprehensive vision document analysis with Strands structured output.

Supports ALL types of inventory-related documents:
- NF-e (Brazilian tax invoices)
- Tables in images/PDFs
- OCR for general text extraction
- Equipment photos (identification)
- Labels and asset tags
- Romaneios/Packing lists

Using Pydantic models with Field constraints to leverage
Gemini's maximum output token capacity (65,536 tokens).
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Literal, Optional, Any

from pydantic import BaseModel, Field


# =============================================================================
# Table Extraction Models
# =============================================================================


class ExtractedTableCell(BaseModel):
    """A single cell extracted from a table."""

    row: int = Field(ge=0, description="Row index (0-based)")
    column: int = Field(ge=0, description="Column index (0-based)")
    value: str = Field(description="Cell text content")
    confidence: float = Field(ge=0.0, le=1.0, description="OCR confidence")


class ExtractedTable(BaseModel):
    """A table extracted from a document."""

    headers: List[str] = Field(max_length=50, description="Column headers")
    rows: List[List[str]] = Field(max_length=500, description="Data rows")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall extraction confidence")
    location: Optional[str] = Field(default=None, description="Location in document (e.g., 'page 1, top-left')")
    table_type: Optional[str] = Field(default=None, description="Type of table (e.g., 'inventory', 'pricing')")


# =============================================================================
# NF-e (Brazilian Tax Invoice) Models
# =============================================================================


class NFItem(BaseModel):
    """Item extracted from NF-e."""

    sequence: int = Field(ge=1, description="Item sequence number")
    description: str = Field(max_length=500, description="Item description")
    quantity: float = Field(ge=0, description="Quantity")
    unit: str = Field(max_length=10, description="Unit of measure (UN, PC, KG, etc.)")
    unit_price: float = Field(ge=0, description="Unit price in BRL")
    total_price: float = Field(ge=0, description="Total price for this item")
    ncm: Optional[str] = Field(default=None, max_length=10, description="NCM fiscal code")
    cfop: Optional[str] = Field(default=None, max_length=10, description="CFOP operation code")
    product_code: Optional[str] = Field(default=None, max_length=50, description="Product/Part number")


class NFData(BaseModel):
    """Complete data extracted from NF-e."""

    nf_number: str = Field(max_length=50, description="NF-e number")
    nf_series: Optional[str] = Field(default=None, max_length=10, description="NF-e series")
    emission_date: Optional[date] = Field(default=None, description="Emission date")
    supplier_name: str = Field(max_length=200, description="Supplier company name")
    supplier_cnpj: str = Field(max_length=20, description="Supplier CNPJ")
    buyer_name: Optional[str] = Field(default=None, max_length=200, description="Buyer company name")
    buyer_cnpj: Optional[str] = Field(default=None, max_length=20, description="Buyer CNPJ")
    items: List[NFItem] = Field(max_length=100, description="List of NF items")
    total_value: float = Field(ge=0, description="Total NF value")
    icms: Optional[float] = Field(default=None, description="ICMS tax value")
    ipi: Optional[float] = Field(default=None, description="IPI tax value")
    access_key: Optional[str] = Field(default=None, max_length=50, description="44-digit access key")


# =============================================================================
# Equipment Identification Models
# =============================================================================


class EquipmentIdentification(BaseModel):
    """Equipment identified from photo."""

    manufacturer: Optional[str] = Field(default=None, max_length=100, description="Manufacturer name")
    model: Optional[str] = Field(default=None, max_length=100, description="Model number/name")
    part_number: Optional[str] = Field(default=None, max_length=100, description="Part number")
    serial_number: Optional[str] = Field(default=None, max_length=100, description="Serial number")
    asset_tag: Optional[str] = Field(default=None, max_length=50, description="Asset tag")
    condition: Literal["new", "used", "refurbished", "damaged", "unknown"] = Field(
        default="unknown", description="Equipment condition"
    )
    visible_labels: List[str] = Field(default_factory=list, max_length=20, description="Visible text labels")
    equipment_type: Optional[str] = Field(default=None, max_length=50, description="Type of equipment")
    confidence: float = Field(ge=0.0, le=1.0, description="Identification confidence")


# =============================================================================
# OCR Models
# =============================================================================


class OCRResult(BaseModel):
    """General OCR result."""

    full_text: str = Field(description="Complete extracted text")
    structured_data: Dict[str, Any] = Field(
        default_factory=dict, description="Structured key-value pairs extracted"
    )
    detected_language: str = Field(default="pt-BR", description="Detected language")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall OCR confidence")


# =============================================================================
# HIL Question Models (for Vision Analysis)
# =============================================================================


class VisionHILQuestionOption(BaseModel):
    """Option for a vision analysis HIL question."""

    value: str = Field(description="Option value for backend")
    label: str = Field(description="Option label for UI")
    warning: bool = Field(default=False, description="Show warning indicator")
    recommended: bool = Field(default=False, description="Mark as recommended option")


class VisionHILQuestion(BaseModel):
    """HIL question for vision analysis clarification."""

    id: str = Field(description="Unique question ID")
    question: str = Field(max_length=300, description="Question text")
    options: List[VisionHILQuestionOption] = Field(max_length=5, description="Available options")
    reason: str = Field(max_length=200, description="Why this question is needed")
    field: Optional[str] = Field(default=None, description="Related field/area")
    priority: Literal["high", "medium", "low"] = Field(default="medium", description="Question priority")


# =============================================================================
# Main Response Model
# =============================================================================


class VisionAnalysisResponse(BaseModel):
    """
    Structured output for vision analysis - MAXIMUM SCOPE.

    Supports all types of inventory-related documents.
    Uses Strands structured_output_model for Pydantic enforcement.

    BUG-025 FIX: Comprehensive vision agent for:
    - NF-e (Brazilian tax invoices)
    - Tables in images/PDFs
    - OCR text extraction
    - Equipment photos
    - Labels and asset tags
    - Romaneios/Packing lists
    """

    success: bool = Field(description="Whether analysis succeeded")
    document_type: Literal[
        "nf-e",
        "invoice",
        "table",
        "equipment_photo",
        "label",
        "packing_list",
        "report",
        "unknown",
    ] = Field(description="Detected document type")
    file_type: Literal["pdf", "image", "multi-page-pdf"] = Field(description="Input file type")
    page_count: int = Field(ge=1, default=1, description="Number of pages processed")
    analysis_confidence: float = Field(ge=0.0, le=1.0, description="Overall analysis confidence")

    # Type-specific results (only one is populated per response)
    nf_data: Optional[NFData] = Field(default=None, description="NF-e extraction result")
    extracted_tables: Optional[List[ExtractedTable]] = Field(
        default=None, max_length=20, description="Extracted tables"
    )
    equipment_info: Optional[EquipmentIdentification] = Field(
        default=None, description="Equipment identification result"
    )
    ocr_result: Optional[OCRResult] = Field(default=None, description="OCR extraction result")

    # Common fields
    warnings: List[str] = Field(default_factory=list, max_length=20, description="Analysis warnings")
    hil_questions: List[VisionHILQuestion] = Field(
        default_factory=list, max_length=10, description="Questions for user clarification"
    )
    needs_human_review: bool = Field(default=False, description="Flag if human review recommended")
    recommended_action: Literal["auto_import", "needs_review", "needs_correction", "reject"] = Field(
        default="needs_review", description="Recommended next action"
    )

    # Metadata
    processing_time_ms: Optional[int] = Field(default=None, description="Processing time in milliseconds")
    raw_text_preview: Optional[str] = Field(
        default=None, max_length=500, description="Preview of raw extracted text"
    )
