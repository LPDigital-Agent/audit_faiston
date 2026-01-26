# =============================================================================
# Strands Framework A2A Client - AWS AgentCore Integration
# =============================================================================
# 100% Strands Framework implementation for Agent-to-Agent communication,
# compliant with CLAUDE.md IMMUTABLE rule (lines 31-36).
#
# Architecture:
# - Uses Strands A2ACardResolver for agent discovery (/.well-known/agent-card.json)
# - Uses Strands ClientFactory for A2A protocol compliance (JSON-RPC 2.0)
# - Custom httpx transport with AWS SigV4 authentication for AgentCore Runtime
# - Replaces custom boto3 implementation with Strands primitives
#
# Key Difference from Legacy Client:
# OLD: boto3.client('bedrock-agentcore').invoke_agent_runtime() - custom implementation
# NEW: Strands A2ACardResolver + ClientFactory - framework-native approach
#
# Reference:
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a-protocol-contract.html
# =============================================================================

import os
import json
import uuid
import logging
import urllib.parse
from typing import Dict, Any, Optional
from dataclasses import dataclass

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession

# Strands Framework imports
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Runtime IDs Configuration (Imported from Legacy Client)
# =============================================================================
# These IDs are IMMUTABLE once created - they only change if you delete/recreate
# the runtime in Terraform. Using hardcoded IDs eliminates SSM latency (~50ms).
# =============================================================================

# Production runtime IDs
PROD_RUNTIME_IDS = {
    "nexo_import": "faiston_sga_nexo_import-0zNtFDAo7M",
    "learning": "faiston_sga_learning-30cZIOFmzo",
    "validation": "faiston_sga_validation-3zgXMwCxGN",
    "data_import": "faiston_sga_data_import-bPG8FYGk5w",
    "intake": "faiston_sga_intake-9I7Nwe6ZfP",
    "estoque_control": "faiston_sga_estoque_control-jLRAIr8EcI",
    "compliance": "faiston_sga_compliance-2Kty3O64vz",
    "reconciliacao": "faiston_sga_reconciliacao-poSPdO6OKm",
    "expedition": "faiston_sga_expedition-yJ7Nb551hS",
    "carrier": "faiston_sga_carrier-fVOntdCJaZ",
    "reverse": "faiston_sga_reverse-jeiH9k8CbC",
    "schema_evolution": "faiston_sga_schema_evolution-Ke1i76BvB0",
    "debug": "faiston_sga_debug-W86Xdj8sAY",
    "file_analyzer": "faiston_sga_file_analyzer-tYGY6H9bHm",
    "vision_analyzer": "faiston_sga_vision_analyzer-Z1qoZUFHzs",
    "enrichment": "faiston_sga_enrichment-PLACEHOLDER",
    # Smart Import Specialist Agents (BUG-023 FIX - Runtime IDs updated)
    "inventory_analyst": "faiston_inventory_analyst-0uGg1W8ITM",
    "schema_mapper": "faiston_schema_mapper-7fxI9bFHzd",
    "data_transformer": "faiston_data_transformer-xjSXPo8HaC",
    "observation": "faiston_sga_observation-tgaIiC6AtX",
    "repair": "faiston_sga_repair-qrBCLNGC4S",
}

# Dev runtime IDs (fallback to prod for agents without dev deployment)
DEV_RUNTIME_IDS = {
    **PROD_RUNTIME_IDS,
    "carrier": "faiston_sga_carrier_dev-V0XnC28gWH",
    "expedition": "faiston_sga_expedition_dev-p5wzSnDV5d",
    "reverse": "faiston_sga_reverse_dev-67E3Uu7FxL",
}

# Select runtime IDs based on environment
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod").lower()
RUNTIME_IDS = DEV_RUNTIME_IDS if _ENVIRONMENT == "dev" else PROD_RUNTIME_IDS

logger.info(f"[Strands A2A] Using {_ENVIRONMENT.upper()} runtime IDs")

# =============================================================================
# AWS SigV4 Authentication for httpx
# =============================================================================


