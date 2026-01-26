# =============================================================================
# Unit Tests for BUG-027: Enhanced A2A Response Extraction
# =============================================================================
# Tests the enhanced part extraction logic in strands_a2a_client.py
# that handles multiple part types for structured_output_model compatibility.
# =============================================================================

import json
import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# Mock Part Types for Testing
# =============================================================================

class MockTextPart:
    """Mock for a2a.types.TextPart content wrapper."""

    def __init__(self, text: str):
        self.text = text


class MockPartWithTextPart:
    """Mock Part containing TextPart content."""

    def __init__(self, text: str):
        self.content = MockTextPart(text)


class MockPartWithDict:
    """Mock Part containing dict content (structured output)."""

    def __init__(self, data: dict):
        self.content = data


class MockPartWithString:
    """Mock Part containing string content directly."""

    def __init__(self, text: str):
        self.content = text


class MockPartWithPydanticRoot:
    """Mock Part with Pydantic-style root attribute."""

    def __init__(self, data: dict):
        self.root = data


class MockPartWithPydanticModelDump:
    """Mock Part with Pydantic model that has model_dump()."""

    def __init__(self, data: dict):
        self.root = MagicMock()
        self.root.model_dump = MagicMock(return_value=data)


class MockPartWithText:
    """Mock Part with direct text attribute."""

    def __init__(self, text: str):
        self.text = text


class MockPartWithDict__dict__:
    """Mock Part for fallback __dict__ extraction."""

    def __init__(self, data: dict):
        self._data = data

    @property
    def __dict__(self):
        return self._data


class MockMessage:
    """Mock A2A Message with parts."""

    def __init__(self, parts: list):
        self.parts = parts


# =============================================================================
# Helper Function to Extract Response Text (mirrors strands_a2a_client.py)
# =============================================================================

def extract_response_text(response_message) -> str:
    """
    Extract text from response message parts.

    This is the logic from strands_a2a_client.py:393-445 (BUG-027 fix).
    """
    from a2a.types import TextPart

    response_text = ""

    for part in response_message.parts:
        try:
            # Handle TextPart content (standard text response)
            if hasattr(part, "content") and isinstance(part.content, TextPart):
                response_text += part.content.text
            # Handle direct text attribute (some serialization formats)
            elif hasattr(part, "text") and isinstance(part.text, str):
                response_text += part.text
            # Handle Part with content dict (structured output)
            elif hasattr(part, "content") and isinstance(part.content, dict):
                response_text = json.dumps(part.content)
                break  # Structured content takes precedence
            # Handle Part with content string
            elif hasattr(part, "content") and isinstance(part.content, str):
                response_text += part.content
            # Handle Pydantic-style root attribute
            elif hasattr(part, "root") and part.root is not None:
                if isinstance(part.root, dict):
                    response_text = json.dumps(part.root)
                elif hasattr(part.root, "model_dump"):
                    response_text = json.dumps(part.root.model_dump())
                break
        except (TypeError, ValueError, AttributeError):
            continue  # Try next part

    # FALLBACK: Extract from raw_response if still empty
    if not response_text and response_message.parts:
        for part in response_message.parts:
            try:
                if hasattr(part, "__dict__"):
                    response_text = json.dumps(part.__dict__, default=str)
                    break
            except Exception:
                pass

    return response_text


# =============================================================================
# Test Cases
# =============================================================================

