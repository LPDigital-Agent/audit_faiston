# =============================================================================
# Coverage Calculator Tools for CodeReviewerAgent
# =============================================================================
# Test coverage analysis for Python code using pytest-cov.
#
# Coverage Thresholds (Industry Standard):
# - 90-100%: Excellent coverage
# - 80-89%: Good coverage
# - 70-79%: Acceptable coverage (INFO)
# - 60-69%: Low coverage (WARNING)
# - < 60%: Very low coverage (CRITICAL)
#
# Coverage Types:
# - Line Coverage: % of lines executed by tests
# - Branch Coverage: % of decision branches taken
# - Function Coverage: % of functions called by tests
#
# Integration:
# - Uses pytest with --cov flag
# - Parses coverage.py JSON report
# - Identifies uncovered lines and branches
# =============================================================================

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from strands.tools import tool

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes for Coverage Results
# =============================================================================


@dataclass
class FileCoverage:
    """Coverage data for a single file."""
    filename: str
    line_coverage: float
    lines_covered: int
    lines_total: int
    uncovered_lines: List[int]
    branch_coverage: Optional[float] = None
    branches_covered: Optional[int] = None
    branches_total: Optional[int] = None


@dataclass
class CoverageFinding:
    """Low coverage finding."""
    filename: str
    line_coverage: float
    threshold: float
    severity: str  # "critical", "warning", "info"
    uncovered_lines: List[int]
    recommendation: str


# =============================================================================
# Coverage Calculator Tool (Strands Tool Interface)
# =============================================================================


@tool
async def coverage_calculator_tool(
    file_path: str,
    test_path: Optional[str] = None,
    coverage_threshold: float = 80.0,
) -> str:
    """
    Calculate test coverage for Python files using pytest-cov.

    Runs pytest with coverage analysis and returns detailed coverage metrics:
    - Line coverage percentage
    - Uncovered line numbers
    - Branch coverage (if available)
    - Coverage violations (files below threshold)

    Coverage Thresholds:
    - 90-100%: Excellent
    - 80-89%: Good
    - 70-79%: Acceptable (INFO)
    - 60-69%: Low (WARNING)
    - < 60%: Very low (CRITICAL)

    Args:
        file_path: Path to Python file to measure coverage for (e.g., "agents/specialists/intake/main.py")
        test_path: Optional path to test file (e.g., "tests/unit/test_intake.py").
                   If not provided, pytest will discover tests automatically.
        coverage_threshold: Minimum acceptable coverage percentage (default: 80.0)

    Returns:
        JSON string with coverage results:
        {
            "success": true,
            "file_path": "agents/specialists/intake/main.py",
            "coverage": {
                "filename": "agents/specialists/intake/main.py",
                "line_coverage": 85.5,
                "lines_covered": 171,
                "lines_total": 200,
                "uncovered_lines": [42, 43, 87, 88, 89],
                "branch_coverage": 75.0,
                "branches_covered": 15,
                "branches_total": 20
            },
            "findings": [
                {
                    "filename": "agents/specialists/intake/main.py",
                    "line_coverage": 85.5,
                    "threshold": 80.0,
                    "severity": "info",
                    "uncovered_lines": [42, 43, 87, 88, 89],
                    "recommendation": "Adicionar testes para 5 linhas não cobertas"
                }
            ],
            "tests_passed": true,
            "test_output": "pytest output (truncated)"
        }

    Example:
        # Test coverage for specific file
        result = await coverage_calculator_tool(
            file_path="agents/specialists/intake/main.py",
            test_path="tests/unit/test_intake.py",
            coverage_threshold=80.0
        )

        # Auto-discover tests
        result = await coverage_calculator_tool(
            file_path="agents/specialists/intake/main.py",
            coverage_threshold=80.0
        )
    """
    try:
        # Create temporary directory for coverage data
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / ".coverage"
            json_report = Path(tmpdir) / "coverage.json"

            # Build pytest command with coverage
            cmd = [
                "python", "-m", "pytest",
                "--cov=" + str(Path(file_path).parent),  # Coverage for directory containing file
                "--cov-report=json:" + str(json_report),
                "--cov-report=term",
                "-v",
                "--tb=short",
            ]

            # Add test path if provided
            if test_path:
                cmd.append(test_path)

            logger.info(f"[CoverageCalculator] Running: {' '.join(cmd)}")

            # Execute pytest with coverage
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,  # 3 minutes max
                cwd=Path(file_path).parent.parent.parent,  # Run from repo root
            )

            tests_passed = result.returncode == 0
            test_output = result.stdout + result.stderr

            # Check if coverage report was generated
            if not json_report.exists():
                logger.error(f"[CoverageCalculator] Coverage report not generated")
                return json.dumps({
                    "success": False,
                    "error": "Coverage report not generated - pytest may have failed",
                    "test_output": test_output[:1000],
                })

            # Parse coverage JSON report
            with open(json_report, "r") as f:
                coverage_data = json.load(f)

            # Extract coverage for target file
            file_coverage = None
            findings = []

            # Normalize file path for matching
            target_file = str(Path(file_path).resolve())

            for file, data in coverage_data.get("files", {}).items():
                file_abs = str(Path(file).resolve())

                # Check if this is our target file
                if file_abs == target_file or file.endswith(Path(file_path).name):
                    # Extract coverage metrics
                    summary = data.get("summary", {})
                    line_coverage = summary.get("percent_covered", 0.0)
                    lines_covered = summary.get("covered_lines", 0)
                    lines_total = summary.get("num_statements", 0)

                    # Get uncovered lines
                    uncovered_lines = data.get("missing_lines", [])

                    # Branch coverage (if available)
                    branch_coverage = summary.get("percent_covered_display", None)
                    branches_covered = summary.get("covered_branches", None)
                    branches_total = summary.get("num_branches", None)

                    file_coverage = FileCoverage(
                        filename=file_path,
                        line_coverage=line_coverage,
                        lines_covered=lines_covered,
                        lines_total=lines_total,
                        uncovered_lines=uncovered_lines,
                        branch_coverage=branch_coverage,
                        branches_covered=branches_covered,
                        branches_total=branches_total,
                    )

                    # Check for coverage violations
                    if line_coverage < coverage_threshold:
                        # Determine severity
                        if line_coverage < 60.0:
                            severity = "critical"
                        elif line_coverage < 70.0:
                            severity = "warning"
                        else:
                            severity = "info"

                        num_uncovered = len(uncovered_lines)
                        finding = CoverageFinding(
                            filename=file_path,
                            line_coverage=line_coverage,
                            threshold=coverage_threshold,
                            severity=severity,
                            uncovered_lines=uncovered_lines,
                            recommendation=f"Adicionar testes para {num_uncovered} linhas não cobertas (coverage atual: {line_coverage:.1f}%, alvo: {coverage_threshold:.1f}%)",
                        )
                        findings.append(finding)

                    break

            # If file not found in coverage report
            if file_coverage is None:
                logger.warning(f"[CoverageCalculator] File not found in coverage report: {file_path}")
                return json.dumps({
                    "success": False,
                    "error": f"File not found in coverage report: {file_path}",
                    "test_output": test_output[:1000],
                })

            logger.info(
                f"[CoverageCalculator] Coverage for {file_path}: "
                f"{file_coverage.line_coverage:.1f}% "
                f"({file_coverage.lines_covered}/{file_coverage.lines_total} lines)"
            )

            return json.dumps({
                "success": True,
                "file_path": file_path,
                "coverage": {
                    "filename": file_coverage.filename,
                    "line_coverage": round(file_coverage.line_coverage, 1),
                    "lines_covered": file_coverage.lines_covered,
                    "lines_total": file_coverage.lines_total,
                    "uncovered_lines": file_coverage.uncovered_lines,
                    "branch_coverage": round(file_coverage.branch_coverage, 1) if file_coverage.branch_coverage else None,
                    "branches_covered": file_coverage.branches_covered,
                    "branches_total": file_coverage.branches_total,
                },
                "findings": [
                    {
                        "filename": f.filename,
                        "line_coverage": round(f.line_coverage, 1),
                        "threshold": f.threshold,
                        "severity": f.severity,
                        "uncovered_lines": f.uncovered_lines,
                        "recommendation": f.recommendation,
                    }
                    for f in findings
                ],
                "tests_passed": tests_passed,
                "test_output": test_output[:1000],  # Truncate for context limits
            })

    except subprocess.TimeoutExpired:
        logger.error(f"[CoverageCalculator] Coverage calculation timeout (180s): {file_path}")
        return json.dumps({
            "success": False,
            "error": "Coverage calculation timeout (180s)",
            "file_path": file_path,
        })

    except FileNotFoundError as e:
        logger.error(f"[CoverageCalculator] File not found: {e}")
        return json.dumps({
            "success": False,
            "error": f"File not found: {e}",
            "file_path": file_path,
        })

    except json.JSONDecodeError as e:
        logger.error(f"[CoverageCalculator] Failed to parse coverage report: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to parse coverage report: {e}",
            "file_path": file_path,
        })

    except Exception as e:
        logger.error(f"[CoverageCalculator] Unexpected error calculating coverage: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "file_path": file_path,
        })


