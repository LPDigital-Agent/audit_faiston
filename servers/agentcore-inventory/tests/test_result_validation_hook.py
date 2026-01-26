# =============================================================================
# Tests for Result Validation Hook (TDD Red Phase)
# =============================================================================
# Unit tests for ResultValidationHook (self-validating agent pattern).
#
# These tests verify:
# - Hook registration with Strands HookRegistry
# - Validation of structured_output against custom validators
# - Self-correction loop triggering when validation fails
# - Max retries enforcement to prevent infinite loops
# - Fail-fast mode for critical agents
# - Multiple validators execution
# - Pydantic and business rule validator support
#
# Based on: "Claude Code Senior Engineers" YouTube video concepts
# Reference: docs/plans/FEAT-self-validating-agents.md
#
# Run: cd server/agentcore-inventory && python -m pytest tests/test_result_validation_hook.py -v
# =============================================================================

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Tuple
from pydantic import BaseModel, Field


# =============================================================================
# Mock Classes for Strands Events
# =============================================================================

class MockStructuredOutput(BaseModel):
    """Mock Pydantic model for structured output."""
    success: bool = True
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    mappings: list = Field(default_factory=list)

    class Config:
        extra = "allow"


class MockAgentResult:
    """Mock for agent result with structured_output."""

    def __init__(
        self,
        structured_output: BaseModel = None,
        stop_reason: str = "end_turn",
        message: str = "Test message",
    ):
        self.structured_output = structured_output
        self.stop_reason = stop_reason
        self.message = message


class MockAgent:
    """Mock for Strands Agent."""

    def __init__(self, name: str = "test_agent"):
        self.name = name
        self.messages = []
        self._invoke_count = 0
        self._mock_responses = []
        self._captured_prompts = []  # Capture prompts for testing

    async def __call__(self, prompt: str) -> MockAgentResult:
        """Mock agent invocation for self-correction."""
        self._invoke_count += 1
        self._captured_prompts.append(prompt)  # Capture the prompt
        if self._mock_responses:
            return self._mock_responses.pop(0)
        return MockAgentResult(structured_output=MockStructuredOutput())

    def set_mock_responses(self, responses: list):
        """Set mock responses for sequential calls."""
        self._mock_responses = responses


class MockAfterInvocationEvent:
    """Mock for strands.hooks.events.AfterInvocationEvent."""

    def __init__(
        self,
        result: MockAgentResult = None,
        agent: MockAgent = None,
        stop_reason: str = "end_turn",
    ):
        self.result = result or MockAgentResult()
        self.agent = agent or MockAgent()
        self.stop_reason = stop_reason


class MockHookRegistry:
    """Mock for strands.hooks.HookRegistry."""

    def __init__(self):
        self.callbacks = {}

    def add_callback(self, event_type, callback):
        self.callbacks[event_type.__name__] = callback


# =============================================================================
# Sample Validators for Testing
# =============================================================================

def always_passes(output: BaseModel) -> Tuple[bool, str]:
    """Validator that always passes."""
    return True, "OK"


def always_fails(output: BaseModel) -> Tuple[bool, str]:
    """Validator that always fails."""
    return False, "Validation always fails"


def check_confidence_threshold(output: BaseModel) -> Tuple[bool, str]:
    """Check if confidence meets minimum threshold (0.7)."""
    if hasattr(output, "confidence"):
        if output.confidence < 0.7:
            return False, f"Confidence too low: {output.confidence:.2f} < 0.70"
    return True, "OK"


def check_required_mappings(output: BaseModel) -> Tuple[bool, str]:
    """Check if required mappings are present."""
    if hasattr(output, "mappings"):
        if len(output.mappings) == 0:
            return False, "Missing required mappings: mappings list is empty"
    return True, "OK"


def raises_exception(output: BaseModel) -> Tuple[bool, str]:
    """Validator that raises an exception."""
    raise ValueError("Validator crashed")


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def validation_hook():
    """Create ResultValidationHook with default configuration."""
    from shared.hooks.result_validation_hook import ResultValidationHook

    return ResultValidationHook(
        validators=[always_passes],
        max_retries=3,
        enabled=True,
        fail_fast=False,
    )


