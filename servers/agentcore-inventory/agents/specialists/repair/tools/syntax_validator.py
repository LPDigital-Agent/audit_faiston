# =============================================================================
# Syntax Validation Tools for RepairAgent
# =============================================================================
# AST-based syntax validation and targeted test execution.
#
# CRITICAL SAFETY:
# - validate_python_ast_tool() MUST be called before commit_fix_tool()
# - Prevents committing syntactically invalid code
# - RepairAgent MUST NOT proceed if syntax validation fails
#
# Tools:
# 1. validate_python_ast_tool - Parse Python code via AST
# 2. run_targeted_tests_tool - Execute pytest on specific tests
# =============================================================================

import ast
import json
import logging
import subprocess
from typing import Any, Dict

from strands.tools import tool

logger = logging.getLogger(__name__)


# =============================================================================
# Syntax Validation Tools (Strands Tool Interface)
# =============================================================================


@tool
async def validate_python_ast_tool(code: str, filename: str) -> str:
    """
    Validate Python code syntax using AST parsing.

    CRITICAL SAFETY: This tool prevents committing syntactically invalid code.
    RepairAgent MUST call this before commit_fix_tool().

    This tool uses Python's built-in ast.parse() to check syntax without
    executing the code. It catches:
    - SyntaxError (invalid Python syntax)
    - IndentationError
    - TabError
    - Other parse-time errors

    Args:
        code: Python source code to validate
        filename: Filename for error reporting (e.g., "main.py")

    Returns:
        JSON string with validation result:
        {
            "success": true,  # Tool execution succeeded
            "valid": true/false,  # Code syntax is valid
            "error": "SyntaxError details if invalid",
            "line_number": 42,  # Line where error occurred
            "offset": 10,  # Column offset
            "filename": "main.py"
        }

    Example:
        # Valid code
        result = await validate_python_ast_tool("print('Hello')", "test.py")
        # {"success": true, "valid": true, "filename": "test.py"}

        # Invalid code
        result = await validate_python_ast_tool("print('Hello'", "test.py")
        # {"success": true, "valid": false, "error": "unterminated string literal", ...}
    """
    try:
        # Attempt to parse the code
        ast.parse(code, filename=filename)

        logger.info(f"[SyntaxValidator] Syntax validation passed: {filename}")
        return json.dumps({
            "success": True,
            "valid": True,
            "filename": filename,
        })

    except SyntaxError as e:
        logger.warning(
            f"[SyntaxValidator] Syntax validation failed: {filename} "
            f"(line {e.lineno}, offset {e.offset}): {e.msg}"
        )
        return json.dumps({
            "success": True,  # Tool executed successfully
            "valid": False,  # But code is invalid
            "error": e.msg,
            "line_number": e.lineno,
            "offset": e.offset,
            "filename": filename,
            "text": e.text.strip() if e.text else None,
        })

    except IndentationError as e:
        logger.warning(
            f"[SyntaxValidator] Indentation error: {filename} "
            f"(line {e.lineno}): {e.msg}"
        )
        return json.dumps({
            "success": True,
            "valid": False,
            "error": f"IndentationError: {e.msg}",
            "line_number": e.lineno,
            "offset": e.offset,
            "filename": filename,
        })

    except TabError as e:
        logger.warning(
            f"[SyntaxValidator] Tab error: {filename} "
            f"(line {e.lineno}): {e.msg}"
        )
        return json.dumps({
            "success": True,
            "valid": False,
            "error": f"TabError: {e.msg}",
            "line_number": e.lineno,
            "offset": e.offset,
            "filename": filename,
        })

    except Exception as e:
        logger.error(f"[SyntaxValidator] Unexpected error validating syntax: {e}")
        return json.dumps({
            "success": False,  # Tool execution failed
            "error": str(e),
            "filename": filename,
        })


@tool
async def run_targeted_tests_tool(file_path: str, test_pattern: str = None) -> str:
    """
    Run pytest on specific test file or pattern.

    This tool executes pytest with targeted test selection to verify
    that fixes don't break existing functionality. Uses pytest's -k flag
    for pattern matching when test_pattern is provided.

    Args:
        file_path: Path to test file (e.g., "tests/unit/test_debug.py")
        test_pattern: Optional pytest -k pattern for specific tests
                     (e.g., "test_error_handler" to match test_error_handler_*)

    Returns:
        JSON string with test results:
        {
            "success": true,  # Tool execution succeeded
            "tests_passed": true/false,  # All tests passed
            "total": 10,  # Total tests run
            "passed": 9,  # Number passed
            "failed": 1,  # Number failed
            "exit_code": 0,  # pytest exit code (0 = all passed)
            "output": "pytest output summary (truncated)"
        }

    Example:
        # Run all tests in file
        result = await run_targeted_tests_tool("tests/unit/test_repair.py")

        # Run specific test pattern
        result = await run_targeted_tests_tool(
            "tests/unit/test_repair.py",
            test_pattern="test_git_operations"
        )
    """
    try:
        # Build pytest command
        cmd = f"python -m pytest {file_path}"

        if test_pattern:
            cmd += f" -k '{test_pattern}'"

        # Add flags for detailed output
        cmd += " --tb=short -v --no-header"

        logger.info(f"[SyntaxValidator] Running tests: {cmd}")

        # Execute pytest
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes max for tests
        )

        # Parse pytest output for counts
        output = result.stdout + result.stderr
        tests_passed = result.returncode == 0

        # Try to extract test counts from output
        total = 0
        passed = 0
        failed = 0

        # Pytest output format: "X passed" or "X failed, Y passed"
        for line in output.split("\n"):
            if "passed" in line:
                try:
                    # Extract numbers from output
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "passed" and i > 0:
                            passed = int(parts[i - 1])
                        elif part == "failed" and i > 0:
                            failed = int(parts[i - 1])
                except:
                    pass

        total = passed + failed

        logger.info(
            f"[SyntaxValidator] Tests completed: "
            f"{passed} passed, {failed} failed (exit code: {result.returncode})"
        )

        return json.dumps({
            "success": True,
            "tests_passed": tests_passed,
            "total": total,
            "passed": passed,
            "failed": failed,
            "exit_code": result.returncode,
            "output": output[:1000],  # Truncate for context limits
        })

    except subprocess.TimeoutExpired:
        logger.error(f"[SyntaxValidator] Test execution timeout (120s): {file_path}")
        return json.dumps({
            "success": False,
            "error": "Test execution timeout (120s)",
            "file_path": file_path,
        })

    except FileNotFoundError:
        logger.error(f"[SyntaxValidator] Test file not found: {file_path}")
        return json.dumps({
            "success": False,
            "error": f"Test file not found: {file_path}",
            "file_path": file_path,
        })

    except Exception as e:
        logger.error(f"[SyntaxValidator] Unexpected error running tests: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "file_path": file_path,
        })


# =============================================================================
# Helper Functions (Not Exposed as Tools)
# =============================================================================


def validate_python_syntax_sync(code: str, filename: str = "<string>") -> Dict[str, Any]:
    """
    Synchronous version of validate_python_ast_tool for internal use.

    Args:
        code: Python source code
        filename: Filename for error reporting

    Returns:
        Dict with validation result (same format as tool)
    """
    try:
        ast.parse(code, filename=filename)
        return {
            "valid": True,
            "filename": filename,
        }
    except SyntaxError as e:
        return {
            "valid": False,
            "error": e.msg,
            "line_number": e.lineno,
            "offset": e.offset,
            "filename": filename,
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "filename": filename,
        }
