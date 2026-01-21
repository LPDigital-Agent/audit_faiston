"""
VisionAnalyzer Image Processing Tools

BUG-025 FIX: Pure Python utilities for document image processing.

Handles:
- S3 document loading
- PDF to image conversion
- Image metadata extraction

Note: PyMuPDF (fitz) is included in requirements.txt for PDF processing.
AgentCore Runtime packages dependencies automatically.
"""

import base64
import io
import logging
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Default S3 bucket for documents
DEFAULT_BUCKET = "faiston-one-sga-documents-prod"

# Maximum pages to process in a PDF
MAX_PDF_PAGES = 10

# DPI for PDF rendering (150 is good balance of quality vs size)
PDF_RENDER_DPI = 150


def load_document_from_s3(
    s3_key: str,
    bucket: str = DEFAULT_BUCKET,
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Load document (PDF/image) from S3 for vision analysis.

    Args:
        s3_key: S3 object key
        bucket: S3 bucket name

    Returns:
        Tuple of (document_bytes, metadata_dict)

    Raises:
        ValueError: If S3 object not found or access denied
    """
    try:
        s3 = boto3.client("s3")
        # NFC normalize S3 key to match upload encoding
        # Prevents NoSuchKey errors with Portuguese characters (Ç, Ã, Õ)
        normalized_key = unicodedata.normalize("NFC", s3_key)
        response = s3.get_object(Bucket=bucket, Key=normalized_key)

        content = response["Body"].read()
        metadata = {
            "content_type": response.get("ContentType", "application/octet-stream"),
            "content_length": response.get("ContentLength", len(content)),
            "last_modified": str(response.get("LastModified", "")),
            "s3_key": s3_key,
            "bucket": bucket,
        }

        logger.info(
            "[VisionAnalyzer] Loaded document from S3: %s (%d bytes)",
            s3_key,
            len(content),
        )
        return content, metadata

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "NoSuchKey":
            raise ValueError(f"Document not found in S3: {s3_key}") from e
        elif error_code in ("AccessDenied", "Forbidden"):
            raise ValueError(f"Access denied to S3 document: {s3_key}") from e
        else:
            raise ValueError(f"S3 error loading document: {error_code}") from e


def convert_pdf_to_images(
    pdf_bytes: bytes,
    max_pages: int = MAX_PDF_PAGES,
    dpi: int = PDF_RENDER_DPI,
) -> List[Dict[str, Any]]:
    """
    Convert PDF pages to images for vision analysis.

    Uses PyMuPDF (fitz) for high-quality PDF rendering.

    Args:
        pdf_bytes: PDF file content
        max_pages: Maximum pages to process (default 10)
        dpi: DPI for rendering (default 150)

    Returns:
        List of dicts with:
        - page_number: 1-indexed page number
        - image_base64: Base64-encoded PNG image
        - width: Image width in pixels
        - height: Image height in pixels

    Raises:
        ValueError: If PDF is invalid or cannot be processed
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("[VisionAnalyzer] PyMuPDF (fitz) not installed")
        raise ValueError("PyMuPDF (fitz) required for PDF processing")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []

        page_count = min(len(doc), max_pages)
        logger.info(
            "[VisionAnalyzer] Processing PDF: %d pages (max %d)",
            len(doc),
            max_pages,
        )

        for i in range(page_count):
            page = doc[i]
            # Render page to pixmap at specified DPI
            pix = page.get_pixmap(dpi=dpi)

            # Convert to PNG bytes and base64
            png_bytes = pix.tobytes("png")
            image_base64 = base64.b64encode(png_bytes).decode("utf-8")

            pages.append({
                "page_number": i + 1,
                "image_base64": image_base64,
                "width": pix.width,
                "height": pix.height,
            })

        doc.close()
        return pages

    except Exception as e:
        logger.error("[VisionAnalyzer] PDF processing failed: %s", e)
        raise ValueError(f"Failed to process PDF: {e}") from e


def get_image_metadata(image_bytes: bytes) -> Dict[str, Any]:
    """
    Extract metadata from an image file.

    Args:
        image_bytes: Image file content

    Returns:
        Dict with:
        - format: Image format (JPEG, PNG, etc.)
        - width: Image width
        - height: Image height
        - mode: Color mode (RGB, RGBA, etc.)
        - size_bytes: File size in bytes

    Raises:
        ValueError: If image cannot be processed
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))

        metadata = {
            "format": img.format or "unknown",
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "size_bytes": len(image_bytes),
        }

        # Get EXIF data if available
        exif = img.getexif()
        if exif:
            metadata["has_exif"] = True
            # Extract common EXIF fields
            exif_data = {}
            for tag_id, value in exif.items():
                try:
                    from PIL.ExifTags import TAGS
                    tag = TAGS.get(tag_id, str(tag_id))
                    # Only include string-serializable values
                    if isinstance(value, (str, int, float)):
                        exif_data[tag] = value
                except Exception:
                    pass
            if exif_data:
                metadata["exif"] = exif_data

        return metadata

    except Exception as e:
        logger.error("[VisionAnalyzer] Image metadata extraction failed: %s", e)
        raise ValueError(f"Failed to extract image metadata: {e}") from e


def is_pdf(content: bytes) -> bool:
    """
    Check if content is a PDF file.

    Args:
        content: File content bytes

    Returns:
        True if content starts with PDF magic bytes
    """
    return content[:4] == b"%PDF"


def is_image(content: bytes) -> bool:
    """
    Check if content is an image file (JPEG, PNG, GIF, WebP, TIFF).

    Args:
        content: File content bytes

    Returns:
        True if content matches known image signatures
    """
    # JPEG
    if content[:2] == b"\xff\xd8":
        return True
    # PNG
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    # GIF
    if content[:4] in (b"GIF8", b"GIF9"):
        return True
    # WebP
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return True
    # TIFF (little-endian and big-endian)
    if content[:4] in (b"II*\x00", b"MM\x00*"):
        return True
    return False


def prepare_for_vision_api(
    content: bytes,
    filename: str = "document",
) -> List[Dict[str, str]]:
    """
    Prepare document content for Gemini Vision API.

    Converts PDFs to images, validates image formats,
    and returns base64-encoded data ready for the API.

    Args:
        content: Document file content
        filename: Original filename (for logging)

    Returns:
        List of dicts with:
        - mime_type: MIME type string
        - data: Base64-encoded image data

    Raises:
        ValueError: If content type is unsupported
    """
    if is_pdf(content):
        # Convert PDF pages to images
        pages = convert_pdf_to_images(content)
        return [
            {
                "mime_type": "image/png",
                "data": page["image_base64"],
            }
            for page in pages
        ]

    elif is_image(content):
        # Determine MIME type
        if content[:2] == b"\xff\xd8":
            mime_type = "image/jpeg"
        elif content[:8] == b"\x89PNG\r\n\x1a\n":
            mime_type = "image/png"
        elif content[:4] in (b"GIF8", b"GIF9"):
            mime_type = "image/gif"
        elif content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            mime_type = "image/webp"
        else:
            mime_type = "image/tiff"

        return [
            {
                "mime_type": mime_type,
                "data": base64.b64encode(content).decode("utf-8"),
            }
        ]

    else:
        raise ValueError(
            f"Unsupported document type for {filename}. "
            "Expected PDF or image (JPEG, PNG, GIF, WebP, TIFF)."
        )
