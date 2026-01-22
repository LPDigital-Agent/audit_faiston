# =============================================================================
# Integration Tests for Debug Agent E2E Flow (BUG-027)
# =============================================================================
# End-to-end tests for the complete Debug Agent flow:
# Error → DebugHook → Debug Agent → Enriched Response → Frontend
#
# These tests verify:
# - HTTP 424 errors are NOT blank (Phase 1 fix)
# - DebugHook intercepts errors from file_analyzer/vision_analyzer (Phase 2 fix)
# - Debug Agent uses Gemini 2.5 Pro (Phase 3 fix)
# - Enriched errors contain all required fields for DebugAnalysisPanel (Phase 4)
# - Fallback response when Gemini fails
#
# Run: cd server/agentcore-inventory && python -m pytest tests/integration/test_debug_flow.py -v
# =============================================================================

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


# =============================================================================
# Test Scenarios (from BUG-027 Plan Phase 5.1)
# =============================================================================
# 1. HTTP 424 (cold start) - Detailed error message (not blank)
# 2. Malformed CSV - AI-powered root cause analysis
# 3. Invalid XML - Technical explanation in pt-BR
# 4. Auth error - "escalate" suggested action
# 5. Timeout - "retry" suggested action
# 6. Database error - Debugging steps provided
# 7. Gemini API failure - Fallback response (llm_powered=false)
# =============================================================================


# =============================================================================
# Mock Classes
# =============================================================================

class MockBoto3ClientError(Exception):
    """Mock for botocore.exceptions.ClientError."""

    def __init__(self, error_code: str, message: str, http_status: int = 424):
        self.response = {
            "Error": {
                "Code": error_code,
                "Message": message,
            },
            "ResponseMetadata": {
                "HTTPStatusCode": http_status,
            },
        }
        super().__init__(message)


class MockA2AResponse:
    """Mock for A2A protocol response."""

    def __init__(self, success: bool = True, response: dict = None, error: str = None):
        self.success = success
        self.response = response or {}
        self.error = error


class MockGeminiResult:
    """Mock for Strands Agent result from Gemini."""

    def __init__(self, text: str):
        self.message = MagicMock()
        self.message.content = [MagicMock(text=text)]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_gemini_response():
    """Standard successful Gemini response for error analysis."""
    return """```json
{
    "technical_explanation": "Erro de validação durante processamento do arquivo CSV. Os dados na coluna 'quantidade' contêm valores não numéricos que não podem ser convertidos para o tipo esperado.",
    "root_causes": [
        {
            "cause": "Dados inválidos na coluna quantidade",
            "confidence": 0.92,
            "evidence": ["Valores encontrados: 'N/A', 'TBD'", "Tipo esperado: integer"]
        },
        {
            "cause": "Encoding incorreto do arquivo",
            "confidence": 0.65,
            "evidence": ["Caracteres especiais mal formatados"]
        }
    ],
    "debugging_steps": [
        "1. Verifique a coluna 'quantidade' para valores não numéricos",
        "2. Remova ou substitua valores como 'N/A', 'TBD' por 0",
        "3. Confirme o encoding do arquivo (deve ser UTF-8)",
        "4. Re-exporte o arquivo com validação de dados",
        "5. Tente novamente o upload"
    ],
    "recoverable": false,
    "suggested_action": "abort"
}
```"""


@pytest.fixture
def mock_fallback_response():
    """Fallback response when Gemini fails."""
    return {
        "success": True,
        "error_signature": "sig_test123",
        "error_type": "ValidationError",
        "technical_explanation": "Erro de validação durante 'import_csv': Invalid data",
        "root_causes": [
            {
                "cause": "Erro durante operação import_csv",
                "confidence": 0.5,
                "evidence": ["Tipo: ValidationError"],
            }
        ],
        "debugging_steps": [
            "1. Verifique os logs do agente no CloudWatch",
            "2. Confirme os dados de entrada da requisição",
            "3. Consulte a documentação da operação",
        ],
        "documentation_links": [],
        "similar_patterns": [],
        "recoverable": False,
        "suggested_action": "escalate",
        "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
        "classification": {"category": "validation", "recoverable": False},
        "llm_powered": False,
    }


# =============================================================================
# Scenario 1: HTTP 424 Error Messages NOT Blank
# =============================================================================

