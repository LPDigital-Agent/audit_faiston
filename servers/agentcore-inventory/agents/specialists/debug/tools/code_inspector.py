# =============================================================================
# DebugAgent v2 - Code Inspector Tool
# =============================================================================
# Security-first source code reading tool for error investigation.
#
# Security Features:
# - Path traversal prevention (Path.resolve + relative_to)
# - Blocked patterns for sensitive files (.env, credentials, etc.)
# - Extension whitelist (only code/config files)
# - File size limit (5MB max)
# - Symlink resolution
#
# Usage:
# - Use FIRST when analyzing any error with a stack trace
# - Provides context lines before/after the error line
# - Visual marker (->) on the target line
#
# Reference:
# - OWASP Path Traversal: https://owasp.org/www-community/attacks/Path_Traversal
# =============================================================================

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from strands import tool

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Security Constants
# =============================================================================

# PROJECT_ROOT is derived dynamically to ensure security even if deployed elsewhere
# Structure: code_inspector.py -> tools/ -> debug/ -> specialists/ -> agents/ -> agentcore-inventory/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

# Maximum file size to read (5MB) - prevents memory exhaustion
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

# Maximum context lines around target line
MAX_CONTEXT_LINES = 50

# Allowed file extensions (code and config files only)
ALLOWED_EXTENSIONS = {
    ".py",      # Python
    ".js",      # JavaScript
    ".ts",      # TypeScript
    ".tsx",     # TypeScript React
    ".jsx",     # JavaScript React
    ".json",    # JSON config
    ".yaml",    # YAML config
    ".yml",     # YAML config
    ".toml",    # TOML config
    ".tf",      # Terraform
    ".sh",      # Shell scripts
    ".md",      # Markdown docs
    ".sql",     # SQL queries
    ".html",    # HTML templates
    ".css",     # CSS styles
    ".go",      # Go
    ".rs",      # Rust
    ".java",    # Java
}

# Blocked patterns - NEVER read these files/folders
BLOCKED_PATTERNS = {
    ".env",           # Environment variables (secrets)
    "credentials",    # Credential files
    "secret",         # Secret files
    "password",       # Password files
    ".git/",          # Git internals
    "__pycache__/",   # Python cache
    ".venv/",         # Virtual environment
    "venv/",          # Virtual environment (alt)
    "node_modules/",  # Node modules
    ".aws/",          # AWS credentials
    ".ssh/",          # SSH keys
    "id_rsa",         # SSH private key
    "id_ed25519",     # SSH private key (ed25519)
    ".pem",           # Certificate/key files
    ".key",           # Key files
}


# =============================================================================
# Security Validation
# =============================================================================

