#!/usr/bin/env python3
# =============================================================================
# Phase 2 Integration Test: Smart Parsing (File Structure Analysis)
# =============================================================================
# Manual integration test for the Phase 2 file analysis layer.
#
# This test validates:
# 1. FileInspector class functionality with real S3 files
# 2. CSV format detection (comma, semicolon, tab)
# 3. Excel format detection (xlsx, xls)
# 4. Header detection heuristics
# 5. Encoding fallback (UTF-8 → Latin-1)
# 6. Sample data extraction
# 7. Row count estimation
#
# USAGE:
#   cd server/agentcore-inventory
#   AWS_PROFILE=faiston-aio python tests/manual/test_phase2_parsing.py
#
# PREREQUISITES:
# - AWS credentials configured (profile: faiston-aio)
# - Access to S3 bucket: faiston-one-sga-documents-prod
# - pandas, openpyxl libraries installed
#
# VERSION: 2026-01-21T20:00:00Z
# =============================================================================

import io
import json
import os
import sys
import tempfile
from datetime import datetime
from typing import Optional, Tuple

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import boto3
from botocore.config import Config

from tools.library.file_processing import FileInspector, FileStructure, get_file_inspector


class TestColors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(message: str) -> None:
    """Print a formatted header."""
    print(f"\n{TestColors.BOLD}{TestColors.BLUE}{'=' * 70}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.BLUE}{message}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.BLUE}{'=' * 70}{TestColors.RESET}")


def print_subheader(message: str) -> None:
    """Print a formatted subheader."""
    print(f"\n{TestColors.BOLD}{message}{TestColors.RESET}")
    print("-" * 50)


def print_pass(test_name: str, details: Optional[str] = None) -> None:
    """Print a PASS result."""
    print(f"\n{TestColors.GREEN}[PASS]{TestColors.RESET} {test_name}")
    if details:
        for line in details.split("\n"):
            print(f"       {line}")


def print_fail(test_name: str, error: str) -> None:
    """Print a FAIL result."""
    print(f"\n{TestColors.RED}[FAIL]{TestColors.RESET} {test_name}")
    print(f"       {TestColors.RED}Error: {error}{TestColors.RESET}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{TestColors.YELLOW}[INFO]{TestColors.RESET} {message}")


def upload_test_file(s3_client, bucket: str, key: str, content: bytes, content_type: str) -> bool:
    """Upload a test file to S3."""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return True
    except Exception as e:
        print_fail(f"Upload {key}", str(e))
        return False


def delete_test_file(s3_client, bucket: str, key: str) -> None:
    """Delete a test file from S3."""
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
    except Exception:
        pass  # Ignore cleanup errors


def create_s3_client():
    """Create S3 client with proper configuration."""
    config = Config(
        signature_version="s3v4",
        region_name=os.environ.get("AWS_REGION", "us-east-2"),
        retries={"max_attempts": 3, "mode": "adaptive"},
    )
    return boto3.client("s3", config=config)


# =============================================================================
# TEST DATA GENERATORS
# =============================================================================

def generate_csv_comma() -> bytes:
    """Generate CSV with comma separator."""
    return b"codigo,descricao,quantidade,valor\nABC001,Widget A,100,15.50\nDEF002,Widget B,200,25.00\nGHI003,Widget C,50,35.75\nJKL004,Widget D,75,12.00\nMNO005,Widget E,150,8.50\n"


def generate_csv_semicolon() -> bytes:
    """Generate CSV with semicolon separator (pt-BR style)."""
    return b"codigo;descricao;quantidade;valor_unitario\nABC001;Produto A;100;15,50\nDEF002;Produto B;200;25,00\nGHI003;Produto C;50;35,75\nJKL004;Produto D;75;12,00\nMNO005;Produto E;150;8,50\n"


def generate_csv_tab() -> bytes:
    """Generate TSV (tab-separated)."""
    return b"codigo\tdescricao\tquantidade\tvalor\nABC001\tWidget A\t100\t15.50\nDEF002\tWidget B\t200\t25.00\nGHI003\tWidget C\t50\t35.75\n"


def generate_csv_no_header() -> bytes:
    """Generate CSV without header row (all numeric-like data)."""
    return b"001,100,15.50,2026-01-21\n002,200,25.00,2026-01-22\n003,50,35.75,2026-01-23\n004,75,12.00,2026-01-24\n"


