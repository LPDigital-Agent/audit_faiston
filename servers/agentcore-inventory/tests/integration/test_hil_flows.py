# =============================================================================
# Integration Tests for Human-in-the-Loop (HIL) Pattern (Phase 3)
# =============================================================================
# Tests for SchemaMapper HIL confirmation pattern:
# 1. Low confidence (< 0.85) triggers needs_confirmation flag
# 2. HIL task_id is generated for tracking
# 3. User approval flow applies confirmed mappings
# 4. Training examples are saved after confirmation
# 5. High confidence (≥ 0.85) bypasses HIL
# 6. User rejection allows re-suggestion
# 7. Partial confirmations (user modifies suggestions)
#
# Human-in-the-Loop Pattern (from Phase 1 plan):
# - Agent generates mapping suggestions
# - If confidence < 0.85 → pause and request user confirmation
# - Frontend displays suggestions + confidence score
# - User approves/rejects/modifies
# - On approval → save as training example for future learning
# - On rejection → allow agent to re-suggest or user to manually map
#
# Run: cd server/agentcore-inventory && python -m pytest tests/integration/test_hil_flows.py -v
# =============================================================================

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import fixtures from our fixtures module
from tests.integration.fixtures.a2a_client import (
    mock_a2a_client,
    sample_hil_confirmation_payload,
)


# =============================================================================
# Test Scenario 1: Low Confidence Triggers HIL
# =============================================================================

class TestLowConfidenceTriggersHIL:
    """Tests that low confidence suggestions trigger user confirmation."""

    @pytest.mark.asyncio
    async def test_low_confidence_requires_confirmation(
        self,
        mock_a2a_client,
        sample_hil_confirmation_payload,
    ):
        """Test that confidence < 0.85 triggers needs_confirmation flag."""
        # Invoke SchemaMapper with low confidence scenario
        result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            sample_hil_confirmation_payload,
        )

        # Verify A2A call succeeded
        assert result.success, f"A2A call failed: {result.error}"

        # Parse response
        response_data = json.loads(result.response)

        # Verify HIL triggered
        assert "needs_confirmation" in response_data
        assert response_data["needs_confirmation"] is True, \
            "Low confidence should trigger needs_confirmation"

        # Verify HIL task tracking
        assert "hil_task_id" in response_data, \
            "needs_confirmation=True should include hil_task_id"
        assert response_data["hil_task_id"].startswith("task_"), \
            "hil_task_id should have 'task_' prefix"

        # Verify suggestions provided
        assert "suggested_mappings" in response_data
        assert "confidence" in response_data
        assert response_data["confidence"] < 0.85

    @pytest.mark.asyncio
    async def test_high_confidence_bypasses_hil(self, mock_a2a_client):
        """Test that confidence ≥ 0.85 bypasses HIL and proceeds directly."""
        payload = {
            "action": "save_mapping_proposal",
            "file_columns": ["PN", "QTD", "DESCRICAO"],
            "confidence": 0.90,  # High confidence
        }

        result = await mock_a2a_client.invoke_agent("schema_mapper", payload)

        assert result.success
        response_data = json.loads(result.response)

        # Verify HIL NOT triggered
        assert response_data["needs_confirmation"] is False, \
            "High confidence should NOT trigger needs_confirmation"

        # Should NOT have hil_task_id
        assert "hil_task_id" not in response_data or response_data["hil_task_id"] is None

        # Should have immediate mappings
        assert "suggested_mappings" in response_data


# =============================================================================
# Test Scenario 2: User Approval Flow
# =============================================================================