class AWSSigV4HTTPXAuth(httpx.Auth):
    """
    httpx authentication handler that signs requests with AWS Signature Version 4.

    This enables Strands Framework to communicate with AWS AgentCore Runtimes
    using standard HTTP A2A protocol while maintaining AWS IAM authentication.
    """

    def __init__(self, service: str = "bedrock-agentcore", region: str = "us-east-2"):
        self.service = service
        self.region = region
        self.session = BotocoreSession()

    def auth_flow(self, request: httpx.Request):
        """
        Sign the HTTP request with AWS SigV4 before sending.

        Args:
            request: httpx.Request to be signed

        Yields:
            Signed httpx.Request
        """
        # Get AWS credentials from environment (IAM role or profile)
        credentials = self.session.get_credentials()

        # Convert httpx.Request to AWSRequest for signing
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            data=request.content if request.content else None,
        )

        # Sign the request using SigV4
        SigV4Auth(credentials, self.service, self.region).add_auth(aws_request)

        # Copy signed headers back to httpx.Request
        # Convert botocore headers to dict format for httpx compatibility
        request.headers.update(dict(aws_request.headers.items()))

        # Yield the signed request
        yield request


# =============================================================================
# A2A Response Dataclass (Backward Compatible Interface)
# =============================================================================


@dataclass
class A2AResponse:
    """
    A2A Protocol response structure (maintains backward compatibility).

    Attributes:
        success: Whether the call succeeded
        response: Response text from the agent
        agent_id: ID of the agent that responded
        message_id: ID of the request message
        error: Error message if failed
        raw_response: Full A2A protocol response
    """
    success: bool
    response: str
    agent_id: str
    message_id: str
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


# =============================================================================
# Strands Framework A2A Client
# =============================================================================


