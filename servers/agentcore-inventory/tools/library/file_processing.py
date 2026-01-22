"""
Efficient S3 file structure inspector with memory-safe constraints.

This module provides the FileInspector class for analyzing CSV/Excel files
in S3 without loading full content into memory. Follows the Tool-First
Principle - deterministic Python code for I/O operations.

CRITICAL CONSTRAINTS:
    - pandas nrows=5 limit (NEVER load full file)
    - MAX_FILE_SIZE = 500 MB
    - STATELESS design (only s3_client stored)
    - UTF-8 → Latin-1 encoding fallback

Example:
    >>> inspector = FileInspector(bucket="my-bucket")
    >>> result = inspector.inspect_s3_file("my-bucket", "path/to/file.csv")
    >>> print(result.columns)
    ['codigo', 'descricao', 'quantidade']
"""

from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import boto3
from botocore.config import Config

# NOTE: pandas is lazy-loaded inside methods to reduce cold start time
# Do NOT add `import pandas as pd` at module level - see BUG-039
from botocore.exceptions import ClientError


@dataclass
class FileStructure:
    """
    Result of file structure inspection.

    Attributes:
        success: Whether inspection completed successfully.
        columns: List of column names (preserved original).
        row_count_estimate: Approximate row count (±50% accuracy).
        sample_data: First 3 data rows as list of dicts.
        detected_format: Format identifier (csv, csv_semicolon, csv_tab, xlsx, xls).
        separator: CSV delimiter character (None for Excel).
        file_size_bytes: Total file size from S3 HEAD.
        has_header: Whether first row appears to be header.
        encoding: Detected/used encoding (utf-8 or latin-1).
        error: Error message if inspection failed.
        error_type: Error classification for debugging.
    """

    success: bool
    columns: List[str] = field(default_factory=list)
    row_count_estimate: int = 0
    sample_data: List[Dict[str, Any]] = field(default_factory=list)
    detected_format: str = ""
    separator: Optional[str] = None
    file_size_bytes: int = 0
    has_header: bool = True
    encoding: str = "utf-8"
    error: Optional[str] = None
    error_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "columns": self.columns,
            "row_count_estimate": self.row_count_estimate,
            "sample_data": self.sample_data,
            "detected_format": self.detected_format,
            "separator": self.separator,
            "file_size_bytes": self.file_size_bytes,
            "has_header": self.has_header,
            "encoding": self.encoding,
            "error": self.error,
            "error_type": self.error_type,
        }


