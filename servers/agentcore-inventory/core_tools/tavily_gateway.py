# =============================================================================
# Tavily Gateway Adapter for Equipment Enrichment
# =============================================================================
# MCP client wrapper for Tavily tools via AgentCore Gateway (built-in template).
#
# Per CLAUDE.md MCP ACCESS POLICY:
# > ALL MCP tools and servers MUST be accessed ONLY via AWS Bedrock AgentCore Gateway.
#
# Gateway Configuration (Created via AWS Console - January 2026):
#     Gateway ID: faiston-one-sga-gateway-tavily-se9zyznpyo
#     Gateway URL: https://faiston-one-sga-gateway-tavily-se9zyznpyo.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp
#     Auth Type: CUSTOM_JWT (Cognito OAuth2)
#     Target Name: target-tavily
#
# Architecture:
#     EnrichmentAgent -> TavilyGatewayAdapter -> CognitoMCPClient (OAuth2) ->
#     AgentCore Gateway -> Tavily API (Built-in Template)
#
# Tool Naming Convention (per AWS docs):
#     Format: {TargetName}___{ToolName} (THREE underscores)
#     Example: target-tavily___TavilySearchPost
#
# Available Tools (Built-in Tavily Template):
#     - TavilySearchPost: AI-optimized web search (POST /search)
#     - TavilySearchExtract: Content extraction from URLs (POST /extract)
#
# NOTE: The built-in Tavily template does NOT include crawl/map tools.
#       Only search and extract are available.
#
# Reference:
#     - PRD: product-development/current-feature/PRD-tavily-enrichment.md
#     - AWS Tavily Integration: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-integrations.html
#
# Author: Faiston NEXO Team
# Date: January 2026
# Updated: January 2026 - Use built-in Tavily template with OAuth2 (Cognito)
# =============================================================================

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core_tools.cognito_mcp_client import CognitoMCPClient, CognitoMCPClientFactory

logger = logging.getLogger(__name__)


# =============================================================================
# Constants - Tavily Gateway Configuration
# =============================================================================

# Gateway details (from AWS Console creation)
TAVILY_GATEWAY_ID = "faiston-one-sga-gateway-tavily-se9zyznpyo"
TAVILY_GATEWAY_URL = f"https://{TAVILY_GATEWAY_ID}.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp"
TAVILY_TOKEN_URL = "https://my-domain-ze9v2zyh.auth.us-east-2.amazoncognito.com/oauth2/token"
TAVILY_COGNITO_CLIENT_ID = "5nq8g72i81uc25dd966tht601p"


# =============================================================================
# Types and Enums
# =============================================================================


class SearchDepth(str, Enum):
    """Search depth for Tavily queries."""
    BASIC = "basic"
    ADVANCED = "advanced"


class SearchTopic(str, Enum):
    """Topic type for Tavily search."""
    GENERAL = "general"
    NEWS = "news"


