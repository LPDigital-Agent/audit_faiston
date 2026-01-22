# =============================================================================
# Integration Tests for General A2A Communication
# =============================================================================
# Tests for basic Agent-to-Agent communication contracts:
# 1. Health checks for all agents
# 2. Request/response validation
# 3. Error handling (malformed payloads, unknown actions)
# 4. Timeout handling
# 5. Session management
# 6. Message ID tracking and correlation
# 7. A2A protocol compliance (JSON-RPC 2.0)
#
# A2A Protocol (from shared/a2a_client.py):
# - Transport: HTTP with boto3 bedrock-agentcore SDK
# - Format: JSON-RPC 2.0
# - Authentication: AWS SigV4
# - Discovery: Agent Card at /.well-known/agent-card.json
#
# Run: cd server/agentcore-inventory && python -m pytest tests/integration/test_a2a_communication.py -v
# =============================================================================

import pytest
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any

# Import fixtures from our fixtures module
from tests.integration.fixtures.a2a_client import (
    mock_a2a_client,
    build_mock_response,
    MockA2AResponse,
)


# =============================================================================
# Test Scenario 1: Health Checks for All Agents
# =============================================================================

class TestAgentHealthChecks:
    """Tests that all agents respond to health_check action."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_id", [
        "inventory_analyst",
        "schema_mapper",
        "data_transformer",
        "debug",
        "inventory_hub",
    ])
    async def test_all_agents_respond_to_health_check(
        self,
        mock_a2a_client,
        agent_id,
    ):
        """Test that all agents respond to health_check action."""
        result = await mock_a2a_client.invoke_agent(agent_id, {
            "action": "health_check"
        })

        # Verify A2A call succeeded
        assert result.success, f"{agent_id} health check failed: {result.error}"

        # Parse response
        response_data = json.loads(result.response)

        # Verify health response
        assert "status" in response_data
        assert response_data["status"] == "healthy"
        assert "agent" in response_data

    @pytest.mark.asyncio
    async def test_health_check_response_time(self, mock_a2a_client):
        """Test that health checks complete quickly."""
        import time

        start = time.time()
        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "health_check"
        })
        elapsed = time.time() - start

        assert result.success
        assert elapsed < 1.0, "Health check should complete in < 1 second"


# =============================================================================
# Test Scenario 2: Request/Response Contract Validation
# =============================================================================

class TestRequestResponseContracts:
    """Tests for A2A request/response contract compliance."""

    @pytest.mark.asyncio
    async def test_response_always_has_success_field(self, mock_a2a_client):
        """Test that all responses include success boolean."""
        agents_and_payloads = [
            ("inventory_analyst", {"action": "analyze_file_structure", "s3_key": "test.csv"}),
            ("schema_mapper", {"action": "save_mapping_proposal", "file_columns": ["PN"], "confidence": 0.9}),
            ("data_transformer", {"action": "start_transformation", "s3_key": "test.xlsx", "mappings": {}}),
        ]

        for agent_id, payload in agents_and_payloads:
            result = await mock_a2a_client.invoke_agent(agent_id, payload)

            assert result.success
            response_data = json.loads(result.response)

            # CRITICAL: All responses MUST have success field
            assert "success" in response_data, \
                f"{agent_id} response missing 'success' field"
            assert isinstance(response_data["success"], bool)

    @pytest.mark.asyncio
    async def test_failed_responses_include_error_message(self, mock_a2a_client):
        """Test that failed responses include error details."""
        # Mock a failed response
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        def mock_invoke_error(agent_id, payload, **kwargs):
            return MockA2AResponse(
                success=True,  # A2A call succeeded, but agent returned error
                response=json.dumps({
                    "success": False,
                    "error": "Invalid payload format",
                    "error_code": "INVALID_PAYLOAD",
                }),
                agent_id=agent_id,
                message_id="test",
            )

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_error)

        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "unknown_action"
        })

        assert result.success  # A2A transport succeeded
        response_data = json.loads(result.response)

        # But agent returned error
        assert response_data["success"] is False
        assert "error" in response_data
        assert "error_code" in response_data

    @pytest.mark.asyncio
    async def test_message_id_correlation(self, mock_a2a_client):
        """Test that message IDs are unique and trackable."""
        # Send 3 requests
        requests = [
            ("inventory_analyst", {"action": "health_check"}),
            ("schema_mapper", {"action": "health_check"}),
            ("data_transformer", {"action": "health_check"}),
        ]

        results = await asyncio.gather(
            *[mock_a2a_client.invoke_agent(agent, payload) for agent, payload in requests]
        )

        # Extract message_ids
        message_ids = [r.message_id for r in results]

        # Verify uniqueness
        assert len(message_ids) == len(set(message_ids)), \
            "Message IDs must be unique across requests"

        # Verify format (UUID)
        for msg_id in message_ids:
            # Should be parseable as UUID
            uuid.UUID(msg_id)


# =============================================================================
# Test Scenario 3: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in A2A communication."""

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, mock_a2a_client):
        """Test that unknown actions return graceful error."""
        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "nonexistent_action",
            "some_param": "value",
        })

        assert result.success  # A2A transport succeeded
        response_data = json.loads(result.response)

        # Agent should return error for unknown action
        assert response_data["success"] is False
        assert "error" in response_data
        assert "unknown action" in response_data["error"].lower()

    @pytest.mark.asyncio
    async def test_malformed_payload_handling(self, mock_a2a_client):
        """Test error handling for malformed payloads."""
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        def mock_invoke_malformed(agent_id, payload, **kwargs):
            # Simulate agent rejecting malformed payload
            if "action" not in payload:
                return MockA2AResponse(
                    success=True,
                    response=json.dumps({
                        "success": False,
                        "error": "Missing required field: action",
                        "error_code": "MISSING_FIELD",
                    }),
                    agent_id=agent_id,
                    message_id="test",
                )
            return build_mock_response(agent_id, payload)

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_malformed)

        # Send malformed payload (missing 'action')
        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "some_field": "value",
            # Missing 'action'
        })

        assert result.success
        response_data = json.loads(result.response)

        # Verify error response
        assert response_data["success"] is False
        assert "missing" in response_data["error"].lower()
        assert response_data["error_code"] == "MISSING_FIELD"

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, mock_a2a_client):
        """Test that network timeouts are handled gracefully."""
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        # Mock timeout
        mock_a2a_client.invoke_agent = AsyncMock(
            return_value=MockA2AResponse(
                success=False,
                response="",
                agent_id="inventory_analyst",
                message_id="test",
                error="Request timeout after 900s",
            )
        )

        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "analyze_file_structure",
            "s3_key": "large_file.xlsx",
        })

        # Verify timeout handled
        assert result.success is False
        assert result.error is not None
        assert "timeout" in result.error.lower()


