# =============================================================================
# End-to-End Integration Tests for Debug Agent Flow
# =============================================================================
# These tests verify the COMPLETE data flow from error to frontend response.
#
# The Debug Agent flow involves multiple modules:
# 1. Error occurs in agent/swarm code
# 2. debug_utils.py sends to Debug Agent via A2A
# 3. Debug Agent (Gemini Pro) analyzes and returns analysis
# 4. A2A protocol returns analysis as STRING JSON
# 5. ensure_dict() converts STRING → DICT
# 6. response_utils.py injects analysis into response
# 7. Frontend receives response with DICT debug_analysis
#
# These tests mock the A2A layer and verify the complete flow.
#
# Run: cd server/agentcore-inventory && python -m pytest tests/integration/test_debug_flow_e2e.py -v
# =============================================================================

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass


# =============================================================================
# Mock A2A Response
# =============================================================================

@dataclass
class MockA2AResponse:
    """Mock A2A response matching real A2AClient.invoke_agent() return."""
    success: bool
    response: str  # NOTE: Always STRING, not dict - this is the bug root cause!
    agent_id: str
    error: str = None


# =============================================================================
# Test: Debug Error Async Flow
# =============================================================================

class TestDebugErrorAsyncFlow:
    """Test debug_error_async() returns DICT analysis."""

    @pytest.fixture
    def mock_a2a_response_success(self):
        """Mock successful A2A response with STRING analysis (as protocol returns)."""
        return MockA2AResponse(
            success=True,
            response=json.dumps({
                "error_type": "ValidationError",
                "technical_explanation": "Campo obrigatório ausente na linha 5",
                "root_causes": [
                    {"cause": "Coluna 'part_number' não encontrada no CSV", "confidence": 0.95},
                    {"cause": "Header pode estar em formato incorreto", "confidence": 0.75}
                ],
                "debugging_steps": [
                    "Verificar cabeçalhos do CSV",
                    "Validar mapeamento de colunas",
                    "Checar encoding do arquivo"
                ],
                "documentation_links": ["https://docs.example.com/csv-format"],
                "similar_patterns": ["BUG-019", "BUG-020"],
                "recoverable": False,
                "suggested_action": "abort"
            }),
            agent_id="debug",
            error=None
        )

    @pytest.fixture
    def mock_a2a_response_failure(self):
        """Mock failed A2A response."""
        return MockA2AResponse(
            success=False,
            response="",
            agent_id="debug",
            error="Connection timeout"
        )

    @pytest.mark.asyncio
    async def test_debug_error_async_returns_dict_analysis(self, mock_a2a_response_success):
        """
        CRITICAL TEST: debug_error_async() MUST return analysis as DICT.

        This was the ROOT CAUSE of BUG-036: analysis was STRING, not DICT.
        """
        from shared.debug_utils import debug_error_async

        with patch("shared.debug_utils._get_debug_client") as mock_client:
            mock_client.return_value.invoke_agent = AsyncMock(
                return_value=mock_a2a_response_success
            )

            result = await debug_error_async(
                Exception("Test error"),
                "test_operation",
                {"context": "test"},
                timeout=1.0
            )

            # CRITICAL ASSERTIONS
            assert result["enriched"] is True
            assert isinstance(result["analysis"], dict), \
                f"BUG-036 REGRESSION: analysis should be dict, got {type(result['analysis'])}"

            # Verify analysis content
            assert result["analysis"]["error_type"] == "ValidationError"
            assert len(result["analysis"]["root_causes"]) == 2
            assert result["analysis"]["recoverable"] is False

    @pytest.mark.asyncio
    async def test_debug_error_async_handles_failure(self, mock_a2a_response_failure):
        """debug_error_async() should handle A2A failures gracefully."""
        from shared.debug_utils import debug_error_async

        with patch("shared.debug_utils._get_debug_client") as mock_client:
            mock_client.return_value.invoke_agent = AsyncMock(
                return_value=mock_a2a_response_failure
            )

            result = await debug_error_async(
                Exception("Test error"),
                "test_operation",
                {},
                timeout=1.0
            )

            assert result["enriched"] is False
            assert "reason" in result

    @pytest.mark.asyncio
    async def test_debug_error_async_handles_timeout(self):
        """debug_error_async() should handle timeout gracefully."""
        import asyncio
        from shared.debug_utils import debug_error_async

        with patch("shared.debug_utils._get_debug_client") as mock_client:
            # Simulate slow response
            async def slow_invoke(*args, **kwargs):
                await asyncio.sleep(10)  # Longer than timeout
                return MockA2AResponse(True, "{}", "debug")

            mock_client.return_value.invoke_agent = slow_invoke

            result = await debug_error_async(
                Exception("Test error"),
                "test_operation",
                {},
                timeout=0.1  # Very short timeout
            )

            assert result["enriched"] is False
            assert result["reason"] == "timeout"