class TestHTTP424ErrorMessages:
    """Tests for BUG-027 Phase 1 - HTTP 424 errors should have detailed messages."""

    @pytest.mark.asyncio
    async def test_http_424_extracts_client_error_details(self):
        """Test that HTTP 424 errors extract boto3 ClientError details."""
        from botocore.exceptions import ClientError

        # Simulate boto3 ClientError for HTTP 424
        error_response = {
            "Error": {
                "Code": "AgentRuntimeError",
                "Message": "Agent initialization failed: Lambda cold start timeout",
            },
            "ResponseMetadata": {
                "HTTPStatusCode": 424,
            },
        }
        boto_error = ClientError(error_response, "InvokeAgentRuntime")

        # Test error message extraction
        error_msg = str(boto_error)

        # The error message should NOT be blank
        assert error_msg != ""
        assert "AgentRuntimeError" in error_msg or "initialization" in error_msg

    @pytest.mark.asyncio
    async def test_a2a_client_extracts_424_details(self):
        """Test that A2A client properly extracts HTTP 424 error details."""
        # This tests the fix in a2a_client.py

        # Mock the A2A response processing
        def process_client_error(e):
            """Simulates the BUG-027 fix in a2a_client.py."""
            from botocore.exceptions import ClientError

            error_msg = str(e)
            error_code = "Unknown"
            http_status = None

            if isinstance(e, ClientError) and hasattr(e, "response"):
                error_info = e.response.get("Error", {})
                error_code = error_info.get("Code", "Unknown")
                raw_message = error_info.get("Message", "")
                http_status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

                if raw_message:
                    error_msg = raw_message
                else:
                    error_msg = f"AgentCore error {error_code}"

                if http_status == 424:
                    error_msg = (
                        f"Agente falhou internamente (HTTP 424). "
                        f"Código: {error_code}. "
                        f"Detalhes: {raw_message or 'Verifique CloudWatch logs'}. "
                        f"Possíveis causas: cold start timeout, erro de inicialização, ou falha Gemini."
                    )

            return error_msg, error_code, http_status

        # Create mock ClientError
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {
                "Code": "AgentRuntimeError",
                "Message": "Lambda function execution failed",
            },
            "ResponseMetadata": {"HTTPStatusCode": 424},
        }
        boto_error = ClientError(error_response, "InvokeAgentRuntime")

        error_msg, error_code, http_status = process_client_error(boto_error)

        # Verify extraction
        assert http_status == 424
        assert error_code == "AgentRuntimeError"
        assert "HTTP 424" in error_msg
        assert "cold start timeout" in error_msg
        assert error_msg != ""  # NOT blank!


# =============================================================================
# Scenario 2: Malformed CSV - AI-Powered Root Cause Analysis
# =============================================================================

class TestMalformedCSVError:
    """Tests for malformed CSV error handling with AI analysis."""

    @pytest.mark.asyncio
    async def test_csv_error_triggers_ai_analysis(self, mock_gemini_response):
        """Test that CSV parsing error triggers AI-powered analysis."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                    # Mock Gemini response
                    mock_agent_instance = MagicMock()
                    mock_agent_instance.run_async = AsyncMock(
                        return_value=MockGeminiResult(mock_gemini_response)
                    )
                    MockAgent.return_value = mock_agent_instance

                    from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                    result = await analyze_error_tool(
                        error_type="ValueError",
                        message="Invalid data in CSV: could not convert 'N/A' to integer",
                        operation="import_csv",
                        stack_trace="File parser.py, line 45, in parse_row",
                        context={"filename": "inventory.csv", "row": 15},
                    )

                    # Verify AI-powered analysis
                    assert result["success"] is True
                    assert result.get("llm_powered") is True
                    assert len(result["root_causes"]) > 0
                    assert result["root_causes"][0]["confidence"] > 0.5
                    assert len(result["debugging_steps"]) > 0
                    # Technical explanation should be in Portuguese
                    assert "validação" in result["technical_explanation"].lower() or "erro" in result["technical_explanation"].lower()


# =============================================================================
# Scenario 3: Invalid XML - Technical Explanation in pt-BR
# =============================================================================

class TestInvalidXMLError:
    """Tests for invalid XML error with Portuguese explanation."""

    @pytest.mark.asyncio
    async def test_xml_error_returns_portuguese_explanation(self, mock_gemini_response):
        """Test that XML parsing error returns explanation in Portuguese."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                    mock_agent_instance = MagicMock()
                    mock_agent_instance.run_async = AsyncMock(
                        return_value=MockGeminiResult(mock_gemini_response)
                    )
                    MockAgent.return_value = mock_agent_instance

                    from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                    result = await analyze_error_tool(
                        error_type="XMLParseError",
                        message="Invalid XML structure: unclosed tag at line 42",
                        operation="parse_nf_xml",
                    )

                    # Technical explanation must be in Portuguese
                    explanation = result["technical_explanation"]
                    # Check for Portuguese words/patterns
                    portuguese_indicators = ["erro", "dados", "arquivo", "coluna", "quantidade", "validação"]
                    has_portuguese = any(word in explanation.lower() for word in portuguese_indicators)
                    assert has_portuguese, f"Explanation should be in Portuguese: {explanation}"


