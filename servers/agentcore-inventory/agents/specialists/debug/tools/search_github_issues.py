# =============================================================================
# DebugAgent Tool: search_github_issues (BUG-034)
# =============================================================================
# Real-time GitHub Issues API integration for error debugging.
#
# Primary focus: strands-agents/sdk-python (as per CLAUDE.md mandate)
# Secondary: boto3, pydantic, and other relevant repos
#
# API Documentation: https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests
#
# Architecture (LLM = Brain / Python = Hands):
# - Python: Handles HTTP requests, response parsing, rate limiting
# - LLM (Debug Agent): Analyzes issues, correlates with current error
#
# Rate Limits (unauthenticated):
# - 10 requests per minute
# - 60 requests per hour
#
# BUG-034: This tool enables the Debug Agent to find known issues and
# workarounds from the open source community, especially for Strands Agents.
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# GitHub API configuration
GITHUB_API_URL = "https://api.github.com"
REQUEST_TIMEOUT = 10.0

# Primary repositories for our tech stack (in priority order)
PRIORITY_REPOS = [
    "strands-agents/sdk-python",  # Strands Agents (MANDATORY per CLAUDE.md)
    "strands-agents/tools",        # Strands Tools
    "boto/boto3",                  # boto3 for AWS
    "pydantic/pydantic",           # Pydantic validation
    "encode/httpx",                # httpx HTTP client
]

# Keywords mapped to specific repos
KEYWORD_TO_REPO = {
    "strands": "strands-agents/sdk-python",
    "agent": "strands-agents/sdk-python",
    "swarm": "strands-agents/sdk-python",
    "a2a": "strands-agents/sdk-python",
    "@tool": "strands-agents/sdk-python",
    "boto3": "boto/boto3",
    "botocore": "boto/boto3",
    "aws": "boto/boto3",
    "pydantic": "pydantic/pydantic",
    "validation": "pydantic/pydantic",
    "httpx": "encode/httpx",
}