@pytest.fixture
def strict_hook():
    """Create ResultValidationHook with fail_fast=True."""
    from shared.hooks.result_validation_hook import ResultValidationHook

    return ResultValidationHook(
        validators=[always_fails, always_passes],
        max_retries=3,
        enabled=True,
        fail_fast=True,
    )


@pytest.fixture
def disabled_hook():
    """Create disabled ResultValidationHook."""
    from shared.hooks.result_validation_hook import ResultValidationHook

    return ResultValidationHook(
        validators=[always_fails],
        enabled=False,
    )


@pytest.fixture
def multi_validator_hook():
    """Create hook with multiple validators."""
    from shared.hooks.result_validation_hook import ResultValidationHook

    return ResultValidationHook(
        validators=[
            check_confidence_threshold,
            check_required_mappings,
        ],
        max_retries=3,
        enabled=True,
    )


# =============================================================================
# Tests for Initialization
# =============================================================================

class TestResultValidationHookInit:
    """Tests for ResultValidationHook initialization."""

    def test_default_configuration(self):
        """Test that default configuration is applied."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        hook = ResultValidationHook()
        assert hook.validators == []
        assert hook.max_retries == 3
        assert hook.enabled is True
        assert hook.fail_fast is False

    def test_custom_configuration(self):
        """Test that custom configuration is applied."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        hook = ResultValidationHook(
            validators=[always_passes, always_fails],
            max_retries=5,
            enabled=False,
            fail_fast=True,
        )
        assert len(hook.validators) == 2
        assert hook.max_retries == 5
        assert hook.enabled is False
        assert hook.fail_fast is True

    def test_environment_variable_override(self):
        """Test that environment variables override parameters."""
        import os

        with patch.dict(
            os.environ,
            {"RESULT_VALIDATION_ENABLED": "false", "RESULT_VALIDATION_MAX_RETRIES": "5"},
        ):
            from shared.hooks.result_validation_hook import ResultValidationHook

            hook = ResultValidationHook()
            assert hook.enabled is False
            assert hook.max_retries == 5


# =============================================================================
# Tests for Hook Registration
# =============================================================================

class TestHookRegistration:
    """Tests for hook registration with Strands registry."""

    def test_register_hooks_adds_callback(self, validation_hook):
        """Test that register_hooks adds callback for AfterInvocationEvent."""
        registry = MockHookRegistry()
        validation_hook.register_hooks(registry)

        assert "AfterInvocationEvent" in registry.callbacks

    def test_callback_is_callable(self, validation_hook):
        """Test that registered callback is callable."""
        registry = MockHookRegistry()
        validation_hook.register_hooks(registry)

        assert callable(registry.callbacks["AfterInvocationEvent"])


# =============================================================================
# Tests for Validation Pass-Through
# =============================================================================

class TestValidationPassThrough:
    """Tests for when validation passes."""

    @pytest.mark.asyncio
    async def test_valid_output_passes_through(self, validation_hook):
        """Test that valid output passes without self-correction."""
        structured = MockStructuredOutput(success=True, confidence=0.9)
        result = MockAgentResult(structured_output=structured)
        event = MockAfterInvocationEvent(result=result)

        # Should not raise
        await validation_hook._validate_result(event)

        # Retry count should stay at 0
        assert validation_hook._retry_count == 0

    @pytest.mark.asyncio
    async def test_no_structured_output_passes_through(self, validation_hook):
        """Test that missing structured_output is ignored."""
        result = MockAgentResult(structured_output=None)
        event = MockAfterInvocationEvent(result=result)

        # Should not raise
        await validation_hook._validate_result(event)

    @pytest.mark.asyncio
    async def test_disabled_hook_passes_through(self, disabled_hook):
        """Test that disabled hook always passes through."""
        structured = MockStructuredOutput(success=False, confidence=0.1)
        result = MockAgentResult(structured_output=structured)
        event = MockAfterInvocationEvent(result=result)

        # Should not raise even with invalid output
        await disabled_hook._validate_result(event)