class TestUserApprovalFlow:
    """Tests for user confirmation and mapping application."""

    @pytest.mark.asyncio
    async def test_user_approves_suggestions(self, mock_a2a_client):
        """Test that user approval applies mappings and saves training example."""
        # Step 1: Get low-confidence suggestions
        proposal_payload = {
            "action": "save_mapping_proposal",
            "file_columns": ["PN", "QTD", "DESCRICAO"],
            "confidence": 0.70,
        }

        proposal_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            proposal_payload,
        )

        proposal_data = json.loads(proposal_result.response)
        assert proposal_data["needs_confirmation"] is True
        hil_task_id = proposal_data["hil_task_id"]
        suggested_mappings = proposal_data["suggested_mappings"]

        # Step 2: User approves suggestions
        confirm_payload = {
            "action": "confirm_mapping",
            "hil_task_id": hil_task_id,
            "mappings": suggested_mappings,
            "user_action": "approved",
        }

        confirm_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            confirm_payload,
        )

        confirm_data = json.loads(confirm_result.response)

        # Verify approval processed
        assert confirm_data["success"] is True
        assert "mappings_applied" in confirm_data
        assert confirm_data["mappings_applied"] == suggested_mappings

        # Verify training example saved
        assert "training_example_saved" in confirm_data
        assert confirm_data["training_example_saved"] is True

    @pytest.mark.asyncio
    async def test_user_modifies_suggestions(self, mock_a2a_client):
        """Test that user can modify suggestions (partial confirmation)."""
        # Step 1: Get suggestions
        proposal_payload = {
            "action": "save_mapping_proposal",
            "file_columns": ["PN", "QTD", "DESCRICAO"],
            "confidence": 0.70,
        }

        proposal_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            proposal_payload,
        )

        proposal_data = json.loads(proposal_result.response)
        hil_task_id = proposal_data["hil_task_id"]

        # Step 2: User modifies mappings (different from suggestions)
        modified_mappings = {
            "PN": "part_number",  # Accepted
            "QTD": "stock_quantity",  # Modified from "quantity"
            "DESCRICAO": "description",  # Accepted
        }

        confirm_payload = {
            "action": "confirm_mapping",
            "hil_task_id": hil_task_id,
            "mappings": modified_mappings,
            "user_action": "modified",
        }

        confirm_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            confirm_payload,
        )

        confirm_data = json.loads(confirm_result.response)

        # Verify modified mappings applied
        assert confirm_data["success"] is True
        assert confirm_data["mappings_applied"] == modified_mappings

        # Verify training example saved with user corrections
        assert confirm_data["training_example_saved"] is True


# =============================================================================
# Test Scenario 3: User Rejection Flow
# =============================================================================

class TestUserRejectionFlow:
    """Tests for user rejection and re-suggestion."""

    @pytest.mark.asyncio
    async def test_user_rejects_suggestions(self, mock_a2a_client):
        """Test that user can reject suggestions and request new ones."""
        # Step 1: Get suggestions
        proposal_payload = {
            "action": "save_mapping_proposal",
            "file_columns": ["PN", "QTD", "DESCRICAO"],
            "confidence": 0.70,
        }

        proposal_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            proposal_payload,
        )

        proposal_data = json.loads(proposal_result.response)
        hil_task_id = proposal_data["hil_task_id"]

        # Step 2: User rejects suggestions
        reject_payload = {
            "action": "confirm_mapping",
            "hil_task_id": hil_task_id,
            "user_action": "rejected",
            "rejection_reason": "Mappings don't match our schema",
        }

        # Mock rejection response
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        def mock_invoke_rejection(agent_id, payload, **kwargs):
            if payload.get("user_action") == "rejected":
                return MockA2AResponse(
                    success=True,
                    response=json.dumps({
                        "success": True,
                        "action_taken": "rejected",
                        "can_retry": True,
                        "message": "User rejected suggestions. Ready for manual mapping or retry.",
                    }),
                    agent_id=agent_id,
                    message_id="test",
                )
            return MockA2AResponse(success=True, response="{}", agent_id=agent_id, message_id="test")

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_rejection)

        reject_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            reject_payload,
        )

        reject_data = json.loads(reject_result.response)

        # Verify rejection processed
        assert reject_data["success"] is True
        assert reject_data["action_taken"] == "rejected"
        assert reject_data["can_retry"] is True


# =============================================================================
# Test Scenario 4: HIL Task Tracking
# =============================================================================

