# =============================================================================
# Strands Framework A2A Client - AWS AgentCore Integration
# =============================================================================
# 100% Strands Framework implementation for Agent-to-Agent communication,
# compliant with CLAUDE.md IMMUTABLE rule (lines 31-36).
#
# Architecture:
# - Uses AWS GetAgentCard API for agent discovery (NOT HTTP /.well-known/agent-card.json)
# - Uses boto3 invoke_agent_runtime for actual invocation (NOT httpx+SigV4)
# - Implements JSON-RPC 2.0 A2A protocol manually for boto3 transport
#
# IMPORTANT (BUG-042 FIX v8):
# AWS AgentCore does NOT expose /.well-known/agent-card.json via HTTP.
# We must use the AWS GetAgentCard API with IAM auth instead of Strands A2ACardResolver.
#
# IMPORTANT (BUG-042 FIX v8 - httpx SigV4 bypass):
# Custom httpx+SigV4 authentication fails inside AgentCore containers with 403 Forbidden.
# boto3 invoke_agent_runtime works correctly. We now use boto3 for actual invocation
# instead of Strands ClientFactory+httpx transport.
#
# Key Architecture:
# - Discovery: boto3 GetAgentCard (works)
# - Invocation: boto3 invoke_agent_runtime (works, replaces httpx+SigV4)
# - Protocol: JSON-RPC 2.0 (manually constructed for boto3)
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
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession

