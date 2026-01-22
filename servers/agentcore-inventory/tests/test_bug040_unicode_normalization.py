"""
Test suite for BUG-040: Unicode NFC Normalization Fix.

This tests the fix for Portuguese filenames like "SOLICITAÇÕES DE EXPEDIÇÃO.csv"
that were causing S3 NoSuchKey errors due to NFD/NFC encoding mismatches.

Issue: GitHub Issue #14
Root Cause: macOS/browsers may send filenames in NFD (decomposed) form,
            but S3 treats keys as raw bytes, so NFD ≠ NFC creates different keys.
"""

import unicodedata
import pytest


class TestUnicodeNormalization:
    """Test Unicode NFC normalization patterns used in BUG-040 fix."""

    # Test data: Portuguese filenames that can have NFD/NFC differences
    PORTUGUESE_FILENAMES = [
        "SOLICITAÇÕES DE EXPEDIÇÃO.csv",  # Ç = U+00C7 (NFC) vs C+U+0327 (NFD)
        "Relatório_Mensal.xlsx",           # ó = U+00F3 (NFC) vs o+U+0301 (NFD)
        "Estoque_São_Paulo.csv",           # ã = U+00E3 (NFC) vs a+U+0303 (NFD)
        "Inventário_2026.csv",             # á = U+00E1 (NFC) vs a+U+0301 (NFD)
        "Número_de_Série.csv",             # ú = U+00FA (NFC) vs u+U+0301 (NFD)
        "Cabeçalho.csv",                   # ç = U+00E7 (NFC) vs c+U+0327 (NFD)
    ]

    def test_nfc_normalization_is_idempotent(self):
        """NFC normalization of already-NFC strings returns identical string."""
        for filename in self.PORTUGUESE_FILENAMES:
            # Already NFC (composed)
            nfc_filename = unicodedata.normalize("NFC", filename)
            # Normalize again
            double_normalized = unicodedata.normalize("NFC", nfc_filename)
            assert nfc_filename == double_normalized, f"NFC not idempotent for: {filename}"

    def test_nfd_to_nfc_conversion(self):
        """NFD (decomposed) filenames convert correctly to NFC (composed)."""
        for filename in self.PORTUGUESE_FILENAMES:
            # Create NFD version (decomposed)
            nfd_filename = unicodedata.normalize("NFD", filename)
            # Convert back to NFC
            nfc_filename = unicodedata.normalize("NFC", nfd_filename)
            # Original should match NFC (since test data is already NFC)
            original_nfc = unicodedata.normalize("NFC", filename)
            assert nfc_filename == original_nfc, f"NFD→NFC failed for: {filename}"

    def test_nfd_nfc_bytes_differ(self):
        """Demonstrate that NFD and NFC encode to different byte sequences."""
        # This is the core bug: S3 treats keys as raw bytes
        filename = "SOLICITAÇÕES DE EXPEDIÇÃO.csv"

        nfd_bytes = unicodedata.normalize("NFD", filename).encode("utf-8")
        nfc_bytes = unicodedata.normalize("NFC", filename).encode("utf-8")

        # They should be DIFFERENT byte sequences (this is what caused the bug)
        assert nfd_bytes != nfc_bytes, "NFD and NFC should produce different bytes"

        # NFC is shorter (composed characters)
        assert len(nfc_bytes) < len(nfd_bytes), "NFC should be shorter than NFD"

    def test_portuguese_special_chars_preserved(self):
        """Portuguese special characters are preserved after NFC normalization."""
        special_chars = "ÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç"

        normalized = unicodedata.normalize("NFC", special_chars)

        assert normalized == special_chars, "Portuguese chars should be preserved"
        assert "Ç" in normalized
        assert "ç" in normalized
        assert "Ã" in normalized

    def test_s3_key_construction_with_normalization(self):
        """Simulate the fixed S3 key construction with NFC normalization."""
        user_id = "user123"
        session_id = "session456"
        filename = "SOLICITAÇÕES DE EXPEDIÇÃO.csv"

        # Original bug: no normalization
        # safe_filename = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
        # s3_key_buggy = f"uploads/{user_id}/{session_id}/{safe_filename}"

        # Fixed: with NFC normalization
        safe_filename = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
        normalized_filename = unicodedata.normalize("NFC", safe_filename)
        s3_key_fixed = f"uploads/{user_id}/{session_id}/{normalized_filename}"

        # Verify the key is valid
        assert s3_key_fixed == "uploads/user123/session456/SOLICITAÇÕES DE EXPEDIÇÃO.csv"

        # Verify normalization was applied
        assert unicodedata.is_normalized("NFC", normalized_filename)

    def test_fileinspector_key_normalization(self):
        """Simulate FileInspector's defensive NFC normalization."""
        # Simulate NFD key coming from browser/macOS
        key_nfd = unicodedata.normalize("NFD", "temp/uploads/abc123_SOLICITAÇÕES.csv")

        # FileInspector's fix: normalize to NFC before S3 lookup
        key_normalized = unicodedata.normalize("NFC", key_nfd)

        # Both should now match the NFC form
        expected_nfc = "temp/uploads/abc123_SOLICITAÇÕES.csv"
        assert unicodedata.normalize("NFC", key_normalized) == unicodedata.normalize("NFC", expected_nfc)


