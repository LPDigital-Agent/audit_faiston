# =============================================================================
# DebugAgent Tool: search_stackoverflow - Real-time External Search
# =============================================================================
# Real-time Stack Exchange API integration for error debugging.
#
# Unlike search_documentation.py which generates static URLs, this tool
# actually FETCHES answers from Stack Overflow to provide concrete solutions.
#
# API Documentation: https://api.stackexchange.com/docs
#
# Architecture (LLM = Brain / Python = Hands):
# - Python: Handles HTTP requests, rate limiting, response parsing
# - LLM (Debug Agent): Analyzes returned answers, extracts relevant solutions
#
# Rate Limits (no API key):
# - 300 requests per day per IP
# - Compressed responses are gzipped
#
# This tool enables the Debug Agent to find community-sourced solutions
# for errors, making debug_analysis more actionable.
# =============================================================================

import gzip
import json
import logging
from io import BytesIO
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Stack Exchange API configuration
STACK_EXCHANGE_API_URL = "https://api.stackexchange.com/2.3"
DEFAULT_SITE = "stackoverflow"
DEFAULT_PAGESIZE = 5
REQUEST_TIMEOUT = 10.0

# Tags commonly associated with our tech stack
RELEVANT_TAGS = {
    "python", "python-3.x", "aws", "boto3", "json", "asyncio",
    "aws-lambda", "amazon-s3", "pydantic", "fastapi", "httpx",
    "amazon-cognito", "postgresql", "aws-aurora", "async-await",
}


