# =============================================================================
# DebugAgent Tools - Module Exports
# =============================================================================
# Tool implementations for the DebugAgent specialist.
#
# Tools:
# - read_code_snippet: Source code inspection at error locations (v2 - NEW)
# - analyze_error: Deep error analysis with root cause identification
# - search_documentation: MCP-based documentation search
# - query_memory_patterns: Historical error pattern lookup
# - store_resolution: Store successful resolutions
# - search_stackoverflow: Real-time Stack Exchange API search
# - search_github_issues: Real-time GitHub Issues search
# =============================================================================

# DebugAgent v2: Code Inspector Tool (USE FIRST for stack traces)
from agents.specialists.debug.tools.code_inspector import read_code_snippet_tool

# Core analysis tools
from agents.specialists.debug.tools.analyze_error import analyze_error_tool
from agents.specialists.debug.tools.search_documentation import search_documentation_tool
from agents.specialists.debug.tools.query_memory_patterns import query_memory_patterns_tool
from agents.specialists.debug.tools.store_resolution import store_resolution_tool
from agents.specialists.debug.tools.search_stackoverflow import search_stackoverflow_tool
from agents.specialists.debug.tools.search_github_issues import search_github_issues_tool

__all__ = [
    # v2 Investigation Tool (USE FIRST)
    "read_code_snippet_tool",
    # Core analysis
    "analyze_error_tool",
    "search_documentation_tool",
    "query_memory_patterns_tool",
    "store_resolution_tool",
    # External search
    "search_stackoverflow_tool",
    "search_github_issues_tool",
]
