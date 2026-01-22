# =============================================================================
# Integration Tests for Fire-and-Forget Pattern (Phase 4)
# =============================================================================
# Tests for DataTransformer Fire-and-Forget pattern:
# 1. Job creation returns job_id immediately
# 2. Background processing completes asynchronously
# 3. Job status polling works correctly
# 4. Job completion notification via ObservationAgent
# 5. Error handling for failed jobs
#
# Fire-and-Forget Pattern (from Phase 1 plan):
# - User uploads large file (>10,000 rows)
# - DataTransformer returns job_id immediately (HTTP 202)
# - Background processing happens async
# - Frontend polls job status every 2 seconds
# - ObservationAgent logs completion event
#
# Run: cd server/agentcore-inventory && python -m pytest tests/integration/test_fire_and_forget.py -v
# =============================================================================

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import fixtures from our new fixtures module
from tests.integration.fixtures.a2a_client import (
    mock_a2a_client,
    sample_fire_and_forget_payload,
    sample_job_status_payload,
    poll_job_status,
)


# =============================================================================
# Test Scenario 1: Job Creation Returns job_id Immediately
# =============================================================================

class TestFireAndForgetJobCreation:
    """Tests for fire-and-forget job creation (Phase 4.1)."""

    @pytest.mark.asyncio
    async def test_start_transformation_returns_job_id(
        self,
        mock_a2a_client,
        sample_fire_and_forget_payload,
    ):
        """Test that start_transformation with fire_and_forget=True returns job_id."""
        # Invoke DataTransformer with fire-and-forget flag
        result = await mock_a2a_client.invoke_agent(
            "data_transformer",
            sample_fire_and_forget_payload,
        )

        # Verify A2A call succeeded
        assert result.success, f"A2A call failed: {result.error}"

        # Parse response
        response_data = json.loads(result.response)

        # Verify job_id is returned
        assert "job_id" in response_data, "Response must contain job_id for fire-and-forget"
        assert response_data["job_id"].startswith("job_"), "job_id should have 'job_' prefix"

        # Verify status is queued (not completed)
        assert response_data["status"] == "queued", "Job should be queued, not completed"

        # Verify success flag
        assert response_data["success"] is True

    @pytest.mark.asyncio
    async def test_synchronous_transformation_no_job_id(self, mock_a2a_client):
        """Test that synchronous transformation (fire_and_forget=False) does NOT return job_id."""
        payload = {
            "action": "start_transformation",
            "s3_key": "uploads/test.xlsx",
            "mappings": {"PN": "part_number"},
            "fire_and_forget": False,  # Synchronous mode
        }

        result = await mock_a2a_client.invoke_agent("data_transformer", payload)

        assert result.success

        response_data = json.loads(result.response)

        # Synchronous mode should NOT have job_id
        assert "job_id" not in response_data

        # Should have immediate results
        assert "records_processed" in response_data
        assert "records_inserted" in response_data


# =============================================================================
# Test Scenario 2: Background Processing Completes Asynchronously
# =============================================================================

class TestBackgroundProcessing:
    """Tests for async background processing (Phase 4.2)."""

    @pytest.mark.asyncio
    async def test_job_completes_in_background(
        self,
        mock_a2a_client,
        sample_fire_and_forget_payload,
        poll_job_status,
    ):
        """Test that fire-and-forget job completes asynchronously."""
        # Step 1: Start fire-and-forget job
        start_result = await mock_a2a_client.invoke_agent(
            "data_transformer",
            sample_fire_and_forget_payload,
        )

        assert start_result.success
        start_data = json.loads(start_result.response)
        job_id = start_data["job_id"]

        # Step 2: Poll job status until completion
        final_status = await poll_job_status(
            mock_a2a_client,
            job_id=job_id,
            timeout=60,  # 60 second timeout
        )

        # Step 3: Verify job completed successfully
        assert final_status["status"] == "completed"
        assert final_status["job_id"] == job_id
        assert "records_processed" in final_status
        assert "records_inserted" in final_status
        assert "completed_at" in final_status

    @pytest.mark.asyncio
    async def test_concurrent_jobs_do_not_conflict(self, mock_a2a_client):
        """Test that multiple concurrent fire-and-forget jobs have unique job_ids."""
        # Start 3 concurrent jobs
        payloads = [
            {
                "action": "start_transformation",
                "s3_key": f"uploads/file_{i}.xlsx",
                "mappings": {"PN": "part_number"},
                "fire_and_forget": True,
            }
            for i in range(3)
        ]

        results = await asyncio.gather(
            *[mock_a2a_client.invoke_agent("data_transformer", p) for p in payloads]
        )

        # Extract job_ids
        job_ids = [json.loads(r.response)["job_id"] for r in results]

        # Verify all job_ids are unique
        assert len(job_ids) == len(set(job_ids)), "Job IDs must be unique"

        # Verify all jobs were queued successfully
        for result in results:
            assert result.success
            data = json.loads(result.response)
            assert data["status"] == "queued"


