# =============================================================================
# A2A Integration Test Fixtures
# =============================================================================
# Reusable fixtures for testing Agent-to-Agent communication patterns:
# - Fire-and-Forget (Phase 4: DataTransformer async jobs)
# - Human-in-the-Loop (Phase 3: SchemaMapper confirmation)
# - General A2A communication contracts
#
# Usage:
#   from tests.integration.fixtures.a2a_client import mock_a2a_client
#
#   async def test_something(mock_a2a_client):
#       result = await mock_a2a_client.invoke_agent("learning", {...})
#       assert result.success
#
# Reference: docs/REQUEST_FLOW.md (5-phase workflow)
# =============================================================================

import pytest
import json
import uuid
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional
from datetime import datetime


# =============================================================================
# Mock A2A Response Builder
# =============================================================================

class MockA2AResponse:
    """
    Mock A2A protocol response for testing.

    Simulates the A2AResponse dataclass from shared/a2a_client.py
    """

    def __init__(
        self,
        success: bool = True,
        response: str = "",
        agent_id: str = "",
        message_id: str = "",
        error: Optional[str] = None,
        raw_response: Optional[Dict] = None,
    ):
        self.success = success
        self.response = response
        self.agent_id = agent_id
        self.message_id = message_id
        self.error = error
        self.raw_response = raw_response or {}