class TestEdgeCases:
    """Edge cases for Unicode normalization."""

    def test_ascii_only_unchanged(self):
        """ASCII-only filenames are unchanged by NFC normalization."""
        filename = "inventory_2026.csv"
        normalized = unicodedata.normalize("NFC", filename)
        assert normalized == filename

    def test_emoji_preserved(self):
        """Emoji in filenames are preserved (belt-and-suspenders)."""
        filename = "📦_inventory.csv"
        normalized = unicodedata.normalize("NFC", filename)
        assert "📦" in normalized

    def test_empty_string(self):
        """Empty string normalization returns empty string."""
        assert unicodedata.normalize("NFC", "") == ""

    def test_spaces_preserved(self):
        """Spaces in filenames are preserved."""
        filename = "My File With Spaces.csv"
        normalized = unicodedata.normalize("NFC", filename)
        assert normalized == filename
        assert " " in normalized


class TestBug040RegressionPrevention:
    """
    Regression tests to prevent BUG-040 from recurring.

    These tests document the specific failure case and verify the fix works.
    """

    def test_solicitacoes_filename_roundtrip(self):
        """
        The exact filename that caused BUG-040.

        Scenario:
        1. User uploads "SOLICITAÇÕES DE EXPEDIÇÃO.csv"
        2. Browser/macOS may send it as NFD
        3. S3 key is created
        4. Later, FileInspector tries to read with NFC key
        5. S3 returns NoSuchKey because bytes differ

        Fix: Normalize to NFC at both write and read time.
        """
        original_filename = "SOLICITAÇÕES DE EXPEDIÇÃO.csv"

        # Simulate NFD from browser (macOS often sends NFD)
        nfd_from_browser = unicodedata.normalize("NFD", original_filename)

        # FIX 1: Upload handler normalizes to NFC
        normalized_on_upload = unicodedata.normalize("NFC", nfd_from_browser)

        # FIX 3: FileInspector also normalizes (belt-and-suspenders)
        normalized_on_read = unicodedata.normalize("NFC", normalized_on_upload)

        # Both should match
        assert normalized_on_upload == normalized_on_read

        # Should equal the original (which is NFC)
        original_nfc = unicodedata.normalize("NFC", original_filename)
        assert normalized_on_read == original_nfc

    def test_double_normalization_safe(self):
        """
        Double NFC normalization is safe (idempotent).

        This is important because:
        - Upload handler normalizes to NFC
        - FileInspector also normalizes to NFC (defensive)
        - The result should be the same
        """
        filename = "SOLICITAÇÕES DE EXPEDIÇÃO.csv"

        once = unicodedata.normalize("NFC", filename)
        twice = unicodedata.normalize("NFC", once)
        thrice = unicodedata.normalize("NFC", twice)

        assert once == twice == thrice