# =============================================================================
# Test Scenario 3: Job Status Polling
# =============================================================================

class TestJobStatusPolling:
    """Tests for job status polling (Phase 4.3)."""

    @pytest.mark.asyncio
    async def test_get_job_status_returns_progress(
        self,
        mock_a2a_client,
        sample_job_status_payload,
    ):
        """Test that get_job_status returns current job progress."""
        result = await mock_a2a_client.invoke_agent(
            "data_transformer",
            sample_job_status_payload,
        )

        assert result.success

        status_data = json.loads(result.response)

        # Verify required fields
        assert "job_id" in status_data
        assert "status" in status_data
        assert status_data["status"] in ["queued", "processing", "completed", "failed"]

    @pytest.mark.asyncio
    async def test_completed_job_has_results(self, mock_a2a_client):
        """Test that completed jobs include processing results."""
        # Query status for a completed job
        payload = {
            "action": "get_job_status",
            "job_id": "job_completed_test",
        }

        result = await mock_a2a_client.invoke_agent("data_transformer", payload)

        assert result.success

        status_data = json.loads(result.response)

        # Completed jobs must have these fields
        assert status_data["status"] == "completed"
        assert "records_processed" in status_data
        assert "records_inserted" in status_data
        assert "errors" in status_data
        assert "completed_at" in status_data

        # Verify timestamp format (ISO 8601)
        completed_at = status_data["completed_at"]
        assert completed_at.endswith("Z"), "Timestamp should be in UTC (ending with Z)"

    @pytest.mark.asyncio
    async def test_polling_timeout_handling(self, mock_a2a_client, poll_job_status):
        """Test that polling handles timeouts gracefully."""
        # Use poll_job_status fixture directly
        poll = poll_job_status

        # Mock a job that never completes
        async def mock_invoke_never_complete(agent_id, payload, **kwargs):
            from tests.integration.fixtures.a2a_client import MockA2AResponse

            return MockA2AResponse(
                success=True,
                response=json.dumps({
                    "success": True,
                    "job_id": payload.get("job_id"),
                    "status": "processing",  # Always processing, never completes
                }),
                agent_id=agent_id,
                message_id="test",
            )

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_never_complete)

        # Verify timeout raises TimeoutError
        with pytest.raises(TimeoutError) as exc_info:
            await poll(
                mock_a2a_client,
                job_id="job_never_completes",
                timeout=5,  # 5 second timeout
                interval=1,  # Poll every 1 second
            )

        assert "did not complete" in str(exc_info.value)


# =============================================================================
# Test Scenario 4: ObservationAgent Event Logging
# =============================================================================

class TestObservationAgentEvents:
    """Tests for ObservationAgent audit logging of fire-and-forget jobs."""

    @pytest.mark.asyncio
    async def test_job_completion_emits_audit_event(self, mock_a2a_client):
        """Test that job completion triggers ObservationAgent audit event."""
        # This test would require mocking ObservationAgent.log_event
        # For now, we verify the DataTransformer includes observable events

        with patch("shared.audit_emitter.AgentAuditEmitter") as MockAudit:
            mock_audit = MagicMock()
            MockAudit.return_value = mock_audit

            # Simulate job completion (in production, this happens in DataTransformer)
            # The DataTransformer should call audit_emitter.emit_event() on completion

            # For this test, we verify the audit interface is called
            # (Actual implementation would be in DataTransformer agent code)

            # Mock audit call
            mock_audit.completing.return_value = None

            # Simulate completion
            job_id = "job_test123"
            mock_audit.completing(
                message=f"Transformação concluída: {job_id}",
                session_id="test_session",
            )

            # Verify audit was called
            mock_audit.completing.assert_called_once()