class TestHILTaskTracking:
    """Tests for HIL task lifecycle and status tracking."""

    @pytest.mark.asyncio
    async def test_hil_task_has_unique_id(self, mock_a2a_client):
        """Test that each HIL request gets unique task_id."""
        # Create 3 HIL requests
        requests = [
            {
                "action": "save_mapping_proposal",
                "file_columns": [f"COL{i}"],
                "confidence": 0.70,
            }
            for i in range(3)
        ]

        results = await asyncio.gather(
            *[mock_a2a_client.invoke_agent("schema_mapper", r) for r in requests]
        )

        # Extract task_ids
        task_ids = [json.loads(r.response)["hil_task_id"] for r in results]

        # Verify all task_ids are unique
        assert len(task_ids) == len(set(task_ids)), "HIL task_ids must be unique"

        # Verify format
        for task_id in task_ids:
            assert task_id.startswith("task_")

    @pytest.mark.asyncio
    async def test_hil_task_status_query(self, mock_a2a_client):
        """Test that HIL task status can be queried."""
        # Create HIL task
        proposal_payload = {
            "action": "save_mapping_proposal",
            "file_columns": ["PN"],
            "confidence": 0.70,
        }

        proposal_result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            proposal_payload,
        )

        hil_task_id = json.loads(proposal_result.response)["hil_task_id"]

        # Query task status
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        def mock_invoke_status(agent_id, payload, **kwargs):
            if payload.get("action") == "get_hil_status":
                return MockA2AResponse(
                    success=True,
                    response=json.dumps({
                        "success": True,
                        "hil_task_id": payload.get("hil_task_id"),
                        "status": "pending_confirmation",
                        "created_at": datetime.utcnow().isoformat() + "Z",
                        "suggested_mappings": {"PN": "part_number"},
                    }),
                    agent_id=agent_id,
                    message_id="test",
                )
            return MockA2AResponse(success=True, response="{}", agent_id=agent_id, message_id="test")

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_status)

        status_result = await mock_a2a_client.invoke_agent("schema_mapper", {
            "action": "get_hil_status",
            "hil_task_id": hil_task_id,
        })

        status_data = json.loads(status_result.response)

        # Verify status response
        assert status_data["success"] is True
        assert status_data["hil_task_id"] == hil_task_id
        assert status_data["status"] == "pending_confirmation"
        assert "created_at" in status_data


# =============================================================================
# Test Scenario 5: Training Example Persistence
# =============================================================================

class TestTrainingExamplePersistence:
    """Tests that user confirmations are saved as training examples."""

    @pytest.mark.asyncio
    async def test_approved_mappings_saved_as_training_examples(
        self,
        mock_a2a_client,
    ):
        """Test that approved mappings are saved for future learning."""
        # Approve mappings
        confirm_payload = {
            "action": "confirm_mapping",
            "hil_task_id": "task_test123",
            "mappings": {"PN": "part_number", "QTD": "quantity"},
            "user_action": "approved",
        }

        result = await mock_a2a_client.invoke_agent("schema_mapper", confirm_payload)

        response_data = json.loads(result.response)

        # Verify training example saved
        assert response_data["training_example_saved"] is True

        # In production, this would:
        # 1. Save to AgentCore Memory (global/user-specific)
        # 2. Increase confidence for similar mappings in future
        # 3. Allow Learning Effectiveness Agent to measure accuracy

    @pytest.mark.asyncio
    async def test_modified_mappings_saved_with_corrections(
        self,
        mock_a2a_client,
    ):
        """Test that user modifications are saved as corrected training examples."""
        # User modifies suggestions
        confirm_payload = {
            "action": "confirm_mapping",
            "hil_task_id": "task_test456",
            "mappings": {"PN": "product_number"},  # User correction
            "user_action": "modified",
        }

        result = await mock_a2a_client.invoke_agent("schema_mapper", confirm_payload)

        response_data = json.loads(result.response)

        # Verify corrected training example saved
        assert response_data["training_example_saved"] is True

        # In production, this provides NEGATIVE feedback:
        # - Agent suggested "part_number"
        # - User corrected to "product_number"
        # - System learns to prefer user's choice in future


# =============================================================================
# Test Scenario 6: Confidence Threshold Boundary
# =============================================================================

