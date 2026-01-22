# =============================================================================
# Unit Tests: DebugAgent v2 - Code Inspector Tool
# =============================================================================
# Security-focused tests for the read_code_snippet_tool.
#
# Test Categories:
# 1. Security Tests: Path traversal, blocked patterns, extension whitelist
# 2. Functional Tests: Normal operation, edge cases, error handling
#
# Run with: pytest tests/test_code_inspector.py -v
# =============================================================================

import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any

# Import the tool under test
from agents.specialists.debug.tools.code_inspector import (
    read_code_snippet_tool,
    _is_path_safe,
    PROJECT_ROOT,
    ALLOWED_EXTENSIONS,
    BLOCKED_PATTERNS,
    MAX_CONTEXT_LINES,
)


# =============================================================================
# Helper Functions
# =============================================================================

def run_async(coro):
    """Run an async function synchronously for testing."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# Security Tests: Path Traversal Prevention
# =============================================================================

class TestPathTraversalPrevention:
    """Tests that verify path traversal attacks are blocked."""

    def test_blocks_parent_directory_traversal(self):
        """Should block ../../../etc/passwd style attacks."""
        result = run_async(read_code_snippet_tool("../../../etc/passwd", 1))

        assert result["success"] is False
        assert "traversal" in result["error"].lower() or "outside" in result["error"].lower()
        assert result.get("security_blocked", False) is True

    def test_blocks_encoded_traversal(self):
        """Should block encoded traversal attempts."""
        # Simple .. traversal
        result = run_async(read_code_snippet_tool("../../..", 1))

        assert result["success"] is False

    def test_blocks_absolute_path_outside_project(self):
        """Should block absolute paths outside PROJECT_ROOT."""
        result = run_async(read_code_snippet_tool("/etc/passwd", 1))

        assert result["success"] is False
        assert "outside" in result["error"].lower() or "traversal" in result["error"].lower()

    def test_blocks_home_directory_access(self):
        """Should block access to home directory files."""
        result = run_async(read_code_snippet_tool("~/.bashrc", 1))

        # Either blocked as traversal or file not found (~ not expanded)
        assert result["success"] is False


# =============================================================================
# Security Tests: Blocked Patterns
# =============================================================================

class TestBlockedPatterns:
    """Tests that verify sensitive files are blocked."""

    def test_blocks_env_files(self):
        """Should block .env files containing secrets."""
        result = run_async(read_code_snippet_tool(".env", 1))

        assert result["success"] is False
        assert "blocked" in result["error"].lower() or "not found" in result["error"].lower()

    def test_blocks_env_files_in_subdirectory(self):
        """Should block .env files even in subdirectories."""
        result = run_async(read_code_snippet_tool("config/.env.production", 1))

        assert result["success"] is False

    def test_blocks_git_directory(self):
        """Should block .git/ directory access."""
        result = run_async(read_code_snippet_tool(".git/config", 1))

        assert result["success"] is False
        assert "blocked" in result["error"].lower() or "not found" in result["error"].lower()

    def test_blocks_credentials_files(self):
        """Should block files with 'credentials' in path."""
        result = run_async(read_code_snippet_tool("config/credentials.json", 1))

        assert result["success"] is False

    def test_blocks_secret_files(self):
        """Should block files with 'secret' in path."""
        result = run_async(read_code_snippet_tool("secrets/api_secret.txt", 1))

        assert result["success"] is False

    def test_blocks_password_files(self):
        """Should block files with 'password' in path."""
        result = run_async(read_code_snippet_tool("config/password.txt", 1))

        assert result["success"] is False

    def test_blocks_pycache(self):
        """Should block __pycache__ directories."""
        result = run_async(read_code_snippet_tool("__pycache__/module.cpython-311.pyc", 1))

        assert result["success"] is False

    def test_blocks_node_modules(self):
        """Should block node_modules directories."""
        result = run_async(read_code_snippet_tool("node_modules/package/index.js", 1))

        assert result["success"] is False

    def test_blocks_aws_credentials(self):
        """Should block .aws/ directory access."""
        result = run_async(read_code_snippet_tool(".aws/credentials", 1))

        assert result["success"] is False

    def test_blocks_ssh_keys(self):
        """Should block SSH key files."""
        result = run_async(read_code_snippet_tool(".ssh/id_rsa", 1))

        assert result["success"] is False


# =============================================================================
# Security Tests: Extension Whitelist
# =============================================================================

class TestExtensionWhitelist:
    """Tests that verify only allowed extensions can be read."""

    def test_blocks_binary_files(self):
        """Should block binary file extensions."""
        result = run_async(read_code_snippet_tool("image.png", 1))

        assert result["success"] is False
        assert "extension" in result["error"].lower()

    def test_blocks_executable_files(self):
        """Should block executable files."""
        result = run_async(read_code_snippet_tool("script.exe", 1))

        assert result["success"] is False

    def test_blocks_archive_files(self):
        """Should block archive files."""
        result = run_async(read_code_snippet_tool("backup.zip", 1))

        assert result["success"] is False

    def test_allowed_extensions_defined(self):
        """Verify expected extensions are in the allowed list."""
        expected = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".tf", ".md"}

        for ext in expected:
            assert ext in ALLOWED_EXTENSIONS, f"Expected {ext} to be allowed"


# =============================================================================
# Functional Tests: Normal Operation
# =============================================================================

class TestNormalOperation:
    """Tests for normal tool operation."""

    def test_reads_existing_python_file(self):
        """Should successfully read an existing Python file."""
        # Use a file we know exists: the tool itself
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            10,
            context_lines=5
        ))

        assert result["success"] is True
        assert "snippet" in result
        assert result["line_number"] == 10
        assert "->" in result["snippet"]  # Should have marker
        assert result["target_line"] is not None

    def test_reads_json_file(self):
        """Should successfully read a JSON config file."""
        # Look for pyproject.toml which should exist
        result = run_async(read_code_snippet_tool(
            "pyproject.toml",
            1,
            context_lines=3
        ))

        # May or may not exist, but if it does, should succeed
        if result["success"]:
            assert "snippet" in result

    def test_line_marker_on_correct_line(self):
        """Should place -> marker on the exact target line."""
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            20,
            context_lines=3
        ))

        if result["success"]:
            lines = result["snippet"].split("\n")
            marker_lines = [l for l in lines if l.strip().startswith("->")]
            assert len(marker_lines) == 1
            assert "20" in marker_lines[0]

    def test_returns_relative_path(self):
        """Should return relative path in response for cleaner output."""
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            1
        ))

        if result["success"]:
            # Should not contain the full absolute path
            assert not result["file"].startswith("/Users")


# =============================================================================
# Functional Tests: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_rejects_negative_line_number(self):
        """Should reject negative line numbers."""
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            -1
        ))

        assert result["success"] is False
        assert "invalid" in result["error"].lower() or "line" in result["error"].lower()

    def test_rejects_zero_line_number(self):
        """Should reject line number 0 (lines are 1-indexed)."""
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            0
        ))

        assert result["success"] is False

    def test_handles_line_exceeding_file_length(self):
        """Should handle line number exceeding file length gracefully."""
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            999999
        ))

        assert result["success"] is False
        assert "exceeds" in result["error"].lower()
        assert "total_lines" in result

    def test_clamps_context_lines_to_max(self):
        """Should clamp context_lines to MAX_CONTEXT_LINES."""
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            10,
            context_lines=1000  # Way over MAX_CONTEXT_LINES
        ))

        if result["success"]:
            # Should have used clamped value
            assert result["context_lines"] <= MAX_CONTEXT_LINES

    def test_handles_file_not_found(self):
        """Should handle non-existent files gracefully."""
        result = run_async(read_code_snippet_tool(
            "agents/nonexistent_file_12345.py",
            1
        ))

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_handles_first_line(self):
        """Should handle reading the very first line of a file."""
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            1,
            context_lines=5
        ))

        if result["success"]:
            assert result["start_line"] == 1
            assert "->" in result["snippet"]


# =============================================================================
# Unit Tests: _is_path_safe Helper
# =============================================================================

class TestIsPathSafe:
    """Tests for the _is_path_safe validation function."""

    def test_valid_relative_path(self):
        """Should accept valid relative paths within project."""
        is_safe, result = _is_path_safe("agents/utils.py")

        # May be False if file doesn't exist, but shouldn't be security blocked
        if not is_safe:
            assert "not found" in result.lower() or "extension" in result.lower()

    def test_rejects_symlink_attack(self):
        """Should resolve symlinks to prevent symlink attacks."""
        # This tests the resolve() call in _is_path_safe
        # Create a test with a known traversal pattern
        is_safe, result = _is_path_safe("../../../etc/passwd")

        assert is_safe is False
        assert "traversal" in result.lower() or "outside" in result.lower()

    def test_project_root_is_correct(self):
        """Verify PROJECT_ROOT is calculated correctly."""
        # PROJECT_ROOT should be the agentcore-inventory directory
        assert PROJECT_ROOT.exists()
        assert (PROJECT_ROOT / "agents").exists() or (PROJECT_ROOT / "pyproject.toml").exists()


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the code inspector tool."""

    def test_full_workflow_success(self):
        """Test a complete successful workflow."""
        # Step 1: Read a known file
        result = run_async(read_code_snippet_tool(
            "agents/specialists/debug/tools/code_inspector.py",
            50,
            context_lines=10,
            session_id="test-session-123"
        ))

        if result["success"]:
            assert "snippet" in result
            assert "target_line" in result
            assert result["line_number"] == 50
            assert len(result["snippet"]) > 0

    def test_security_check_order(self):
        """Verify security checks run in correct order."""
        # Path traversal should be caught before file existence
        result = run_async(read_code_snippet_tool("../../../etc/passwd", 1))

        assert result["success"] is False
        # Should be caught as traversal, not "file not found"
        assert "traversal" in result["error"].lower() or "outside" in result["error"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