async def search_stackoverflow_tool(
    query: str,
    tags: Optional[List[str]] = None,
    max_results: int = 5,
    include_body: bool = True,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search Stack Overflow for answers related to an error.

    This tool performs a REAL API call to Stack Exchange to fetch
    actual questions and answers, not just generate search URLs.

    Args:
        query: Error message or search query (e.g., "JSONDecodeError python")
        tags: Optional list of tags to filter by (e.g., ["python", "json"])
        max_results: Maximum number of questions to return (1-10)
        include_body: Whether to include answer body in results
        session_id: Session ID for logging context

    Returns:
        Dict with:
        - success: bool
        - questions: List of questions with their top answers
        - total_found: Total number of matching questions
        - search_url: URL to view results in browser

    Example:
        result = await search_stackoverflow_tool(
            query="JSONDecodeError Expecting property name",
            tags=["python", "json"],
            max_results=3
        )

    Raises:
        httpx.TimeoutException: If Stack Exchange API request times out (caught internally).
        httpx.HTTPStatusError: If Stack Exchange API returns error status (caught internally).
    """
    logger.info(
        "[search_stackoverflow] Fetching real SO answers for: %s",
        query[:80]
    )

    # Clamp max_results
    max_results = min(max(1, max_results), 10)

    # Build search parameters
    params = {
        "order": "desc",
        "sort": "relevance",
        "site": DEFAULT_SITE,
        "pagesize": max_results,
        "filter": "withbody" if include_body else "default",
        "q": query,
    }

    # Add tags if provided
    if tags:
        # Filter to known relevant tags
        filtered_tags = [t for t in tags if t.lower() in RELEVANT_TAGS]
        if filtered_tags:
            params["tagged"] = ";".join(filtered_tags[:5])

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # Step 1: Search for questions
            response = await client.get(
                f"{STACK_EXCHANGE_API_URL}/search/advanced",
                params=params,
            )
            response.raise_for_status()

            # Stack Exchange returns gzipped responses
            data = _decompress_response(response.content)

            if not data.get("items"):
                logger.info("[search_stackoverflow] No questions found")
                return {
                    "success": True,
                    "questions": [],
                    "total_found": 0,
                    "search_url": _build_browser_url(query, tags),
                    "message": "Nenhuma pergunta encontrada no Stack Overflow",
                }

            # Step 2: Fetch top answer for each question
            questions = []
            for item in data["items"][:max_results]:
                question_data = {
                    "question_id": item.get("question_id"),
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "score": item.get("score", 0),
                    "is_answered": item.get("is_answered", False),
                    "answer_count": item.get("answer_count", 0),
                    "tags": item.get("tags", []),
                    "creation_date": item.get("creation_date"),
                }

                # Include body if requested
                if include_body and item.get("body"):
                    question_data["body_preview"] = _truncate_html(
                        item.get("body", ""), 500
                    )

                # Fetch accepted/top answer if question is answered
                if item.get("is_answered") and item.get("accepted_answer_id"):
                    answer = await _fetch_answer(
                        client,
                        item["accepted_answer_id"],
                        include_body
                    )
                    if answer:
                        question_data["top_answer"] = answer

                questions.append(question_data)

            logger.info(
                "[search_stackoverflow] Found %d questions with answers",
                len(questions)
            )

            return {
                "success": True,
                "questions": questions,
                "total_found": data.get("total", len(questions)),
                "quota_remaining": data.get("quota_remaining"),
                "search_url": _build_browser_url(query, tags),
            }

    except httpx.TimeoutException:
        logger.warning("[search_stackoverflow] API timeout")
        return {
            "success": False,
            "error": "Stack Overflow API timeout",
            "search_url": _build_browser_url(query, tags),
        }
    except httpx.HTTPStatusError as e:
        logger.warning(
            "[search_stackoverflow] API error: %s %s",
            e.response.status_code,
            e.response.text[:200]
        )
        return {
            "success": False,
            "error": f"Stack Overflow API error: {e.response.status_code}",
            "search_url": _build_browser_url(query, tags),
        }
    except Exception as e:
        logger.exception("[search_stackoverflow] Unexpected error: %s", e)
        return {
            "success": False,
            "error": str(e),
            "search_url": _build_browser_url(query, tags),
        }


async def _fetch_answer(
    client: httpx.AsyncClient,
    answer_id: int,
    include_body: bool
) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific answer by ID.

    Args:
        client: HTTP client
        answer_id: Stack Overflow answer ID
        include_body: Whether to include full answer body

    Returns:
        Answer data or None if failed
    """
    try:
        params = {
            "site": DEFAULT_SITE,
            "filter": "withbody" if include_body else "default",
        }

        response = await client.get(
            f"{STACK_EXCHANGE_API_URL}/answers/{answer_id}",
            params=params,
        )
        response.raise_for_status()

        data = _decompress_response(response.content)

        if data.get("items"):
            item = data["items"][0]
            answer = {
                "answer_id": item.get("answer_id"),
                "is_accepted": item.get("is_accepted", False),
                "score": item.get("score", 0),
            }

            if include_body and item.get("body"):
                # Extract code blocks and key text
                answer["body_preview"] = _truncate_html(item["body"], 1000)
                answer["code_blocks"] = _extract_code_blocks(item["body"])

            return answer

    except Exception as e:
        logger.debug("[_fetch_answer] Failed to fetch answer %d: %s", answer_id, e)

    return None


def _decompress_response(content: bytes) -> Dict[str, Any]:
    """
    Decompress gzipped Stack Exchange API response.

    Stack Exchange always returns gzipped responses for efficiency.

    Args:
        content: Raw response bytes

    Returns:
        Parsed JSON data
    """
    try:
        # Try to decompress as gzip
        with gzip.GzipFile(fileobj=BytesIO(content)) as f:
            return json.loads(f.read().decode("utf-8"))
    except (gzip.BadGzipFile, OSError):
        # Response wasn't gzipped (shouldn't happen but handle gracefully)
        return json.loads(content.decode("utf-8"))


def _truncate_html(html: str, max_length: int = 500) -> str:
    """
    Truncate HTML content, preserving readability.

    Args:
        html: HTML string
        max_length: Maximum length

    Returns:
        Truncated text (HTML tags removed)
    """
    import re

    # Remove HTML tags for cleaner text
    text = re.sub(r"<[^>]+>", " ", html)
    # Normalize whitespace
    text = " ".join(text.split())

    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def _extract_code_blocks(html: str) -> List[str]:
    """
    Extract code blocks from HTML answer.

    Args:
        html: HTML string with <code> or <pre> blocks

    Returns:
        List of code snippets
    """
    import re

    code_blocks = []

    # Extract <pre><code>...</code></pre> blocks (most common)
    pre_pattern = re.compile(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", re.DOTALL)
    for match in pre_pattern.findall(html):
        code = _unescape_html(match.strip())
        if code and len(code) > 10:  # Skip trivial snippets
            code_blocks.append(code[:500])  # Limit size

    # Also extract inline <code> if no blocks found
    if not code_blocks:
        code_pattern = re.compile(r"<code[^>]*>(.*?)</code>", re.DOTALL)
        for match in code_pattern.findall(html)[:3]:  # Max 3 inline
            code = _unescape_html(match.strip())
            if code and len(code) > 10:
                code_blocks.append(code[:200])

    return code_blocks[:5]  # Max 5 code blocks


def _unescape_html(text: str) -> str:
    """Unescape HTML entities."""
    import html
    return html.unescape(text)


def _build_browser_url(query: str, tags: Optional[List[str]] = None) -> str:
    """
    Build Stack Overflow search URL for browser viewing.

    Args:
        query: Search query
        tags: Optional tags

    Returns:
        Browser-friendly search URL
    """
    from urllib.parse import quote_plus

    base = "https://stackoverflow.com/search?q="
    search_query = query

    if tags:
        tag_query = " ".join(f"[{t}]" for t in tags[:3])
        search_query = f"{tag_query} {query}"

    return base + quote_plus(search_query)
