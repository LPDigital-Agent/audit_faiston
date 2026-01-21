"""
VisionAnalyzer A2A Agent - Maximum Scope Vision Document Analysis

BUG-025 FIX: Strands Agent for comprehensive document vision analysis.

Supports ALL types of inventory-related documents:
- NF-e (Brazilian tax invoices)
- Tables in images/PDFs
- OCR for general text extraction
- Equipment photos (identification)
- Labels and asset tags
- Romaneios/Packing lists

Uses:
- Strands Agent Framework with GeminiModel
- Pydantic structured output (VisionAnalysisResponse)
- A2A Protocol for inter-agent communication
- AgentCore Runtime deployment
"""

from .schemas import (
    VisionAnalysisResponse,
    NFData,
    NFItem,
    ExtractedTable,
    ExtractedTableCell,
    EquipmentIdentification,
    OCRResult,
    VisionHILQuestion,
    VisionHILQuestionOption,
)

__all__ = [
    "VisionAnalysisResponse",
    "NFData",
    "NFItem",
    "ExtractedTable",
    "ExtractedTableCell",
    "EquipmentIdentification",
    "OCRResult",
    "VisionHILQuestion",
    "VisionHILQuestionOption",
]
