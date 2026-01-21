#!/usr/bin/env python3
"""
BUG-025: Automated Tool Compliance Validator

Validates that ALL @tool decorated functions follow Strands patterns:
1. Have proper docstrings with Args section
2. Have type hints for all parameters
3. Have return type annotation
4. Don't use google.genai SDK directly

Usage:
    python scripts/validate_tools.py
    python scripts/validate_tools.py --strict  # Fail on warnings
    python scripts/validate_tools.py --verbose  # Show all checked files

Exit codes:
    0 - All tools compliant
    1 - Compliance errors found
    2 - Invalid arguments
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple, Set
import argparse


class ToolValidator:
    """Validates Strands @tool decorated functions for compliance."""

    # Parameters that don't require Args documentation
    SKIP_ARGS = {"self", "tool_context", "cls"}

    # SDK patterns that indicate violations
    # Note: Strings are constructed to avoid false positive on this file itself
    SDK_VIOLATIONS = [
        "from " + "google import genai",
        "from " + "google.genai",
        "import " + "google.genai",
    ]

    def __init__(self, root: Path, verbose: bool = False):
        self.root = root
        self.verbose = verbose
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.files_checked = 0
        self.tools_found = 0

    def find_tool_functions(self, file_path: Path) -> List[Tuple[str, ast.FunctionDef]]:
        """Find all @tool decorated functions in a file.

        Args:
            file_path: Path to Python file to analyze

        Returns:
            List of tuples (file_path_str, function_node)
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except SyntaxError as e:
            self.errors.append(f"{file_path}: Syntax error - {e}")
            return []

        tools = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    # Check for @tool decorator
                    if self._is_tool_decorator(decorator):
                        tools.append((str(file_path), node))
                        break
        return tools

    def _is_tool_decorator(self, decorator: ast.expr) -> bool:
        """Check if a decorator is the @tool decorator.

        Args:
            decorator: AST decorator node

        Returns:
            True if this is the @tool decorator
        """
        # @tool
        if isinstance(decorator, ast.Name) and decorator.id == "tool":
            return True
        # @tool(...) with arguments
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name) and decorator.func.id == "tool":
                return True
            # @strands.tool
            if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "tool":
                return True
        # @strands.tool
        if isinstance(decorator, ast.Attribute) and decorator.attr == "tool":
            return True
        return False

    def validate_tool(self, file_path: str, func: ast.FunctionDef) -> List[str]:
        """Validate a @tool function follows Strands patterns.

        Args:
            file_path: Path to the file containing the function
            func: AST node for the function

        Returns:
            List of error messages
        """
        errors = []
        func_name = func.name
        line = func.lineno

        # 1. Check docstring exists
        docstring = ast.get_docstring(func)
        if not docstring:
            errors.append(f"{file_path}:{line} - {func_name}: Missing docstring")
        else:
            # 2. Check Args section in docstring if function has parameters
            real_args = [
                a for a in func.args.args
                if a.arg not in self.SKIP_ARGS
            ]
            if real_args and "Args:" not in docstring:
                errors.append(
                    f"{file_path}:{line} - {func_name}: "
                    "Missing 'Args:' section in docstring"
                )

        # 3. Check type hints for all parameters
        for arg in func.args.args:
            if arg.arg in self.SKIP_ARGS:
                continue
            if arg.annotation is None:
                errors.append(
                    f"{file_path}:{line} - {func_name}: "
                    f"Missing type hint for parameter '{arg.arg}'"
                )

        # 4. Check return type annotation
        if func.returns is None:
            errors.append(
                f"{file_path}:{line} - {func_name}: "
                "Missing return type annotation"
            )

        return errors

    def check_sdk_violations(self, file_path: Path) -> List[str]:
        """Check for direct google.genai SDK usage.

        Args:
            file_path: Path to Python file to check

        Returns:
            List of error messages for violations found
        """
        errors = []
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            self.warnings.append(f"{file_path}: Could not read - {e}")
            return errors

        for violation in self.SDK_VIOLATIONS:
            if violation in content:
                errors.append(
                    f"{file_path}: VIOLATION - Uses google.genai SDK directly "
                    "(must use Strands Agent framework)"
                )
        return errors

    def validate_directory(self) -> bool:
        """Validate all Python files in the root directory.

        Returns:
            True if all tools are compliant, False otherwise
        """
        # Find all Python files (excluding venv, __pycache__, etc.)
        exclude_dirs = {
            "__pycache__", ".venv", "venv", ".git", "node_modules",
            ".pytest_cache", ".mypy_cache", "dist", "build",
        }

        for py_file in self.root.rglob("*.py"):
            # Skip excluded directories
            if any(excluded in py_file.parts for excluded in exclude_dirs):
                continue

            self.files_checked += 1

            # Check for SDK violations
            sdk_errors = self.check_sdk_violations(py_file)
            self.errors.extend(sdk_errors)

            # Find and validate @tool functions
            tools = self.find_tool_functions(py_file)
            for file_path, func in tools:
                self.tools_found += 1
                errors = self.validate_tool(file_path, func)
                self.errors.extend(errors)

        if self.verbose:
            print(f"Files checked: {self.files_checked}")
            print(f"Tools found: {self.tools_found}")

        return len(self.errors) == 0

    def report(self) -> None:
        """Print validation report to stdout."""
        if self.errors:
            print("\n❌ TOOL COMPLIANCE ERRORS:")
            for error in sorted(set(self.errors)):
                print(f"  {error}")
            print(f"\nTotal errors: {len(self.errors)}")
        else:
            print(f"\n✅ All {self.tools_found} tools are Strands compliant!")
            print(f"   Files checked: {self.files_checked}")

        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in sorted(set(self.warnings)):
                print(f"  {warning}")


def main():
    """Main entry point for tool validation."""
    parser = argparse.ArgumentParser(
        description="Validate Strands @tool functions for compliance"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings as well as errors"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to validate (default: auto-detect)"
    )
    args = parser.parse_args()

    # Auto-detect root path
    if args.path:
        root = args.path
    else:
        # Try common locations
        candidates = [
            Path("server/agentcore-inventory"),
            Path("agentcore-inventory"),
            Path("."),
        ]
        root = None
        for candidate in candidates:
            if candidate.exists() and (candidate / "agents").exists():
                root = candidate
                break
        if root is None:
            print("ERROR: Could not find agentcore-inventory directory")
            print("Please run from repo root or specify --path")
            sys.exit(2)

    if not root.exists():
        print(f"ERROR: Path does not exist: {root}")
        sys.exit(2)

    if args.verbose:
        print(f"Validating tools in: {root.absolute()}")

    validator = ToolValidator(root, verbose=args.verbose)
    is_valid = validator.validate_directory()
    validator.report()

    if not is_valid:
        sys.exit(1)
    if args.strict and validator.warnings:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