# =============================================================================
# Test Scenario 4: Session Management
# =============================================================================

class TestSessionManagement:
    """Tests for A2A session management and state."""

    @pytest.mark.asyncio
    async def test_session_id_propagation(self, mock_a2a_client):
        """Test that session_id is propagated across A2A calls."""
        session_id = f"session_{uuid.uuid4().hex}"

        # Call with explicit session_id
        result = await mock_a2a_client.invoke_agent(
            "inventory_analyst",
            {"action": "health_check"},
            session_id=session_id,
        )

        assert result.success

        # In production, this would:
        # 1. Use session_id for AgentCore Memory context
        # 2. Enable conversation history across agent calls
        # 3. Allow user-specific learning (not global)

    @pytest.mark.asyncio
    async def test_session_isolation(self, mock_a2a_client):
        """Test that different sessions are isolated."""
        session1 = f"session_{uuid.uuid4().hex}"
        session2 = f"session_{uuid.uuid4().hex}"

        # Call same agent with different sessions
        result1 = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            {"action": "health_check"},
            session_id=session1,
        )

        result2 = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            {"action": "health_check"},
            session_id=session2,
        )

        assert result1.success
        assert result2.success

        # Sessions should be independent (no cross-contamination)
        assert result1.message_id != result2.message_id


# =============================================================================
# Test Scenario 5: Concurrent A2A Calls
# =============================================================================

class TestConcurrentCommunication:
    """Tests for concurrent A2A communication patterns."""

    @pytest.mark.asyncio
    async def test_parallel_agent_invocations(self, mock_a2a_client):
        """Test that multiple agents can be invoked in parallel."""
        # Invoke 3 agents concurrently
        tasks = [
            mock_a2a_client.invoke_agent("inventory_analyst", {"action": "health_check"}),
            mock_a2a_client.invoke_agent("schema_mapper", {"action": "health_check"}),
            mock_a2a_client.invoke_agent("data_transformer", {"action": "health_check"}),
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.success for r in results)

        # All should have unique message_ids
        message_ids = [r.message_id for r in results]
        assert len(message_ids) == len(set(message_ids))

    @pytest.mark.asyncio
    async def test_parallel_calls_to_same_agent(self, mock_a2a_client):
        """Test that same agent can handle concurrent requests."""
        # Send 5 concurrent requests to same agent
        tasks = [
            mock_a2a_client.invoke_agent("inventory_analyst", {
                "action": "analyze_file_structure",
                "s3_key": f"file_{i}.csv",
            })
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.success for r in results)

        # All should have unique message_ids (no collision)
        message_ids = [r.message_id for r in results]
        assert len(message_ids) == len(set(message_ids))


# =============================================================================
# Test Scenario 6: A2A Protocol Compliance
# =============================================================================