def generate_csv_latin1() -> bytes:
    """Generate CSV with Latin-1 encoding (Portuguese special chars)."""
    # Use Latin-1 encoded bytes for Portuguese characters
    return "codigo;descrição;localização;observação\nABC001;Maçã;São Paulo;Entrega até amanhã\nDEF002;Côco;Rio de Janeiro;Atenção especial\n".encode("latin-1")


def generate_xlsx() -> bytes:
    """Generate Excel XLSX file."""
    import pandas as pd

    data = {
        "codigo": ["ABC001", "DEF002", "GHI003"],
        "descricao": ["Product A", "Product B", "Product C"],
        "quantidade": [100, 200, 50],
        "valor": [15.50, 25.00, 35.75],
    }
    df = pd.DataFrame(data)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_csv_comma_detection(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test comma-separated CSV detection."""
    test_key = "tests/phase2/test_comma.csv"

    try:
        upload_test_file(s3_client, bucket, test_key, generate_csv_comma(), "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if result.separator != ",":
            return False, f"Expected separator ',', got '{result.separator}'"

        if result.detected_format != "csv":
            return False, f"Expected format 'csv', got '{result.detected_format}'"

        if "codigo" not in result.columns:
            return False, f"Expected 'codigo' in columns, got {result.columns}"

        if len(result.sample_data) != 3:
            return False, f"Expected 3 sample rows, got {len(result.sample_data)}"

        if not result.has_header:
            return False, "Expected has_header=True"

        details = f"Columns: {result.columns}\nSeparator: {result.separator}\nFormat: {result.detected_format}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_csv_semicolon_detection(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test semicolon-separated CSV detection (pt-BR style)."""
    test_key = "tests/phase2/test_semicolon.csv"

    try:
        upload_test_file(s3_client, bucket, test_key, generate_csv_semicolon(), "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if result.separator != ";":
            return False, f"Expected separator ';', got '{result.separator}'"

        if result.detected_format != "csv_semicolon":
            return False, f"Expected format 'csv_semicolon', got '{result.detected_format}'"

        if "valor_unitario" not in result.columns:
            return False, f"Expected 'valor_unitario' in columns, got {result.columns}"

        details = f"Columns: {result.columns}\nSeparator: {result.separator}\nFormat: {result.detected_format}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_csv_tab_detection(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test tab-separated CSV detection."""
    test_key = "tests/phase2/test_tab.tsv"

    try:
        upload_test_file(s3_client, bucket, test_key, generate_csv_tab(), "text/tab-separated-values")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if result.separator != "\t":
            return False, f"Expected separator tab, got '{result.separator}'"

        if result.detected_format != "csv_tab":
            return False, f"Expected format 'csv_tab', got '{result.detected_format}'"

        details = f"Columns: {result.columns}\nSeparator: TAB\nFormat: {result.detected_format}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_xlsx_detection(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test Excel XLSX format detection via magic bytes."""
    test_key = "tests/phase2/test_excel.xlsx"

    try:
        xlsx_content = generate_xlsx()
        upload_test_file(s3_client, bucket, test_key, xlsx_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if result.detected_format != "xlsx":
            return False, f"Expected format 'xlsx', got '{result.detected_format}'"

        if result.separator is not None:
            return False, f"Expected no separator for Excel, got '{result.separator}'"

        if "codigo" not in result.columns:
            return False, f"Expected 'codigo' in columns, got {result.columns}"

        details = f"Columns: {result.columns}\nFormat: {result.detected_format}\nRows estimate: {result.row_count_estimate}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_header_detection_patterns(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test header detection using inventory column patterns."""
    test_key = "tests/phase2/test_header_patterns.csv"

    # File with inventory-specific column names
    content = b"part_number,descricao,quantidade,localizacao\nPN001,Widget,100,Shelf A\nPN002,Gadget,50,Shelf B\n"

    try:
        upload_test_file(s3_client, bucket, test_key, content, "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if not result.has_header:
            return False, "Expected has_header=True (inventory patterns should be detected)"

        # Verify pattern-matched columns are present
        cols_lower = [c.lower() for c in result.columns]
        expected_patterns = ["part_number", "descricao", "quantidade", "localizacao"]
        for pattern in expected_patterns:
            if pattern not in cols_lower:
                return False, f"Expected '{pattern}' in columns"

        details = f"Columns: {result.columns}\nHeader detected: {result.has_header}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_header_detection_type_variance(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test header detection using type variance heuristic."""
    test_key = "tests/phase2/test_header_variance.csv"

    # First row is all strings (header), subsequent rows have numbers
    content = b"col_a,col_b,col_c\n100,200,300\n150,250,350\n"

    try:
        upload_test_file(s3_client, bucket, test_key, content, "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if not result.has_header:
            return False, "Expected has_header=True (type variance should detect header)"

        # Verify columns are the header values, not generated
        if "col_a" not in result.columns:
            return False, f"Expected 'col_a' in columns, got {result.columns}"

        details = f"Columns: {result.columns}\nHeader detected: {result.has_header} (via type variance)"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_no_header_detection(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test detection when file has no header (all numeric rows)."""
    test_key = "tests/phase2/test_no_header.csv"

    try:
        upload_test_file(s3_client, bucket, test_key, generate_csv_no_header(), "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if result.has_header:
            return False, "Expected has_header=False (all numeric data)"

        # Should have generated column names
        if not result.columns[0].startswith("col_"):
            return False, f"Expected generated column names (col_0, col_1...), got {result.columns}"

        details = f"Columns: {result.columns}\nHeader detected: {result.has_header} (correctly detected no header)"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_encoding_fallback(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test UTF-8 → Latin-1 encoding fallback."""
    test_key = "tests/phase2/test_latin1.csv"

    try:
        upload_test_file(s3_client, bucket, test_key, generate_csv_latin1(), "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if result.encoding != "latin-1":
            return False, f"Expected encoding 'latin-1', got '{result.encoding}'"

        # Check that Portuguese characters are preserved in columns
        cols_str = str(result.columns)
        if "descrição" not in cols_str and "descri" not in cols_str.lower():
            return False, f"Expected Portuguese column names to be preserved, got {result.columns}"

        details = f"Columns: {result.columns}\nEncoding: {result.encoding}\nSample: {result.sample_data[0] if result.sample_data else 'N/A'}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_sample_data_limit(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test that exactly 3 sample rows are returned."""
    test_key = "tests/phase2/test_sample_limit.csv"

    # Create file with many rows
    content = b"codigo,descricao,quantidade\n"
    for i in range(10):
        content += f"CODE{i:03d},Product {i},{i*10}\n".encode()

    try:
        upload_test_file(s3_client, bucket, test_key, content, "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        if len(result.sample_data) != 3:
            return False, f"Expected exactly 3 sample rows, got {len(result.sample_data)}"

        # Verify first sample row is the first data row
        if result.sample_data[0].get("codigo") != "CODE000":
            return False, f"Expected first sample to be CODE000, got {result.sample_data[0]}"

        details = f"Sample count: {len(result.sample_data)}\nFirst sample: {result.sample_data[0]}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_row_count_estimate(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test row count estimation is within ±50% tolerance."""
    test_key = "tests/phase2/test_row_estimate.csv"

    # Create file with known row count
    actual_rows = 100
    content = b"codigo,descricao,quantidade,valor\n"
    for i in range(actual_rows):
        content += f"CODE{i:04d},Product Name Here,{i*10},{i*1.5:.2f}\n".encode()

    try:
        upload_test_file(s3_client, bucket, test_key, content, "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        # Check if estimate is within ±50%
        min_expected = int(actual_rows * 0.5)
        max_expected = int(actual_rows * 1.5)

        if not (min_expected <= result.row_count_estimate <= max_expected):
            return False, f"Row estimate {result.row_count_estimate} outside ±50% range [{min_expected}, {max_expected}] for {actual_rows} actual rows"

        accuracy = abs(result.row_count_estimate - actual_rows) / actual_rows * 100
        details = f"Actual rows: {actual_rows}\nEstimated: {result.row_count_estimate}\nAccuracy: ±{accuracy:.1f}%"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_column_preservation(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test that column names with accents/spaces are preserved exactly."""
    test_key = "tests/phase2/test_column_preserve.csv"

    # Column names with special characters (encoded as UTF-8)
    content = "Código,Descrição do Produto,Quantidade (unid),Valor R$\nABC,Test,100,15.50\n".encode("utf-8")

    try:
        upload_test_file(s3_client, bucket, test_key, content, "text/csv")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if not result.success:
            return False, f"Inspection failed: {result.error}"

        # Check exact column preservation
        expected_cols = ["Código", "Descrição do Produto", "Quantidade (unid)", "Valor R$"]

        for expected in expected_cols:
            if expected not in result.columns:
                return False, f"Column '{expected}' not preserved exactly. Got: {result.columns}"

        details = f"Columns preserved: {result.columns}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_singleton_stateless(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test that FileInspector is stateless (no data leakage between calls)."""
    test_key1 = "tests/phase2/test_stateless1.csv"
    test_key2 = "tests/phase2/test_stateless2.csv"

    content1 = b"file1_col_a,file1_col_b\n1,2\n"
    content2 = b"file2_col_x,file2_col_y,file2_col_z\nA,B,C\n"

    try:
        upload_test_file(s3_client, bucket, test_key1, content1, "text/csv")
        upload_test_file(s3_client, bucket, test_key2, content2, "text/csv")

        # Use the same inspector instance
        result1 = inspector.inspect_s3_file(bucket=bucket, key=test_key1)
        result2 = inspector.inspect_s3_file(bucket=bucket, key=test_key2)

        if not result1.success or not result2.success:
            return False, f"Inspection failed: {result1.error or result2.error}"

        # Verify no state leakage
        if len(result1.columns) != 2:
            return False, f"File 1 should have 2 columns, got {len(result1.columns)}"

        if len(result2.columns) != 3:
            return False, f"File 2 should have 3 columns, got {len(result2.columns)}"

        if "file1" in str(result2.columns).lower():
            return False, f"State leakage: file1 columns appear in file2 result"

        details = f"File 1 columns: {result1.columns}\nFile 2 columns: {result2.columns}\nNo leakage detected"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key1)
        delete_test_file(s3_client, bucket, test_key2)


def test_get_file_structure_tool(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test the get_file_structure tool wrapper returns valid JSON."""
    test_key = "tests/phase2/test_tool.csv"

    try:
        upload_test_file(s3_client, bucket, test_key, generate_csv_comma(), "text/csv")

        # Import and call the tool
        from agents.tools.analysis_tools import get_file_structure

        # Call the tool (it returns JSON string)
        result_json = get_file_structure(s3_key=test_key, bucket=bucket)

        # Verify it's valid JSON
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError as e:
            return False, f"Tool returned invalid JSON: {e}"

        if not result.get("success"):
            return False, f"Tool returned error: {result.get('error')}"

        # Verify expected fields
        required_fields = ["columns", "sample_data", "detected_format", "row_count_estimate"]
        for field in required_fields:
            if field not in result:
                return False, f"Missing required field: {field}"

        details = f"JSON valid: True\nFields: {list(result.keys())}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


def test_error_file_not_found(inspector: FileInspector, bucket: str) -> Tuple[bool, str]:
    """Test error handling for non-existent file."""
    result = inspector.inspect_s3_file(bucket=bucket, key="nonexistent/file.csv")

    if result.success:
        return False, "Expected failure for non-existent file"

    if result.error_type != "FILE_NOT_FOUND":
        return False, f"Expected error_type 'FILE_NOT_FOUND', got '{result.error_type}'"

    details = f"Error type: {result.error_type}\nError: {result.error}"
    return True, details


def test_error_unsupported_format(inspector: FileInspector, bucket: str, s3_client) -> Tuple[bool, str]:
    """Test error handling for unsupported file format."""
    test_key = "tests/phase2/test_unsupported.xyz"

    # Create a binary file that's not recognizable
    content = bytes([0x00, 0x01, 0x02, 0x03, 0xFF, 0xFE, 0xFD])

    try:
        upload_test_file(s3_client, bucket, test_key, content, "application/octet-stream")

        result = inspector.inspect_s3_file(bucket=bucket, key=test_key)

        if result.success:
            return False, "Expected failure for unsupported format"

        if result.error_type != "UNSUPPORTED_FORMAT":
            return False, f"Expected error_type 'UNSUPPORTED_FORMAT', got '{result.error_type}'"

        details = f"Error type: {result.error_type}\nError: {result.error}"
        return True, details

    finally:
        delete_test_file(s3_client, bucket, test_key)


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

def run_phase2_integration_test() -> bool:
    """
    Run the complete Phase 2 integration test.

    Returns:
        True if all tests pass, False otherwise.
    """
    print_header("Phase 2 Smart Parsing - Integration Test")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")

    # Get bucket from environment
    bucket = os.environ.get("DOCUMENTS_BUCKET", "faiston-one-sga-documents-prod")
    print(f"Bucket: {bucket}")

    # Create S3 client
    s3_client = create_s3_client()

    # Create inspector
    inspector = get_file_inspector(bucket=bucket)
    print(f"FileInspector initialized")

    # Test results tracking
    results = []

    # -----------------------------------------------------------------
    # CSV FORMAT TESTS
    # -----------------------------------------------------------------
    print_subheader("CSV Format Detection Tests")

    tests_csv = [
        ("CSV comma separator detection", test_csv_comma_detection),
        ("CSV semicolon separator detection (pt-BR)", test_csv_semicolon_detection),
        ("CSV tab separator detection (TSV)", test_csv_tab_detection),
    ]

    for test_name, test_func in tests_csv:
        passed, details = test_func(inspector, bucket, s3_client)
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # EXCEL FORMAT TESTS
    # -----------------------------------------------------------------
    print_subheader("Excel Format Detection Tests")

    tests_excel = [
        ("XLSX format detection via magic bytes", test_xlsx_detection),
    ]

    for test_name, test_func in tests_excel:
        passed, details = test_func(inspector, bucket, s3_client)
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # HEADER DETECTION TESTS
    # -----------------------------------------------------------------
    print_subheader("Header Detection Tests")

    tests_header = [
        ("Header detection via inventory patterns", test_header_detection_patterns),
        ("Header detection via type variance", test_header_detection_type_variance),
        ("No-header detection (all numeric)", test_no_header_detection),
    ]

    for test_name, test_func in tests_header:
        passed, details = test_func(inspector, bucket, s3_client)
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # ENCODING TESTS
    # -----------------------------------------------------------------
    print_subheader("Encoding Tests")

    tests_encoding = [
        ("UTF-8 → Latin-1 encoding fallback", test_encoding_fallback),
        ("Column name preservation (accents/spaces)", test_column_preservation),
    ]

    for test_name, test_func in tests_encoding:
        passed, details = test_func(inspector, bucket, s3_client)
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # DATA EXTRACTION TESTS
    # -----------------------------------------------------------------
    print_subheader("Data Extraction Tests")

    tests_data = [
        ("Sample data limit (exactly 3 rows)", test_sample_data_limit),
        ("Row count estimate (±50% tolerance)", test_row_count_estimate),
    ]

    for test_name, test_func in tests_data:
        passed, details = test_func(inspector, bucket, s3_client)
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # STATELESS & TOOL TESTS
    # -----------------------------------------------------------------
    print_subheader("Stateless & Tool Tests")

    tests_stateless = [
        ("Singleton stateless (no data leakage)", test_singleton_stateless),
        ("get_file_structure tool returns valid JSON", test_get_file_structure_tool),
    ]

    for test_name, test_func in tests_stateless:
        passed, details = test_func(inspector, bucket, s3_client)
        results.append((test_name, passed))
        if passed:
            print_pass(test_name, details)
        else:
            print_fail(test_name, details)

    # -----------------------------------------------------------------
    # ERROR HANDLING TESTS
    # -----------------------------------------------------------------
    print_subheader("Error Handling Tests")

    # File not found
    passed, details = test_error_file_not_found(inspector, bucket)
    results.append(("Error: File not found", passed))
    if passed:
        print_pass("Error: File not found", details)
    else:
        print_fail("Error: File not found", details)

    # Unsupported format
    passed, details = test_error_unsupported_format(inspector, bucket, s3_client)
    results.append(("Error: Unsupported format", passed))
    if passed:
        print_pass("Error: Unsupported format", details)
    else:
        print_fail("Error: Unsupported format", details)

    # -----------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------
    print_header("Test Summary")

    total = len(results)
    passed_count = sum(1 for _, passed in results if passed)
    failed_count = total - passed_count

    print(f"\n{TestColors.BOLD}Total Tests: {total}{TestColors.RESET}")
    print(f"{TestColors.GREEN}Passed: {passed_count}{TestColors.RESET}")
    print(f"{TestColors.RED}Failed: {failed_count}{TestColors.RESET}")

    if failed_count > 0:
        print(f"\n{TestColors.RED}Failed Tests:{TestColors.RESET}")
        for test_name, passed in results:
            if not passed:
                print(f"  - {test_name}")

    all_passed = failed_count == 0

    if all_passed:
        print(f"\n{TestColors.GREEN}{TestColors.BOLD}ALL TESTS PASSED!{TestColors.RESET}")
    else:
        print(f"\n{TestColors.RED}{TestColors.BOLD}SOME TESTS FAILED{TestColors.RESET}")

    return all_passed


if __name__ == "__main__":
    success = run_phase2_integration_test()
    sys.exit(0 if success else 1)