def build_mock_response(
    agent_id: str,
    payload: Dict[str, Any],
    success: bool = True,
    error_message: Optional[str] = None,
) -> MockA2AResponse:
    """
    Build a mock A2A response based on agent and payload.

    This function simulates how each agent would respond to specific actions.
    It implements the response contracts for Phase 2-5 agents.

    Args:
        agent_id: Agent identifier (e.g., "inventory_analyst", "schema_mapper")
        payload: Request payload sent to agent
        success: Whether the call succeeded
        error_message: Error message if failed

    Returns:
        MockA2AResponse with appropriate structure for the agent
    """
    message_id = str(uuid.uuid4())

    if not success:
        return MockA2AResponse(
            success=False,
            response="",
            agent_id=agent_id,
            message_id=message_id,
            error=error_message or "Simulated error",
        )

    # Phase 2: InventoryAnalyst
    if agent_id == "inventory_analyst":
        action = payload.get("action")

        if action == "analyze_file_structure":
            response_data = {
                "success": True,
                "file_info": {
                    "filename": payload.get("s3_key", "test.csv").split("/")[-1],
                    "row_count": 1000,
                    "column_count": 10,
                    "file_size_bytes": 50000,
                    "encoding": "UTF-8",
                },
                "columns": [
                    {"name": "PN", "sample_values": ["ABC123", "DEF456"]},
                    {"name": "QTD", "sample_values": ["10", "25"]},
                    {"name": "DESCRICAO", "sample_values": ["Item A", "Item B"]},
                ],
                "health_ok": True,
            }
        elif action == "health_check":
            response_data = {"status": "healthy", "agent": "InventoryAnalyst"}
        else:
            response_data = {"success": False, "error": f"Unknown action: {action}"}

    # Phase 3: SchemaMapper (HIL pattern)
    elif agent_id == "schema_mapper":
        action = payload.get("action")

        if action == "save_mapping_proposal":
            # Simulate low confidence requiring user confirmation
            confidence = payload.get("confidence", 0.7)
            needs_confirmation = confidence < 0.85

            response_data = {
                "success": True,
                "needs_confirmation": needs_confirmation,
                "suggested_mappings": {
                    "PN": "part_number",
                    "QTD": "quantity",
                    "DESCRICAO": "description",
                },
                "confidence": confidence,
            }

            if needs_confirmation:
                response_data["hil_task_id"] = f"task_{uuid.uuid4().hex[:8]}"

        elif action == "confirm_mapping":
            # Simulate user confirmation applied
            response_data = {
                "success": True,
                "mappings_applied": payload.get("mappings", {}),
                "training_example_saved": True,
            }

        elif action == "health_check":
            response_data = {"status": "healthy", "agent": "SchemaMapper"}

        else:
            response_data = {"success": False, "error": f"Unknown action: {action}"}

    # Phase 4: DataTransformer (Fire-and-Forget pattern)
    elif agent_id == "data_transformer":
        action = payload.get("action")

        if action == "start_transformation":
            # Simulate fire-and-forget job creation
            fire_and_forget = payload.get("fire_and_forget", False)

            if fire_and_forget:
                job_id = f"job_{uuid.uuid4().hex[:8]}"
                response_data = {
                    "success": True,
                    "job_id": job_id,
                    "status": "queued",
                    "message": "Transformação iniciada em background",
                }
            else:
                # Synchronous transformation
                response_data = {
                    "success": True,
                    "records_processed": 1000,
                    "records_inserted": 950,
                    "errors": 50,
                }

        elif action == "get_job_status":
            # Simulate job status polling
            job_id = payload.get("job_id", "")

            # For testing, simulate completed job
            response_data = {
                "success": True,
                "job_id": job_id,
                "status": "completed",
                "records_processed": 1000,
                "records_inserted": 950,
                "errors": 50,
                "completed_at": datetime.utcnow().isoformat() + "Z",
            }

        elif action == "health_check":
            response_data = {"status": "healthy", "agent": "DataTransformer"}

        else:
            response_data = {"success": False, "error": f"Unknown action: {action}"}

    # Debug Agent
    elif agent_id == "debug":
        action = payload.get("action")

        if action == "analyze_error":
            response_data = {
                "success": True,
                "error_signature": f"sig_{uuid.uuid4().hex[:8]}",
                "error_type": payload.get("error_type", "UnknownError"),
                "technical_explanation": "Análise simulada do erro para testes",
                "root_causes": [
                    {
                        "cause": "Erro simulado para teste",
                        "confidence": 0.8,
                        "evidence": ["Stack trace analysis"],
                    }
                ],
                "debugging_steps": [
                    "1. Verificar logs no CloudWatch",
                    "2. Validar dados de entrada",
                ],
                "recoverable": False,
                "suggested_action": "escalate",
            }
        elif action == "health_check":
            response_data = {"status": "healthy", "agent": "DebugAgent"}
        else:
            response_data = {"success": False, "error": f"Unknown action: {action}"}

    # InventoryHub Orchestrator
    elif agent_id == "inventory_hub":
        action = payload.get("action")

        if action == "health_check":
            response_data = {"status": "healthy", "agent": "InventoryHub"}
        else:
            # Orchestrator delegates to specialists
            response_data = {
                "success": True,
                "phase": "analysis",
                "message": "Processamento iniciado",
            }

    # Default fallback
    else:
        response_data = {
            "success": True,
            "message": f"Mock response from {agent_id}",
        }

    return MockA2AResponse(
        success=True,
        response=json.dumps(response_data),
        agent_id=agent_id,
        message_id=message_id,
    )


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture
def mock_a2a_client():
    """
    Mock A2A client for integration tests.

    This fixture provides a fully-mocked A2AClient that simulates
    agent-to-agent communication without requiring deployed agents.

    Usage:
        async def test_fire_and_forget(mock_a2a_client):
            result = await mock_a2a_client.invoke_agent("data_transformer", {
                "action": "start_transformation",
                "fire_and_forget": True
            })
            assert result.success
            assert "job_id" in json.loads(result.response)

    Returns:
        Mock A2AClient with invoke_agent method that returns realistic responses
    """
    from shared.strands_a2a_client import A2AClient

    mock_client = MagicMock(spec=A2AClient)

    async def mock_invoke_agent(
        agent_id: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        timeout: float = 900.0,
        use_discovery: Optional[bool] = None,
    ) -> MockA2AResponse:
        """Mock invoke_agent that returns realistic responses."""
        return build_mock_response(agent_id, payload)

    mock_client.invoke_agent = AsyncMock(side_effect=mock_invoke_agent)

    return mock_client


@pytest.fixture
def sample_fire_and_forget_payload():
    """
    Sample payload for testing Fire-and-Forget pattern (Phase 4).

    Returns:
        Dict with DataTransformer transformation request
    """
    return {
        "action": "start_transformation",
        "s3_key": "uploads/test_inventory.xlsx",
        "mappings": {
            "PN": "part_number",
            "QTD": "quantity",
            "DESCRICAO": "description",
        },
        "fire_and_forget": True,
    }