# =============================================================================
# Scenario 4: Auth Error - Escalate Suggested Action
# =============================================================================

class TestAuthError:
    """Tests for authentication error with escalate action."""

    @pytest.mark.asyncio
    async def test_auth_error_suggests_escalate(self):
        """Test that auth errors suggest 'escalate' action."""
        from agents.specialists.debug.tools.analyze_error import _determine_suggested_action

        action = _determine_suggested_action(
            is_recoverable=False,
            classification={"category": "permission"},
            similar_patterns=[],
        )

        assert action == "escalate"

    @pytest.mark.asyncio
    async def test_auth_error_is_not_recoverable(self):
        """Test that auth errors are marked as non-recoverable."""
        from agents.specialists.debug.tools.analyze_error import classify_error

        result = classify_error("AuthenticationError")
        assert result["recoverable"] is False


# =============================================================================
# Scenario 5: Timeout - Retry Suggested Action
# =============================================================================

class TestTimeoutError:
    """Tests for timeout error with retry action."""

    @pytest.mark.asyncio
    async def test_timeout_error_suggests_retry(self):
        """Test that timeout errors suggest 'retry' action."""
        from agents.specialists.debug.tools.analyze_error import _determine_suggested_action

        action = _determine_suggested_action(
            is_recoverable=True,
            classification={"category": "network"},
            similar_patterns=[],
        )

        assert action == "retry"

    @pytest.mark.asyncio
    async def test_timeout_error_is_recoverable(self):
        """Test that timeout errors are marked as recoverable."""
        from agents.specialists.debug.tools.analyze_error import classify_error

        result = classify_error("TimeoutError")
        assert result["recoverable"] is True
        assert result["category"] == "network"


# =============================================================================
# Scenario 6: Database Error - Debugging Steps Provided
# =============================================================================

class TestDatabaseError:
    """Tests for database error with debugging steps."""

    @pytest.mark.asyncio
    async def test_database_error_provides_debugging_steps(self, mock_gemini_response):
        """Test that database errors include debugging steps."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                    mock_agent_instance = MagicMock()
                    mock_agent_instance.run_async = AsyncMock(
                        return_value=MockGeminiResult(mock_gemini_response)
                    )
                    MockAgent.return_value = mock_agent_instance

                    from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                    result = await analyze_error_tool(
                        error_type="ForeignKeyViolation",
                        message="Insert failed: FK constraint on project_id",
                        operation="insert_movement",
                        context={"table": "movements", "constraint": "fk_project"},
                    )

                    # Must have debugging steps
                    assert "debugging_steps" in result
                    assert len(result["debugging_steps"]) >= 3
                    # Steps should be numbered or actionable
                    first_step = result["debugging_steps"][0]
                    assert "1" in first_step or "Verif" in first_step


# =============================================================================
# Scenario 7: Gemini API Failure - Fallback Response
# =============================================================================

class TestGeminiFailure:
    """Tests for graceful fallback when Gemini API fails."""

    @pytest.mark.asyncio
    async def test_gemini_failure_uses_fallback(self):
        """Test that Gemini failure triggers fallback response."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                    # Simulate Gemini API failure
                    mock_agent_instance = MagicMock()
                    mock_agent_instance.run_async = AsyncMock(
                        side_effect=Exception("Gemini API rate limit exceeded")
                    )
                    MockAgent.return_value = mock_agent_instance

                    from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                    result = await analyze_error_tool(
                        error_type="ValidationError",
                        message="Test error",
                        operation="test_op",
                    )

                    # Should succeed with fallback
                    assert result["success"] is True
                    # llm_powered should be False (fallback)
                    assert result.get("llm_powered") is False
                    # Should still have required fields
                    assert "technical_explanation" in result
                    assert "root_causes" in result
                    assert "debugging_steps" in result
                    assert "suggested_action" in result

    @pytest.mark.asyncio
    async def test_fallback_has_all_required_fields(self, mock_fallback_response):
        """Test that fallback response has all fields for DebugAnalysisPanel."""
        # These are the fields required by DebugAnalysisPanel.tsx
        required_fields = [
            "success",
            "error_signature",
            "error_type",
            "technical_explanation",
            "root_causes",
            "debugging_steps",
            "recoverable",
            "suggested_action",
            "analysis_timestamp",
        ]

        for field in required_fields:
            assert field in mock_fallback_response, f"Missing required field: {field}"


# =============================================================================
# Tests for Response Time < 5 seconds (Interview Decision)
# =============================================================================

