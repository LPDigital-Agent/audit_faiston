# =============================================================================
# Cognito OAuth2 MCP Client for AgentCore Gateway
# =============================================================================
# MCP client with OAuth2 (client_credentials) authentication via AWS Cognito.
#
# Per AWS AgentCore Gateway documentation:
# > Gateways with CUSTOM_JWT authentication require OAuth2 Bearer tokens.
#
# This client is designed for AgentCore Gateways that use Cognito User Pools
# for authentication (like the Tavily built-in integration template).
#
# Architecture:
#     Agent -> CognitoMCPClient (OAuth2) -> AgentCore Gateway -> External API
#
# Key Features:
# - OAuth2 client_credentials flow with Cognito
# - Automatic token caching with expiry handling
# - Thread-safe token refresh
# - MCP protocol compliance (JSON-RPC 2.0)
#
# Reference:
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-inbound-auth.html
# - https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html
#
# Author: Faiston NEXO Team
# Date: January 2026
# =============================================================================

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
import requests

from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


# =============================================================================
# Token Cache
# =============================================================================


@dataclass
class TokenCache:
    """Cached OAuth2 access token with expiry tracking."""
    access_token: str
    expires_at: float  # Unix timestamp
    token_type: str = "Bearer"

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """
        Check if token is expired or about to expire.

        Args:
            buffer_seconds: Refresh token this many seconds before expiry

        Returns:
            True if token should be refreshed
        """
        return time.time() >= (self.expires_at - buffer_seconds)


# =============================================================================
# Cognito OAuth2 MCP Client
# =============================================================================


