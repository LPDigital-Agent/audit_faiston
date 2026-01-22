# =============================================================================
# Tests for Debug Agent Tools
# =============================================================================
# Unit tests for DebugAgent tool implementations.
#
# These tests verify:
# - Error signature generation and uniqueness
# - Error classification logic
# - Root cause analysis
# - Pattern matching
# - Documentation search
# - Resolution storage
#
# Run: cd server/agentcore-inventory && python -m pytest tests/test_debug_agent_tools.py -v
# =============================================================================

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# Tests for analyze_error Tool
# =============================================================================

class TestAnalyzeErrorTool:
    """Tests for analyze_error tool implementation."""

    def test_generate_error_signature_consistency(self):
        """Test that same inputs generate same signature."""
        from agents.specialists.debug.tools.analyze_error import generate_error_signature

        sig1 = generate_error_signature("ValueError", "Invalid input", "import")
        sig2 = generate_error_signature("ValueError", "Invalid input", "import")

        assert sig1 == sig2

    def test_generate_error_signature_different_for_different_inputs(self):
        """Test that different inputs generate different signatures."""
        from agents.specialists.debug.tools.analyze_error import generate_error_signature

        sig1 = generate_error_signature("ValueError", "Invalid input", "import")
        sig2 = generate_error_signature("KeyError", "Missing key", "export")

        assert sig1 != sig2

    def test_generate_error_signature_normalizes_uuids(self):
        """Test that UUIDs are normalized in signatures."""
        from agents.specialists.debug.tools.analyze_error import generate_error_signature

        sig1 = generate_error_signature(
            "Error",
            "Failed for id 12345678-1234-1234-1234-123456789abc",
            "op"
        )
        sig2 = generate_error_signature(
            "Error",
            "Failed for id 87654321-4321-4321-4321-cba987654321",
            "op"
        )

        # Should be same after UUID normalization
        assert sig1 == sig2

    def test_classify_error_validation(self):
        """Test validation error classification."""
        from agents.specialists.debug.tools.analyze_error import classify_error

        result = classify_error("ValidationError")
        assert result["recoverable"] is False
        assert result["category"] == "validation"

    def test_classify_error_network(self):
        """Test network error classification."""
        from agents.specialists.debug.tools.analyze_error import classify_error

        result = classify_error("TimeoutError")
        assert result["recoverable"] is True
        assert result["category"] == "network"

    def test_classify_error_unknown(self):
        """Test unknown error classification."""
        from agents.specialists.debug.tools.analyze_error import classify_error

        result = classify_error("CustomUnknownError")
        assert result["recoverable"] is False
        assert result["category"] == "unknown"

    @pytest.mark.asyncio
    async def test_analyze_error_returns_structured_response(self):
        """Test that analyze_error returns proper structure."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.return_value = {"success": True, "patterns": []}

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                result = await analyze_error_tool(
                    error_type="ValueError",
                    message="Invalid input data",
                    operation="import_csv",
                )

                assert result["success"] is True
                assert "error_signature" in result
                assert "technical_explanation" in result
                assert "root_causes" in result
                assert "debugging_steps" in result
                assert "recoverable" in result
                assert "suggested_action" in result

    @pytest.mark.asyncio
    async def test_analyze_error_handles_memory_failure(self):
        """Test graceful handling of memory query failure."""
        with patch("agents.specialists.debug.tools.query_memory_patterns.query_memory_patterns_tool") as mock_memory:
            mock_memory.side_effect = Exception("Memory unavailable")

            with patch("agents.specialists.debug.tools.search_documentation.search_documentation_tool") as mock_docs:
                mock_docs.return_value = {"success": True, "results": []}

                from agents.specialists.debug.tools.analyze_error import analyze_error_tool

                # Should not raise, should gracefully degrade
                result = await analyze_error_tool(
                    error_type="ValueError",
                    message="Test error",
                    operation="test_op",
                )

                assert result["success"] is True


# =============================================================================
# Tests for search_documentation Tool
# =============================================================================

class TestSearchDocumentationTool:
    """Tests for search_documentation tool implementation."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """Test that search returns structured results."""
        from agents.specialists.debug.tools.search_documentation import search_documentation_tool

        result = await search_documentation_tool(
            query="agentcore memory configuration",
            sources=["agentcore"],
            max_results=3,
        )

        assert result["success"] is True
        assert "results" in result
        assert "sources_searched" in result

    @pytest.mark.asyncio
    async def test_search_with_default_sources(self):
        """Test search with default sources."""
        from agents.specialists.debug.tools.search_documentation import search_documentation_tool

        result = await search_documentation_tool(
            query="agent configuration",
        )

        assert result["success"] is True
        assert "agentcore" in result["sources_searched"] or "strands" in result["sources_searched"]

    def test_extract_keywords(self):
        """Test keyword extraction from query."""
        from agents.specialists.debug.tools.search_documentation import _extract_keywords

        keywords = _extract_keywords("agentcore memory storage")
        assert "memory" in keywords

        keywords = _extract_keywords("strands agent hooks lifecycle")
        assert "hooks" in keywords


# =============================================================================
# Tests for query_memory_patterns Tool
# =============================================================================

class TestQueryMemoryPatternsTool:
    """Tests for query_memory_patterns tool implementation."""

    def test_calculate_similarity_exact_match(self):
        """Test exact signature match gets 1.0 similarity."""
        from agents.specialists.debug.tools.query_memory_patterns import _calculate_similarity

        score = _calculate_similarity(
            error_signature="abc12345",
            record_signature="abc12345",
            error_type="ValueError",
            record_type="ValueError",
            operation="import",
            record_operation="import",
        )

        assert score == 1.0

    def test_calculate_similarity_partial_match(self):
        """Test partial signature match gets 0.9 similarity."""
        from agents.specialists.debug.tools.query_memory_patterns import _calculate_similarity

        score = _calculate_similarity(
            error_signature="abc12345xyz",
            record_signature="abc12345000",  # First 8 chars match
            error_type="ValueError",
            record_type="ValueError",
            operation="import",
            record_operation="import",
        )

        assert score == 0.9

    def test_calculate_similarity_type_operation_match(self):
        """Test type + operation match gets 0.8 similarity."""
        from agents.specialists.debug.tools.query_memory_patterns import _calculate_similarity

        score = _calculate_similarity(
            error_signature="different",
            record_signature="completely_different",
            error_type="ValueError",
            record_type="ValueError",
            operation="import",
            record_operation="import",
        )

        assert score == 0.8

    def test_calculate_similarity_type_only_match(self):
        """Test type-only match gets 0.6 similarity."""
        from agents.specialists.debug.tools.query_memory_patterns import _calculate_similarity

        score = _calculate_similarity(
            error_signature="different",
            record_signature="completely_different",
            error_type="ValueError",
            record_type="ValueError",
            operation="import",
            record_operation="export",  # Different operation
        )

        assert score == 0.6

    def test_calculate_similarity_no_match(self):
        """Test no match gets 0.0 similarity."""
        from agents.specialists.debug.tools.query_memory_patterns import _calculate_similarity

        score = _calculate_similarity(
            error_signature="abc",
            record_signature="xyz",
            error_type=None,
            record_type="ValueError",
            operation=None,
            record_operation="import",
        )

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_query_memory_patterns_returns_structure(self):
        """Test that query returns proper structure."""
        with patch("agents.specialists.debug.tools.query_memory_patterns._get_memory") as mock_get_mem:
            mock_memory = MagicMock()
            mock_memory.observe = AsyncMock(return_value=[])
            mock_get_mem.return_value = mock_memory

            from agents.specialists.debug.tools.query_memory_patterns import query_memory_patterns_tool

            result = await query_memory_patterns_tool(
                error_signature="test123",
                error_type="ValueError",
                operation="import",
            )

            assert result["success"] is True
            assert "patterns" in result
            assert "patterns_found" in result


# =============================================================================
# Tests for store_resolution Tool
# =============================================================================

class TestStoreResolutionTool:
    """Tests for store_resolution tool implementation."""

    @pytest.mark.asyncio
    async def test_store_resolution_success(self):
        """Test successful resolution storage."""
        with patch("agents.specialists.debug.tools.store_resolution._get_memory") as mock_get_mem:
            mock_memory = MagicMock()
            mock_memory.learn_episode = AsyncMock(return_value="evt_123")
            mock_get_mem.return_value = mock_memory

            from agents.specialists.debug.tools.store_resolution import store_resolution_tool

            result = await store_resolution_tool(
                error_signature="test123",
                error_type="ValueError",
                operation="import",
                resolution="Fixed by validating input",
                success=True,
                debugging_steps=["Step 1", "Step 2"],
            )

            assert result["success"] is True
            assert result["stored"] is True
            assert "pattern_id" in result

    @pytest.mark.asyncio
    async def test_store_resolution_memory_failure(self):
        """Test graceful handling of memory storage failure."""
        with patch("agents.specialists.debug.tools.store_resolution._get_memory") as mock_get_mem:
            mock_memory = MagicMock()
            mock_memory.learn_episode = AsyncMock(side_effect=Exception("Storage failed"))
            mock_get_mem.return_value = mock_memory

            from agents.specialists.debug.tools.store_resolution import store_resolution_tool

            result = await store_resolution_tool(
                error_signature="test123",
                error_type="ValueError",
                operation="import",
                resolution="Fixed",
                success=True,
            )

            # Should succeed with stored=False (graceful degradation)
            assert result["success"] is True
            assert result["stored"] is False

    @pytest.mark.asyncio
    async def test_store_resolution_generates_pattern_id(self):
        """Test that pattern ID is generated correctly."""
        with patch("agents.specialists.debug.tools.store_resolution._get_memory") as mock_get_mem:
            mock_memory = MagicMock()
            mock_memory.learn_episode = AsyncMock(return_value="evt_123")
            mock_get_mem.return_value = mock_memory

            from agents.specialists.debug.tools.store_resolution import store_resolution_tool

            result = await store_resolution_tool(
                error_signature="abcdef123456",
                error_type="ValueError",
                operation="import",
                resolution="Fixed",
                success=True,
            )

            # Pattern ID should start with "pat_" and contain part of signature
            assert result["pattern_id"].startswith("pat_")
            assert "abcdef12" in result["pattern_id"]


# =============================================================================
# Tests for Root Cause Analysis
# =============================================================================

class TestRootCauseAnalysis:
    """Tests for root cause analysis logic."""

    def test_analyze_root_causes_validation_error(self):
        """Test root cause analysis for validation errors."""
        from agents.specialists.debug.tools.analyze_error import _analyze_root_causes

        causes = _analyze_root_causes(
            error_type="ValidationError",
            message="Missing required field: part_number",
            operation="import",
            stack_trace=None,
            context=None,
            similar_patterns=[],
        )

        assert len(causes) > 0
        # Should identify validation as root cause
        validation_cause = any("inválid" in c["cause"].lower() or "campo" in c["cause"].lower() for c in causes)
        assert validation_cause

    def test_analyze_root_causes_timeout_error(self):
        """Test root cause analysis for timeout errors."""
        from agents.specialists.debug.tools.analyze_error import _analyze_root_causes

        causes = _analyze_root_causes(
            error_type="TimeoutError",
            message="Connection timed out after 30s",
            operation="fetch_data",
            stack_trace=None,
            context=None,
            similar_patterns=[],
        )

        assert len(causes) > 0
        # Should identify timeout as root cause
        timeout_cause = any("timeout" in c["cause"].lower() for c in causes)
        assert timeout_cause

    def test_analyze_root_causes_uses_patterns(self):
        """Test that root cause analysis uses similar patterns."""
        from agents.specialists.debug.tools.analyze_error import _analyze_root_causes

        patterns = [{
            "pattern_id": "pat_123",
            "resolution": "Fixed by increasing timeout",
            "similarity": 0.9,
        }]

        causes = _analyze_root_causes(
            error_type="TimeoutError",
            message="Timeout",
            operation="fetch",
            stack_trace=None,
            context=None,
            similar_patterns=patterns,
        )

        # Should include pattern-based cause
        pattern_cause = any("histórico" in c["cause"].lower() or "padrão" in c["cause"].lower() for c in causes)
        assert pattern_cause


# =============================================================================
# Tests for Debugging Steps Generation
# =============================================================================

class TestDebuggingSteps:
    """Tests for debugging steps generation."""

    def test_generate_steps_validation(self):
        """Test debugging steps for validation errors."""
        from agents.specialists.debug.tools.analyze_error import _generate_debugging_steps

        steps = _generate_debugging_steps(
            error_type="ValidationError",
            operation="import",
            classification={"category": "validation", "recoverable": False},
            similar_patterns=[],
        )

        assert len(steps) > 0
        # Should mention input/data validation
        assert any("dados" in s.lower() or "input" in s.lower() for s in steps)

    def test_generate_steps_network(self):
        """Test debugging steps for network errors."""
        from agents.specialists.debug.tools.analyze_error import _generate_debugging_steps

        steps = _generate_debugging_steps(
            error_type="TimeoutError",
            operation="fetch",
            classification={"category": "network", "recoverable": True},
            similar_patterns=[],
        )

        assert len(steps) > 0
        # Should mention network/connectivity
        assert any("conectividade" in s.lower() or "rede" in s.lower() or "timeout" in s.lower() for s in steps)

    def test_generate_steps_limits_to_five(self):
        """Test that debugging steps are limited to 5."""
        from agents.specialists.debug.tools.analyze_error import _generate_debugging_steps

        # Provide patterns with many steps
        patterns = [{
            "debugging_steps": ["S1", "S2", "S3", "S4", "S5", "S6", "S7"],
        }]

        steps = _generate_debugging_steps(
            error_type="Error",
            operation="op",
            classification={"category": "unknown", "recoverable": False},
            similar_patterns=patterns,
        )

        assert len(steps) <= 5


# =============================================================================
# Tests for Suggested Action
# =============================================================================

class TestSuggestedAction:
    """Tests for suggested action determination."""

    def test_suggested_action_recoverable(self):
        """Test suggested action for recoverable errors."""
        from agents.specialists.debug.tools.analyze_error import _determine_suggested_action

        action = _determine_suggested_action(
            is_recoverable=True,
            classification={"category": "network"},
            similar_patterns=[],
        )

        assert action == "retry"

    def test_suggested_action_permission(self):
        """Test suggested action for permission errors."""
        from agents.specialists.debug.tools.analyze_error import _determine_suggested_action

        action = _determine_suggested_action(
            is_recoverable=False,
            classification={"category": "permission"},
            similar_patterns=[],
        )

        assert action == "escalate"

    def test_suggested_action_validation(self):
        """Test suggested action for validation errors."""
        from agents.specialists.debug.tools.analyze_error import _determine_suggested_action

        action = _determine_suggested_action(
            is_recoverable=False,
            classification={"category": "validation"},
            similar_patterns=[],
        )

        assert action == "abort"

    def test_suggested_action_with_high_success_pattern(self):
        """Test that high success rate patterns suggest retry."""
        from agents.specialists.debug.tools.analyze_error import _determine_suggested_action

        patterns = [{"success_rate": 0.9}]

        action = _determine_suggested_action(
            is_recoverable=False,
            classification={"category": "unknown"},
            similar_patterns=patterns,
        )

        assert action == "retry"


# =============================================================================
# Tests for Technical Explanation
# =============================================================================

class TestTechnicalExplanation:
    """Tests for technical explanation generation."""

    def test_explanation_in_portuguese(self):
        """Test that explanation is in Portuguese."""
        from agents.specialists.debug.tools.analyze_error import _build_technical_explanation

        explanation = _build_technical_explanation(
            error_type="ValueError",
            message="Invalid input",
            operation="import",
            classification={"category": "validation", "recoverable": False},
        )

        # Should contain Portuguese keywords
        assert "validação" in explanation.lower() or "erro" in explanation.lower()

    def test_explanation_includes_error_info(self):
        """Test that explanation includes error information."""
        from agents.specialists.debug.tools.analyze_error import _build_technical_explanation

        explanation = _build_technical_explanation(
            error_type="TimeoutError",
            message="Connection timeout after 30s",
            operation="fetch_data",
            classification={"category": "network", "recoverable": True},
        )

        assert "TimeoutError" in explanation
        assert "fetch_data" in explanation