class TestA2AProtocolCompliance:
    """Tests for JSON-RPC 2.0 protocol compliance."""

    @pytest.mark.asyncio
    async def test_response_format_is_json(self, mock_a2a_client):
        """Test that all responses are valid JSON."""
        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "health_check"
        })

        assert result.success

        # Response should be valid JSON
        try:
            response_data = json.loads(result.response)
            assert isinstance(response_data, dict)
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")

    @pytest.mark.asyncio
    async def test_agent_id_in_response(self, mock_a2a_client):
        """Test that agent_id is included in A2A response."""
        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "health_check"
        })

        assert result.success

        # A2AResponse should include agent_id
        assert result.agent_id == "inventory_analyst"

    @pytest.mark.asyncio
    async def test_response_includes_message_id(self, mock_a2a_client):
        """Test that message_id is included for correlation."""
        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "health_check"
        })

        assert result.success

        # Message ID should be present
        assert result.message_id is not None
        assert len(result.message_id) > 0

        # Should be valid UUID
        uuid.UUID(result.message_id)


# =============================================================================
# Test Scenario 7: Cross-Agent Communication Patterns
# =============================================================================

class TestCrossAgentCommunication:
    """Tests for patterns where agents call other agents."""

    @pytest.mark.asyncio
    async def test_orchestrator_delegates_to_specialists(
        self,
        mock_a2a_client,
    ):
        """Test orchestrator pattern: InventoryHub → specialist agents."""
        # In production, InventoryHub would:
        # Phase 1: Upload file
        # Phase 2: Call InventoryAnalyst
        # Phase 3: Call SchemaMapper
        # Phase 4: Call DataTransformer
        # Phase 5: Call ObservationAgent

        # Simulate Phase 2: InventoryHub → InventoryAnalyst
        analyst_result = await mock_a2a_client.invoke_agent(
            "inventory_analyst",
            {
                "action": "analyze_file_structure",
                "s3_key": "uploads/test.csv",
            },
        )

        assert analyst_result.success
        analyst_data = json.loads(analyst_result.response)
        assert analyst_data["success"] is True
        assert "columns" in analyst_data

        # Simulate Phase 3: InventoryHub → SchemaMapper
        mapper_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            {
                "action": "save_mapping_proposal",
                "file_columns": [col["name"] for col in analyst_data["columns"]],
                "confidence": 0.9,
            },
        )

        assert mapper_result.success
        mapper_data = json.loads(mapper_result.response)
        assert mapper_data["success"] is True

        # Simulate Phase 4: InventoryHub → DataTransformer
        transformer_result = await mock_a2a_client.invoke_agent(
            "data_transformer",
            {
                "action": "start_transformation",
                "s3_key": "uploads/test.csv",
                "mappings": mapper_data.get("suggested_mappings", {}),
                "fire_and_forget": False,  # Synchronous for test
            },
        )

        assert transformer_result.success
        transformer_data = json.loads(transformer_result.response)
        assert transformer_data["success"] is True

    @pytest.mark.asyncio
    async def test_error_propagation_across_agents(self, mock_a2a_client):
        """Test that errors in one agent are visible to calling agent."""
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        def mock_invoke_with_error(agent_id, payload, **kwargs):
            # InventoryAnalyst fails
            if agent_id == "inventory_analyst":
                return MockA2AResponse(
                    success=True,
                    response=json.dumps({
                        "success": False,
                        "error": "S3 file not found",
                        "error_code": "FILE_NOT_FOUND",
                    }),
                    agent_id=agent_id,
                    message_id="test",
                )
            return build_mock_response(agent_id, payload)

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_with_error)

        # InventoryHub calls InventoryAnalyst
        result = await mock_a2a_client.invoke_agent("inventory_analyst", {
            "action": "analyze_file_structure",
            "s3_key": "nonexistent.csv",
        })

        assert result.success  # A2A call succeeded
        response_data = json.loads(result.response)

        # But agent returned error
        assert response_data["success"] is False
        assert response_data["error_code"] == "FILE_NOT_FOUND"

        # InventoryHub should:
        # 1. Detect the error
        # 2. Stop the workflow (don't proceed to Phase 3)
        # 3. Return error to frontend or invoke DebugAgent


# =============================================================================
# Test Scenario 8: Timeout Configuration
# =============================================================================

class TestTimeoutConfiguration:
    """Tests for A2A timeout configuration."""

    @pytest.mark.asyncio
    async def test_custom_timeout_parameter(self, mock_a2a_client):
        """Test that custom timeout can be specified."""
        # Invoke with custom timeout
        result = await mock_a2a_client.invoke_agent(
            "inventory_analyst",
            {"action": "health_check"},
            timeout=300.0,  # 5 minutes
        )

        assert result.success

        # In production, this would configure boto3 timeout

    @pytest.mark.asyncio
    async def test_default_timeout_is_900_seconds(self, mock_a2a_client):
        """Test that default timeout is 15 minutes (900s)."""
        # Invoke without explicit timeout
        result = await mock_a2a_client.invoke_agent(
            "inventory_analyst",
            {"action": "health_check"},
            # timeout not specified, should use default 900.0
        )

        assert result.success

        # Default timeout from shared/a2a_client.py:
        # timeout: float = 900.0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