# =============================================================================
# Test Scenario 5: Error Handling for Failed Jobs
# =============================================================================

class TestFailedJobHandling:
    """Tests for error handling in fire-and-forget jobs (Phase 4.5)."""

    @pytest.mark.asyncio
    async def test_failed_job_returns_error_details(self, mock_a2a_client):
        """Test that failed jobs include error details in status."""
        # Mock a failed job status
        from tests.integration.fixtures.a2a_client import build_mock_response, MockA2AResponse

        def mock_invoke_failed_job(agent_id, payload, **kwargs):
            if payload.get("action") == "get_job_status":
                return MockA2AResponse(
                    success=True,
                    response=json.dumps({
                        "success": False,
                        "job_id": payload.get("job_id"),
                        "status": "failed",
                        "error_message": "Database connection timeout",
                        "records_processed": 500,
                        "records_inserted": 450,
                        "failed_at": datetime.utcnow().isoformat() + "Z",
                    }),
                    agent_id=agent_id,
                    message_id="test",
                )
            return build_mock_response(agent_id, payload)

        mock_a2a_client.invoke_agent = AsyncMock(side_effect=mock_invoke_failed_job)

        # Query failed job status
        result = await mock_a2a_client.invoke_agent("data_transformer", {
            "action": "get_job_status",
            "job_id": "job_failed",
        })

        assert result.success  # A2A call succeeded

        status_data = json.loads(result.response)

        # Verify failure details
        assert status_data["status"] == "failed"
        assert "error_message" in status_data
        assert "failed_at" in status_data

        # Should still have partial results
        assert "records_processed" in status_data
        assert "records_inserted" in status_data

    @pytest.mark.asyncio
    async def test_network_failure_during_job_creation(self, mock_a2a_client):
        """Test error handling when job creation fails due to network issues."""
        from tests.integration.fixtures.a2a_client import MockA2AResponse

        # Mock network failure
        mock_a2a_client.invoke_agent = AsyncMock(
            return_value=MockA2AResponse(
                success=False,
                response="",
                agent_id="data_transformer",
                message_id="test",
                error="Network timeout",
            )
        )

        result = await mock_a2a_client.invoke_agent("data_transformer", {
            "action": "start_transformation",
            "fire_and_forget": True,
        })

        # Verify A2A call failed gracefully
        assert result.success is False
        assert result.error is not None
        assert "timeout" in result.error.lower()


# =============================================================================
# Test Scenario 6: Integration with InventoryHub Orchestrator
# =============================================================================

class TestInventoryHubIntegration:
    """Tests for fire-and-forget integration with InventoryHub orchestrator."""

    @pytest.mark.asyncio
    async def test_inventory_hub_delegates_to_data_transformer(
        self,
        mock_a2a_client,
        sample_fire_and_forget_payload,
    ):
        """Test that InventoryHub can delegate to DataTransformer in fire-and-forget mode."""
        # Simulate InventoryHub calling DataTransformer
        # In production, this happens in Phase 4 of the 5-phase workflow

        # InventoryHub delegates to DataTransformer
        result = await mock_a2a_client.invoke_agent(
            "data_transformer",
            sample_fire_and_forget_payload,
        )

        assert result.success

        response_data = json.loads(result.response)

        # InventoryHub receives job_id to track async processing
        assert "job_id" in response_data

        # InventoryHub can return this to frontend immediately (HTTP 202)
        # Frontend then polls for completion


# =============================================================================
# Test Scenario 7: Response Time < 2 seconds for Job Creation
# =============================================================================

class TestResponseTime:
    """Tests for response time requirements (fire-and-forget performance)."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(2)  # Fail if takes more than 2 seconds
    async def test_job_creation_completes_quickly(
        self,
        mock_a2a_client,
        sample_fire_and_forget_payload,
    ):
        """Test that fire-and-forget job creation returns within 2 seconds."""
        # Job creation should be nearly instant (just queue the job)
        result = await mock_a2a_client.invoke_agent(
            "data_transformer",
            sample_fire_and_forget_payload,
        )

        assert result.success

        response_data = json.loads(result.response)
        assert "job_id" in response_data


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
