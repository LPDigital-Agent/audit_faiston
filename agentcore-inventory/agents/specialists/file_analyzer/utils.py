"""
Utility functions for FileAnalyzer A2A Agent

BUG-025 FIX: Includes json-repair fallback for partial response recovery.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def recover_partial_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    BUG-025 FIX: Attempt to recover valid JSON from truncated/malformed response.

    Uses json-repair library for robust reconstruction when Strands
    structured output fails unexpectedly.

    Args:
        raw_text: Raw LLM response text that may contain malformed JSON

    Returns:
        Parsed dict if recovery successful, None otherwise
    """
    # First try standard parse
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Try json-repair library
    try:
        from json_repair import repair_json

        repaired = repair_json(raw_text)
        result = json.loads(repaired)
        logger.info("[BUG-025] Successfully recovered JSON via json-repair")
        return result
    except ImportError:
        logger.warning("[BUG-025] json-repair library not installed")
    except Exception as e:
        logger.warning("[BUG-025] json-repair failed: %s", e)

    # Try to extract JSON from markdown code blocks
    try:
        import re

        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", raw_text)
        if json_match:
            extracted = json_match.group(1).strip()
            return json.loads(extracted)
    except Exception:
        pass

    # Try to find JSON object boundaries
    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            potential_json = raw_text[start:end]
            return json.loads(potential_json)
    except Exception:
        pass

    logger.warning("[BUG-025] All recovery methods failed")
    return None


def format_file_content_for_llm(
    headers: list,
    rows: list,
    max_rows: int = 10,
    max_value_length: int = 100,
) -> str:
    """
    Format file content for LLM analysis.

    Creates a clean, structured representation of the data
    that helps the LLM understand column contents.

    Args:
        headers: Column headers
        rows: Data rows
        max_rows: Maximum rows to include
        max_value_length: Truncate values longer than this

    Returns:
        Formatted string for LLM analysis
    """
    lines = []
    lines.append(f"## File Content ({len(rows)} total rows, showing first {min(len(rows), max_rows)})")
    lines.append("")

    # Headers
    lines.append("### Columns:")
    for i, header in enumerate(headers):
        lines.append(f"{i+1}. `{header}`")
    lines.append("")

    # Sample data as table
    lines.append("### Sample Data:")
    lines.append("")

    # Create markdown table
    header_row = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines.append(header_row)
    lines.append(separator)

    for row in rows[:max_rows]:
        # Truncate long values
        truncated = []
        for cell in row:
            cell_str = str(cell)
            if len(cell_str) > max_value_length:
                cell_str = cell_str[: max_value_length - 3] + "..."
            # Escape pipe characters
            cell_str = cell_str.replace("|", "\\|")
            truncated.append(cell_str)

        # Pad row if needed
        while len(truncated) < len(headers):
            truncated.append("")

        lines.append("| " + " | ".join(truncated) + " |")

    lines.append("")
    return "\n".join(lines)


def build_analysis_prompt(
    file_content: str,
    filename: str,
    analysis_round: int,
    user_responses: Optional[dict] = None,
) -> str:
    """
    Build the analysis prompt for the LLM.

    Args:
        file_content: Formatted file content
        filename: Original filename
        analysis_round: Current round number
        user_responses: Previous user responses if round > 1

    Returns:
        Complete prompt for analysis
    """
    lines = []

    lines.append(f"# File Analysis Request (Round {analysis_round})")
    lines.append("")
    lines.append(f"**Filename:** {filename}")
    lines.append("")

    if analysis_round > 1 and user_responses:
        lines.append("## Previous User Responses")
        lines.append("```json")
        lines.append(json.dumps(user_responses, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")
        lines.append("Apply these responses to update the analysis.")
        lines.append("")

    lines.append(file_content)
    lines.append("")
    lines.append("## Instructions")
    lines.append("")
    lines.append("Analyze the file and return a structured InventoryAnalysisResponse with:")
    lines.append("1. Column mappings to database fields")
    lines.append("2. HIL questions for ambiguous mappings")
    lines.append("3. Unmapped column handling questions")
    lines.append("")
    lines.append("Respond with valid JSON matching the schema. DO NOT include markdown formatting.")

    return "\n".join(lines)


def validate_analysis_response(response: dict) -> tuple[bool, list]:
    """
    Validate that an analysis response has required fields.

    Args:
        response: The response dict to validate

    Returns:
        Tuple of (is_valid, list of validation errors)
    """
    errors = []

    required_fields = ["success", "file_type", "columns", "hil_questions", "recommended_action"]
    for field in required_fields:
        if field not in response:
            errors.append(f"Missing required field: {field}")

    if "hil_questions" in response:
        for i, q in enumerate(response["hil_questions"]):
            if not q.get("question"):
                errors.append(f"hil_questions[{i}] missing 'question' text")
            if not q.get("id"):
                errors.append(f"hil_questions[{i}] missing 'id'")

    return len(errors) == 0, errors
