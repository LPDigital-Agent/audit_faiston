# =============================================================================
# AST Analysis Tools for CodeReviewerAgent
# =============================================================================
# Abstract Syntax Tree analysis for code quality metrics:
# - Cyclomatic complexity calculation (McCabe)
# - Type annotation coverage tracking
# - Function/class structure analysis
# - Complexity violation detection
#
# Used by CodeReviewerAgent to detect maintainability issues and suggest
# refactoring for overly complex code.
#
# Complexity Thresholds (Industry Standard):
# - 1-10: Simple, low risk
# - 11-20: Moderate, medium risk (WARNING)
# - 21-50: Complex, high risk (CRITICAL)
# - 50+: Untestable, very high risk (CRITICAL)
#
# Type Coverage Thresholds:
# - 90-100%: Excellent
# - 70-89%: Good
# - 50-69%: Fair (INFO)
# - < 50%: Poor (WARNING)
# =============================================================================

import ast
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from strands.tools import tool

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes for Analysis Results
# =============================================================================


@dataclass
class FunctionAnalysis:
    """Analysis result for a single function."""
    name: str
    line_number: int
    complexity: int
    num_parameters: int
    has_return_type: bool
    has_parameter_types: bool
    lines_of_code: int
    num_branches: int


@dataclass
class ComplexityFinding:
    """High complexity finding."""
    function_name: str
    line_number: int
    complexity: int
    threshold: int
    severity: str  # "warning" or "critical"
    recommendation: str


# =============================================================================
# McCabe Cyclomatic Complexity Calculator
# =============================================================================


class ComplexityVisitor(ast.NodeVisitor):
    """
    AST visitor that calculates McCabe cyclomatic complexity.

    Complexity = Number of decision points + 1

    Decision points include:
    - if, elif
    - for, while
    - except (each except clause)
    - with
    - and, or (boolean operators)
    - ternary expressions (x if y else z)
    - comprehensions
    """

    def __init__(self):
        self.complexity = 1  # Start at 1
        self.num_branches = 0

    def visit_If(self, node):
        """if, elif statements"""
        self.complexity += 1
        self.num_branches += 1
        # Count elif as separate branches
        if node.orelse:
            if isinstance(node.orelse[0], ast.If):
                # This is an elif
                pass  # Will be counted by recursive visit
            else:
                # This is an else (not a decision point, don't count)
                pass
        self.generic_visit(node)

    def visit_For(self, node):
        """for loops"""
        self.complexity += 1
        self.num_branches += 1
        self.generic_visit(node)

    def visit_While(self, node):
        """while loops"""
        self.complexity += 1
        self.num_branches += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        """except clauses"""
        self.complexity += 1
        self.num_branches += 1
        self.generic_visit(node)

    def visit_With(self, node):
        """with statements"""
        self.complexity += 1
        self.num_branches += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        """Boolean operators (and, or)"""
        # Each additional and/or adds complexity
        self.complexity += len(node.values) - 1
        self.num_branches += len(node.values) - 1
        self.generic_visit(node)

    def visit_IfExp(self, node):
        """Ternary expressions (x if y else z)"""
        self.complexity += 1
        self.num_branches += 1
        self.generic_visit(node)

    def visit_ListComp(self, node):
        """List comprehensions"""
        # Each generator adds complexity
        self.complexity += len(node.generators)
        self.num_branches += len(node.generators)
        self.generic_visit(node)

    def visit_SetComp(self, node):
        """Set comprehensions"""
        self.complexity += len(node.generators)
        self.num_branches += len(node.generators)
        self.generic_visit(node)

    def visit_DictComp(self, node):
        """Dictionary comprehensions"""
        self.complexity += len(node.generators)
        self.num_branches += len(node.generators)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        """Generator expressions"""
        self.complexity += len(node.generators)
        self.num_branches += len(node.generators)
        self.generic_visit(node)


def calculate_complexity(func_node: ast.FunctionDef) -> tuple[int, int]:
    """
    Calculate McCabe cyclomatic complexity for a function.

    Args:
        func_node: AST FunctionDef node

    Returns:
        Tuple of (complexity, num_branches)
    """
    visitor = ComplexityVisitor()
    visitor.visit(func_node)
    return visitor.complexity, visitor.num_branches