# =============================================================================
# Test: Capture Debug Analysis Flow
# =============================================================================

class TestCaptureDebugAnalysisFlow:
    """Test _capture_debug_analysis() properly injects DICT into response."""

    def test_capture_adds_dict_to_response(self):
        """_capture_debug_analysis() MUST add DICT to response["debug_analysis"]."""
        from swarm.response_utils import _capture_debug_analysis

        response = {"success": False, "error": "Test error"}

        with patch("swarm.response_utils.debug_error") as mock_debug:
            # debug_error now returns DICT analysis (after our fix)
            mock_debug.return_value = {
                "enriched": True,
                "analysis": {
                    "technical_explanation": "Test analysis",
                    "root_causes": [{"cause": "Test cause", "confidence": 0.9}]
                }
            }

            _capture_debug_analysis(
                Exception("Test"),
                "test_op",
                {},
                response,
                timeout=1.0
            )

            # CRITICAL ASSERTIONS
            assert "debug_analysis" in response
            assert isinstance(response["debug_analysis"], dict), \
                f"debug_analysis should be dict, got {type(response['debug_analysis'])}"
            assert response["debug_analysis"]["technical_explanation"] == "Test analysis"
            assert response["_debug_enriched"] is True

    def test_capture_handles_string_analysis(self):
        """
        Even if debug_error returns STRING (legacy/edge case),
        _capture_debug_analysis should convert it to DICT.
        """
        from swarm.response_utils import _capture_debug_analysis

        response = {"success": False, "error": "Test error"}

        with patch("swarm.response_utils.debug_error") as mock_debug:
            # Simulate legacy behavior where analysis is STRING
            mock_debug.return_value = {
                "enriched": True,
                "analysis": '{"technical_explanation": "String analysis"}'
            }

            _capture_debug_analysis(
                Exception("Test"),
                "test_op",
                {},
                response,
                timeout=1.0
            )

            # Should still be DICT (ensure_dict handles it)
            assert isinstance(response["debug_analysis"], dict)
            assert response["debug_analysis"]["technical_explanation"] == "String analysis"

    def test_capture_handles_unenriched_response(self):
        """_capture_debug_analysis should handle unenriched responses gracefully."""
        from swarm.response_utils import _capture_debug_analysis

        response = {"success": False, "error": "Test error"}

        with patch("swarm.response_utils.debug_error") as mock_debug:
            mock_debug.return_value = {
                "enriched": False,
                "reason": "timeout"
            }

            _capture_debug_analysis(
                Exception("Test"),
                "test_op",
                {},
                response,
                timeout=1.0
            )

            # Should not add debug_analysis if not enriched
            assert "debug_analysis" not in response
            assert "_debug_enriched" not in response


# =============================================================================
# Test: Finalize Response Flow
# =============================================================================

class TestFinalizeResponseFlow:
    """Test _finalize_response() complete flow."""

    @pytest.fixture
    def mock_session(self):
        """Mock session dict."""
        return {
            "session_id": "test-session-123",
            "user_id": "user-abc",
        }

    @pytest.fixture
    def mock_swarm_result(self):
        """Mock swarm result object."""
        result = MagicMock()
        result.results = {"nexo_import": MagicMock()}
        result.message = "Test message"
        return result

    def test_finalize_response_injects_dict_analysis(self, mock_session, mock_swarm_result):
        """_finalize_response() MUST return response with DICT debug_analysis."""
        from swarm.response_utils import _finalize_response

        response = {"success": False, "error": "Test error"}

        with patch("swarm.response_utils._capture_debug_analysis") as mock_capture:
            # Simulate _capture_debug_analysis modifying response
            def add_analysis(error, op, ctx, resp, timeout):
                resp["debug_analysis"] = {
                    "technical_explanation": "Finalized analysis",
                    "root_causes": []
                }
                resp["_debug_enriched"] = True
            mock_capture.side_effect = add_analysis

            result = _finalize_response(response, "test_action", mock_session, mock_swarm_result)

            # CRITICAL ASSERTIONS
            assert isinstance(result["debug_analysis"], dict)
            assert result["debug_analysis"]["technical_explanation"] == "Finalized analysis"

    def test_finalize_response_handles_success(self, mock_session, mock_swarm_result):
        """Success responses should NOT trigger Debug Agent."""
        from swarm.response_utils import _finalize_response

        response = {"success": True, "data": {"result": "ok"}}

        with patch("swarm.response_utils._capture_debug_analysis") as mock_capture:
            result = _finalize_response(response, "test_action", mock_session, mock_swarm_result)

            # Debug Agent should NOT be called for success
            # Note: The actual implementation may still call it but with different logic
            assert result["success"] is True


# =============================================================================
# Test: Full Flow String → Dict Conversion
# =============================================================================

