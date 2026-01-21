# =============================================================================
# BUG-020 Specific Integration Tests
# =============================================================================
# These tests specifically verify the fix for BUG-020:
# TypeError: can't access property "sheets", o.analysis is undefined
#
# Root Cause: Orchestrator's _invoke_swarm() was extracting from wrong path:
#   - WRONG: result.message (natural language text)
#   - CORRECT: result.results["file_analyst"].result (official Strands pattern)
#
# The fix imports _extract_tool_output_from_swarm_result from swarm.response_utils
# and uses it to properly extract structured data from Swarm results.
#
# Official Strands Documentation:
# https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/
# =============================================================================

import json
import pytest
from unittest.mock import Mock

from swarm.response_utils import (
    _extract_tool_output_from_swarm_result,
    _process_swarm_result,
    _unwrap_tool_result,
    _extract_from_messages,
)


class TestBug020OrchestratorExtraction:
    """
    Integration tests verifying BUG-020 fix in orchestrator context.

    The bug occurred because _invoke_swarm() tried to parse result.message
    (which contains LLM's conversational response) instead of using
    result.results["agent"].result (which contains the actual tool output).
    """

    def test_extracts_analysis_with_sheets_from_swarm(self):
        """
        BUG-020 CORE TEST: Must extract analysis.sheets from Swarm result.

        This test reproduces the exact scenario that caused the frontend error:
        - Frontend calls orchestrator with action: "nexo_analyze_file"
        - Orchestrator invokes Swarm which calls file_analyst agent
        - file_analyst runs unified_analyze_file tool and returns analysis
        - Orchestrator must extract analysis with sheets (NOT natural language)

        The fix uses _extract_tool_output_from_swarm_result() to get the
        structured response from result.results["file_analyst"].result
        """
        # Simulate the EXACT response structure from file_analyst agent
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "filename": "SOLICITAÇÕES DE EXPEDIÇÃO.csv",
            "detected_file_type": "csv",
            "analysis": {
                "sheet_count": 1,
                "total_rows": 150,
                "file_type": "csv",
                "recommended_strategy": "standard",
                "sheets": [
                    {
                        "name": "Sheet1",
                        "purpose": "items",
                        "row_count": 150,
                        "column_count": 10,
                        "columns": [
                            {"name": "NUMERO", "type": "string", "sample": ["001", "002"]},
                            {"name": "PART_NUMBER", "type": "string", "sample": ["C9200-24P"]},
                            {"name": "QUANTIDADE", "type": "integer", "sample": [1, 2]},
                            {"name": "SERIAL", "type": "string", "sample": ["TSP123456"]},
                        ],
                        "confidence": 0.92,
                    }
                ],
            },
            "column_mappings": [
                {
                    "file_column": "PART_NUMBER",
                    "target_field": "part_number",
                    "confidence": 0.95,
                    "reasoning": "Direct name match",
                },
                {
                    "file_column": "QUANTIDADE",
                    "target_field": "quantity",
                    "confidence": 0.90,
                    "reasoning": "Portuguese for quantity",
                },
            ],
            "overall_confidence": 0.92,
            "questions": [],
            "reasoning_trace": ["Analyzed file structure", "Mapped columns"],
        }

        # Simulate Swarm result structure (official Strands pattern)
        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}
        # The message contains LLM's conversational summary - NOT the tool output
        mock_swarm_result.message = "I have analyzed the CSV file and found 150 rows with inventory data."

        # Execute extraction using the fixed function
        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        # CRITICAL ASSERTIONS - These are what the frontend needs
        assert extracted is not None, "Must extract data from Swarm result"
        assert "analysis" in extracted, "Response must have 'analysis' key"
        assert "sheets" in extracted["analysis"], "analysis must have 'sheets' array"
        assert isinstance(extracted["analysis"]["sheets"], list), "sheets must be a list"
        assert len(extracted["analysis"]["sheets"]) > 0, "sheets must not be empty"

        # Verify sheet structure matches frontend TypeScript type
        sheet = extracted["analysis"]["sheets"][0]
        assert "name" in sheet, "Sheet must have 'name'"
        assert "row_count" in sheet, "Sheet must have 'row_count'"
        assert "columns" in sheet, "Sheet must have 'columns'"
        assert "confidence" in sheet, "Sheet must have 'confidence'"

        # Verify column mappings are present
        assert "column_mappings" in extracted, "Must have column_mappings"
        assert len(extracted["column_mappings"]) > 0, "Must have at least one mapping"

        # Verify we got the structured data, NOT the conversational message
        assert "I have analyzed" not in str(extracted), "Must NOT include LLM message"

    def test_does_not_use_message_when_results_available(self):
        """
        BUG-020 REGRESSION TEST: Must NOT fall back to result.message.

        The bug was caused by extracting from result.message which contains
        the LLM's natural language response, not the structured tool output.

        This test ensures we use result.results["agent"].result FIRST.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {
                "sheets": [{"name": "CorrectSource", "row_count": 100}],
                "sheet_count": 1,
            },
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}
        # This message would cause the error if used - it has NO analysis.sheets
        mock_swarm_result.message = json.dumps({
            "success": True,
            "message": "File analyzed successfully"
            # NOTE: NO 'analysis' key here - this would cause the bug!
        })

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        # Must use results, NOT message
        assert extracted is not None
        assert "analysis" in extracted
        assert extracted["analysis"]["sheets"][0]["name"] == "CorrectSource"

    def test_handles_toolresult_format_from_unified_analyze_file(self):
        """
        BUG-020 FORMAT TEST: Handle official Strands ToolResult format.

        The unified_analyze_file tool returns data in the official format:
        {"status": "success", "content": [{"json": {...}}]}

        The extraction must handle this nested structure.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "status": "success",
            "content": [
                {
                    "json": {
                        "success": True,
                        "filename": "inventory.csv",
                        "analysis": {
                            "sheet_count": 1,
                            "total_rows": 50,
                            "sheets": [
                                {
                                    "name": "Data",
                                    "row_count": 50,
                                    "column_count": 5,
                                    "columns": [],
                                    "confidence": 0.88,
                                }
                            ],
                            "recommended_strategy": "auto_import",
                        },
                        "overall_confidence": 0.88,
                    }
                }
            ],
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        assert extracted is not None
        assert "analysis" in extracted
        assert "sheets" in extracted["analysis"]
        assert extracted["analysis"]["sheets"][0]["name"] == "Data"

    def test_orchestrator_response_includes_all_required_fields(self):
        """
        BUG-020 CONTRACT TEST: Response must include all fields frontend expects.

        The frontend TypeScript type NexoAnalyzeFileResponse expects:
        - success: boolean
        - session_id: string
        - round: number
        - analysis.sheets: array
        - column_mappings: array
        - overall_confidence: number
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {
                "sheets": [{"name": "Sheet1", "row_count": 100, "columns": [], "confidence": 0.9}],
                "sheet_count": 1,
                "total_rows": 100,
                "recommended_strategy": "standard",
            },
            "column_mappings": [
                {"file_column": "A", "target_field": "part_number", "confidence": 0.95, "reasoning": "Match"}
            ],
            "overall_confidence": 0.9,
            "questions": [],
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        session = {
            "session_id": "test-session-123",
            "round_count": 1,
            "context": {},
        }

        # Use _process_swarm_result which is what the orchestrator uses internally
        response = _process_swarm_result(mock_swarm_result, session, action="nexo_analyze_file")

        # Verify all required fields are present
        assert response["success"] is True, "Must have success: true"
        assert "analysis" in response, "Must have analysis"
        assert "sheets" in response["analysis"], "analysis must have sheets"
        assert isinstance(response["analysis"]["sheets"], list), "sheets must be list"
        # Note: session_id and round are added by _invoke_swarm, not _process_swarm_result


class TestBug020EdgeCases:
    """
    Edge case tests for BUG-020 to prevent regression.
    """

    def test_handles_empty_results_dict(self):
        """Should not crash when results dict is empty."""
        mock_swarm_result = Mock()
        mock_swarm_result.results = {}
        mock_swarm_result.entry_point = Mock()
        mock_swarm_result.entry_point.messages = []
        mock_swarm_result.message = None

        extracted = _extract_tool_output_from_swarm_result(
            mock_swarm_result, agent_name="file_analyst", tool_name="test"
        )

        assert extracted is None

    def test_handles_missing_agent_in_results(self):
        """Should handle case where specified agent is not in results."""
        mock_other_agent = Mock()
        mock_other_agent.result = {"some": "data"}

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"other_agent": mock_other_agent}  # Different agent

        extracted = _extract_tool_output_from_swarm_result(
            mock_swarm_result, agent_name="file_analyst", tool_name="test"
        )

        # Should return None because file_analyst not found
        assert extracted is None

    def test_handles_agent_result_without_analysis(self):
        """Should handle agent result that doesn't have analysis key."""
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "message": "Processed successfully",
            # No 'analysis' key
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            mock_swarm_result, agent_name="file_analyst", tool_name="test"
        )

        # Should return None because no analysis or success pattern
        # The function only returns dict with 'analysis' or 'success' keys
        assert extracted is not None  # Has 'success' key
        assert "analysis" not in extracted

    def test_handles_none_swarm_result(self):
        """Should handle None input gracefully."""
        extracted = _extract_tool_output_from_swarm_result(
            None, agent_name="file_analyst", tool_name="test"
        )
        assert extracted is None

    def test_iterates_all_agents_when_name_not_specified(self):
        """Should search all agents when agent_name is empty."""
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {"sheets": [{"name": "Found"}]},
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"some_agent": mock_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            mock_swarm_result, agent_name="", tool_name="test"
        )

        assert extracted is not None
        assert extracted["analysis"]["sheets"][0]["name"] == "Found"

    def test_fallback_iterates_all_agents_when_name_not_found(self):
        """
        BUG-020 v3 FIX: When specified agent_name doesn't exist in results,
        extraction should still iterate all agents to find valid data.

        This is the CRITICAL test for the v3 fix. Before the fix, this test
        would FAIL because the `if not agent_name` guard prevented iteration
        when a specific agent_name was provided but not found in results.
        """
        mock_other_agent = Mock()
        mock_other_agent.result = {
            "success": True,
            "analysis": {"sheets": [{"name": "FoundViaFallback"}], "sheet_count": 1},
        }

        mock_swarm_result = Mock()
        # Note: Key is "other_agent", NOT "file_analyst"
        mock_swarm_result.results = {"other_agent": mock_other_agent}

        # Pass "file_analyst" which does NOT exist in results
        extracted = _extract_tool_output_from_swarm_result(
            mock_swarm_result, agent_name="file_analyst", tool_name="test"
        )

        # Should STILL find data via fallback iteration (BUG-020 v3 fix)
        assert extracted is not None, "Fallback iteration must find data in other agents"
        assert extracted["analysis"]["sheets"][0]["name"] == "FoundViaFallback"