# =============================================================================
# Tests for Validation Failure Detection
# =============================================================================

class TestValidationFailureDetection:
    """Tests for when validation fails."""

    @pytest.mark.asyncio
    async def test_single_validator_failure_detected(self):
        """Test that single validator failure is detected."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        hook = ResultValidationHook(
            validators=[always_fails],
            max_retries=0,  # No retries for this test
            enabled=True,
        )

        structured = MockStructuredOutput()
        result = MockAgentResult(structured_output=structured)
        event = MockAfterInvocationEvent(result=result)

        with pytest.raises(Exception) as exc_info:
            await hook._validate_result(event)

        assert "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_multiple_validators_all_failures_reported(self, multi_validator_hook):
        """Test that all validator failures are collected."""
        # Set low confidence and empty mappings to fail both validators
        structured = MockStructuredOutput(confidence=0.5, mappings=[])
        result = MockAgentResult(structured_output=structured)
        event = MockAfterInvocationEvent(result=result)

        # Disable retries for this test
        multi_validator_hook.max_retries = 0

        with pytest.raises(Exception) as exc_info:
            await multi_validator_hook._validate_result(event)

        error_message = str(exc_info.value).lower()
        assert "confidence" in error_message or "mappings" in error_message

    @pytest.mark.asyncio
    async def test_fail_fast_stops_on_first_failure(self, strict_hook):
        """Test that fail_fast mode stops on first failure."""
        structured = MockStructuredOutput()
        result = MockAgentResult(structured_output=structured)
        event = MockAfterInvocationEvent(result=result)

        # Disable retries
        strict_hook.max_retries = 0

        # Track which validators run
        call_count = {"always_fails": 0, "always_passes": 0}

        def tracked_fails(output):
            call_count["always_fails"] += 1
            return False, "Failed"

        def tracked_passes(output):
            call_count["always_passes"] += 1
            return True, "OK"

        strict_hook.validators = [tracked_fails, tracked_passes]

        with pytest.raises(Exception):
            await strict_hook._validate_result(event)

        # In fail_fast mode, second validator should NOT run
        assert call_count["always_fails"] == 1
        assert call_count["always_passes"] == 0


# =============================================================================
# Tests for Self-Correction Loop
# =============================================================================

class TestSelfCorrectionLoop:
    """Tests for self-correction mechanism."""

    @pytest.mark.asyncio
    async def test_self_correction_triggered_on_failure(self):
        """Test that self-correction is triggered when validation fails."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        # Create agent that will be re-invoked
        mock_agent = MockAgent()

        # First call fails validation, second call passes
        fail_output = MockStructuredOutput(confidence=0.5)
        pass_output = MockStructuredOutput(confidence=0.9)

        mock_agent.set_mock_responses([
            MockAgentResult(structured_output=pass_output),
        ])

        hook = ResultValidationHook(
            validators=[check_confidence_threshold],
            max_retries=3,
            enabled=True,
        )

        # First result fails validation
        result = MockAgentResult(structured_output=fail_output)
        event = MockAfterInvocationEvent(result=result, agent=mock_agent)

        await hook._validate_result(event)

        # Agent should have been re-invoked
        assert mock_agent._invoke_count >= 1

    @pytest.mark.asyncio
    async def test_max_retries_enforced(self):
        """Test that max_retries limit is enforced."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        mock_agent = MockAgent()

        # All responses fail validation
        fail_output = MockStructuredOutput(confidence=0.5)
        mock_agent.set_mock_responses([
            MockAgentResult(structured_output=fail_output),
            MockAgentResult(structured_output=fail_output),
            MockAgentResult(structured_output=fail_output),
        ])

        hook = ResultValidationHook(
            validators=[check_confidence_threshold],
            max_retries=3,
            enabled=True,
        )

        result = MockAgentResult(structured_output=fail_output)
        event = MockAfterInvocationEvent(result=result, agent=mock_agent)

        with pytest.raises(Exception) as exc_info:
            await hook._validate_result(event)

        # Should mention max retries in error
        assert "3" in str(exc_info.value) or "retries" in str(exc_info.value).lower()

        # Should have tried exactly max_retries times
        assert mock_agent._invoke_count == 3

    @pytest.mark.asyncio
    async def test_retry_count_resets_on_success(self):
        """Test that retry count resets after successful validation."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        hook = ResultValidationHook(
            validators=[always_passes],
            max_retries=3,
            enabled=True,
        )

        # Manually set retry count
        hook._retry_count = 2

        structured = MockStructuredOutput()
        result = MockAgentResult(structured_output=structured)
        event = MockAfterInvocationEvent(result=result)

        await hook._validate_result(event)

        # Retry count should reset
        assert hook._retry_count == 0

    @pytest.mark.asyncio
    async def test_correction_prompt_includes_failure_details(self):
        """Test that correction prompt includes validation failure details."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        mock_agent = MockAgent()
        # Set mock response that passes validation to stop the loop
        mock_agent.set_mock_responses([
            MockAgentResult(structured_output=MockStructuredOutput(confidence=0.9))
        ])

        hook = ResultValidationHook(
            validators=[check_confidence_threshold],
            max_retries=3,
            enabled=True,
        )

        fail_output = MockStructuredOutput(confidence=0.5)
        result = MockAgentResult(structured_output=fail_output)
        event = MockAfterInvocationEvent(result=result, agent=mock_agent)

        await hook._validate_result(event)

        # Correction prompt should include failure reason
        # MockAgent now captures prompts in _captured_prompts
        assert len(mock_agent._captured_prompts) >= 1
        prompt = mock_agent._captured_prompts[0].lower()
        assert "confidence" in prompt or "validation" in prompt or "failed" in prompt


# =============================================================================
# Tests for Validator Exception Handling
# =============================================================================

class TestValidatorExceptionHandling:
    """Tests for handling validator exceptions."""

    @pytest.mark.asyncio
    async def test_validator_exception_is_caught(self):
        """Test that validator exceptions are caught and treated as failures."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        hook = ResultValidationHook(
            validators=[raises_exception],
            max_retries=0,
            enabled=True,
        )

        structured = MockStructuredOutput()
        result = MockAgentResult(structured_output=structured)
        event = MockAfterInvocationEvent(result=result)

        with pytest.raises(Exception) as exc_info:
            await hook._validate_result(event)

        # Should include validator name or error message
        error_str = str(exc_info.value).lower()
        assert "raises_exception" in error_str or "crashed" in error_str