# =============================================================================
# Type Annotation Checker
# =============================================================================


def check_type_annotations(func_node: ast.FunctionDef) -> tuple[bool, bool]:
    """
    Check if function has type annotations.

    Args:
        func_node: AST FunctionDef node

    Returns:
        Tuple of (has_return_type, has_parameter_types)
    """
    # Check return type annotation
    has_return_type = func_node.returns is not None

    # Check parameter type annotations
    has_parameter_types = True
    for arg in func_node.args.args:
        if arg.annotation is None:
            has_parameter_types = False
            break

    # Also check *args and **kwargs
    if func_node.args.vararg and func_node.args.vararg.annotation is None:
        has_parameter_types = False
    if func_node.args.kwarg and func_node.args.kwarg.annotation is None:
        has_parameter_types = False

    return has_return_type, has_parameter_types


# =============================================================================
# AST Analysis Tool (Strands Tool Interface)
# =============================================================================


@tool
async def ast_analyzer_tool(
    code: str,
    filename: str,
    complexity_threshold: int = 10,
) -> str:
    """
    Analyze Python code using Abstract Syntax Tree (AST).

    Calculates code quality metrics including:
    - McCabe cyclomatic complexity per function
    - Type annotation coverage
    - Lines of code per function
    - Number of parameters per function
    - Complexity violations (functions exceeding threshold)

    Complexity Levels:
    - 1-10: Simple, low risk
    - 11-20: Moderate, medium risk (WARNING)
    - 21+: Complex, high risk (CRITICAL - requires refactoring)

    Args:
        code: Python source code to analyze
        filename: Filename for error reporting (e.g., "main.py")
        complexity_threshold: Maximum acceptable complexity (default: 10)

    Returns:
        JSON string with analysis results:
        {
            "success": true,
            "filename": "main.py",
            "functions": [
                {
                    "name": "process_data",
                    "line_number": 42,
                    "complexity": 15,
                    "num_parameters": 3,
                    "has_return_type": true,
                    "has_parameter_types": false,
                    "lines_of_code": 50,
                    "num_branches": 12
                }
            ],
            "violations": [
                {
                    "function_name": "process_data",
                    "line_number": 42,
                    "complexity": 15,
                    "threshold": 10,
                    "severity": "warning",
                    "recommendation": "Refatorar em funções menores (complexidade: 15, limite: 10)"
                }
            ],
            "max_complexity": 15,
            "avg_complexity": 8.5,
            "type_coverage": 75.0,
            "total_functions": 4,
            "functions_with_violations": 1
        }

    Example:
        result = await ast_analyzer_tool(
            code="def foo():\\n    if x:\\n        return 1",
            filename="test.py",
            complexity_threshold=10
        )
    """
    try:
        # Parse the code into AST
        tree = ast.parse(code, filename=filename)

        functions: List[FunctionAnalysis] = []
        violations: List[ComplexityFinding] = []

        # Analyze all function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Calculate complexity
                complexity, num_branches = calculate_complexity(node)

                # Check type annotations
                has_return_type, has_parameter_types = check_type_annotations(node)

                # Count parameters
                num_parameters = (
                    len(node.args.args)
                    + len(node.args.posonlyargs)
                    + len(node.args.kwonlyargs)
                )
                if node.args.vararg:
                    num_parameters += 1
                if node.args.kwarg:
                    num_parameters += 1

                # Count lines of code (approximate)
                if hasattr(node, "end_lineno") and node.end_lineno:
                    lines_of_code = node.end_lineno - node.lineno
                else:
                    lines_of_code = 0

                # Create analysis result
                func_analysis = FunctionAnalysis(
                    name=node.name,
                    line_number=node.lineno,
                    complexity=complexity,
                    num_parameters=num_parameters,
                    has_return_type=has_return_type,
                    has_parameter_types=has_parameter_types,
                    lines_of_code=lines_of_code,
                    num_branches=num_branches,
                )
                functions.append(func_analysis)

                # Check for complexity violations
                if complexity > complexity_threshold:
                    severity = "warning" if complexity <= 20 else "critical"
                    violation = ComplexityFinding(
                        function_name=node.name,
                        line_number=node.lineno,
                        complexity=complexity,
                        threshold=complexity_threshold,
                        severity=severity,
                        recommendation=f"Refatorar em funções menores (complexidade: {complexity}, limite: {complexity_threshold})",
                    )
                    violations.append(violation)

        # Calculate aggregate metrics
        total_functions = len(functions)
        if total_functions > 0:
            max_complexity = max(f.complexity for f in functions)
            avg_complexity = sum(f.complexity for f in functions) / total_functions

            # Calculate type coverage
            functions_with_return_type = sum(1 for f in functions if f.has_return_type)
            functions_with_param_types = sum(1 for f in functions if f.has_parameter_types)
            type_coverage = (
                (functions_with_return_type + functions_with_param_types) / (2 * total_functions) * 100
            )
        else:
            max_complexity = 0
            avg_complexity = 0.0
            type_coverage = 0.0

        logger.info(
            f"[ASTAnalyzer] Analyzed {filename}: "
            f"{total_functions} functions, "
            f"max complexity: {max_complexity}, "
            f"avg complexity: {avg_complexity:.1f}, "
            f"type coverage: {type_coverage:.1f}%, "
            f"{len(violations)} violations"
        )

        return json.dumps({
            "success": True,
            "filename": filename,
            "functions": [
                {
                    "name": f.name,
                    "line_number": f.line_number,
                    "complexity": f.complexity,
                    "num_parameters": f.num_parameters,
                    "has_return_type": f.has_return_type,
                    "has_parameter_types": f.has_parameter_types,
                    "lines_of_code": f.lines_of_code,
                    "num_branches": f.num_branches,
                }
                for f in functions
            ],
            "violations": [
                {
                    "function_name": v.function_name,
                    "line_number": v.line_number,
                    "complexity": v.complexity,
                    "threshold": v.threshold,
                    "severity": v.severity,
                    "recommendation": v.recommendation,
                }
                for v in violations
            ],
            "max_complexity": max_complexity,
            "avg_complexity": round(avg_complexity, 1),
            "type_coverage": round(type_coverage, 1),
            "total_functions": total_functions,
            "functions_with_violations": len(violations),
        })

    except SyntaxError as e:
        logger.warning(
            f"[ASTAnalyzer] Syntax error in {filename} "
            f"(line {e.lineno}): {e.msg}"
        )
        return json.dumps({
            "success": False,
            "error": f"SyntaxError: {e.msg}",
            "line_number": e.lineno,
            "filename": filename,
        })

    except Exception as e:
        logger.error(f"[ASTAnalyzer] Unexpected error analyzing {filename}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "filename": filename,
        })