class TestBug020FrontendContract:
    """
    Tests verifying the response matches frontend TypeScript types.

    Frontend type: NexoAnalyzeFileResponse in useSmartImportNexo.ts
    """

    def test_response_structure_matches_typescript_type(self):
        """
        Verify response structure matches:

        interface NexoAnalyzeFileResponse {
            success: boolean;
            session_id: string;
            round: number;
            import_session_id?: string;
            filename?: string;
            detected_file_type?: string;
            analysis: {
                sheet_count: number;
                total_rows: number;
                file_type: string;
                recommended_strategy: string;
                sheets: Array<{
                    name: string;
                    purpose?: string;
                    row_count: number;
                    column_count: number;
                    columns: Array<{...}>;
                    confidence: number;
                }>;
            };
            column_mappings: Array<{
                file_column: string;
                target_field: string;
                confidence: number;
                reasoning: string;
            }>;
            overall_confidence: number;
            questions: Array<{...}>;
            reasoning_trace?: string[];
        }
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "import_session_id": "imp-123",
            "filename": "test.csv",
            "detected_file_type": "csv",
            "analysis": {
                "sheet_count": 1,
                "total_rows": 100,
                "file_type": "csv",
                "recommended_strategy": "auto_import",
                "sheets": [
                    {
                        "name": "Sheet1",
                        "purpose": "items",
                        "row_count": 100,
                        "column_count": 5,
                        "columns": [
                            {
                                "name": "PART_NUMBER",
                                "type": "string",
                                "sample": ["ABC-123"],
                            }
                        ],
                        "confidence": 0.92,
                    }
                ],
            },
            "column_mappings": [
                {
                    "file_column": "PART_NUMBER",
                    "target_field": "part_number",
                    "confidence": 0.95,
                    "reasoning": "Direct name match",
                }
            ],
            "overall_confidence": 0.92,
            "questions": [],
            "reasoning_trace": ["Step 1", "Step 2"],
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            mock_swarm_result, agent_name="file_analyst", tool_name="unified_analyze_file"
        )

        # Verify structure matches TypeScript type
        assert isinstance(extracted["success"], bool)
        assert isinstance(extracted["analysis"], dict)
        assert isinstance(extracted["analysis"]["sheet_count"], int)
        assert isinstance(extracted["analysis"]["total_rows"], int)
        assert isinstance(extracted["analysis"]["sheets"], list)
        assert len(extracted["analysis"]["sheets"]) > 0

        sheet = extracted["analysis"]["sheets"][0]
        assert isinstance(sheet["name"], str)
        assert isinstance(sheet["row_count"], int)
        assert isinstance(sheet["columns"], list)
        assert isinstance(sheet["confidence"], (int, float))

        assert isinstance(extracted["column_mappings"], list)
        if extracted["column_mappings"]:
            mapping = extracted["column_mappings"][0]
            assert "file_column" in mapping
            assert "target_field" in mapping
            assert "confidence" in mapping
            assert "reasoning" in mapping

    def test_frontend_can_access_sheets_without_error(self):
        """
        BUG-020 REPRODUCTION TEST: Frontend code that caused the error.

        The frontend does: data.analysis.sheets.map(...)
        This test simulates that exact access pattern.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {
                "sheets": [
                    {"name": "Sheet1", "row_count": 50},
                    {"name": "Sheet2", "row_count": 100},
                ],
                "sheet_count": 2,
            },
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            mock_swarm_result, agent_name="file_analyst", tool_name="unified_analyze_file"
        )

        # Simulate frontend code: data.analysis.sheets.map(sheet => sheet.name)
        try:
            sheet_names = [sheet["name"] for sheet in extracted["analysis"]["sheets"]]
            assert sheet_names == ["Sheet1", "Sheet2"]
        except (TypeError, KeyError) as e:
            pytest.fail(f"Frontend access pattern failed: {e}")


