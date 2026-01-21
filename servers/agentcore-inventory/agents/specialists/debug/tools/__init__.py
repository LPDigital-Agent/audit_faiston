# =============================================================================
# DebugAgent Tools - Module Exports
# =============================================================================
# Tool implementations for the DebugAgent specialist.
#
# Tools:
# - analyze_error: Deep error analysis with root cause identification
# - search_documentation: MCP-based documentation search
# - query_memory_patterns: Historical error pattern lookup
# - store_resolution: Store successful resolutions
# - search_stackoverflow: Real-time Stack Exchange API search (BUG-034)
# - search_github_issues: Real-time GitHub Issues search (BUG-034)
# =============================================================================

from agents.specialists.debug.tools.analyze_error import analyze_error_tool
from agents.specialists.debug.tools.search_documentation import search_documentation_tool
from agents.specialists.debug.tools.query_memory_patterns import query_memory_patterns_tool
from agents.specialists.debug.tools.store_resolution import store_resolution_tool
from agents.specialists.debug.tools.search_stackoverflow import search_stackoverflow_tool
from agents.specialists.debug.tools.search_github_issues import search_github_issues_tool

__all__ = [
    "analyze_error_tool",
    "search_documentation_tool",
    "query_memory_patterns_tool",
    "store_resolution_tool",
    "search_stackoverflow_tool",
    "search_github_issues_tool",
]