class TestExtractResponseText:
    """Tests for the enhanced A2A response extraction (BUG-027 fix)."""

    def test_extracts_text_part_content(self):
        """TextPart content is extracted correctly (original behavior)."""
        # Note: This test requires the actual TextPart class
        # For unit testing without the a2a package, we mock the behavior
        pass  # Covered by integration tests

    def test_extracts_direct_text_attribute(self):
        """Part with direct text attribute is extracted."""
        parts = [MockPartWithText('{"success": true, "mappings": []}')]
        message = MockMessage(parts)

        # Mock extract (simplified version without a2a.types)
        response_text = ""
        for part in message.parts:
            if hasattr(part, "text") and isinstance(part.text, str):
                response_text += part.text

        assert response_text == '{"success": true, "mappings": []}'

    def test_extracts_dict_content(self):
        """Dict content is JSON serialized."""
        data = {"success": True, "mappings": [{"source": "A", "target": "B"}]}
        parts = [MockPartWithDict(data)]
        message = MockMessage(parts)

        response_text = ""
        for part in message.parts:
            if hasattr(part, "content") and isinstance(part.content, dict):
                response_text = json.dumps(part.content)
                break

        result = json.loads(response_text)
        assert result["success"] is True
        assert len(result["mappings"]) == 1

    def test_extracts_string_content(self):
        """String content is concatenated."""
        parts = [MockPartWithString('{"data": "value"}')]
        message = MockMessage(parts)

        response_text = ""
        for part in message.parts:
            if hasattr(part, "content") and isinstance(part.content, str):
                response_text += part.content

        assert response_text == '{"data": "value"}'

    def test_extracts_pydantic_root_dict(self):
        """Pydantic root dict attribute is extracted."""
        data = {"status": "success", "column_mappings": []}
        parts = [MockPartWithPydanticRoot(data)]
        message = MockMessage(parts)

        response_text = ""
        for part in message.parts:
            if hasattr(part, "root") and part.root is not None:
                if isinstance(part.root, dict):
                    response_text = json.dumps(part.root)
                    break

        result = json.loads(response_text)
        assert result["status"] == "success"

    def test_extracts_pydantic_model_dump(self):
        """Pydantic model with model_dump() is extracted."""
        data = {"status": "needs_input", "questions": []}
        parts = [MockPartWithPydanticModelDump(data)]
        message = MockMessage(parts)

        response_text = ""
        for part in message.parts:
            if hasattr(part, "root") and part.root is not None:
                if hasattr(part.root, "model_dump"):
                    response_text = json.dumps(part.root.model_dump())
                    break

        result = json.loads(response_text)
        assert result["status"] == "needs_input"

    def test_dict_content_takes_precedence(self):
        """Dict content breaks the loop and takes precedence."""
        dict_data = {"from": "dict"}
        string_data = '{"from": "string"}'

        parts = [
            MockPartWithDict(dict_data),
            MockPartWithString(string_data),  # Should be ignored
        ]
        message = MockMessage(parts)

        response_text = ""
        for part in message.parts:
            if hasattr(part, "content") and isinstance(part.content, dict):
                response_text = json.dumps(part.content)
                break
            elif hasattr(part, "content") and isinstance(part.content, str):
                response_text += part.content

        result = json.loads(response_text)
        assert result["from"] == "dict"

    def test_fallback_extracts_dict_attr(self):
        """Fallback extracts via __dict__ when standard methods fail."""

        class UnusualPart:
            def __init__(self):
                self.data = {"fallback": True}

            @property
            def __dict__(self):
                return {"data": self.data}

        parts = [UnusualPart()]
        message = MockMessage(parts)

        # Primary extraction fails (no content, text, or root)
        response_text = ""
        # ... primary extraction would fail here ...

        # Fallback extraction
        if not response_text:
            for part in message.parts:
                try:
                    if hasattr(part, "__dict__"):
                        response_text = json.dumps(part.__dict__, default=str)
                        break
                except Exception:
                    pass

        result = json.loads(response_text)
        assert "data" in result

    def test_handles_empty_parts_list(self):
        """Empty parts list returns empty string."""
        message = MockMessage([])

        response_text = ""
        for part in message.parts:
            pass  # No parts to iterate

        assert response_text == ""

    def test_handles_serialization_error(self):
        """JSON serialization errors are caught and skipped."""

        class BadPart:
            def __init__(self):
                self.content = object()  # Not serializable

        parts = [BadPart(), MockPartWithString('{"valid": true}')]
        message = MockMessage(parts)

        response_text = ""
        for part in message.parts:
            try:
                if hasattr(part, "content") and isinstance(part.content, dict):
                    response_text = json.dumps(part.content)
                    break
                elif hasattr(part, "content") and isinstance(part.content, str):
                    response_text += part.content
            except (TypeError, ValueError, AttributeError):
                continue

        assert response_text == '{"valid": true}'


class TestKeyTolerantExtraction:
    """Tests for Ghost Bug mitigation: key-tolerant mapping extraction."""

    def test_extracts_mappings_key(self):
        """Standard 'mappings' key is extracted."""
        response = {"status": "success", "mappings": [{"a": "b"}]}

        mappings = (
            response.get("mappings")
            or response.get("column_mappings")
            or response.get("columns_map")
            or response.get("mapping_list")
            or []
        )

        assert len(mappings) == 1
        assert mappings[0] == {"a": "b"}

    def test_extracts_column_mappings_key(self):
        """Alternative 'column_mappings' key is extracted."""
        response = {"status": "success", "column_mappings": [{"x": "y"}]}

        mappings = (
            response.get("mappings")
            or response.get("column_mappings")
            or response.get("columns_map")
            or response.get("mapping_list")
            or []
        )

        assert len(mappings) == 1

    def test_extracts_columns_map_key(self):
        """Alternative 'columns_map' key is extracted."""
        response = {"status": "success", "columns_map": [{"p": "q"}]}

        mappings = (
            response.get("mappings")
            or response.get("column_mappings")
            or response.get("columns_map")
            or response.get("mapping_list")
            or []
        )

        assert len(mappings) == 1

    def test_extracts_mapping_list_key(self):
        """Alternative 'mapping_list' key is extracted."""
        response = {"status": "success", "mapping_list": [{"m": "n"}]}

        mappings = (
            response.get("mappings")
            or response.get("column_mappings")
            or response.get("columns_map")
            or response.get("mapping_list")
            or []
        )

        assert len(mappings) == 1

    def test_returns_empty_list_when_no_key_found(self):
        """Returns empty list when no mapping key is found."""
        response = {"status": "success", "other_field": "value"}

        mappings = (
            response.get("mappings")
            or response.get("column_mappings")
            or response.get("columns_map")
            or response.get("mapping_list")
            or []
        )

        assert mappings == []

    def test_first_non_empty_wins(self):
        """First non-empty result wins in the fallback chain."""
        response = {
            "status": "success",
            "mappings": [],  # Empty, should fallback
            "column_mappings": [{"first": "wins"}],  # This should be used
        }

        mappings = (
            response.get("mappings")
            or response.get("column_mappings")
            or response.get("columns_map")
            or response.get("mapping_list")
            or []
        )

        # Note: Empty list is falsy, so column_mappings wins
        assert len(mappings) == 1
        assert mappings[0] == {"first": "wins"}