# =============================================================================
# Helper Functions (Not Exposed as Tools)
# =============================================================================


def analyze_python_file_sync(
    code: str,
    filename: str = "<string>",
    complexity_threshold: int = 10,
) -> Dict[str, Any]:
    """
    Synchronous version of ast_analyzer_tool for internal use.

    Args:
        code: Python source code
        filename: Filename for error reporting
        complexity_threshold: Maximum acceptable complexity

    Returns:
        Dict with analysis results (same format as tool)
    """
    try:
        tree = ast.parse(code, filename=filename)
        functions = []
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity, num_branches = calculate_complexity(node)
                has_return_type, has_parameter_types = check_type_annotations(node)

                func_analysis = {
                    "name": node.name,
                    "line_number": node.lineno,
                    "complexity": complexity,
                    "num_branches": num_branches,
                    "has_return_type": has_return_type,
                    "has_parameter_types": has_parameter_types,
                }
                functions.append(func_analysis)

                if complexity > complexity_threshold:
                    severity = "warning" if complexity <= 20 else "critical"
                    violations.append({
                        "function_name": node.name,
                        "line_number": node.lineno,
                        "complexity": complexity,
                        "threshold": complexity_threshold,
                        "severity": severity,
                    })

        return {
            "success": True,
            "filename": filename,
            "functions": functions,
            "violations": violations,
            "total_functions": len(functions),
            "functions_with_violations": len(violations),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "filename": filename,
        }