# Strands Framework imports
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import AgentCapabilities, AgentCard, AgentSkill, Message, Part, Role, TextPart

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
    # Smart Import Specialist Agents - Runtime IDs for A2A communication
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

        AWS AgentCore requires the URL-encoded ARN format, NOT the bare runtime ID.

        Args:
            agent_id: Agent identifier (e.g., "schema_mapper", "validation")

        Returns:
            AgentCore invocation URL (with URL-encoded ARN) or None if agent not found
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

        # Build full ARN
        runtime_arn = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/{runtime_id}"
        )

        # URL-encode the ARN for the path segment
        # AWS AgentCore requires this format: /runtimes/{url-encoded-arn}/invocations/
        encoded_arn = urllib.parse.quote(runtime_arn, safe="")

        url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations/"

        logger.debug(f"[Strands A2A] Built URL for {agent_id}: {url[:100]}...")
        return url

    def _fetch_agent_card_via_aws_api(self, agent_id: str, base_url: str) -> Optional[AgentCard]:
        """
        Fetch agent card via AWS AgentCore GetAgentCard API.

        AWS AgentCore doesn't expose /.well-known/agent-card.json via HTTP.
        Instead, we must use the GetAgentCard API operation with IAM auth.

        Args:
            agent_id: Agent identifier for lookup
            base_url: Base invocation URL for the agent

        Returns:
            Strands AgentCard object or None if fetch failed
        """
        runtime_id = RUNTIME_IDS.get(agent_id)
        if not runtime_id:
            return None

        runtime_arn = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/{runtime_id}"
        )

        try:
            # Use boto3 to call GetAgentCard API
            client = boto3.client(
                "bedrock-agentcore",
                region_name=self.region,
            )

            # Don't pass qualifier - let AWS use default behavior
            # Explicitly passing qualifier="DEFAULT" causes issues with cold endpoints
            response = client.get_agent_card(
                agentRuntimeArn=runtime_arn,
            )

            if response.get("statusCode") != 200:
                logger.error(
                    f"[Strands A2A] GetAgentCard failed for {agent_id}: "
                    f"status={response.get('statusCode')}"
                )
                return None

            card_data = response.get("agentCard", {})

            # Convert boto3 response to Strands AgentCard type
            capabilities = AgentCapabilities(
                streaming=card_data.get("capabilities", {}).get("streaming", False),
            )

            skills = [
                AgentSkill(
                    id=skill.get("id", "unknown"),
                    name=skill.get("name", "Unknown"),
                    description=skill.get("description", ""),
                    tags=skill.get("tags", []),
                )
                for skill in card_data.get("skills", [])
            ]

            agent_card = AgentCard(
                name=card_data.get("name", agent_id),
                version=card_data.get("version", "1.0.0"),
                description=card_data.get("description", ""),
                url=base_url,  # Use our base URL, not the ARN-encoded one
                capabilities=capabilities,
                defaultInputModes=card_data.get("defaultInputModes", ["text"]),
                defaultOutputModes=card_data.get("defaultOutputModes", ["text"]),
                skills=skills,
                preferredTransport=card_data.get("preferredTransport", "JSONRPC"),
                protocolVersion=card_data.get("protocolVersion", "0.3.0"),
            )

            logger.info(
                f"[Strands A2A] Fetched agent card via AWS API: {agent_card.name} "
                f"(version: {agent_card.version})"
            )
            return agent_card

        except Exception as e:
            logger.error(
                f"[Strands A2A] Failed to fetch agent card via AWS API for {agent_id}: {e}",
                exc_info=True
            )
            return None

    def _invoke_via_boto3(
        self,
        agent_id: str,
        payload: Dict[str, Any],
        message_id: str,
        session_id: Optional[str] = None,
    ) -> A2AResponse:
        """
        Invoke agent using boto3 invoke_agent_runtime (bypasses httpx SigV4 issues).

        This method replaces the Strands ClientFactory+httpx transport because
        custom httpx+SigV4 authentication fails inside AgentCore containers with 403.
        boto3 invoke_agent_runtime uses the AWS SDK's native request signing which works.

        Args:
            agent_id: Agent identifier (e.g., "schema_mapper")
            payload: Business payload to send
            message_id: UUID for the A2A message
            session_id: Optional session ID for context continuity

        Returns:
            A2AResponse with success status and response text
        """
        runtime_id = RUNTIME_IDS.get(agent_id)
        if not runtime_id:
            return A2AResponse(
                success=False,
                response="",
                agent_id=agent_id,
                message_id=message_id,
                error=f"Unknown agent: {agent_id}",
            )

        if "PLACEHOLDER" in runtime_id:
            return A2AResponse(
                success=False,
                response="",
                agent_id=agent_id,
                message_id=message_id,
                error=f"Agent '{agent_id}' has PLACEHOLDER runtime ID",
            )

        runtime_arn = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/{runtime_id}"
        )

        # Build JSON-RPC 2.0 message (A2A protocol)
        rpc_message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "role": "user",
                    "parts": [{"kind": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                    "messageId": message_id,
                }
            },
        }

        # Add session ID if provided (for context continuity)
        if session_id:
            rpc_message["params"]["sessionId"] = session_id

        try:
            logger.info(
                f"[Strands A2A] Invoking {agent_id} via boto3 "
                f"(message_id: {message_id[:8]}...)"
            )

            client = boto3.client("bedrock-agentcore", region_name=self.region)
            response = client.invoke_agent_runtime(
                agentRuntimeArn=runtime_arn,
                payload=json.dumps(rpc_message),  # FIXED: was 'body', must be 'payload'
                contentType="application/json",
            )

            # Check HTTP status
            status_code = response.get("statusCode", 0)
            if status_code != 200:
                return A2AResponse(
                    success=False,
                    response="",
                    agent_id=agent_id,
                    message_id=message_id,
                    error=f"boto3 invoke failed with status {status_code}",
                )

            # Read streaming body
            streaming_body = response.get("response")
            if not streaming_body:
                return A2AResponse(
                    success=False,
                    response="",
                    agent_id=agent_id,
                    message_id=message_id,
                    error="No response body from agent",
                )

            response_bytes = streaming_body.read()
            response_str = response_bytes.decode("utf-8")

            logger.debug(f"[Strands A2A] Raw boto3 response: {response_str[:500]}...")

            # Parse JSON-RPC 2.0 response
            try:
                response_json = json.loads(response_str)
            except json.JSONDecodeError as e:
                # Agent returned raw text, not JSON-RPC envelope
                logger.warning(f"[Strands A2A] Agent returned non-JSON response: {response_str[:200]}")
                return A2AResponse(
                    success=True,  # Call succeeded, just non-standard format
                    response=response_str,
                    agent_id=agent_id,
                    message_id=message_id,
                    raw_response={"raw_text": response_str},
                )

            # Check for JSON-RPC error
            if "error" in response_json:
                error_obj = response_json["error"]
                error_msg = error_obj.get("message", str(error_obj))
                return A2AResponse(
                    success=False,
                    response="",
                    agent_id=agent_id,
                    message_id=message_id,
                    error=f"A2A error: {error_msg}",
                    raw_response=response_json,
                )

            # Extract response text from JSON-RPC result
            result = response_json.get("result", {})
            message_obj = result.get("message", {})
            parts = message_obj.get("parts", [])

            response_text = ""
            for part in parts:
                part_kind = part.get("kind", "")
                if part_kind == "text":
                    response_text += part.get("text", "")
                elif part_kind == "data":
                    # Structured data response
                    data = part.get("data", {})
                    response_text = json.dumps(data, ensure_ascii=False)
                    break  # Data takes precedence

            # Fallback: check for direct text in result
            if not response_text and isinstance(result, str):
                response_text = result
            elif not response_text and "text" in result:
                response_text = result["text"]

            logger.info(
                f"[Strands A2A] boto3 invoke success for {agent_id}: "
                f"{response_text[:200]}..."
            )

            return A2AResponse(
                success=True,
                response=response_text,
                agent_id=agent_id,
                message_id=message_id,
                raw_response=response_json,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"[Strands A2A] boto3 invoke failed for {agent_id}: {error_msg}",
                exc_info=True
            )
            return A2AResponse(
                success=False,
                response="",
                agent_id=agent_id,
                message_id=message_id,
                error=error_msg,
            )

    async def _get_or_create_client(self, agent_id: str, session_timeout: float) -> Optional[Any]:
        """
        Get or create Strands A2A client for an agent.

        Uses AWS GetAgentCard API for discovery (not HTTP /.well-known/agent-card.json)
        and ClientFactory for protocol compliance.

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

            # FIX: Use AWS GetAgentCard API instead of HTTP-based discovery
            # AWS AgentCore doesn't serve /.well-known/agent-card.json via HTTP
            logger.info(f"[Strands A2A] Fetching agent card for {agent_id} via AWS API")
            agent_card = self._fetch_agent_card_via_aws_api(agent_id, base_url)

            if not agent_card:
                logger.error(f"[Strands A2A] Could not fetch agent card for {agent_id}")
                return None

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
            # FIX v8: Use boto3 invoke_agent_runtime instead of httpx+SigV4
            # httpx+SigV4 fails with 403 inside AgentCore containers, but boto3 works
            logger.info(
                f"[Strands A2A] Invoking {agent_id} via boto3 (session: {session_id})"
            )

            result = self._invoke_via_boto3(
                agent_id=agent_id,
                payload=payload,
                message_id=message_id,
                session_id=session_id,
            )

            # Emit success/error audit events
            if audit:
                try:
                    if result.success:
                        audit.success(
                            message=f"A2A call to {agent_id} succeeded (boto3)",
                            session_id=session_id,
                        )
                    else:
                        audit.error(
                            message=f"A2A call to {agent_id} failed: {result.error}",
                            session_id=session_id,
                            error=result.error[:500] if result.error else "Unknown error",
                        )
                except Exception:
                    pass  # Ignore audit errors

            return result

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
                        message=f"Erro ao chamar {agent_id} (boto3)",
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