# =============================================================================
# Tests for Business Rule Validators
# =============================================================================

class TestBusinessRuleValidators:
    """Tests for business rule validator patterns."""

    @pytest.mark.asyncio
    async def test_confidence_threshold_validator(self):
        """Test confidence threshold validator logic."""
        # Below threshold
        low_output = MockStructuredOutput(confidence=0.5)
        passed, message = check_confidence_threshold(low_output)
        assert passed is False
        assert "0.5" in message or "confidence" in message.lower()

        # Above threshold
        high_output = MockStructuredOutput(confidence=0.9)
        passed, message = check_confidence_threshold(high_output)
        assert passed is True

    @pytest.mark.asyncio
    async def test_required_mappings_validator(self):
        """Test required mappings validator logic."""
        # Empty mappings
        empty_output = MockStructuredOutput(mappings=[])
        passed, message = check_required_mappings(empty_output)
        assert passed is False
        assert "mappings" in message.lower()

        # With mappings
        with_mappings = MockStructuredOutput(mappings=["mapping1", "mapping2"])
        passed, message = check_required_mappings(with_mappings)
        assert passed is True


# =============================================================================
# Tests for State Management
# =============================================================================

class TestStateManagement:
    """Tests for hook state management."""

    def test_get_validation_failures(self, validation_hook):
        """Test that validation failures can be retrieved."""
        validation_hook._last_failures = [("test_validator", "Test failure")]
        failures = validation_hook.get_last_failures()
        assert len(failures) == 1
        assert failures[0][0] == "test_validator"

    def test_disable_hook(self, validation_hook):
        """Test that hook can be disabled."""
        validation_hook.disable()
        assert validation_hook.enabled is False

    def test_enable_hook(self, validation_hook):
        """Test that hook can be re-enabled."""
        validation_hook.disable()
        validation_hook.enable()
        assert validation_hook.enabled is True

    def test_reset_retry_count(self, validation_hook):
        """Test that retry count can be reset."""
        validation_hook._retry_count = 5
        validation_hook.reset()
        assert validation_hook._retry_count == 0


