"""
MCP Gateway Client with AWS SigV4 Authentication.

Per AWS Well-Architected Framework (Security Pillar):
> "Use IAM roles for service-to-service communication, NOT static credentials or tokens."

This client handles communication with AgentCore Gateway using IAM-based
authentication with SigV4 request signing. This replaces the previous
Bearer token pattern which was incorrect for AWS_IAM-configured Gateways.

Architecture:
    Agent -> MCPGatewayClient (SigV4) -> AgentCore Gateway -> Lambda MCP Target

Key Features:
- Uses SigV4 signing with IAM credentials (auto-refreshed)
- Supports tool discovery via list_tools()
- Supports tool invocation via call_tool()
- Caches tool list for performance
- Sync-first design for simplicity (avoids async complexity)

Reference:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-inbound-auth.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-call.html

Author: Faiston NEXO Team
Date: January 2026
Updated: January 2026 - SigV4 auth (AWS Best Practice)
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


class MCPGatewayClient:
    """
    Client for invoking tools via AgentCore Gateway using IAM SigV4 auth.

    This follows AWS best practices for service-to-service communication
    using IAM roles instead of Bearer tokens. The AgentCore Runtime's
    execution role already has `bedrock-agentcore:InvokeGateway` permission.

    Example usage:
        ```python
        client = MCPGatewayClient(
            gateway_url="https://{id}.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp"
        )

        # Sync call - no context manager needed
        result = client.call_tool(
            "SGAPostgresTools___sga_get_balance",  # 3 underscores
            {"part_number": "PN-001"}
        )
        ```

    Attributes:
        _gateway_url: Full MCP endpoint URL for AgentCore Gateway
        _region: AWS region for SigV4 signing
        _session: boto3 Session for credential management
        _tools_cache: Cached list of available tools
    """

    # Service name for SigV4 signing
    SERVICE_NAME = "bedrock-agentcore"

    def __init__(
        self,
        gateway_url: str,
        region: Optional[str] = None
    ):
        """
        Initialize MCP Gateway Client with IAM auth.

        Args:
            gateway_url: Gateway MCP endpoint URL
                Format: https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp
            region: AWS region for SigV4 signing (default: from env or us-east-2)
        """
        self._gateway_url = gateway_url
        self._region = region or os.environ.get("AWS_REGION", "us-east-2")
        self._session = boto3.Session()
        self._tools_cache: Optional[List[Dict]] = None

        logger.info(
            f"[MCPGatewayClient] Initialized with IAM auth (SigV4) "
            f"for region {self._region}"
        )

    @property
    def gateway_url(self) -> str:
        """Get the configured Gateway URL."""
        return self._gateway_url

    def _get_credentials(self):
        """
        Get fresh AWS credentials.

        Uses boto3 Session which handles credential refresh automatically
        for temporary credentials (from IAM roles, instance profiles, etc.)

        Returns:
            Frozen credentials tuple (access_key, secret_key, token)
        """
        credentials = self._session.get_credentials()
        if credentials is None:
            raise ValueError(
                "No AWS credentials found. Ensure IAM role is configured "
                "or AWS credentials are available in environment."
            )
        return credentials.get_frozen_credentials()

    def _sign_request(
        self,
        method: str,
        url: str,
        payload: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Sign HTTP request with AWS SigV4 for AgentCore Gateway.

        Args:
            method: HTTP method (POST, GET, etc.)
            url: Full request URL
            payload: Request body as dictionary

        Returns:
            Dictionary of signed headers to include in request
        """
        body = json.dumps(payload)

        # Create AWS request object
        request = AWSRequest(
            method=method,
            url=url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        # Sign with SigV4
        credentials = self._get_credentials()
        SigV4Auth(credentials, self.SERVICE_NAME, self._region).add_auth(request)

        logger.debug(f"[MCPGatewayClient] Request signed for {self.SERVICE_NAME}")

        return dict(request.headers)

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Invoke a tool via Gateway using MCP protocol (JSON-RPC 2.0).

        Per AWS docs (gateway-using-mcp-call.html):
        - Method: tools/call
        - Tool name format: {TargetName}___{tool_name} (THREE underscores)
        - Response contains content array with results

        Args:
            tool_name: Full tool name (e.g., "SGAPostgresTools___sga_get_balance")
            arguments: Tool arguments as dictionary
            timeout: Request timeout in seconds (default 30)

        Returns:
            Tool execution result parsed from response content

        Raises:
            requests.HTTPError: If Gateway returns error status
            ValueError: If response cannot be parsed
            Exception: If MCP error in response
        """
        payload = {
            "jsonrpc": "2.0",
            "id": f"call-{tool_name}-{id(arguments)}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        logger.debug(f"[MCPGatewayClient] Calling tool: {tool_name}")

        # Sign and execute request
        headers = self._sign_request("POST", self._gateway_url, payload)

        try:
            response = requests.post(
                self._gateway_url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()

        except requests.exceptions.HTTPError as e:
            debug_error(e, "mcp_gateway_http_error", {"tool_name": tool_name, "status_code": e.response.status_code})
            raise
        except requests.exceptions.RequestException as e:
            debug_error(e, "mcp_gateway_request_failed", {"tool_name": tool_name})
            raise

        # Parse JSON-RPC response
        result = response.json()

        # Check for JSON-RPC error
        if "error" in result:
            error = result["error"]
            error_msg = error.get("message", str(error))
            mcp_error = Exception(f"MCP error: {error_msg}")
            debug_error(mcp_error, "mcp_gateway_error", {"tool_name": tool_name, "error": error})
            raise mcp_error

        # Parse MCP response content
        # MCP response format: {"result": {"content": [{"type": "text", "text": "..."}]}}
        if "result" in result:
            content = result["result"].get("content", [])
            for content_item in content:
                if content_item.get("type") == "text":
                    text = content_item.get("text", "{}")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"[MCPGatewayClient] Could not parse response as JSON: {text[:100]}"
                        )
                        return {"raw_text": text}
                elif "data" in content_item:
                    return content_item["data"]

        # Return raw result if no parseable content
        logger.debug(f"[MCPGatewayClient] Returning raw result for {tool_name}")
        return result.get("result", {})

    def list_tools(self, use_cache: bool = True) -> List[Dict]:
        """
        List all available tools from Gateway.

        Per AWS docs (gateway-using-mcp-list.html), this method supports
        pagination for large tool sets.

        Args:
            use_cache: If True, returns cached tools if available

        Returns:
            List of tool definitions with name, description, and input_schema
        """
        if use_cache and self._tools_cache is not None:
            return self._tools_cache

        tools = []
        cursor = None

        while True:
            payload = {
                "jsonrpc": "2.0",
                "id": "list-tools",
                "method": "tools/list",
                "params": {"cursor": cursor} if cursor else {}
            }

            headers = self._sign_request("POST", self._gateway_url, payload)

            response = requests.post(
                self._gateway_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()

            if "error" in result:
                raise Exception(f"MCP error: {result['error']}")

            result_data = result.get("result", {})
            tools.extend(result_data.get("tools", []))

            # Check for pagination
            cursor = result_data.get("nextCursor")
            if not cursor:
                break

        self._tools_cache = tools
        logger.info(f"[MCPGatewayClient] Discovered {len(tools)} tools from Gateway")

        return tools

    def search_tools(self, query: str) -> List[Dict]:
        """
        Semantic search for tools (if enabled on Gateway).

        Per AWS docs (gateway-using-mcp-semantic-search.html):
        - Uses special tool: x_amz_bedrock_agentcore_search
        - Returns relevant tools based on natural language query

        Args:
            query: Natural language description of desired functionality

        Returns:
            List of matching tool definitions
        """
        logger.info(f"[MCPGatewayClient] Searching tools: '{query}'")

        try:
            result = self.call_tool(
                tool_name="x_amz_bedrock_agentcore_search",
                arguments={"query": query}
            )
            return result.get("tools", [])
        except Exception as e:
            logger.warning(
                f"[MCPGatewayClient] Semantic search failed (may not be enabled): {e}"
            )
            return self.list_tools()

    def clear_cache(self) -> None:
        """Clear the cached tools list."""
        self._tools_cache = None
        logger.debug("[MCPGatewayClient] Tool cache cleared")


class MCPGatewayClientFactory:
    """
    Factory for creating MCPGatewayClient instances.

    This factory handles configuration from environment variables
    and provides a consistent way to create clients across agents.

    Environment Variables:
        AGENTCORE_GATEWAY_URL: Full MCP endpoint URL
        AGENTCORE_GATEWAY_ID: Gateway ID (alternative to full URL)
        AWS_REGION: AWS region for URL construction and SigV4 signing
    """

    @staticmethod
    def create_from_env() -> MCPGatewayClient:
        """
        Create MCPGatewayClient from environment variables.

        Uses IAM-based authentication (SigV4) - no token provider needed.
        The AgentCore Runtime's execution role provides credentials.

        Returns:
            Configured MCPGatewayClient instance

        Raises:
            ValueError: If required environment variables are missing
        """
        # Try full URL first
        gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL")

        if not gateway_url:
            # Construct from ID and region
            gateway_id = os.environ.get("AGENTCORE_GATEWAY_ID")
            region = os.environ.get("AWS_REGION", "us-east-2")

            if not gateway_id:
                raise ValueError(
                    "Either AGENTCORE_GATEWAY_URL or AGENTCORE_GATEWAY_ID "
                    "environment variable must be set"
                )

            gateway_url = (
                f"https://{gateway_id}.gateway.bedrock-agentcore."
                f"{region}.amazonaws.com/mcp"
            )

        return MCPGatewayClient(gateway_url=gateway_url)

    @staticmethod
    def create_with_url(gateway_url: str, region: str = "us-east-2") -> MCPGatewayClient:
        """
        Create MCPGatewayClient with explicit URL.

        Args:
            gateway_url: Full Gateway MCP endpoint URL
            region: AWS region for SigV4 signing

        Returns:
            Configured MCPGatewayClient instance
        """
        return MCPGatewayClient(gateway_url=gateway_url, region=region)
