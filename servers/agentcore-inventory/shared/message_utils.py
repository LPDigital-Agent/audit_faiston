"""
Strands SDK Message Text Extraction Utilities.

BUG-039 FIX: Handles multiple response formats from Strands SDK.

The Strands SDK can return messages in various formats:
- str: Simple string response
- Message object: With .content[] array of ContentPart objects
- dict: A2A format with parts[] or content[] arrays

This module provides robust extraction to ensure failure indicators
are properly detected regardless of the message format.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_text_from_message(message: Any) -> str:
    """
    Extract text from various Strands SDK message formats.

    Handles:
    - str: return directly
    - Message object: extract .content[].text
    - dict with parts[]: extract A2A format text
    - dict with content[]: extract alternative format
    - None: return ""
    - Other: str(message) fallback

    Args:
        message: The message in any Strands SDK format

    Returns:
        Extracted text as a string
    """
    if message is None:
        return ""

    if isinstance(message, str):
        return message

    # Message object with .content[] (Strands Message)
    if hasattr(message, "content"):
        text_parts = []
        try:
            for part in message.content:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
            if text_parts:
                return "".join(text_parts)
        except (TypeError, AttributeError):
            pass

    # Dict formats
    if isinstance(message, dict):
        # A2A format: {"parts": [{"kind": "text", "text": "..."}]}
        parts = message.get("parts", [])
        if parts:
            text_parts = [
                p.get("text", "")
                for p in parts
                if isinstance(p, dict) and p.get("kind") == "text"
            ]
            if text_parts:
                return "".join(text_parts)

        # Alternative: {"content": [{"text": "..."}]}
        content = message.get("content", [])
        if content:
            text_parts = [
                p.get("text", "") for p in content if isinstance(p, dict)
            ]
            if text_parts:
                return "".join(text_parts)

        # Direct text key
        if "text" in message:
            return str(message["text"])

        # Nested message
        if "message" in message:
            return extract_text_from_message(message["message"])

    # Object with .text attribute
    if hasattr(message, "text") and message.text:
        return str(message.text)

    # Fallback with warning
    logger.warning(
        f"[message_utils] Unknown message type {type(message).__name__}, "
        f"falling back to str()"
    )
    return str(message)


def safe_message_lower(message: Any) -> str:
    """
    Extract text and convert to lowercase for pattern matching.

    This is a convenience wrapper for failure indicator detection.

    Args:
        message: The message in any Strands SDK format

    Returns:
        Extracted text in lowercase
    """
    return extract_text_from_message(message).lower()