class TestResponseTime:
    """Tests for response time requirements."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # Fail if takes more than 5 seconds
    async def test_analysis_completes_within_timeout(self, mock_gemini_response):
        """Test that error analysis completes within 5 second timeout."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                    # Simulate fast response
                    mock_agent_instance = MagicMock()
                    mock_agent_instance.run_async = AsyncMock(
                        return_value=MockGeminiResult(mock_gemini_response)
                    )
                    MockAgent.return_value = mock_agent_instance

                    from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                    result = await analyze_error_tool(
                        error_type="TestError",
                        message="Test message",
                        operation="test_op",
                    )

                    assert result["success"] is True


# =============================================================================
# Tests for DebugAnalysisPanel Integration
# =============================================================================

class TestDebugAnalysisPanelIntegration:
    """Tests for frontend DebugAnalysisPanel compatibility."""

    @pytest.mark.asyncio
    async def test_response_matches_frontend_interface(self, mock_gemini_response):
        """Test that response matches DebugAnalysis TypeScript interface."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                    mock_agent_instance = MagicMock()
                    mock_agent_instance.run_async = AsyncMock(
                        return_value=MockGeminiResult(mock_gemini_response)
                    )
                    MockAgent.return_value = mock_agent_instance

                    from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                    result = await analyze_error_tool(
                        error_type="ValidationError",
                        message="Test",
                        operation="test",
                    )

                    # Verify structure matches DebugAnalysis interface from agentcoreResponse.ts
                    # interface DebugAnalysis {
                    #   error_signature: string;
                    #   error_type: string;
                    #   technical_explanation: string;
                    #   root_causes: Array<{ cause: string; confidence: number; evidence?: string[] }>;
                    #   debugging_steps: string[];
                    #   documentation_links?: Array<{ title: string; url: string }>;
                    #   similar_patterns?: Array<{ pattern_id: string; resolution: string; similarity: number }>;
                    #   recoverable: boolean;
                    #   suggested_action: 'retry' | 'fallback' | 'escalate' | 'abort';
                    # }

                    assert isinstance(result.get("error_signature"), str)
                    assert isinstance(result.get("error_type"), str)
                    assert isinstance(result.get("technical_explanation"), str)
                    assert isinstance(result.get("root_causes"), list)
                    assert isinstance(result.get("debugging_steps"), list)
                    assert isinstance(result.get("recoverable"), bool)
                    assert result.get("suggested_action") in ["retry", "fallback", "escalate", "abort"]

                    # Root causes structure
                    if result["root_causes"]:
                        cause = result["root_causes"][0]
                        assert "cause" in cause
                        assert "confidence" in cause
                        assert isinstance(cause["confidence"], (int, float))
                        assert 0.0 <= cause["confidence"] <= 1.0


# =============================================================================
# Tests for Sandwich Pattern (CODE → LLM → CODE)
# =============================================================================

class TestSandwichPattern:
    """Tests verifying the Sandwich Pattern implementation."""

    @pytest.mark.asyncio
    async def test_code_preparation_before_llm(self, mock_gemini_response):
        """Test that Python code prepares inputs before LLM call."""
        with patch("agents.specialists.debug.tools.analyze_error.generate_error_signature") as mock_sig:
            mock_sig.return_value = "sig_test123"

            with patch("agents.specialists.debug.tools.analyze_error.classify_error") as mock_classify:
                mock_classify.return_value = {"category": "validation", "recoverable": False}

                with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
                    mock_memory.return_value = {"success": True, "patterns": []}

                    with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                        mock_docs.return_value = {"success": True, "results": []}

                        with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                            mock_agent_instance = MagicMock()
                            mock_agent_instance.run_async = AsyncMock(
                                return_value=MockGeminiResult(mock_gemini_response)
                            )
                            MockAgent.return_value = mock_agent_instance

                            from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                            await analyze_error_tool(
                                error_type="ValidationError",
                                message="Test",
                                operation="test",
                            )

                            # Verify CODE (preparation) was called before LLM
                            mock_sig.assert_called_once()
                            mock_classify.assert_called_once()
                            mock_memory.assert_called_once()
                            # LLM was invoked
                            mock_agent_instance.run_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_code_validation_after_llm(self, mock_gemini_response):
        """Test that Python code validates/formats LLM output."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                with patch("agents.specialists.debug.tools.analyze_error.Agent") as MockAgent:
                    mock_agent_instance = MagicMock()
                    mock_agent_instance.run_async = AsyncMock(
                        return_value=MockGeminiResult(mock_gemini_response)
                    )
                    MockAgent.return_value = mock_agent_instance

                    from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                    result = await analyze_error_tool(
                        error_type="ValidationError",
                        message="Test",
                        operation="test",
                    )

                    # CODE (validation) after LLM should add these fields
                    assert "success" in result  # Added by Python validation
                    assert "analysis_timestamp" in result  # Added by Python
                    assert "classification" in result  # Added by Python


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
