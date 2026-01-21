"""
FileAnalyzer A2A Agent - BUG-025 Fix

This agent replaces the direct google.genai SDK usage in gemini_text_analyzer.py
with a Strands-compliant A2A agent using structured output via Pydantic.

Architecture:
- Uses Strands Agent with GeminiModel (gemini-2.5-pro with thinking)
- Exposes A2A Server for inter-agent communication
- Returns InventoryAnalysisResponse with Pydantic validation
- Eliminates JSON parsing issues that caused BUG-025
"""

from .schemas import (
    HILQuestionOption,
    HILQuestion,
    UnmappedQuestion,
    ColumnAnalysis,
    InventoryAnalysisResponse,
)

__all__ = [
    "HILQuestionOption",
    "HILQuestion",
    "UnmappedQuestion",
    "ColumnAnalysis",
    "InventoryAnalysisResponse",
]