class StrandsA2AClient:
    """
    Strands Framework-based A2A client for AWS AgentCore Runtime communication.

    Implements CLAUDE.md IMMUTABLE rule (lines 31-36):
    "ALL Agent-to-Agent (A2A) communication MUST be done via Strands Framework
    (A2AClientToolProvider or A2ACardResolver) running on AgentCore Runtime."

    Architecture:
    - Agent discovery: A2ACardResolver (/.well-known/agent-card.json)
    - Protocol compliance: ClientFactory (JSON-RPC 2.0)
    - AWS authentication: AWSSigV4HTTPXAuth (httpx transport)
    - Runtime URLs: Same as legacy client (bedrock-agentcore.{region}.amazonaws.com)

    Usage:
        client = StrandsA2AClient()
        result = await client.invoke_agent("schema_mapper", {
            "action": "map_columns",
            "columns": ["col1", "col2"]
        })
    """

    def __init__(self, use_discovery: bool = True):
        """
        Initialize Strands A2A client with Agent Card discovery support.

        Args:
            use_discovery: Enable Agent Card discovery by default (A2A protocol)
        """
        self.region = os.environ.get("AWS_REGION", "us-east-2")
        self.account_id = os.environ.get("AWS_ACCOUNT_ID", "377311924364")
        self.use_discovery = use_discovery

        # Agent Card cache: {agent_id: {"card": AgentCard, "client": A2AClient}}
        self._agent_cache: Dict[str, Dict] = {}

    def _build_runtime_url(self, agent_id: str) -> Optional[str]:
        """
        Build AgentCore runtime URL from agent ID.

        Args:
            agent_id: Agent identifier (e.g., "schema_mapper", "validation")

        Returns:
            AgentCore invocation URL or None if agent not found
        """
        runtime_id = RUNTIME_IDS.get(agent_id)
        if not runtime_id:
            logger.warning(f"[Strands A2A] Unknown agent: {agent_id}")
            return None

        if "PLACEHOLDER" in runtime_id:
            logger.error(
                f"[Strands A2A] Agent '{agent_id}' has PLACEHOLDER runtime ID. "
                f"Run `terraform apply` and update RUNTIME_IDS."
            )
            return None

        # Build AgentCore invocation URL (same format as legacy client)
        # Format: https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtime_id}/invocations/
        # Note: URL encoding not needed for Strands (handles internally)
        url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{runtime_id}/invocations/"

        logger.debug(f"[Strands A2A] Built URL for {agent_id}: {url[:80]}...")
        return url

    async def _get_or_create_client(self, agent_id: str, session_timeout: float) -> Optional[Any]:
        """
        Get or create Strands A2A client for an agent.

        Uses A2ACardResolver for agent discovery and ClientFactory for protocol compliance.

        Args:
            agent_id: Agent identifier
            session_timeout: HTTP timeout for this session

        Returns:
            Strands A2A client or None if agent not found
        """
        # Check cache first
        if agent_id in self._agent_cache:
            logger.debug(f"[Strands A2A] Using cached client for {agent_id}")
            return self._agent_cache[agent_id]["client"]

        # Build runtime URL
        base_url = self._build_runtime_url(agent_id)
        if not base_url:
            return None

        try:
            # Create httpx client with AWS SigV4 authentication
            httpx_client = httpx.AsyncClient(
                auth=AWSSigV4HTTPXAuth(
                    service="bedrock-agentcore",
                    region=self.region
                ),
                timeout=httpx.Timeout(session_timeout),
            )

            # Discover agent capabilities via Agent Card
            logger.info(f"[Strands A2A] Discovering agent card for {agent_id} at {base_url}")
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
            agent_card = await resolver.get_agent_card()

            logger.info(
                f"[Strands A2A] Discovered agent: {agent_card.name} "
                f"(version: {agent_card.version})"
            )

            # Create Strands A2A client using ClientFactory
            config = ClientConfig(httpx_client=httpx_client, streaming=False)
            factory = ClientFactory(config)
            a2a_client = factory.create(agent_card)

            # Cache for reuse
            self._agent_cache[agent_id] = {
                "card": agent_card,
                "client": a2a_client,
            }

            return a2a_client

        except Exception as e:
            logger.error(
                f"[Strands A2A] Failed to discover/create client for {agent_id}: {e}",
                exc_info=True
            )
            return None

    async def invoke_agent(
        self,
        agent_id: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        timeout: float = 900.0,
        use_discovery: Optional[bool] = None,
    ) -> A2AResponse:
        """
        Invoke another agent via Strands Framework A2A protocol.

        This is the main method for cross-agent communication using Strands Framework.

        Args:
            agent_id: ID of the agent to invoke (e.g., "schema_mapper", "validation")
            payload: Payload to send (will be JSON-serialized as A2A message)
            session_id: Optional session ID for context continuity
            timeout: Request timeout in seconds (default: 900s / 15 minutes)
            use_discovery: Enable Agent Card discovery (default: instance setting)

        Returns:
            A2AResponse with success status and response text

        Example:
            result = await client.invoke_agent("schema_mapper", {
                "action": "map_columns",
                "columns": ["col1", "col2", "col3"],
                "schema": {"part_number": "string", "quantity": "integer"}
            })

            if result.success:
                mapping_result = json.loads(result.response)
        """
        # Import audit emitter for event emission (optional for test environments)
        audit = None
        try:
            from shared.audit_emitter import AgentAuditEmitter
            current_agent = os.environ.get("AGENT_ID", "unknown")
            audit = AgentAuditEmitter(current_agent)

            # Emit delegation event
            audit.delegating(
                target_agent=agent_id,
                message=f"Delegando para {agent_id} (Strands Framework)...",
                session_id=session_id,
            )
        except Exception as e:
            # Audit emitter not available (likely test environment without AUDIT_LOG_TABLE)
            logger.debug(f"[Strands A2A] Audit emitter not available: {e}")

        # Generate message ID for A2A protocol
        message_id = str(uuid.uuid4())

        try:
            # Get or create Strands A2A client for this agent
            a2a_client = await self._get_or_create_client(agent_id, timeout)
            if not a2a_client:
                return A2AResponse(
                    success=False,
                    response="",
                    agent_id=agent_id,
                    message_id=message_id,
                    error=f"Agent '{agent_id}' not found or discovery failed",
                )

            # Build A2A message using Strands types
            # Convert payload dict to JSON text for TextPart
            payload_text = json.dumps(payload, ensure_ascii=False)

            message = Message(
                kind="message",
                role=Role.user,
                parts=[Part(TextPart(kind="text", text=payload_text))],
                message_id=message_id,
            )

            logger.info(f"[Strands A2A] Sending message to {agent_id} (session: {session_id})")

            # Send message via Strands client
            response_message = None
            async for event in a2a_client.send_message(message):
                if isinstance(event, Message):
                    response_message = event
                    break  # First message is the response (non-streaming)

            if not response_message:
                return A2AResponse(
                    success=False,
                    response="",
                    agent_id=agent_id,
                    message_id=message_id,
                    error="No response received from agent",
                )

            # Diagnostic logging for A2A response structure (BUG-027)
            if response_message:
                logger.debug(
                    f"[Strands A2A] Response parts count: {len(response_message.parts)}, "
                    f"types: {[type(p).__name__ for p in response_message.parts]}"
                )

            # Extract text from response message parts
            # BUG-027 FIX: Handle multiple part types for structured_output_model compatibility
            response_text = ""
            for part in response_message.parts:
                try:
                    # Handle TextPart content (standard text response)
                    if hasattr(part, "content") and isinstance(part.content, TextPart):
                        response_text += part.content.text
                    # Handle direct text attribute (some serialization formats)
                    elif hasattr(part, "text") and isinstance(part.text, str):
                        response_text += part.text
                    # Handle Part with content dict (structured output)
                    elif hasattr(part, "content") and isinstance(part.content, dict):
                        response_text = json.dumps(part.content)
                        break  # Structured content takes precedence
                    # Handle Part with content string
                    elif hasattr(part, "content") and isinstance(part.content, str):
                        response_text += part.content
                    # Handle Pydantic-style root attribute
                    elif hasattr(part, "root") and part.root is not None:
                        if isinstance(part.root, dict):
                            response_text = json.dumps(part.root)
                        elif hasattr(part.root, "model_dump"):
                            response_text = json.dumps(part.root.model_dump())
                        break
                except (TypeError, ValueError, AttributeError) as e:
                    logger.warning(
                        f"[Strands A2A] Failed to extract from part {type(part).__name__}: {e}"
                    )
                    continue  # Try next part

            # FALLBACK: Extract from raw_response if still empty (BUG-027)
            if not response_text and response_message.parts:
                logger.warning(
                    f"[Strands A2A] No text extracted from parts. "
                    f"Part types: {[type(p).__name__ for p in response_message.parts]}. "
                    f"Attempting fallback extraction..."
                )
                # Try to extract from the Message object directly
                for part in response_message.parts:
                    try:
                        # Last resort: serialize the entire part
                        if hasattr(part, "__dict__"):
                            response_text = json.dumps(part.__dict__, default=str)
                            logger.info("[Strands A2A] Extracted via __dict__ fallback")
                            break
                    except Exception as e:
                        logger.warning(f"[Strands A2A] Fallback extraction failed: {e}")

            logger.info(
                f"[Strands A2A] Received response from {agent_id}: "
                f"{response_text[:200]}..."
            )

            # Return success response
            return A2AResponse(
                success=True,
                response=response_text,
                agent_id=agent_id,
                message_id=message_id,
                error=None,
                raw_response={"message": response_message},
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"[Strands A2A] Error invoking {agent_id}: {error_msg}",
                exc_info=True
            )

            # Emit error audit event if audit emitter is available
            if audit:
                try:
                    audit.error(
                        message=f"Erro ao chamar {agent_id} (Strands Framework)",
                        session_id=session_id,
                        error=error_msg[:500],
                    )
                except Exception:
                    pass  # Ignore audit errors in error handler

            return A2AResponse(
                success=False,
                response="",
                agent_id=agent_id,
                message_id=message_id,
                error=error_msg,
            )

    async def clear_card_cache(self, agent_id: Optional[str] = None):
        """
        Clear Agent Card cache for one or all agents.

        Args:
            agent_id: Agent to clear cache for, or None for all agents
        """
        if agent_id:
            if agent_id in self._agent_cache:
                del self._agent_cache[agent_id]
                logger.info(f"[Strands A2A] Cleared cache for {agent_id}")
        else:
            self._agent_cache.clear()
            logger.info("[Strands A2A] Cleared all agent cache")


# =============================================================================
# Backward Compatibility Helpers
# =============================================================================


# Aliases for easier migration (some imports might use these names)
A2AClient = StrandsA2AClient
LocalA2AClient = StrandsA2AClient  # Legacy alias for local testing