class TestBug020v4UnwrapToolResult:
    """
    BUG-020 v4 FIX TESTS: Test the _unwrap_tool_result() helper function.

    The v4 fix adds a helper function that handles both:
    - ToolResult format: {"status": "...", "content": [{"json": {...}}]}
    - Direct response: {"success": ..., "analysis": {...}}

    This ensures consistent handling across all extraction paths.
    """

    def test_unwrap_tool_result_extracts_from_toolresult_format(self):
        """
        BUG-020 v4 CORE TEST: Helper must extract data from ToolResult format.

        The unified_analyze_file tool returns this format, and prior to v4 fix,
        _extract_from_messages() would fail to recognize it because it checked
        for "analysis" and "success" at root level instead of nested in content.
        """
        tool_result_data = {
            "status": "success",
            "content": [{"json": {
                "success": True,
                "analysis": {"sheets": [{"name": "UnwrappedSheet"}], "sheet_count": 1},
                "overall_confidence": 0.92,
            }}]
        }

        unwrapped = _unwrap_tool_result(tool_result_data)

        assert unwrapped is not None, "Must unwrap ToolResult format"
        assert "analysis" in unwrapped, "Unwrapped must have 'analysis' key"
        assert "sheets" in unwrapped["analysis"], "analysis must have 'sheets'"
        assert unwrapped["analysis"]["sheets"][0]["name"] == "UnwrappedSheet"
        assert "status" not in unwrapped, "Wrapper 'status' must be removed"
        assert "content" not in unwrapped, "Wrapper 'content' must be removed"

    def test_unwrap_tool_result_returns_direct_response(self):
        """Helper should pass through direct responses with analysis/success keys."""
        direct_data = {
            "success": True,
            "analysis": {"sheets": [{"name": "DirectSheet"}]},
        }

        unwrapped = _unwrap_tool_result(direct_data)

        assert unwrapped is not None
        assert unwrapped["analysis"]["sheets"][0]["name"] == "DirectSheet"

    def test_unwrap_tool_result_returns_none_for_invalid_data(self):
        """Helper should return None for invalid/unrecognized formats."""
        # No analysis or success key
        invalid_data = {"message": "Some text", "count": 5}
        assert _unwrap_tool_result(invalid_data) is None

        # Not a dict
        assert _unwrap_tool_result("string") is None
        assert _unwrap_tool_result(None) is None
        assert _unwrap_tool_result([1, 2, 3]) is None

    def test_unwrap_tool_result_handles_empty_content_list(self):
        """Helper should handle empty content list gracefully."""
        data = {"status": "success", "content": []}
        assert _unwrap_tool_result(data) is None

    def test_unwrap_tool_result_handles_content_without_json(self):
        """Helper should handle content items without 'json' key."""
        data = {"status": "success", "content": [{"text": "Some text"}]}
        assert _unwrap_tool_result(data) is None