def _is_path_safe(file_path: str) -> Tuple[bool, str]:
    """
    Validate that a file path is safe to read.

    Security checks performed:
    1. Resolve to absolute path (handles symlinks)
    2. Verify within PROJECT_ROOT (prevents traversal)
    3. Check against blocked patterns
    4. Validate file extension
    5. Check file exists and size

    Args:
        file_path: Path to validate (relative or absolute)

    Returns:
        Tuple of (is_safe, error_message_or_resolved_path)
    """
    try:
        # Handle relative paths - resolve from PROJECT_ROOT
        path = Path(file_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        # Resolve to absolute path (follows symlinks for security)
        resolved = path.resolve()

        # Security Check 1: Must be within PROJECT_ROOT
        try:
            resolved.relative_to(PROJECT_ROOT)
        except ValueError:
            return False, f"Path traversal blocked: {file_path} is outside project root"

        # Security Check 2: Check blocked patterns
        path_str = str(resolved).lower()
        for pattern in BLOCKED_PATTERNS:
            if pattern in path_str:
                return False, f"Blocked pattern: {pattern} found in path"

        # Security Check 3: Validate extension
        if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
            return False, f"Extension not allowed: {resolved.suffix}. Allowed: {ALLOWED_EXTENSIONS}"

        # Security Check 4: File must exist
        if not resolved.exists():
            return False, f"File not found: {file_path}"

        # Security Check 5: Must be a regular file (not directory, device, etc.)
        if not resolved.is_file():
            return False, f"Not a regular file: {file_path}"

        # Security Check 6: File size limit
        file_size = resolved.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return False, f"File too large: {file_size} bytes (max {MAX_FILE_SIZE_BYTES})"

        return True, str(resolved)

    except Exception as e:
        return False, f"Path validation error: {str(e)}"


# =============================================================================
# Tool Implementation
# =============================================================================

@tool
async def read_code_snippet_tool(
    file_path: str,
    line_number: int,
    context_lines: int = 10,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read a code snippet from a file, highlighting the target line.

    USE THIS TOOL FIRST when analyzing any error with a stack trace.
    This enables you to SEE the actual code where the error occurred,
    not just guess based on the error message.

    Args:
        file_path: Path to the file (relative to project root or absolute)
        line_number: Line number to highlight (1-indexed)
        context_lines: Number of lines before/after to include (default 10, max 50)
        session_id: Optional session ID for logging

    Returns:
        Dict containing:
        - success: Whether the read was successful
        - file: Resolved file path
        - snippet: Formatted code snippet with line numbers
        - target_line: The actual content of the target line
        - start_line: First line number in snippet
        - end_line: Last line number in snippet
        - error: Error message if not successful

    Example output snippet:
        38 |     try:
        39 |         data = json.loads(content)
     -> 40 |         return data["missing_key"]  # KeyError here
        41 |     except Exception as e:
        42 |         logger.error(e)

    Raises:
        ValueError: If line_number < 1 (returned as error dict).
        FileNotFoundError: If file doesn't exist (caught internally).
        PermissionError: If file can't be read due to permissions (caught internally).
        UnicodeDecodeError: If file encoding cannot be detected (caught internally).
    """
    logger.info(f"[CodeInspector] Reading {file_path}:{line_number} (context={context_lines})")

    # Input validation
    if line_number < 1:
        return {
            "success": False,
            "error": f"Invalid line number: {line_number}. Must be >= 1",
            "file": file_path,
        }

    # Clamp context lines to max
    context_lines = min(max(1, context_lines), MAX_CONTEXT_LINES)

    # Security validation
    is_safe, result = _is_path_safe(file_path)
    if not is_safe:
        logger.warning(f"[CodeInspector] Security block: {result}")
        return {
            "success": False,
            "error": result,
            "file": file_path,
            "security_blocked": True,
        }

    resolved_path = result

    try:
        # Read file content
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Validate line number
        if line_number > total_lines:
            return {
                "success": False,
                "error": f"Line {line_number} exceeds file length ({total_lines} lines)",
                "file": resolved_path,
                "total_lines": total_lines,
            }

        # Calculate range (0-indexed internally, 1-indexed for display)
        start_idx = max(0, line_number - 1 - context_lines)
        end_idx = min(total_lines, line_number + context_lines)

        # Extract lines
        snippet_lines = lines[start_idx:end_idx]

        # Format with line numbers and marker
        formatted_lines = []
        target_line_content = ""

        for i, line in enumerate(snippet_lines):
            actual_line_num = start_idx + i + 1  # 1-indexed

            # Remove trailing newline for clean formatting
            line_content = line.rstrip('\n\r')

            # Add marker for target line
            if actual_line_num == line_number:
                prefix = f"  -> {actual_line_num:4d} | "
                target_line_content = line_content
            else:
                prefix = f"     {actual_line_num:4d} | "

            formatted_lines.append(prefix + line_content)

        snippet = "\n".join(formatted_lines)

        # Get relative path for cleaner output
        try:
            relative_path = Path(resolved_path).relative_to(PROJECT_ROOT)
            display_path = str(relative_path)
        except ValueError:
            display_path = resolved_path

        logger.info(f"[CodeInspector] Successfully read {display_path}:{line_number}")

        return {
            "success": True,
            "file": display_path,
            "snippet": snippet,
            "target_line": target_line_content,
            "line_number": line_number,
            "start_line": start_idx + 1,
            "end_line": end_idx,
            "total_lines": total_lines,
            "context_lines": context_lines,
        }

    except UnicodeDecodeError as e:
        logger.error(f"[CodeInspector] Encoding error: {e}")
        return {
            "success": False,
            "error": f"File encoding error: {str(e)}",
            "file": resolved_path,
        }
    except Exception as e:
        logger.error(f"[CodeInspector] Read error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}",
            "file": resolved_path,
        }