# =============================================================================
# Helper Functions (Not Exposed as Tools)
# =============================================================================


def calculate_coverage_sync(
    file_path: str,
    test_path: Optional[str] = None,
    coverage_threshold: float = 80.0,
) -> Dict[str, Any]:
    """
    Synchronous version of coverage_calculator_tool for internal use.

    Args:
        file_path: Path to Python file
        test_path: Optional path to test file
        coverage_threshold: Minimum acceptable coverage

    Returns:
        Dict with coverage results (same format as tool)
    """
    # Implementation would be similar to the async version
    # For now, return a placeholder
    return {
        "success": False,
        "error": "Synchronous coverage calculation not yet implemented",
        "file_path": file_path,
    }


def get_uncovered_functions(
    file_path: str,
    uncovered_lines: List[int],
) -> List[str]:
    """
    Identify which functions contain uncovered lines.

    Args:
        file_path: Path to Python file
        uncovered_lines: List of uncovered line numbers

    Returns:
        List of function names with uncovered lines
    """
    try:
        import ast

        with open(file_path, "r") as f:
            code = f.read()

        tree = ast.parse(code, filename=file_path)
        uncovered_functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function contains any uncovered lines
                func_start = node.lineno
                func_end = node.end_lineno if hasattr(node, "end_lineno") else func_start

                for line in uncovered_lines:
                    if func_start <= line <= func_end:
                        if node.name not in uncovered_functions:
                            uncovered_functions.append(node.name)
                        break

        return uncovered_functions

    except Exception as e:
        logger.error(f"[CoverageCalculator] Error identifying uncovered functions: {e}")
        return []