@pytest.fixture
def sample_hil_confirmation_payload():
    """
    Sample payload for testing HIL confirmation pattern (Phase 3).

    Returns:
        Dict with SchemaMapper mapping proposal request
    """
    return {
        "action": "save_mapping_proposal",
        "file_columns": ["PN", "QTD", "DESCRICAO"],
        "confidence": 0.70,  # Low confidence triggers HIL
    }


@pytest.fixture
def sample_job_status_payload():
    """
    Sample payload for polling job status (Fire-and-Forget).

    Returns:
        Dict with job status request
    """
    return {
        "action": "get_job_status",
        "job_id": "job_test123",
    }


@pytest.fixture
def mock_boto3_agentcore_client():
    """
    Mock boto3 bedrock-agentcore client for A2A invoke_agent_runtime.

    This fixture mocks the boto3 client.invoke_agent_runtime() method
    that is used by A2AClient for production invocations.

    Usage:
        with patch("shared.a2a_client._get_boto3") as mock_boto3:
            mock_boto3.return_value.client.return_value = mock_boto3_agentcore_client
            # Test code that calls A2AClient.invoke_agent()

    Returns:
        Mock boto3 client with invoke_agent_runtime method
    """
    mock_client = MagicMock()

    def mock_invoke_agent_runtime(
        agentRuntimeArn: str,
        runtimeSessionId: str,
        payload: bytes,
    ) -> Dict:
        """
        Mock invoke_agent_runtime that returns JSON-RPC 2.0 response.

        This simulates the actual AWS Bedrock AgentCore Runtime API response.
        """
        # Parse the request payload
        request_data = json.loads(payload.decode('utf-8'))

        # Extract agent ID from ARN
        # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/runtime_id
        runtime_id = agentRuntimeArn.split("/")[-1]

        # Map runtime_id to agent_id (simplified for tests)
        agent_id = "data_transformer"  # Default for testing

        # Extract request payload
        request_payload = json.loads(
            request_data["params"]["message"]["parts"][0]["text"]
        )

        # Build mock response
        mock_response = build_mock_response(agent_id, request_payload)

        # Format as JSON-RPC 2.0 response
        response_data = {
            "jsonrpc": "2.0",
            "id": request_data["id"],
            "result": {
                "message": {
                    "role": "assistant",
                    "parts": [
                        {
                            "kind": "text",
                            "text": mock_response.response,
                        }
                    ],
                },
            },
        }

        # Return as boto3 would (with StreamingBody)
        from io import BytesIO

        class MockStreamingBody:
            def __init__(self, data: bytes):
                self._data = data

            def read(self) -> bytes:
                return self._data

            def decode(self, encoding: str = 'utf-8') -> str:
                return self._data.decode(encoding)

        response_body = json.dumps(response_data).encode('utf-8')

        return {
            "response": MockStreamingBody(response_body),
            "ResponseMetadata": {
                "HTTPStatusCode": 200,
                "RequestId": str(uuid.uuid4()),
            },
        }

    mock_client.invoke_agent_runtime = MagicMock(side_effect=mock_invoke_agent_runtime)

    return mock_client


@pytest.fixture
def poll_job_status():
    """
    Helper fixture for polling job status until completion.

    This simulates the polling logic that would be used in production
    to wait for fire-and-forget jobs to complete.

    Usage:
        job_status = await poll_job_status(
            mock_a2a_client,
            job_id="job_123",
            timeout=60
        )
        assert job_status["status"] == "completed"

    Returns:
        Async function that polls job status
    """
    import asyncio

    async def _poll(client, job_id: str, timeout: int = 60, interval: int = 2) -> Dict:
        """
        Poll job status until completed or timeout.

        Args:
            client: A2A client instance
            job_id: Job ID to poll
            timeout: Maximum wait time in seconds
            interval: Polling interval in seconds

        Returns:
            Final job status dict

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

            result = await client.invoke_agent("data_transformer", {
                "action": "get_job_status",
                "job_id": job_id,
            })

            if not result.success:
                raise RuntimeError(f"Job status query failed: {result.error}")

            status_data = json.loads(result.response)

            if status_data.get("status") in ["completed", "failed"]:
                return status_data

            await asyncio.sleep(interval)

    return _poll