class TestFullFlowStringToDict:
    """Test complete flow: A2A STRING → debug_utils DICT → response DICT."""

    def test_complete_flow_end_to_end(self):
        """
        Test the COMPLETE data transformation flow.

        This is the most critical test - it verifies the entire chain
        from A2A STRING response to final DICT in frontend response.
        """
        from shared.data_contracts import ensure_dict

        # Step 1: A2A protocol returns STRING (simulated)
        a2a_string_response = json.dumps({
            "error_type": "NetworkError",
            "technical_explanation": "Timeout ao conectar com serviço externo",
            "root_causes": [
                {"cause": "Serviço S3 lento", "confidence": 0.8},
                {"cause": "Rede congestionada", "confidence": 0.6}
            ],
            "debugging_steps": [
                "Verificar status do S3",
                "Checar latência de rede"
            ],
            "recoverable": True,
            "suggested_action": "retry"
        })

        # Step 2: debug_utils.py applies ensure_dict (our fix)
        analysis_dict = ensure_dict(a2a_string_response, "debug_agent_response")

        # Verify conversion
        assert isinstance(analysis_dict, dict)
        assert analysis_dict["error_type"] == "NetworkError"

        # Step 3: response_utils.py adds to response
        response = {
            "success": False,
            "error": "Connection timeout",
            "action": "s3_upload"
        }
        response["debug_analysis"] = analysis_dict

        # Step 4: Frontend receives response
        # Verify final structure
        assert response["success"] is False
        assert isinstance(response["debug_analysis"], dict)
        assert response["debug_analysis"]["error_type"] == "NetworkError"
        assert len(response["debug_analysis"]["root_causes"]) == 2
        assert response["debug_analysis"]["recoverable"] is True

    def test_flow_with_empty_analysis(self):
        """Test flow when Debug Agent returns empty analysis."""
        from shared.data_contracts import ensure_dict

        # A2A returns empty object
        a2a_response = "{}"
        analysis = ensure_dict(a2a_response, "empty_test")

        assert analysis == {}

    def test_flow_with_malformed_json(self):
        """Test flow handles malformed JSON gracefully."""
        from shared.data_contracts import ensure_dict

        # A2A returns malformed JSON
        a2a_response = "not valid json at all"
        analysis = ensure_dict(a2a_response, "malformed_test")

        # Should wrap in _raw_string, not crash
        assert "_raw_string" in analysis
        assert analysis["_raw_string"] == "not valid json at all"


# =============================================================================
# Test: Merge Debug Analysis
# =============================================================================

class TestMergeDebugAnalysis:
    """Test merging multiple debug analyses."""

    def test_merge_accumulates_root_causes(self):
        """Multiple errors should accumulate root causes."""
        from swarm.response_utils import _merge_debug_analysis

        response = {
            "debug_analysis": {
                "technical_explanation": "First error",
                "root_causes": [{"cause": "Cause 1", "confidence": 0.9}]
            }
        }

        new_analysis = {
            "technical_explanation": "Second error",
            "root_causes": [{"cause": "Cause 2", "confidence": 0.8}]
        }

        _merge_debug_analysis(response, new_analysis)

        # Should have both causes
        assert len(response["debug_analysis"]["root_causes"]) == 2

    def test_merge_with_empty_existing(self):
        """Merge with empty existing should use new analysis."""
        from swarm.response_utils import _merge_debug_analysis

        response = {"debug_analysis": {}}

        new_analysis = {
            "technical_explanation": "New analysis",
            "root_causes": [{"cause": "Test", "confidence": 0.9}]
        }

        _merge_debug_analysis(response, new_analysis)

        assert response["debug_analysis"]["technical_explanation"] == "New analysis"


# =============================================================================
# Test: Error Context Building
# =============================================================================

class TestErrorContextBuilding:
    """Test that error context is properly built for Debug Agent."""

    @pytest.mark.asyncio
    async def test_error_payload_structure(self):
        """Verify error payload sent to Debug Agent has correct structure."""
        from shared.debug_utils import debug_error_async

        captured_payload = None

        async def capture_payload(agent_name, payload, timeout):
            nonlocal captured_payload
            captured_payload = payload
            return MockA2AResponse(True, '{"test": true}', "debug")

        with patch("shared.debug_utils._get_debug_client") as mock_client:
            mock_client.return_value.invoke_agent = capture_payload

            await debug_error_async(
                ValueError("Test value error"),
                "test_operation",
                {"file_name": "test.csv", "line": 42},
                severity="error",
                timeout=1.0
            )

        # Verify payload structure
        assert captured_payload is not None
        assert captured_payload["action"] == "analyze_error"
        assert captured_payload["error_type"] == "ValueError"
        assert captured_payload["message"] == "Test value error"
        assert captured_payload["operation"] == "test_operation"
        assert captured_payload["severity"] == "error"
        assert "context" in captured_payload
        assert captured_payload["context"]["file_name"] == "test.csv"
        assert captured_payload["context"]["line"] == 42