# =============================================================================
# Tests for Metrics Emission
# =============================================================================

class TestMetricsEmission:
    """Tests for CloudWatch metrics emission."""

    @pytest.mark.asyncio
    async def test_validation_success_metric_emitted(self):
        """Test that success metric is emitted on validation pass."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        with patch.object(
            ResultValidationHook,
            "_emit_validation_metric",
            new_callable=AsyncMock,
        ) as mock_emit:
            hook = ResultValidationHook(
                validators=[always_passes],
                enabled=True,
            )

            structured = MockStructuredOutput()
            result = MockAgentResult(structured_output=structured)
            event = MockAfterInvocationEvent(result=result)

            await hook._validate_result(event)

            mock_emit.assert_called()
            call_args = mock_emit.call_args
            assert call_args[1]["success"] is True or call_args[0][0] == "success"

    @pytest.mark.asyncio
    async def test_validation_failure_metric_emitted(self):
        """Test that failure metric is emitted on validation failure."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        with patch.object(
            ResultValidationHook,
            "_emit_validation_metric",
            new_callable=AsyncMock,
        ) as mock_emit:
            hook = ResultValidationHook(
                validators=[always_fails],
                max_retries=0,
                enabled=True,
            )

            structured = MockStructuredOutput()
            result = MockAgentResult(structured_output=structured)
            event = MockAfterInvocationEvent(result=result)

            with pytest.raises(Exception):
                await hook._validate_result(event)

            mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_self_correction_metric_emitted(self):
        """Test that self-correction metric is emitted on retry."""
        from shared.hooks.result_validation_hook import ResultValidationHook

        with patch.object(
            ResultValidationHook,
            "_emit_self_correction_metric",
            new_callable=AsyncMock,
        ) as mock_emit:
            mock_agent = MockAgent()
            pass_output = MockStructuredOutput(confidence=0.9)
            mock_agent.set_mock_responses([
                MockAgentResult(structured_output=pass_output),
            ])

            hook = ResultValidationHook(
                validators=[check_confidence_threshold],
                max_retries=3,
                enabled=True,
            )

            fail_output = MockStructuredOutput(confidence=0.5)
            result = MockAgentResult(structured_output=fail_output)
            event = MockAfterInvocationEvent(result=result, agent=mock_agent)

            await hook._validate_result(event)

            mock_emit.assert_called()


# =============================================================================
# Tests for Validator Registry Integration
# =============================================================================

class TestValidatorRegistry:
    """Tests for validator registry pattern."""

    def test_get_validators_for_agent(self):
        """Test that validators can be retrieved for specific agent."""
        from shared.validators import AGENT_VALIDATORS

        # Schema mapper should have validators
        schema_mapper_validators = AGENT_VALIDATORS.get("schema_mapper", [])
        assert isinstance(schema_mapper_validators, list)

    def test_unknown_agent_returns_empty_list(self):
        """Test that unknown agent returns empty validator list."""
        from shared.validators import AGENT_VALIDATORS

        unknown_validators = AGENT_VALIDATORS.get("unknown_agent", [])
        assert unknown_validators == []
