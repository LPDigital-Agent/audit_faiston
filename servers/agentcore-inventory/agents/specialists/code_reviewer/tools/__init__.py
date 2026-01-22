# =============================================================================
# Code Reviewer Tools Package
# =============================================================================
# Export all tools for CodeReviewerAgent.
#
# Tools:
# - ast_analyzer_tool: McCabe complexity and type annotation analysis
# - security_scanner_tool: OWASP Top 10 vulnerability detection
# - coverage_calculator_tool: Test coverage measurement via pytest-cov
# =============================================================================

from agents.specialists.code_reviewer.tools.ast_analyzer import (
    ast_analyzer_tool,
    analyze_python_file_sync,
)

from agents.specialists.code_reviewer.tools.security_scanner import (
    security_scanner_tool,
    scan_python_file_sync,
)

from agents.specialists.code_reviewer.tools.coverage_calculator import (
    coverage_calculator_tool,
    calculate_coverage_sync,
    get_uncovered_functions,
)

__all__ = [
    # Strands tools (async)
    "ast_analyzer_tool",
    "security_scanner_tool",
    "coverage_calculator_tool",
    # Helper functions (sync)
    "analyze_python_file_sync",
    "scan_python_file_sync",
    "calculate_coverage_sync",
    "get_uncovered_functions",
]