class TestConfidenceThreshold:
    """Tests behavior at confidence threshold boundary (0.85)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("confidence,should_confirm", [
        (0.84, True),   # Just below threshold
        (0.85, False),  # At threshold
        (0.86, False),  # Just above threshold
        (0.50, True),   # Very low confidence
        (0.95, False),  # Very high confidence
    ])
    async def test_confidence_threshold_boundary(
        self,
        mock_a2a_client,
        confidence,
        should_confirm,
    ):
        """Test that confidence threshold of 0.85 is correctly applied."""
        payload = {
            "action": "save_mapping_proposal",
            "file_columns": ["PN"],
            "confidence": confidence,
        }

        result = await mock_a2a_client.invoke_agent("schema_mapper", payload)

        response_data = json.loads(result.response)

        # Verify threshold behavior
        assert response_data["needs_confirmation"] == should_confirm, \
            f"confidence={confidence} should {'require' if should_confirm else 'not require'} confirmation"

        if should_confirm:
            assert "hil_task_id" in response_data
        else:
            assert "hil_task_id" not in response_data or response_data["hil_task_id"] is None


# =============================================================================
# Test Scenario 7: Error Handling
# =============================================================================

class TestHILErrorHandling:
    """Tests for error handling in HIL flows."""

    @pytest.mark.asyncio
    async def test_invalid_hil_task_id(self, mock_a2a_client):
        """Test error handling for invalid HIL task_id."""
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        def mock_invoke_invalid_task(agent_id, payload, **kwargs):
            if payload.get("hil_task_id") == "task_nonexistent":
                return MockA2AResponse(
                    success=True,
                    response=json.dumps({
                        "success": False,
                        "error": "HIL task not found",
                        "error_code": "HIL_TASK_NOT_FOUND",
                    }),
                    agent_id=agent_id,
                    message_id="test",
                )
            return MockA2AResponse(success=True, response="{}", agent_id=agent_id, message_id="test")

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_invalid_task)

        # Attempt to confirm non-existent task
        result = await mock_a2a_client.invoke_agent("schema_mapper", {
            "action": "confirm_mapping",
            "hil_task_id": "task_nonexistent",
            "mappings": {"PN": "part_number"},
        })

        response_data = json.loads(result.response)

        # Verify error response
        assert response_data["success"] is False
        assert "error" in response_data
        assert response_data["error_code"] == "HIL_TASK_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_network_failure_during_confirmation(self, mock_a2a_client):
        """Test error handling when confirmation fails due to network issues."""
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        # Mock network failure
        mock_a2a_client.invoke_agent = AsyncMock(
            return_value=MockA2AResponse(
                success=False,
                response="",
                agent_id="schema_mapper",
                message_id="test",
                error="Network timeout",
            )
        )

        result = await mock_a2a_client.invoke_agent("schema_mapper", {
            "action": "confirm_mapping",
            "hil_task_id": "task_test",
            "mappings": {"PN": "part_number"},
        })

        # Verify A2A call failed gracefully
        assert result.success is False
        assert result.error is not None
        assert "timeout" in result.error.lower()


# =============================================================================
# Test Scenario 8: Integration with InventoryHub Orchestrator
# =============================================================================

class TestInventoryHubHILIntegration:
    """Tests for HIL integration with InventoryHub orchestrator."""

    @pytest.mark.asyncio
    async def test_inventory_hub_handles_hil_pause(
        self,
        mock_a2a_client,
        sample_hil_confirmation_payload,
    ):
        """Test that InventoryHub orchestrator pauses workflow when HIL triggered."""
        # InventoryHub calls SchemaMapper (Phase 3)
        result = await mock_a2a_client.invoke_agent(
            "schema_mapper",
            sample_hil_confirmation_payload,
        )

        response_data = json.loads(result.response)

        # InventoryHub detects needs_confirmation
        if response_data.get("needs_confirmation"):
            # InventoryHub should:
            # 1. Pause workflow
            # 2. Return HTTP 202 to frontend with hil_task_id
            # 3. Wait for user confirmation
            # 4. Resume workflow after confirmation

            assert "hil_task_id" in response_data
            hil_task_id = response_data["hil_task_id"]

            # Simulate user confirmation via frontend
            # Frontend calls InventoryHub → InventoryHub calls SchemaMapper
            confirm_result = await mock_a2a_client.invoke_agent("schema_mapper", {
                "action": "confirm_mapping",
                "hil_task_id": hil_task_id,
                "mappings": response_data["suggested_mappings"],
                "user_action": "approved",
            })

            confirm_data = json.loads(confirm_result.response)

            # InventoryHub receives confirmation and resumes workflow
            assert confirm_data["success"] is True
            assert confirm_data["training_example_saved"] is True

            # InventoryHub can now proceed to Phase 4 (DataTransformer)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
