"""
VisionAnalyzer Tools - Document Processing Utilities

BUG-025 FIX: Pure Python tools for document processing.

These tools are used by the VisionAnalyzer Strands Agent:
- image_processor: S3 loading, PDF to images conversion
- ocr_helpers: Text preprocessing and extraction
- nf_parser: Brazilian NF-e specific parsing rules
"""

from .image_processor import (
    load_document_from_s3,
    convert_pdf_to_images,
    get_image_metadata,
)
from .nf_parser import (
    validate_cnpj,
    validate_access_key,
    parse_brazilian_date,
    parse_brazilian_currency,
)

__all__ = [
    # Image processing
    "load_document_from_s3",
    "convert_pdf_to_images",
    "get_image_metadata",
    # NF-e parsing
    "validate_cnpj",
    "validate_access_key",
    "parse_brazilian_date",
    "parse_brazilian_currency",
]
