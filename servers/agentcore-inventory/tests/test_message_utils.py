# =============================================================================
# Tests for BUG-039 Message Utils
# =============================================================================
# Unit tests for Strands SDK message text extraction utilities.
#
# These tests verify:
# - String passthrough (direct return)
# - None handling (returns "")
# - Message object with .content[] extraction
# - Dict with parts[] (A2A format) extraction
# - Dict with content[] (alternative format) extraction
# - Dict with direct text key
# - Dict with nested message
# - Object with .text attribute
# - Fallback to str() for unknown types
# - safe_message_lower() for pattern matching
# - Failure indicator detection with complex objects
#
# Run: cd server/agentcore-inventory && python -m pytest tests/test_message_utils.py -v
# =============================================================================

import pytest
from dataclasses import dataclass
from typing import List, Optional

from shared.message_utils import extract_text_from_message, safe_message_lower


# =============================================================================
# Mock Classes (Simulating Strands SDK Types)
# =============================================================================

@dataclass
class MockContentPart:
    """Simulates Strands ContentPart with .text attribute."""
    text: Optional[str] = None


@dataclass
class MockMessage:
    """Simulates Strands Message with .content[] array."""
    content: List[MockContentPart] = None

    def __post_init__(self):
        if self.content is None:
            self.content = []


@dataclass
class MockObjectWithText:
    """Generic object with .text attribute."""
    text: str


# =============================================================================
# Tests: extract_text_from_message
# =============================================================================

class TestExtractTextFromMessage:
    """Tests for extract_text_from_message function."""

    def test_string_input_returns_directly(self):
        """String input should be returned as-is."""
        result = extract_text_from_message("Hello, world!")
        assert result == "Hello, world!"

    def test_empty_string_returns_empty(self):
        """Empty string should return empty string."""
        result = extract_text_from_message("")
        assert result == ""

    def test_none_returns_empty_string(self):
        """None should return empty string."""
        result = extract_text_from_message(None)
        assert result == ""

    def test_message_object_with_single_content_part(self):
        """Message object with single content part extracts text."""
        message = MockMessage(content=[MockContentPart(text="Single part")])
        result = extract_text_from_message(message)
        assert result == "Single part"

    def test_message_object_with_multiple_content_parts(self):
        """Message object with multiple content parts concatenates text."""
        message = MockMessage(content=[
            MockContentPart(text="First "),
            MockContentPart(text="Second "),
            MockContentPart(text="Third"),
        ])
        result = extract_text_from_message(message)
        assert result == "First Second Third"

    def test_message_object_with_empty_content(self):
        """Message object with empty content falls through to fallback."""
        message = MockMessage(content=[])
        result = extract_text_from_message(message)
        # Falls through to str() fallback
        assert "MockMessage" in result or result == ""

    def test_message_object_with_none_text_parts(self):
        """Message object with None text parts handles gracefully."""
        message = MockMessage(content=[
            MockContentPart(text=None),
            MockContentPart(text="Valid"),
            MockContentPart(text=None),
        ])
        result = extract_text_from_message(message)
        assert result == "Valid"

    def test_dict_a2a_format_with_parts(self):
        """Dict with A2A parts[] format extracts text."""
        message = {
            "parts": [
                {"kind": "text", "text": "A2A message"},
            ]
        }
        result = extract_text_from_message(message)
        assert result == "A2A message"

    def test_dict_a2a_format_with_multiple_parts(self):
        """Dict with multiple A2A parts concatenates text."""
        message = {
            "parts": [
                {"kind": "text", "text": "First "},
                {"kind": "text", "text": "Second"},
            ]
        }
        result = extract_text_from_message(message)
        assert result == "First Second"

    def test_dict_a2a_format_ignores_non_text_parts(self):
        """Dict with A2A format ignores non-text parts."""
        message = {
            "parts": [
                {"kind": "image", "url": "http://example.com/img.png"},
                {"kind": "text", "text": "Text only"},
            ]
        }
        result = extract_text_from_message(message)
        assert result == "Text only"

    def test_dict_content_list_format(self):
        """Dict with content[] list extracts text."""
        message = {
            "content": [
                {"text": "Content format"},
            ]
        }
        result = extract_text_from_message(message)
        assert result == "Content format"

    def test_dict_direct_text_key(self):
        """Dict with direct 'text' key extracts it."""
        message = {"text": "Direct text"}
        result = extract_text_from_message(message)
        assert result == "Direct text"

    def test_dict_nested_message(self):
        """Dict with nested 'message' recursively extracts."""
        message = {
            "message": "Nested string message"
        }
        result = extract_text_from_message(message)
        assert result == "Nested string message"

    def test_dict_deeply_nested_message(self):
        """Dict with deeply nested message extracts recursively."""
        message = {
            "message": {
                "text": "Deep nested text"
            }
        }
        result = extract_text_from_message(message)
        assert result == "Deep nested text"

    def test_object_with_text_attribute(self):
        """Generic object with .text attribute extracts it."""
        obj = MockObjectWithText(text="Object text")
        result = extract_text_from_message(obj)
        assert result == "Object text"

    def test_unknown_type_falls_back_to_str(self):
        """Unknown types fall back to str() conversion."""
        result = extract_text_from_message(12345)
        assert result == "12345"

    def test_list_falls_back_to_str(self):
        """Lists fall back to str() conversion."""
        result = extract_text_from_message(["item1", "item2"])
        assert "item1" in result and "item2" in result