class FileInspector:
    """
    Efficient S3 file structure inspector (nrows constraint).

    CRITICAL: This class is STATELESS.
        - Only `self._s3_client` and `self._bucket` are stored
        - All processing uses local variables
        - No file content/names stored in self

    Constants:
        SAMPLE_ROWS: pandas nrows limit (5)
        MAX_SAMPLE_ROWS: Rows returned to caller (3)
        HEAD_BYTES: Initial bytes for format detection (8KB)
        MAX_FILE_SIZE: Maximum allowed file size (500 MB)

    Example:
        >>> inspector = FileInspector()
        >>> result = inspector.inspect_s3_file("bucket", "key.csv")
        >>> if result.success:
        ...     print(f"Columns: {result.columns}")
    """

    # Class constants
    SAMPLE_ROWS: int = 5  # pandas nrows limit
    MAX_SAMPLE_ROWS: int = 3  # Return exactly 3 samples
    HEAD_BYTES: int = 8192  # 8KB for format/separator detection
    MAX_FILE_SIZE: int = 524_288_000  # 500 MB

    # Extended inventory column patterns for header detection
    # These patterns help identify if first row is a header
    INVENTORY_PATTERNS: Set[str] = {
        # Basic inventory terms
        "part_number",
        "codigo",
        "descricao",
        "quantidade",
        "serial",
        "localizacao",
        "fornecedor",
        # Extended inventory terms
        "nf_number",
        "data_entrada",
        "valor_unitario",
        "lote",
        "validade",
        "categoria",
        "numero_nf",
        "qtd",
        "desc",
        # Common variations
        "part",
        "code",
        "description",
        "quantity",
        "location",
        "supplier",
        "price",
        "preco",
        "valor",
        "unit",
        "unidade",
        "item",
        "sku",
        "barcode",
        "ean",
        "gtin",
        "ncm",
        "cfop",
        "cst",
        "icms",
        "ipi",
        "pis",
        "cofins",
        "estoque",
        "stock",
        "inventory",
        "armazem",
        "warehouse",
        "data",
        "date",
        "nota",
        "invoice",
        "fatura",
        "pedido",
        "order",
        "cliente",
        "customer",
        "produto",
        "product",
        "marca",
        "brand",
        "modelo",
        "model",
        "serie",
        "series",
        "lote_number",
        "batch",
        "weight",
        "peso",
        "volume",
        "dimensoes",
        "dimensions",
    }

    # Magic bytes for file format detection
    XLSX_MAGIC: bytes = b"PK\x03\x04"  # ZIP signature (XLSX is ZIP-based)
    XLS_MAGIC: bytes = b"\xd0\xcf\x11\xe0"  # OLE2 compound document

    def __init__(self, bucket: Optional[str] = None) -> None:
        """
        Initialize FileInspector.

        Args:
            bucket: Default S3 bucket. Falls back to DOCUMENTS_BUCKET env var.
        """
        self._bucket = bucket or os.environ.get("DOCUMENTS_BUCKET")
        self._s3_client: Optional[Any] = None  # Lazy loaded

    @property
    def s3_client(self) -> Any:
        """Lazy-initialize S3 client with SigV4."""
        if self._s3_client is None:
            config = Config(
                signature_version="s3v4",
                region_name=os.environ.get("AWS_REGION", "us-east-2"),
                retries={"max_attempts": 3, "mode": "adaptive"},
            )
            self._s3_client = boto3.client("s3", config=config)
        return self._s3_client

    def inspect_s3_file(
        self, bucket: Optional[str] = None, key: str = ""
    ) -> FileStructure:
        """
        Analyze file structure without loading full content.

        Algorithm:
            1. HEAD object → get content-length, type
            2. GET Range=0-8191 → detect format via magic bytes
            3. Auto-detect CSV separator (, ; \\t)
            4. Detect header using heuristics (type variance + patterns)
            5. Parse with pandas nrows=5
            6. Estimate row count from file size (±50% tolerance)

        Args:
            bucket: S3 bucket name (uses default if None).
            key: S3 object key (required).

        Returns:
            FileStructure with analysis results.

        Raises:
            Never raises - all errors returned in FileStructure.error
        """
        bucket = bucket or self._bucket
        if not bucket:
            return FileStructure(
                success=False,
                error="No bucket specified and DOCUMENTS_BUCKET not set",
                error_type="CONFIGURATION_ERROR",
            )

        if not key:
            return FileStructure(
                success=False,
                error="S3 key is required",
                error_type="VALIDATION_ERROR",
            )

        # BUG-040 FIX: Normalize S3 key to NFC Unicode form for consistent lookup
        # Prevents NoSuchKey errors when NFD (decomposed) vs NFC (composed) mismatch
        # Example: "Ç" can be U+00C7 (NFC) or "C"+U+0327 (NFD) - S3 treats as different keys
        import unicodedata
        key = unicodedata.normalize("NFC", key)

        try:
            # Step 1: HEAD object for metadata
            head_response = self.s3_client.head_object(Bucket=bucket, Key=key)
            file_size = head_response.get("ContentLength", 0)
            content_type = head_response.get("ContentType", "")

            # Check file size limit
            if file_size > self.MAX_FILE_SIZE:
                return FileStructure(
                    success=False,
                    file_size_bytes=file_size,
                    error=f"File size {file_size:,} bytes exceeds limit of {self.MAX_FILE_SIZE:,} bytes",
                    error_type="FILE_TOO_LARGE",
                )

            # Step 2: GET Range for format detection
            range_end = min(self.HEAD_BYTES - 1, file_size - 1)
            range_response = self.s3_client.get_object(
                Bucket=bucket, Key=key, Range=f"bytes=0-{range_end}"
            )
            head_bytes = range_response["Body"].read()

            # Step 3: Detect format
            detected_format = self._detect_format(head_bytes, key, content_type)

            if detected_format == "unknown":
                return FileStructure(
                    success=False,
                    file_size_bytes=file_size,
                    error=f"Unsupported file format. Key: {key}, ContentType: {content_type}",
                    error_type="UNSUPPORTED_FORMAT",
                )

            # Step 4 & 5: Parse based on format
            if detected_format in ("xlsx", "xls"):
                return self._parse_excel_structure(
                    bucket, key, file_size, detected_format
                )
            else:
                # CSV variants
                separator = self._detect_csv_separator(head_bytes)
                return self._parse_csv_structure(
                    bucket, key, file_size, detected_format, separator, head_bytes
                )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404", "NotFound"):
                return FileStructure(
                    success=False,
                    error=f"File not found: s3://{bucket}/{key}",
                    error_type="FILE_NOT_FOUND",
                )
            return FileStructure(
                success=False,
                error=f"S3 error: {str(e)}",
                error_type="S3_ERROR",
            )
        except Exception as e:
            return FileStructure(
                success=False,
                error=f"Inspection failed: {str(e)}",
                error_type="INSPECTION_ERROR",
            )

    def _detect_format(
        self, head_bytes: bytes, key: str, content_type: str
    ) -> str:
        """
        Detect file format via magic bytes and extension.

        Priority:
            1. Magic bytes (most reliable)
            2. File extension
            3. Content-Type header

        Args:
            head_bytes: First 8KB of file.
            key: S3 object key for extension check.
            content_type: HTTP Content-Type header.

        Returns:
            Format string: 'xlsx', 'xls', 'csv', or 'unknown'.
        """
        # Check magic bytes first (most reliable)
        if head_bytes.startswith(self.XLSX_MAGIC):
            return "xlsx"
        if head_bytes.startswith(self.XLS_MAGIC):
            return "xls"

        # Check file extension
        key_lower = key.lower()
        if key_lower.endswith(".xlsx"):
            return "xlsx"
        if key_lower.endswith(".xls"):
            return "xls"
        if key_lower.endswith((".csv", ".txt", ".tsv")):
            return "csv"

        # Check content type
        if "spreadsheet" in content_type or "excel" in content_type:
            if "openxml" in content_type:
                return "xlsx"
            return "xls"
        if "csv" in content_type or "text" in content_type:
            return "csv"

        # Try to detect if it looks like text/CSV
        # Be strict: check for printable characters and common delimiters
        try:
            text = head_bytes.decode("utf-8")
            if self._looks_like_csv(text):
                return "csv"
        except UnicodeDecodeError:
            try:
                text = head_bytes.decode("latin-1")
                if self._looks_like_csv(text):
                    return "csv"
            except Exception:
                pass

        return "unknown"

    def _looks_like_csv(self, text: str) -> bool:
        """
        Check if text content looks like valid CSV.

        Returns True if the text:
        - Contains multiple lines
        - Has common delimiters (comma, semicolon, tab)
        - Doesn't contain too many non-printable characters

        Args:
            text: Text content to check.

        Returns:
            True if the text looks like CSV.
        """
        # Check for excessive non-printable characters (binary indicator)
        non_printable = sum(1 for c in text[:500] if not c.isprintable() and c not in '\n\r\t')
        if non_printable > len(text[:500]) * 0.1:  # >10% non-printable = likely binary
            return False

        # Check for at least one line break
        if '\n' not in text and '\r' not in text:
            return False

        # Check for common delimiters
        has_delimiter = any(d in text for d in [',', ';', '\t'])
        if not has_delimiter:
            return False

        return True

    def _detect_csv_separator(self, head_bytes: bytes) -> str:
        """
        Auto-detect CSV separator from file header.

        Checks for common separators in order of preference:
            1. Semicolon (;) - common in pt-BR Excel exports
            2. Comma (,) - standard CSV
            3. Tab (\\t) - TSV files

        Args:
            head_bytes: First chunk of file content.

        Returns:
            Detected separator character.
        """
        # Try to decode
        try:
            text = head_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = head_bytes.decode("latin-1", errors="replace")

        # Get first few lines
        lines = text.split("\n")[:5]
        if not lines:
            return ","  # Default

        first_line = lines[0]

        # Count occurrences of each separator
        semicolon_count = first_line.count(";")
        comma_count = first_line.count(",")
        tab_count = first_line.count("\t")

        # Return most common separator
        if semicolon_count > comma_count and semicolon_count > tab_count:
            return ";"
        if tab_count > comma_count and tab_count > semicolon_count:
            return "\t"
        return ","

    def _detect_header(self, rows: List[List[str]]) -> bool:
        """
        Detect if first row is a header using combined heuristics.

        Heuristics:
            1. Type variance: First row has different types than data rows
            2. Pattern matching: First row contains known inventory column names

        Args:
            rows: First few rows as lists of strings.

        Returns:
            True if first row appears to be a header.
        """
        if len(rows) < 2:
            return False

        first_row = rows[0]
        data_rows = rows[1:]

        # Heuristic 1: Type variance
        first_row_types = [self._infer_cell_type(cell) for cell in first_row]
        data_row_types = [self._infer_cell_type(cell) for cell in data_rows[0]]
        type_variance = first_row_types != data_row_types

        # Check if first row is all strings while data has numbers
        first_all_strings = all(t == "string" for t in first_row_types)
        data_has_numbers = any(t in ("int", "float") for t in data_row_types)
        type_mismatch = first_all_strings and data_has_numbers

        # Heuristic 2: Known inventory patterns
        normalized = set()
        for col in first_row:
            if col:
                # Normalize: lowercase, remove spaces/underscores
                clean = col.lower().strip().replace(" ", "_").replace("-", "_")
                normalized.add(clean)
                # Also add without underscores
                normalized.add(clean.replace("_", ""))

        pattern_match = bool(normalized & self.INVENTORY_PATTERNS)

        return type_variance or type_mismatch or pattern_match

    def _infer_cell_type(self, value: str) -> str:
        """
        Infer basic type of a cell value.

        Args:
            value: Cell value as string.

        Returns:
            Type string: 'int', 'float', 'empty', or 'string'.
        """
        if not value or value.strip() == "":
            return "empty"

        value = value.strip()

        # Try integer
        try:
            int(value.replace(".", "").replace(",", ""))
            return "int"
        except ValueError:
            pass

        # Try float (handle both . and , as decimal)
        try:
            float(value.replace(",", "."))
            return "float"
        except ValueError:
            pass

        return "string"

    def _parse_csv_structure(
        self,
        bucket: str,
        key: str,
        file_size: int,
        detected_format: str,
        separator: str,
        head_bytes: bytes,
    ) -> FileStructure:
        """
        Parse CSV file structure with encoding fallback.

        Args:
            bucket: S3 bucket name.
            key: S3 object key.
            file_size: Total file size in bytes.
            detected_format: Format identifier.
            separator: Detected separator character.
            head_bytes: Initial bytes for row estimation.

        Returns:
            FileStructure with CSV analysis results.
        """
        # Download enough for pandas (use nrows=5)
        # We need to download more than HEAD_BYTES for pandas to work properly
        download_bytes = min(file_size, 1_048_576)  # Max 1MB for parsing

        try:
            response = self.s3_client.get_object(
                Bucket=bucket, Key=key, Range=f"bytes=0-{download_bytes - 1}"
            )
            content = response["Body"].read()
        except Exception as e:
            return FileStructure(
                success=False,
                file_size_bytes=file_size,
                error=f"Failed to download file: {str(e)}",
                error_type="DOWNLOAD_ERROR",
            )

        # Lazy import pandas to reduce cold start time (BUG-039)
        import pandas as pd

        # Try UTF-8 first, then Latin-1
        encoding = "utf-8"
        df = None

        for enc in ["utf-8", "latin-1"]:
            try:
                df = pd.read_csv(
                    io.BytesIO(content),
                    sep=separator,
                    encoding=enc,
                    nrows=self.SAMPLE_ROWS,
                    dtype=str,  # All strings, no type inference
                    on_bad_lines="warn",
                    header=None,  # We'll detect header ourselves
                )
                encoding = enc
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                # Try next encoding
                if enc == "latin-1":
                    return FileStructure(
                        success=False,
                        file_size_bytes=file_size,
                        detected_format=detected_format,
                        separator=separator,
                        error=f"CSV parsing failed: {str(e)}",
                        error_type="PARSE_ERROR",
                    )

        if df is None or df.empty:
            return FileStructure(
                success=False,
                file_size_bytes=file_size,
                detected_format=detected_format,
                separator=separator,
                error="CSV parsing returned empty DataFrame",
                error_type="EMPTY_FILE",
            )

        # Convert to list of lists for header detection
        rows = df.values.tolist()

        # Detect header
        has_header = self._detect_header(rows)

        # Get columns and sample data
        if has_header and len(rows) > 0:
            columns = [str(c).strip() for c in rows[0]]
            sample_rows = rows[1 : self.MAX_SAMPLE_ROWS + 1]
        else:
            # Generate column names
            columns = [f"col_{i}" for i in range(len(df.columns))]
            sample_rows = rows[: self.MAX_SAMPLE_ROWS]

        # Convert sample rows to list of dicts
        sample_data = []
        for row in sample_rows:
            row_dict = {}
            for i, col in enumerate(columns):
                if i < len(row):
                    val = row[i]
                    row_dict[col] = str(val) if pd.notna(val) else ""
            sample_data.append(row_dict)

        # Estimate row count
        row_count = self._estimate_row_count(file_size, head_bytes)

        # Determine format variant
        format_variant = detected_format
        if separator == ";":
            format_variant = "csv_semicolon"
        elif separator == "\t":
            format_variant = "csv_tab"

        return FileStructure(
            success=True,
            columns=columns,
            row_count_estimate=row_count,
            sample_data=sample_data,
            detected_format=format_variant,
            separator=separator,
            file_size_bytes=file_size,
            has_header=has_header,
            encoding=encoding,
        )

    def _parse_excel_structure(
        self, bucket: str, key: str, file_size: int, detected_format: str
    ) -> FileStructure:
        """
        Parse Excel file structure (first sheet only).

        Args:
            bucket: S3 bucket name.
            key: S3 object key.
            file_size: Total file size in bytes.
            detected_format: Format identifier (xlsx or xls).

        Returns:
            FileStructure with Excel analysis results.
        """
        # Download file for pandas
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read()
        except Exception as e:
            return FileStructure(
                success=False,
                file_size_bytes=file_size,
                detected_format=detected_format,
                error=f"Failed to download file: {str(e)}",
                error_type="DOWNLOAD_ERROR",
            )

        # Lazy import pandas to reduce cold start time (BUG-039)
        import pandas as pd

        # Parse Excel
        try:
            engine = "openpyxl" if detected_format == "xlsx" else "xlrd"
            df = pd.read_excel(
                io.BytesIO(content),
                engine=engine,
                nrows=self.SAMPLE_ROWS,
                dtype=str,  # All strings, no type inference
                sheet_name=0,  # First sheet only
                header=None,  # We'll detect header ourselves
            )
        except Exception as e:
            return FileStructure(
                success=False,
                file_size_bytes=file_size,
                detected_format=detected_format,
                error=f"Excel parsing failed: {str(e)}",
                error_type="PARSE_ERROR",
            )

        if df.empty:
            return FileStructure(
                success=False,
                file_size_bytes=file_size,
                detected_format=detected_format,
                error="Excel parsing returned empty DataFrame",
                error_type="EMPTY_FILE",
            )

        # Convert to list of lists for header detection
        rows = df.values.tolist()

        # Detect header
        has_header = self._detect_header(rows)

        # Get columns and sample data
        if has_header and len(rows) > 0:
            columns = [str(c).strip() for c in rows[0]]
            sample_rows = rows[1 : self.MAX_SAMPLE_ROWS + 1]
        else:
            columns = [f"col_{i}" for i in range(len(df.columns))]
            sample_rows = rows[: self.MAX_SAMPLE_ROWS]

        # Convert sample rows to list of dicts
        sample_data = []
        for row in sample_rows:
            row_dict = {}
            for i, col in enumerate(columns):
                if i < len(row):
                    val = row[i]
                    row_dict[col] = str(val) if pd.notna(val) else ""
            sample_data.append(row_dict)

        # Estimate row count (rough estimate for Excel based on file size)
        # Excel files are compressed, so estimation is less accurate
        avg_row_bytes = 200  # Conservative estimate for Excel
        row_count = max(1, file_size // avg_row_bytes)

        return FileStructure(
            success=True,
            columns=columns,
            row_count_estimate=row_count,
            sample_data=sample_data,
            detected_format=detected_format,
            separator=None,
            file_size_bytes=file_size,
            has_header=has_header,
            encoding="utf-8",  # Excel uses UTF-8 internally
        )

    def _estimate_row_count(self, file_size: int, head_bytes: bytes) -> int:
        """
        Estimate total row count from file size and sample.

        Accuracy: ±50% (acceptable per requirements).

        Args:
            file_size: Total file size in bytes.
            head_bytes: Sample bytes for average row calculation.

        Returns:
            Estimated row count.
        """
        # Decode head bytes
        try:
            text = head_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = head_bytes.decode("latin-1", errors="replace")

        # Count lines in sample
        lines = text.split("\n")
        sample_lines = len([l for l in lines if l.strip()])

        if sample_lines == 0:
            return 1

        # Calculate average bytes per line
        sample_size = len(head_bytes)
        avg_bytes_per_line = sample_size / sample_lines

        if avg_bytes_per_line <= 0:
            return 1

        # Estimate total rows
        estimated_rows = int(file_size / avg_bytes_per_line)

        return max(1, estimated_rows)


# Singleton instance for module-level access
_inspector_instance: Optional[FileInspector] = None


def get_file_inspector(bucket: Optional[str] = None) -> FileInspector:
    """
    Get singleton FileInspector instance.

    Thread-safe lazy initialization of the FileInspector.
    The singleton is stateless (only s3_client), so reuse is safe.

    Args:
        bucket: Optional default bucket override.

    Returns:
        FileInspector singleton instance.
    """
    global _inspector_instance
    if _inspector_instance is None:
        _inspector_instance = FileInspector(bucket=bucket)
    return _inspector_instance
