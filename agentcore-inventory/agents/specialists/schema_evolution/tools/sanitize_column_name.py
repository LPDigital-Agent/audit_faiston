# =============================================================================
# Sanitize Column Name Tool
# =============================================================================
# Sanitizes column names for PostgreSQL identifiers.
# =============================================================================

import re
from typing import Dict, Any

from shared.xray_tracer import trace_tool_call


@trace_tool_call("sga_sanitize_column_name")
async def sanitize_column_name_tool(
    raw_name: str,
) -> Dict[str, Any]:
    """
    Sanitize column name for PostgreSQL.

    Transforms arbitrary input into a safe PostgreSQL identifier:
    - Lowercase
    - Replace spaces/special chars with underscore
    - Remove consecutive underscores
    - Ensure doesn't start with a number
    - Limit to 63 chars (PostgreSQL identifier limit)

    Args:
        raw_name: Original column name (e.g., from CSV header)

    Returns:
        Dictionary with:
        - original: Original input
        - sanitized: Sanitized column name safe for PostgreSQL
        - changes_made: List of transformations applied

    Examples:
        >>> sanitize_column_name_tool("Serial Number")
        {"original": "Serial Number", "sanitized": "serial_number", ...}
        >>> sanitize_column_name_tool("123_field")
        {"original": "123_field", "sanitized": "col_123_field", ...}
        >>> sanitize_column_name_tool("Número NF-e")
        {"original": "Número NF-e", "sanitized": "numero_nf_e", ...}
    """
    changes = []

    if not raw_name:
        return {
            "original": "",
            "sanitized": "unknown_field",
            "changes_made": ["Empty input replaced with 'unknown_field'"],
        }

    original = raw_name

    # Lowercase and strip whitespace
    name = raw_name.lower().strip()
    if name != raw_name:
        changes.append("Converted to lowercase")

    # Replace any non-alphanumeric char (except underscore) with underscore
    new_name = re.sub(r'[^a-z0-9_]', '_', name)
    if new_name != name:
        changes.append("Replaced special characters with underscore")
    name = new_name

    # Remove consecutive underscores
    new_name = re.sub(r'_+', '_', name)
    if new_name != name:
        changes.append("Removed consecutive underscores")
    name = new_name

    # Strip leading/trailing underscores
    new_name = name.strip('_')
    if new_name != name:
        changes.append("Stripped leading/trailing underscores")
    name = new_name

    # Ensure doesn't start with a number
    if name and name[0].isdigit():
        name = f"col_{name}"
        changes.append("Added 'col_' prefix (cannot start with number)")

    # PostgreSQL identifier limit is 63 characters
    if len(name) > 63:
        name = name[:63]
        changes.append("Truncated to 63 characters (PostgreSQL limit)")

    # Final fallback
    if not name:
        name = "unknown_field"
        changes.append("Empty result replaced with 'unknown_field'")

    return {
        "original": original,
        "sanitized": name,
        "changes_made": changes if changes else ["No changes needed"],
        "length": len(name),
    }