class CognitoMCPClient:
    """
    MCP Gateway Client with Cognito OAuth2 authentication.

    This client authenticates to AgentCore Gateway using OAuth2 Bearer tokens
    obtained from AWS Cognito's token endpoint. It's designed for Gateways
    configured with CUSTOM_JWT authentication.

    The client handles:
    - OAuth2 client_credentials grant flow
    - Token caching with automatic refresh
    - MCP protocol (JSON-RPC 2.0) requests
    - Thread-safe operations

    Example:
        ```python
        client = CognitoMCPClient(
            gateway_url="https://{id}.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp",
            token_url="https://{domain}.auth.us-east-2.amazoncognito.com/oauth2/token",
            client_id="your-cognito-client-id",
            client_secret="your-cognito-client-secret",  # From Secrets Manager
        )

        # Call a tool
        result = client.call_tool(
            "target-tavily___TavilySearchPost",
            {"query": "Cisco C9200-24P specifications"}
        )
        ```

    Attributes:
        _gateway_url: AgentCore Gateway MCP endpoint
        _token_url: Cognito OAuth2 token endpoint
        _client_id: Cognito app client ID
        _client_secret: Cognito app client secret
        _token_cache: Cached access token
        _lock: Thread lock for token refresh
    """

    def __init__(
        self,
        gateway_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
    ):
        """
        Initialize Cognito OAuth2 MCP Client.

        Args:
            gateway_url: Gateway MCP endpoint URL
            token_url: Cognito token endpoint URL
            client_id: Cognito app client ID
            client_secret: Cognito app client secret
        """
        self._gateway_url = gateway_url
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_cache: Optional[TokenCache] = None
        self._lock = threading.Lock()
        self._tools_cache: Optional[List[Dict]] = None

        logger.info(
            f"[CognitoMCPClient] Initialized with OAuth2 auth "
            f"for gateway: {gateway_url}"
        )

    @property
    def gateway_url(self) -> str:
        """Get the configured Gateway URL."""
        return self._gateway_url

    def _fetch_token(self) -> TokenCache:
        """
        Fetch new access token from Cognito.

        Uses OAuth2 client_credentials grant flow:
        POST /oauth2/token
        Content-Type: application/x-www-form-urlencoded
        Body: grant_type=client_credentials&client_id=...&client_secret=...

        Returns:
            TokenCache with fresh access token

        Raises:
            Exception: If token fetch fails
        """
        logger.debug("[CognitoMCPClient] Fetching new access token from Cognito")

        response = requests.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30,
        )

        if response.status_code != 200:
            token_error = Exception(f"Failed to fetch Cognito token: {response.text}")
            debug_error(token_error, "cognito_mcp_fetch_token", {"status_code": response.status_code, "token_url": self._token_url})
            raise token_error

        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        token_type = token_data.get("token_type", "Bearer")

        token_cache = TokenCache(
            access_token=access_token,
            expires_at=time.time() + expires_in,
            token_type=token_type,
        )

        logger.info(
            f"[CognitoMCPClient] Token fetched successfully, "
            f"expires in {expires_in}s"
        )

        return token_cache

    def _get_access_token(self) -> str:
        """
        Get valid access token, refreshing if needed.

        Thread-safe implementation that ensures only one thread
        refreshes the token at a time.

        Returns:
            Valid access token string
        """
        # Check if we have a valid cached token (without lock for performance)
        if self._token_cache and not self._token_cache.is_expired():
            return self._token_cache.access_token

        # Acquire lock for token refresh
        with self._lock:
            # Double-check after acquiring lock (another thread may have refreshed)
            if self._token_cache and not self._token_cache.is_expired():
                return self._token_cache.access_token

            # Fetch new token
            self._token_cache = self._fetch_token()
            return self._token_cache.access_token

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers with OAuth2 Bearer token.

        Returns:
            Dictionary of headers for Gateway requests
        """
        access_token = self._get_access_token()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        Invoke a tool via Gateway using MCP protocol (JSON-RPC 2.0).

        Args:
            tool_name: Full tool name (e.g., "target-tavily___TavilySearchPost")
            arguments: Tool arguments as dictionary
            timeout: Request timeout in seconds

        Returns:
            Tool execution result parsed from response content

        Raises:
            requests.HTTPError: If Gateway returns error status
            Exception: If MCP error in response
        """
        payload = {
            "jsonrpc": "2.0",
            "id": f"call-{tool_name}-{int(time.time())}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        logger.debug(f"[CognitoMCPClient] Calling tool: {tool_name}")

        try:
            response = requests.post(
                self._gateway_url,
                headers=self._get_auth_headers(),
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()

        except requests.exceptions.HTTPError as e:
            debug_error(e, "cognito_mcp_http_error", {"tool_name": tool_name, "status_code": e.response.status_code})
            # If 401, clear token cache and retry once
            if e.response.status_code == 401:
                logger.info("[CognitoMCPClient] Token expired, refreshing...")
                self._token_cache = None
                response = requests.post(
                    self._gateway_url,
                    headers=self._get_auth_headers(),
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
            else:
                raise
        except requests.exceptions.RequestException as e:
            debug_error(e, "cognito_mcp_request_failed", {"tool_name": tool_name})
            raise

        # Parse JSON-RPC response
        result = response.json()

        # Check for JSON-RPC error
        if "error" in result:
            error = result["error"]
            error_msg = error.get("message", str(error))
            mcp_error = Exception(f"MCP error: {error_msg}")
            debug_error(mcp_error, "cognito_mcp_error", {"tool_name": tool_name, "error": error})
            raise mcp_error

        # Parse MCP response content
        if "result" in result:
            content = result["result"].get("content", [])
            for content_item in content:
                if content_item.get("type") == "text":
                    text = content_item.get("text", "{}")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"[CognitoMCPClient] Could not parse response as JSON: "
                            f"{text[:100]}"
                        )
                        return {"raw_text": text}
                elif "data" in content_item:
                    return content_item["data"]

        logger.debug(f"[CognitoMCPClient] Returning raw result for {tool_name}")
        return result.get("result", {})

    def list_tools(self, use_cache: bool = True) -> List[Dict]:
        """
        List all available tools from Gateway.

        Args:
            use_cache: If True, returns cached tools if available

        Returns:
            List of tool definitions
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
                "params": {"cursor": cursor} if cursor else {},
            }

            response = requests.post(
                self._gateway_url,
                headers=self._get_auth_headers(),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()

            if "error" in result:
                raise Exception(f"MCP error: {result['error']}")

            result_data = result.get("result", {})
            tools.extend(result_data.get("tools", []))

            cursor = result_data.get("nextCursor")
            if not cursor:
                break

        self._tools_cache = tools
        logger.info(f"[CognitoMCPClient] Discovered {len(tools)} tools from Gateway")

        return tools

    def clear_cache(self) -> None:
        """Clear cached tokens and tools list."""
        self._token_cache = None
        self._tools_cache = None
        logger.debug("[CognitoMCPClient] Cache cleared")


# =============================================================================
# Factory
# =============================================================================


class CognitoMCPClientFactory:
    """
    Factory for creating CognitoMCPClient instances.

    Handles configuration from environment variables and AWS Secrets Manager.

    Environment Variables:
        TAVILY_GATEWAY_URL: Gateway MCP endpoint URL
        TAVILY_TOKEN_URL: Cognito token endpoint URL
        TAVILY_CLIENT_ID: Cognito app client ID
        TAVILY_CLIENT_SECRET_ARN: ARN of secret in Secrets Manager (optional)
        TAVILY_CLIENT_SECRET: Client secret (fallback if ARN not set)
    """

    @staticmethod
    def create_from_env() -> CognitoMCPClient:
        """
        Create CognitoMCPClient from environment variables.

        Fetches client secret from Secrets Manager if ARN is provided,
        otherwise uses direct environment variable.

        Returns:
            Configured CognitoMCPClient instance

        Raises:
            ValueError: If required environment variables are missing
        """
        gateway_url = os.environ.get("TAVILY_GATEWAY_URL")
        token_url = os.environ.get("TAVILY_TOKEN_URL")
        client_id = os.environ.get("TAVILY_CLIENT_ID")

        if not all([gateway_url, token_url, client_id]):
            raise ValueError(
                "Missing required environment variables: "
                "TAVILY_GATEWAY_URL, TAVILY_TOKEN_URL, TAVILY_CLIENT_ID"
            )

        # Get client secret
        client_secret = CognitoMCPClientFactory._get_client_secret()

        logger.info("[CognitoMCPClientFactory] Created client from environment")

        return CognitoMCPClient(
            gateway_url=gateway_url,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
        )

    @staticmethod
    def _get_client_secret() -> str:
        """
        Get client secret from Secrets Manager or environment.

        Returns:
            Client secret string

        Raises:
            ValueError: If secret cannot be obtained
        """
        # Try Secrets Manager first
        secret_arn = os.environ.get("TAVILY_CLIENT_SECRET_ARN")
        if secret_arn:
            logger.debug(
                "[CognitoMCPClientFactory] Fetching secret from Secrets Manager"
            )
            try:
                secrets_client = boto3.client("secretsmanager")
                response = secrets_client.get_secret_value(SecretId=secret_arn)
                secret_value = response["SecretString"]

                # Check if it's JSON (secret may contain multiple values)
                try:
                    secret_data = json.loads(secret_value)
                    # Try common key names
                    for key in ["client_secret", "clientSecret", "secret"]:
                        if key in secret_data:
                            return secret_data[key]
                    # If no known key, return first value
                    return list(secret_data.values())[0]
                except json.JSONDecodeError:
                    # Plain string secret
                    return secret_value

            except Exception as e:
                debug_error(e, "cognito_mcp_factory_get_secret", {"secret_arn": secret_arn})
                raise ValueError(f"Failed to fetch secret from Secrets Manager: {e}")

        # Fallback to environment variable
        client_secret = os.environ.get("TAVILY_CLIENT_SECRET")
        if not client_secret:
            raise ValueError(
                "Missing client secret: Set TAVILY_CLIENT_SECRET_ARN "
                "or TAVILY_CLIENT_SECRET environment variable"
            )

        return client_secret

    @staticmethod
    def create_with_config(
        gateway_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
    ) -> CognitoMCPClient:
        """
        Create CognitoMCPClient with explicit configuration.

        Args:
            gateway_url: Gateway MCP endpoint URL
            token_url: Cognito token endpoint URL
            client_id: Cognito app client ID
            client_secret: Cognito app client secret

        Returns:
            Configured CognitoMCPClient instance
        """
        return CognitoMCPClient(
            gateway_url=gateway_url,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "CognitoMCPClient",
    "CognitoMCPClientFactory",
    "TokenCache",
]