async def search_github_issues_tool(
    query: str,
    repos: Optional[List[str]] = None,
    include_closed: bool = True,
    max_results: int = 5,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search GitHub Issues for known problems and solutions.

    This tool performs a REAL API call to GitHub to fetch actual issues
    and their discussions, enabling the Debug Agent to find known
    workarounds and solutions.

    Primary focus is on strands-agents/sdk-python as per CLAUDE.md.

    Args:
        query: Error message or search query
        repos: Optional list of repos to search (default: auto-detect from query)
        include_closed: Whether to include closed issues (often have solutions)
        max_results: Maximum number of issues to return (1-10)
        session_id: Session ID for logging context

    Returns:
        Dict with:
        - success: bool
        - issues: List of matching issues with details
        - repos_searched: List of repositories searched
        - search_url: URL to view results in browser

    Example:
        result = await search_github_issues_tool(
            query="Agent loop not calling tools",
            repos=["strands-agents/sdk-python"],
            max_results=5
        )

    Raises:
        httpx.TimeoutException: If GitHub API request times out (caught internally).
        httpx.HTTPStatusError: If GitHub API returns error status (caught internally).
    """
    logger.info(
        "[search_github_issues] BUG-034: Searching GitHub for: %s",
        query[:80]
    )

    # Clamp max_results
    max_results = min(max(1, max_results), 10)

    # Determine repos to search
    search_repos = repos or _detect_repos_from_query(query)
    if not search_repos:
        # Default to Strands (per CLAUDE.md mandate)
        search_repos = ["strands-agents/sdk-python"]

    logger.debug("[search_github_issues] Searching repos: %s", search_repos)

    all_issues = []

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            for repo in search_repos[:3]:  # Max 3 repos to avoid rate limits
                issues = await _search_repo_issues(
                    client,
                    repo,
                    query,
                    include_closed,
                    max_results
                )
                all_issues.extend(issues)

        # Sort by relevance (score) and limit results
        all_issues.sort(key=lambda x: x.get("score", 0), reverse=True)
        all_issues = all_issues[:max_results]

        logger.info(
            "[search_github_issues] Found %d issues across %d repos",
            len(all_issues),
            len(search_repos)
        )

        return {
            "success": True,
            "issues": all_issues,
            "total_found": len(all_issues),
            "repos_searched": search_repos,
            "search_url": _build_github_search_url(query, search_repos),
        }

    except httpx.TimeoutException:
        logger.warning("[search_github_issues] API timeout")
        return {
            "success": False,
            "error": "GitHub API timeout",
            "repos_searched": search_repos,
            "search_url": _build_github_search_url(query, search_repos),
        }
    except httpx.HTTPStatusError as e:
        logger.warning(
            "[search_github_issues] API error: %s",
            e.response.status_code
        )
        return {
            "success": False,
            "error": f"GitHub API error: {e.response.status_code}",
            "repos_searched": search_repos,
            "search_url": _build_github_search_url(query, search_repos),
        }
    except Exception as e:
        logger.exception("[search_github_issues] Unexpected error: %s", e)
        return {
            "success": False,
            "error": str(e),
            "repos_searched": search_repos,
            "search_url": _build_github_search_url(query, search_repos),
        }


async def _search_repo_issues(
    client: httpx.AsyncClient,
    repo: str,
    query: str,
    include_closed: bool,
    max_results: int,
) -> List[Dict[str, Any]]:
    """
    Search issues in a specific repository.

    Args:
        client: HTTP client
        repo: Repository in "owner/name" format
        query: Search query
        include_closed: Include closed issues
        max_results: Maximum results

    Returns:
        List of issue data
    """
    # Build search query
    # Format: query repo:owner/name state:open|closed
    state_filter = "" if include_closed else "state:open"
    search_q = f"{query} repo:{repo} is:issue {state_filter}".strip()

    params = {
        "q": search_q,
        "sort": "relevance",
        "order": "desc",
        "per_page": max_results,
    }

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = await client.get(
            f"{GITHUB_API_URL}/search/issues",
            params=params,
            headers=headers,
        )
        response.raise_for_status()

        data = response.json()
        issues = []

        for item in data.get("items", [])[:max_results]:
            issue = {
                "repo": repo,
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),  # "open" or "closed"
                "html_url": item.get("html_url"),
                "score": item.get("score", 0),
                "comments_count": item.get("comments", 0),
                "created_at": item.get("created_at"),
                "closed_at": item.get("closed_at"),
                "labels": [
                    label.get("name")
                    for label in item.get("labels", [])
                ],
            }

            # Include body preview
            body = item.get("body", "")
            if body:
                issue["body_preview"] = _truncate_text(body, 500)

            # If closed, likely has a solution
            if item.get("state") == "closed":
                issue["likely_has_solution"] = True

            issues.append(issue)

        return issues

    except Exception as e:
        logger.debug(
            "[_search_repo_issues] Failed to search %s: %s",
            repo, e
        )
        return []


def _detect_repos_from_query(query: str) -> List[str]:
    """
    Auto-detect relevant repositories from query keywords.

    Args:
        query: Search query

    Returns:
        List of repositories to search
    """
    query_lower = query.lower()
    detected = set()

    for keyword, repo in KEYWORD_TO_REPO.items():
        if keyword in query_lower:
            detected.add(repo)

    # Always include Strands as primary (per CLAUDE.md)
    if not detected:
        detected.add("strands-agents/sdk-python")

    return list(detected)


def _truncate_text(text: str, max_length: int = 500) -> str:
    """
    Truncate text to max length.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    # Normalize whitespace
    text = " ".join(text.split())

    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def _build_github_search_url(
    query: str,
    repos: List[str]
) -> str:
    """
    Build GitHub search URL for browser viewing.

    Args:
        query: Search query
        repos: Repositories to search

    Returns:
        Browser-friendly GitHub search URL
    """
    from urllib.parse import quote_plus

    # Build repo filter
    repo_filter = " ".join(f"repo:{r}" for r in repos[:3])

    search_q = f"{query} {repo_filter} is:issue"
    return f"https://github.com/search?q={quote_plus(search_q)}&type=issues"