class TimeRange(str, Enum):
    """Time range filter for search results."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class ExtractFormat(str, Enum):
    """Output format for content extraction."""
    MARKDOWN = "markdown"
    TEXT = "text"


@dataclass
class SearchResult:
    """A single search result from Tavily."""
    url: str
    title: str
    content: str
    raw_content: Optional[str] = None
    favicon: Optional[str] = None
    relevance_score: float = 0.0


@dataclass
class ExtractResult:
    """Content extracted from a URL."""
    url: str
    title: str
    content: str
    raw_content: Optional[str] = None
    favicon: Optional[str] = None
    images: List[str] = field(default_factory=list)


# =============================================================================
# Tavily Gateway Adapter
# =============================================================================


class TavilyGatewayAdapter:
    """
    Adapter for Tavily tools via AgentCore Gateway (built-in template).

    This adapter uses the AWS-provided Tavily integration template which
    provides search and extract capabilities through the MCP protocol.

    The adapter handles:
    - Tool name prefixing with target name (target-tavily___)
    - OAuth2 authentication via Cognito
    - Argument serialization
    - Response parsing into typed dataclasses
    - Error handling with sensible defaults

    Note: Uses CognitoMCPClient for OAuth2 authentication (CUSTOM_JWT).
          NOT SigV4/IAM - the Tavily Gateway uses Cognito for auth.

    Attributes:
        TARGET_PREFIX: MCP target name for Tavily tools (target-tavily)
        _client: CognitoMCPClient instance for Gateway communication

    Example:
        ```python
        adapter = TavilyGatewayAdapter.create_from_env()

        # Search for equipment documentation
        results = adapter.search(
            query="Cisco C9200-24P datasheet PDF",
            search_depth=SearchDepth.ADVANCED,
            include_domains=["cisco.com"],
            max_results=5,
        )

        # Extract content from official page
        extracted = adapter.extract(
            urls=["https://cisco.com/c9200-datasheet"],
            extract_depth="advanced",
            format=ExtractFormat.MARKDOWN,
        )
        ```
    """

    # MCP target name (from AWS Console - built-in Tavily template)
    TARGET_PREFIX = "target-tavily"

    def __init__(self, mcp_client: CognitoMCPClient):
        """
        Initialize Tavily Gateway Adapter.

        Args:
            mcp_client: Configured CognitoMCPClient for Gateway communication
        """
        self._client = mcp_client
        logger.info("[TavilyGatewayAdapter] Initialized with Cognito OAuth2 client")

    def _tool_name(self, tool: str) -> str:
        """
        Build full tool name with target prefix.

        Per AWS MCP Gateway convention, tools are prefixed with:
        {TargetName}___{ToolName} (THREE underscores)

        Available tools in built-in Tavily template:
        - TavilySearchPost -> POST /search
        - TavilySearchExtract -> POST /extract

        Args:
            tool: Base tool name (e.g., "TavilySearchPost")

        Returns:
            Full tool name (e.g., "target-tavily___TavilySearchPost")
        """
        return f"{self.TARGET_PREFIX}___{tool}"

    def _clean_none_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove None values from dictionary for cleaner MCP calls.

        Args:
            data: Dictionary potentially containing None values

        Returns:
            Dictionary with None values removed
        """
        return {k: v for k, v in data.items() if v is not None}

    # =========================================================================
    # TavilySearchPost: AI-Optimized Web Search
    # =========================================================================

    def search(
        self,
        query: str,
        search_depth: SearchDepth = SearchDepth.BASIC,
        topic: SearchTopic = SearchTopic.GENERAL,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_images: bool = False,
        include_raw_content: bool = False,
        include_answer: bool = True,
        time_range: Optional[TimeRange] = None,
        days: Optional[int] = None,
        country: Optional[str] = None,
        timeout: int = 60,
    ) -> List[SearchResult]:
        """
        Search the web using Tavily's AI-optimized search engine.

        Uses the built-in TavilySearchPost tool via Gateway MCP.

        Tavily search is optimized for AI agents and provides:
        - Relevant, high-quality results
        - Domain filtering for official sources
        - Raw content extraction for RAG pipelines
        - Image extraction for documentation

        Args:
            query: Search query (e.g., "Cisco C9200-24P specifications PDF")
            search_depth: BASIC (fast) or ADVANCED (comprehensive)
            topic: GENERAL or NEWS
            max_results: Maximum results to return (default 5)
            include_domains: Only include results from these domains
            exclude_domains: Exclude results from these domains
            include_images: Include images in results
            include_raw_content: Include full page content
            include_answer: Include AI-generated answer summary
            time_range: Filter by time (day, week, month, year)
            days: Number of days for news search
            country: Country for localized results
            timeout: Request timeout in seconds

        Returns:
            List of SearchResult objects with url, title, content

        Example:
            ```python
            # Search for official Cisco documentation
            results = adapter.search(
                query="Cisco C9200-24P datasheet",
                search_depth=SearchDepth.ADVANCED,
                include_domains=["cisco.com"],
                include_raw_content=True,
            )
            ```
        """
        logger.info(f"[TavilyGatewayAdapter] search: query='{query[:50]}...'")

        arguments = self._clean_none_values({
            "query": query,
            "search_depth": search_depth.value,
            "topic": topic.value,
            "max_results": max_results,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "include_images": include_images,
            "include_raw_content": include_raw_content,
            "include_answer": include_answer,
            "time_range": time_range.value if time_range else None,
            "days": days,
            "country": country,
        })

        try:
            result = self._client.call_tool(
                tool_name=self._tool_name("TavilySearchPost"),
                arguments=arguments,
                timeout=timeout,
            )

            # Parse response into SearchResult objects
            results = self._parse_search_results(result)
            logger.info(f"[TavilyGatewayAdapter] search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"[TavilyGatewayAdapter] search failed: {e}")
            return []

    def _parse_search_results(self, response: Dict[str, Any]) -> List[SearchResult]:
        """Parse Tavily search response into SearchResult objects."""
        results = []

        # Handle different response structures
        items = response.get("results", response.get("items", []))
        if not isinstance(items, list):
            items = [response] if "url" in response else []

        for item in items:
            try:
                results.append(SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("content", item.get("snippet", "")),
                    raw_content=item.get("raw_content"),
                    favicon=item.get("favicon"),
                    relevance_score=float(item.get("score", item.get("relevance_score", 0.5))),
                ))
            except Exception as e:
                logger.warning(f"[TavilyGatewayAdapter] Failed to parse result: {e}")

        return results

    # =========================================================================
    # TavilySearchExtract: Content Extraction from URLs
    # =========================================================================

    def extract(
        self,
        urls: List[str],
        extract_depth: str = "basic",
        format: ExtractFormat = ExtractFormat.MARKDOWN,
        include_images: bool = False,
        include_favicon: bool = False,
        timeout: int = 120,
    ) -> List[ExtractResult]:
        """
        Extract and process content from specified URLs.

        Uses the built-in TavilySearchExtract tool via Gateway MCP.

        Useful for:
        - Extracting datasheet content from manufacturer sites
        - Processing documentation pages into structured text
        - Batch extraction from multiple URLs

        Args:
            urls: List of URLs to extract content from
            extract_depth: "basic" or "advanced"
            format: Output format (MARKDOWN or TEXT)
            include_images: Extract images from pages
            include_favicon: Include favicon URLs
            timeout: Request timeout in seconds

        Returns:
            List of ExtractResult objects with extracted content

        Example:
            ```python
            # Extract content from Cisco datasheet
            extracted = adapter.extract(
                urls=["https://cisco.com/c/dam/en/us/products/collateral/switches/catalyst-9200-series-switches/nb-06-cat9200-ser-data-sheet-cte-en.pdf"],
                extract_depth="advanced",
                format=ExtractFormat.MARKDOWN,
            )
            ```
        """
        logger.info(f"[TavilyGatewayAdapter] extract: {len(urls)} URLs")

        arguments = self._clean_none_values({
            "urls": urls,
            "extract_depth": extract_depth,
            "format": format.value,
            "include_images": include_images,
            "include_favicon": include_favicon,
        })

        try:
            result = self._client.call_tool(
                tool_name=self._tool_name("TavilySearchExtract"),
                arguments=arguments,
                timeout=timeout,
            )

            # Parse response into ExtractResult objects
            results = self._parse_extract_results(result)
            logger.info(f"[TavilyGatewayAdapter] extract returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"[TavilyGatewayAdapter] extract failed: {e}")
            return []

    def _parse_extract_results(self, response: Dict[str, Any]) -> List[ExtractResult]:
        """Parse Tavily extract response into ExtractResult objects."""
        results = []

        items = response.get("results", [])
        if not isinstance(items, list):
            items = [response] if "url" in response else []

        for item in items:
            try:
                images = item.get("images", [])
                if isinstance(images, list):
                    image_urls = [
                        img.get("url", img) if isinstance(img, dict) else img
                        for img in images
                    ]
                else:
                    image_urls = []

                results.append(ExtractResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    raw_content=item.get("raw_content"),
                    favicon=item.get("favicon"),
                    images=image_urls,
                ))
            except Exception as e:
                logger.warning(f"[TavilyGatewayAdapter] Failed to parse extract result: {e}")

        return results

    # =========================================================================
    # High-Level Equipment Research Methods
    # =========================================================================

    def research_equipment(
        self,
        part_number: str,
        manufacturer: Optional[str] = None,
        search_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive equipment research using Tavily search and extract.

        Combines search and extract tools to gather complete documentation
        for a piece of equipment.

        Args:
            part_number: Equipment part number (e.g., "C9200-24P")
            manufacturer: Manufacturer name for domain filtering
            search_types: Types of docs to search for (default: all)

        Returns:
            Dictionary with:
            - part_number: str
            - manufacturer: str
            - datasheet: SearchResult or None
            - manual: SearchResult or None
            - specifications: Dict[str, Any]
            - sources: List[str] (all URLs used)

        Example:
            ```python
            research = adapter.research_equipment(
                part_number="C9200-24P",
                manufacturer="Cisco",
            )
            logger.info("Found datasheet: %s", research['datasheet'].url)
            ```
        """
        logger.info(
            f"[TavilyGatewayAdapter] research_equipment: "
            f"part_number={part_number}, manufacturer={manufacturer}"
        )

        search_types = search_types or ["datasheet", "manual", "specifications"]
        sources = []
        results = {
            "part_number": part_number,
            "manufacturer": manufacturer or "Unknown",
            "datasheet": None,
            "manual": None,
            "specifications": {},
            "sources": [],
        }

        # Build domain filters
        include_domains = None
        if manufacturer:
            # Common manufacturer domain patterns
            manufacturer_domains = {
                "cisco": ["cisco.com"],
                "dell": ["dell.com"],
                "hp": ["hp.com", "hpe.com"],
                "lenovo": ["lenovo.com"],
                "ibm": ["ibm.com"],
                "juniper": ["juniper.net"],
                "arista": ["arista.com"],
                "netgear": ["netgear.com"],
                "ubiquiti": ["ui.com", "ubnt.com"],
            }
            include_domains = manufacturer_domains.get(
                manufacturer.lower(), [f"{manufacturer.lower()}.com"]
            )

        # Search for each document type
        for doc_type in search_types:
            query = f"{part_number} {doc_type}"
            if manufacturer:
                query = f"{manufacturer} {query}"

            search_results = self.search(
                query=query,
                search_depth=SearchDepth.ADVANCED,
                include_domains=include_domains,
                max_results=3,
                include_raw_content=True,
            )

            if search_results:
                best_result = search_results[0]
                sources.append(best_result.url)

                if doc_type == "datasheet":
                    results["datasheet"] = best_result
                elif doc_type == "manual":
                    results["manual"] = best_result
                elif doc_type == "specifications":
                    results["specifications"] = {
                        "url": best_result.url,
                        "content": best_result.content,
                        "raw_content": best_result.raw_content,
                    }

        results["sources"] = list(set(sources))
        logger.info(
            f"[TavilyGatewayAdapter] research_equipment completed: "
            f"{len(results['sources'])} sources found"
        )

        return results


# =============================================================================
# Factory
# =============================================================================


class TavilyGatewayAdapterFactory:
    """
    Factory for creating TavilyGatewayAdapter instances.

    Handles the setup of CognitoMCPClient and adapter creation,
    abstracting the complexity from agent code.

    Uses OAuth2 (Cognito) authentication - NOT IAM/SigV4.
    The Tavily Gateway is configured with CUSTOM_JWT auth.
    """

    @staticmethod
    def create_from_env() -> TavilyGatewayAdapter:
        """
        Create adapter from environment variables.

        Uses Cognito OAuth2 authentication.

        Environment Variables:
            TAVILY_GATEWAY_URL: Full MCP endpoint URL
            TAVILY_TOKEN_URL: Cognito OAuth2 token endpoint
            TAVILY_CLIENT_ID: Cognito app client ID
            TAVILY_CLIENT_SECRET_ARN: ARN of secret in Secrets Manager
            TAVILY_CLIENT_SECRET: Client secret (fallback)

        Returns:
            Configured TavilyGatewayAdapter

        Raises:
            ValueError: If required environment variables are missing
        """
        client = CognitoMCPClientFactory.create_from_env()
        logger.info("[TavilyGatewayAdapterFactory] Created adapter with Cognito OAuth2")

        return TavilyGatewayAdapter(client)

    @staticmethod
    def create_with_defaults(client_secret: str) -> TavilyGatewayAdapter:
        """
        Create adapter with default Gateway configuration.

        Uses the known Tavily Gateway created via AWS Console.
        Only requires the Cognito client secret.

        Args:
            client_secret: Cognito app client secret

        Returns:
            Configured TavilyGatewayAdapter
        """
        client = CognitoMCPClient(
            gateway_url=TAVILY_GATEWAY_URL,
            token_url=TAVILY_TOKEN_URL,
            client_id=TAVILY_COGNITO_CLIENT_ID,
            client_secret=client_secret,
        )
        logger.info(
            f"[TavilyGatewayAdapterFactory] Created adapter for "
            f"Gateway {TAVILY_GATEWAY_ID}"
        )

        return TavilyGatewayAdapter(client)

    @staticmethod
    def create_with_config(
        gateway_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
    ) -> TavilyGatewayAdapter:
        """
        Create adapter with explicit configuration.

        Args:
            gateway_url: Full Gateway MCP endpoint URL
            token_url: Cognito OAuth2 token endpoint
            client_id: Cognito app client ID
            client_secret: Cognito app client secret

        Returns:
            Configured TavilyGatewayAdapter
        """
        client = CognitoMCPClient(
            gateway_url=gateway_url,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
        )
        logger.info(f"[TavilyGatewayAdapterFactory] Created adapter for {gateway_url}")

        return TavilyGatewayAdapter(client)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Constants
    "TAVILY_GATEWAY_ID",
    "TAVILY_GATEWAY_URL",
    "TAVILY_TOKEN_URL",
    "TAVILY_COGNITO_CLIENT_ID",
    # Types
    "SearchDepth",
    "SearchTopic",
    "TimeRange",
    "ExtractFormat",
    "SearchResult",
    "ExtractResult",
    # Adapter
    "TavilyGatewayAdapter",
    "TavilyGatewayAdapterFactory",
]