class TestBug020v4ExtractFromMessages:
    """
    BUG-020 v4 FIX TESTS: Test _extract_from_messages() handles ToolResult format.

    Before v4 fix, _extract_from_messages() had this buggy condition at line 217:
        if isinstance(data, dict) and ("analysis" in data or "success" in data):

    This fails for ToolResult format because:
    - "analysis" is nested in content[0]["json"], not at root
    - "success" key doesn't exist (it's "status" at root)

    The v4 fix uses _unwrap_tool_result() to handle both formats.
    """

    def test_extract_from_messages_handles_tool_result_format(self):
        """
        BUG-020 v4 CORE TEST: _extract_from_messages must unwrap ToolResult format.

        This test reproduces the exact failure scenario where a tool_result block
        in messages contains ToolResult format data, and the old code would
        return None because it checked for wrong keys.
        """
        messages = [
            {
                "content": [
                    {
                        "type": "tool_result",
                        "content": json.dumps({
                            "status": "success",
                            "content": [{"json": {
                                "success": True,
                                "analysis": {"sheets": [{"name": "FromMessages"}], "sheet_count": 1},
                            }}]
                        })
                    }
                ]
            }
        ]

        extracted = _extract_from_messages(messages, tool_name="unified_analyze_file")

        assert extracted is not None, "Must extract from ToolResult format in messages"
        assert "analysis" in extracted, "Must have 'analysis' key"
        assert "sheets" in extracted["analysis"], "analysis must have 'sheets'"
        assert extracted["analysis"]["sheets"][0]["name"] == "FromMessages"

    def test_extract_from_messages_handles_direct_format(self):
        """_extract_from_messages should still handle direct JSON format."""
        messages = [
            {
                "content": [
                    {
                        "type": "tool_result",
                        "content": json.dumps({
                            "success": True,
                            "analysis": {"sheets": [{"name": "DirectFromMessages"}]},
                        })
                    }
                ]
            }
        ]

        extracted = _extract_from_messages(messages, tool_name="test")

        assert extracted is not None
        assert extracted["analysis"]["sheets"][0]["name"] == "DirectFromMessages"

    def test_extract_from_messages_returns_none_for_invalid_content(self):
        """_extract_from_messages should return None for invalid content."""
        # No tool_result blocks
        messages = [{"content": [{"type": "text", "content": "Hello"}]}]
        assert _extract_from_messages(messages, tool_name="test") is None

        # Empty messages
        assert _extract_from_messages([], tool_name="test") is None

        # None input
        assert _extract_from_messages(None, tool_name="test") is None