# =============================================================================
# Tests: safe_message_lower
# =============================================================================

class TestSafeMessageLower:
    """Tests for safe_message_lower function."""

    def test_string_lowercases(self):
        """String input is lowercased."""
        result = safe_message_lower("HELLO WORLD")
        assert result == "hello world"

    def test_none_returns_empty(self):
        """None returns empty string."""
        result = safe_message_lower(None)
        assert result == ""

    def test_message_object_lowercases(self):
        """Message object text is extracted and lowercased."""
        message = MockMessage(content=[MockContentPart(text="ERROR OCCURRED")])
        result = safe_message_lower(message)
        assert result == "error occurred"

    def test_dict_a2a_lowercases(self):
        """A2A dict text is extracted and lowercased."""
        message = {
            "parts": [
                {"kind": "text", "text": "NÃO CONSEGUI processar"},
            ]
        }
        result = safe_message_lower(message)
        assert result == "não consegui processar"


# =============================================================================
# Tests: BUG-039 Failure Indicator Detection
# =============================================================================

class TestFailureIndicatorDetection:
    """Tests verifying BUG-039 fix: failure indicators detected in complex objects."""

    # Portuguese failure indicators from inventory_hub/main.py
    FAILURE_INDICATORS = [
        "não consegui",
        "não foi possível",
        "houve um problema",
        "houve um erro",
        "falhou",
        "failed",
        "error occurred",
        "A2A call failed",
    ]

    def _has_failure_indicator(self, message) -> bool:
        """Replicate the failure detection logic from inventory_hub."""
        message_lower = safe_message_lower(message)
        return any(indicator in message_lower for indicator in self.FAILURE_INDICATORS)

    def test_string_failure_detected(self):
        """String with failure indicator is detected."""
        message = "Não consegui processar o arquivo."
        assert self._has_failure_indicator(message) is True

    def test_message_object_failure_detected(self):
        """Message object with failure indicator is detected (BUG-039 FIX)."""
        message = MockMessage(content=[
            MockContentPart(text="Desculpe, não foi possível analisar o arquivo."),
        ])
        assert self._has_failure_indicator(message) is True

    def test_dict_a2a_failure_detected(self):
        """A2A dict with failure indicator is detected (BUG-039 FIX)."""
        message = {
            "parts": [
                {"kind": "text", "text": "A2A call failed: timeout"},
            ]
        }
        assert self._has_failure_indicator(message) is True

    def test_dict_content_failure_detected(self):
        """Content dict with failure indicator is detected."""
        message = {
            "content": [
                {"text": "Houve um erro durante o processamento."},
            ]
        }
        assert self._has_failure_indicator(message) is True

    def test_success_message_not_flagged(self):
        """Success messages should not be flagged as failures."""
        message = MockMessage(content=[
            MockContentPart(text="Arquivo processado com sucesso!"),
        ])
        assert self._has_failure_indicator(message) is False

    def test_empty_message_not_flagged(self):
        """Empty message should not be flagged as failure."""
        message = MockMessage(content=[])
        assert self._has_failure_indicator(message) is False

    def test_none_not_flagged(self):
        """None should not be flagged as failure."""
        assert self._has_failure_indicator(None) is False


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_message_with_non_iterable_content(self):
        """Message with non-iterable content handles gracefully."""
        @dataclass
        class BadMessage:
            content: int = 42  # Not iterable

        message = BadMessage()
        # Should not raise, falls back to str()
        result = extract_text_from_message(message)
        assert isinstance(result, str)

    def test_dict_with_empty_parts(self):
        """Dict with empty parts list handles gracefully."""
        message = {"parts": []}
        result = extract_text_from_message(message)
        assert isinstance(result, str)

    def test_unicode_handling(self):
        """Unicode characters are preserved."""
        message = MockMessage(content=[
            MockContentPart(text="Análise concluída com êxito! 🎉"),
        ])
        result = extract_text_from_message(message)
        assert "Análise" in result
        assert "êxito" in result
        assert "🎉" in result

    def test_multiline_text(self):
        """Multiline text is preserved."""
        message = MockMessage(content=[
            MockContentPart(text="Line 1\nLine 2\nLine 3"),
        ])
        result = extract_text_from_message(message)
        assert result == "Line 1\nLine 2\nLine 3"