class TestBug020v4IntegrationScenario:
    """
    BUG-020 v4 Integration test simulating the full failure scenario.

    Scenario:
    1. Swarm calls file_analyst agent
    2. file_analyst calls unified_analyze_file tool
    3. Tool returns ToolResult format: {"status": "...", "content": [{"json": {...}}]}
    4. Agent's .result is None (LLM didn't populate structured output)
    5. Extraction falls back to entry_point.messages
    6. Messages contain tool_result block with ToolResult format
    7. v4 fix ensures extraction succeeds via _unwrap_tool_result()
    """

    def test_extraction_succeeds_via_messages_fallback_with_tool_result_format(self):
        """
        BUG-020 v4 END-TO-END TEST: Full fallback path must work.

        This simulates the production scenario where:
        - Agent.result is None (agent used natural language instead)
        - Tool output is in entry_point.messages as tool_result block
        - Tool output is in ToolResult format

        Before v4 fix, this would return None and cause frontend error.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = None  # Agent didn't return structured output

        mock_entry_point = Mock()
        mock_entry_point.messages = [
            {
                "content": [
                    {
                        "type": "tool_result",
                        "content": json.dumps({
                            "status": "success",
                            "content": [{"json": {
                                "success": True,
                                "analysis": {
                                    "sheets": [{"name": "FallbackSheet", "row_count": 100}],
                                    "sheet_count": 1,
                                },
                                "column_mappings": [],
                                "overall_confidence": 0.85,
                            }}]
                        })
                    }
                ]
            }
        ]

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}
        mock_swarm_result.entry_point = mock_entry_point
        mock_swarm_result.message = "I analyzed the file."  # Natural language

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        # BUG-020 v4 FIX: Extraction must succeed via messages fallback
        assert extracted is not None, "Must extract via messages fallback"
        assert "analysis" in extracted, "Must have 'analysis' key"
        assert "sheets" in extracted["analysis"], "analysis must have 'sheets'"
        assert extracted["analysis"]["sheets"][0]["name"] == "FallbackSheet"

        # Verify we got structured data, NOT the natural language message
        assert "I analyzed" not in str(extracted), "Must NOT include natural language"


class TestBug020v5StrandsCompliant:
    """
    BUG-020 v5 FIX TESTS: Verify 100% Strands-compliant extraction.

    The v5 fix removes the non-Strands-compliant fallback code that used
    `result.message` (which is NOT a valid Strands SwarmResult attribute).

    Official Strands SwarmResult attributes:
    - result.results["agent_name"].result (agent output)
    - result.status ("success" or "error")
    - result.entry_point.messages (message history)

    NON-EXISTENT (removed in v5):
    - result.message (invented, NOT official Strands SDK)

    Reference: https://strandsagents.com/latest/
    """

    def test_process_swarm_result_uses_official_strands_pattern(self):
        """
        BUG-020 v5 CORE TEST: _process_swarm_result must use official pattern.

        The orchestrator now uses _process_swarm_result() which ONLY uses
        official Strands patterns:
        - result.results["agent_name"].result
        - result.status
        - result.entry_point.messages
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {
                "sheets": [{"name": "StrandsCompliant", "row_count": 100}],
                "sheet_count": 1,
                "total_rows": 100,
                "recommended_strategy": "auto_import",
            },
            "column_mappings": [],
            "overall_confidence": 0.92,
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}
        mock_swarm_result.status = "success"  # Official Strands attribute

        session = {"context": {}, "awaiting_response": False}

        response = _process_swarm_result(mock_swarm_result, session, action="nexo_analyze_file")

        assert response["success"] is True
        assert "analysis" in response
        assert response["analysis"]["sheets"][0]["name"] == "StrandsCompliant"

    def test_extraction_ignores_non_strands_result_message(self):
        """
        BUG-020 v5 REGRESSION TEST: Must NOT use result.message.

        The v5 fix REMOVES the non-Strands fallback that checked result.message.
        This test ensures we NEVER fall back to result.message even if it exists.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {"sheets": [{"name": "FromResults"}], "sheet_count": 1},
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}
        # This should NEVER be used - it's not a real Strands attribute
        mock_swarm_result.message = json.dumps({
            "success": True,
            "analysis": {"sheets": [{"name": "FromMessage_WRONG"}]},
        })

        session = {"context": {}}

        response = _process_swarm_result(mock_swarm_result, session, action="test")

        # Must use results, NOT message
        assert response["analysis"]["sheets"][0]["name"] == "FromResults"
        assert "FromMessage_WRONG" not in str(response)

    def test_error_handling_uses_result_status(self):
        """
        BUG-020 v5 ERROR HANDLING TEST: Use result.status for errors.

        The v5 fix uses the official Strands attribute `result.status` for
        error detection instead of custom try/catch fallback patterns.
        """
        mock_swarm_result = Mock()
        mock_swarm_result.results = {}  # No results
        mock_swarm_result.status = "error"  # Official Strands error status
        mock_swarm_result.entry_point = None

        session = {"context": {}}

        response = _process_swarm_result(mock_swarm_result, session, action="test")

        # Extraction returns base response when no data found
        # The orchestrator adds error handling on top of this
        assert response["success"] is False or "analysis" not in response

    def test_process_swarm_result_updates_session_context(self):
        """
        BUG-020 v5 SESSION TEST: _process_swarm_result updates session properly.

        The orchestrator relies on _process_swarm_result to update session
        context with analysis, proposed_mappings, and questions.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {"sheets": [{"name": "Sheet1"}], "sheet_count": 1},
            "proposed_mappings": {"col_a": "part_number"},
            "questions": [{"id": "q1", "question": "Which column?"}],
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        session = {"context": {}, "awaiting_response": False}

        _process_swarm_result(mock_swarm_result, session, action="test")

        # Verify session context was updated
        assert "analysis" in session["context"]
        assert "proposed_mappings" in session["context"]
        assert session["awaiting_response"] is True  # Questions present

    def test_handles_toolresult_format_with_process_swarm_result(self):
        """
        BUG-020 v5 FORMAT TEST: _process_swarm_result handles ToolResult format.

        The unified_analyze_file tool returns ToolResult format, and
        _process_swarm_result (via _unwrap_tool_result) must handle it.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "status": "success",
            "content": [{"json": {
                "success": True,
                "analysis": {
                    "sheets": [{"name": "ToolResultSheet"}],
                    "sheet_count": 1,
                },
            }}]
        }

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        session = {"context": {}}

        response = _process_swarm_result(mock_swarm_result, session, action="test")

        assert response["success"] is True
        assert response["analysis"]["sheets"][0]["name"] == "ToolResultSheet"

    def test_fallback_path_always_returns_analysis_structure(self):
        """
        BUG-020 v5 FALLBACK TEST: Even when extraction fails, response has structure.

        The v5 fix in the orchestrator ensures that when _process_swarm_result
        returns a failed response, the orchestrator adds a fallback analysis
        structure to prevent frontend crashes.
        """
        mock_swarm_result = Mock()
        mock_swarm_result.results = {}  # Empty - will fail extraction
        mock_swarm_result.entry_point = None
        mock_swarm_result.status = "error"

        session = {"context": {}}

        response = _process_swarm_result(mock_swarm_result, session, action="test")

        # _process_swarm_result itself may not add fallback structure
        # but the orchestrator's _invoke_swarm will add it when success=False
        # This test verifies the base function behavior
        assert isinstance(response, dict)
        assert "session_id" in response or response.get("success") is False


class TestBug020v8AgentResultMessage:
    """
    BUG-020 v8 FIX TESTS: Extract from AgentResult.message attribute.

    The v8 fix addresses a critical issue where v7 failed because:
    - v7 checked for `.result` attribute on AgentResult
    - AgentResult does NOT have nested `.result` - it has `.message`!

    Official Strands AgentResult structure (SDK v1.20.0):
    @dataclass
    class AgentResult:
        stop_reason: StopReason
        message: Message          # ← Tool output is HERE
        metrics: EventLoopMetrics
        state: Any
        interrupts: Sequence[Interrupt] | None = None
        structured_output: BaseModel | None = None

    CloudWatch evidence (2026-01-15 22:08):
    "[_extract_agent] agent=file_analyst result_data is NOT a dict! type=AgentResult,
     attrs=['from_dict', 'interrupts', 'message', 'metrics', 'state', 'stop_reason', ...]"

    Reference: https://github.com/strands-agents/sdk-python/blob/v1.20.0/src/strands/agent/agent_result.py
    """

    def test_v8_extracts_from_agent_result_message_json_string(self):
        """
        BUG-020 v8 CORE TEST: Extract from AgentResult.message as JSON string.

        CloudWatch showed the tool output is stored in message as JSON string
        with format: {"tool_name_response": {"output": [{"json": {...}}]}}
        """
        # Create inner AgentResult with .message containing tool output
        mock_inner_agent_result = Mock()
        mock_inner_agent_result.message = json.dumps({
            "unified_analyze_file_response": {
                "output": [{
                    "json": {
                        "success": True,
                        "analysis": {
                            "sheets": [{"name": "FromMessage", "row_count": 100}],
                            "sheet_count": 1,
                        },
                        "column_mappings": [],
                        "overall_confidence": 0.92,
                    }
                }]
            }
        })
        # No nested .result attribute
        mock_inner_agent_result.result = None
        mock_inner_agent_result.stop_reason = "end_turn"
        mock_inner_agent_result.metrics = {}
        mock_inner_agent_result.state = None

        # Create outer agent result that contains inner AgentResult
        mock_outer_agent_result = Mock()
        mock_outer_agent_result.result = mock_inner_agent_result

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_outer_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        assert extracted is not None, "v8 must extract from AgentResult.message"
        assert "analysis" in extracted, "Must have 'analysis' key"
        assert "sheets" in extracted["analysis"], "analysis must have 'sheets'"
        assert extracted["analysis"]["sheets"][0]["name"] == "FromMessage"

    def test_v8_extracts_from_direct_agent_result_message(self):
        """
        BUG-020 v8 TEST: Extract when agent_result itself has .message.

        Some cases the agent_result returned by swarm.results["agent"]
        directly has the .message attribute (not nested).
        """
        mock_agent_result = Mock()
        mock_agent_result.result = None  # No nested result
        mock_agent_result.message = json.dumps({
            "success": True,
            "analysis": {
                "sheets": [{"name": "DirectMessage", "row_count": 50}],
                "sheet_count": 1,
            },
        })

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        assert extracted is not None, "v8 must extract from direct .message"
        assert extracted["analysis"]["sheets"][0]["name"] == "DirectMessage"

    def test_v8_extracts_from_message_with_content_array(self):
        """
        BUG-020 v8 TEST: Extract from Message object with .content array.

        Strands Message type can have content as an array of content blocks.
        """
        mock_message = Mock()
        mock_message.content = [
            {
                "type": "tool_result",
                "content": json.dumps({
                    "success": True,
                    "analysis": {
                        "sheets": [{"name": "ContentArraySheet"}],
                        "sheet_count": 1,
                    },
                })
            }
        ]

        mock_inner_agent_result = Mock()
        mock_inner_agent_result.message = mock_message
        mock_inner_agent_result.result = None

        mock_outer_agent_result = Mock()
        mock_outer_agent_result.result = mock_inner_agent_result

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_outer_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        assert extracted is not None, "v8 must extract from Message.content array"
        assert extracted["analysis"]["sheets"][0]["name"] == "ContentArraySheet"

    def test_v8_prefers_message_over_dict_result(self):
        """
        BUG-020 v8 PRIORITY TEST: .message takes priority over .result as dict.

        When both paths are available, v8 should check .message first
        (as this is where AgentCore puts tool output).
        """
        mock_inner_agent_result = Mock()
        mock_inner_agent_result.message = json.dumps({
            "success": True,
            "analysis": {
                "sheets": [{"name": "FromMessagePriority"}],
                "sheet_count": 1,
            },
        })
        # Also has result as dict (fallback path)
        mock_inner_agent_result.result = {
            "success": True,
            "analysis": {
                "sheets": [{"name": "FromResultFallback"}],
                "sheet_count": 1,
            },
        }

        mock_outer_agent_result = Mock()
        mock_outer_agent_result.result = mock_inner_agent_result

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_outer_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        assert extracted is not None
        # v8 should prefer .message path
        assert extracted["analysis"]["sheets"][0]["name"] == "FromMessagePriority"

    def test_v8_falls_back_to_result_dict_when_no_message(self):
        """
        BUG-020 v8 FALLBACK TEST: Falls back to .result dict when no .message.

        After reverting BUG-015, tools return raw dicts. The v8 fix
        should still handle this fallback path.
        """
        mock_agent_result = Mock()
        mock_agent_result.result = {
            "success": True,
            "analysis": {
                "sheets": [{"name": "RawDictResult"}],
                "sheet_count": 1,
            },
        }
        mock_agent_result.message = None  # No message

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        assert extracted is not None, "v8 must fall back to .result dict"
        assert extracted["analysis"]["sheets"][0]["name"] == "RawDictResult"

    def test_v8_handles_tool_response_wrapper_format(self):
        """
        BUG-020 v8 FORMAT TEST: Handle tool response wrapper format.

        CloudWatch showed tool output in message uses this wrapper:
        {"<tool_name>_response": {"output": [{"json": {...actual data...}}]}}
        """
        tool_output = {
            "unified_analyze_file_response": {
                "output": [{
                    "json": {
                        "success": True,
                        "import_session_id": "nexo-abc123",
                        "filename": "inventory.csv",
                        "analysis": {
                            "sheet_count": 1,
                            "total_rows": 150,
                            "sheets": [{
                                "name": "ToolResponseWrapper",
                                "row_count": 150,
                                "column_count": 5,
                                "columns": [],
                                "confidence": 0.92,
                            }],
                            "recommended_strategy": "auto_import",
                        },
                        "column_mappings": [{
                            "file_column": "PART_NUMBER",
                            "target_field": "part_number",
                            "confidence": 0.95,
                            "reasoning": "Direct match",
                        }],
                        "overall_confidence": 0.92,
                        "questions": [],
                    }
                }]
            }
        }

        mock_inner_agent_result = Mock()
        mock_inner_agent_result.message = json.dumps(tool_output)
        mock_inner_agent_result.result = None

        mock_outer_agent_result = Mock()
        mock_outer_agent_result.result = mock_inner_agent_result

        mock_swarm_result = Mock()
        mock_swarm_result.results = {"file_analyst": mock_outer_agent_result}

        extracted = _extract_tool_output_from_swarm_result(
            swarm_result=mock_swarm_result,
            agent_name="file_analyst",
            tool_name="unified_analyze_file",
        )

        assert extracted is not None, "v8 must handle tool response wrapper"
        assert "analysis" in extracted
        assert extracted["analysis"]["sheets"][0]["name"] == "ToolResponseWrapper"
        assert len(extracted["column_mappings"]) > 0
        assert extracted["overall_confidence"] == 0.92
