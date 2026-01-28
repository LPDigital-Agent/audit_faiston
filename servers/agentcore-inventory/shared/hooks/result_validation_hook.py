# =============================================================================
# Result Validation Hook for Strands Agents
# =============================================================================
# Implements the Self-Validating Agent Pattern from "Claude Code Senior Engineers"
# video. Adds deterministic validation layers that verify agent outputs against
# custom validators, enabling automatic self-correction loops when validation fails.
#
# Pattern: "Closed Loop Prompts" - CODE → LLM → CODE sandwich
# - Pre-process input (Python)
# - Reasoning and generation (LLM)
# - Validate output (Python) ← THIS HOOK
#
# Reference:
# - docs/plans/FEAT-self-validating-agents.md
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/
# =============================================================================

import logging
import os
from datetime import datetime
from typing import Any, Callable, List, Optional, Tuple

from pydantic import BaseModel
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import AfterInvocationEvent

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when agent output fails validation after max retries."""

    def __init__(self, message: str, failures: List[Tuple[str, str]] = None):
        super().__init__(message)
        self.failures = failures or []


class ResultValidationHook(HookProvider):
    """
    Self-validating hook that runs deterministic validators on agent outputs.

    Pattern from: "Claude Code Senior Engineers" video
    Concept: "Closed loop prompts" - Deterministic validation after LLM output

    When validation fails, this hook triggers a self-correction loop by
    re-invoking the agent with feedback about what went wrong. This continues
    until validation passes or max_retries is reached.

    Usage:
        validators = [validate_mapping_completeness, validate_confidence_threshold]
        hook = ResultValidationHook(validators=validators, max_retries=3)
        agent = Agent(hooks=[LoggingHook(), MetricsHook(), hook])

    Configuration via environment variables:
        RESULT_VALIDATION_ENABLED: Enable/disable hook (default: true)
        RESULT_VALIDATION_MAX_RETRIES: Max retry attempts (default: 3)

    Validator signature:
        def validator(output: BaseModel) -> Tuple[bool, str]:
            # Return (True, "OK") if valid
            # Return (False, "Error message") if invalid
    """

    def __init__(
        self,
        validators: List[Callable[[BaseModel], Tuple[bool, str]]] = None,
        max_retries: int = 3,
        enabled: bool = True,
        fail_fast: bool = False,
    ):
        """
        Initialize ResultValidationHook.

        Args:
            validators: List of validator functions to run on structured output.
                        Each validator takes a BaseModel and returns (bool, str).
            max_retries: Maximum number of self-correction attempts (default: 3).
            enabled: Whether hook is active (default: True).
            fail_fast: If True, stop on first validation failure (default: False).
        """
        # Configuration from environment or parameters
        self.enabled = os.environ.get(
            "RESULT_VALIDATION_ENABLED", str(enabled)
        ).lower() == "true"
        self.max_retries = int(
            os.environ.get("RESULT_VALIDATION_MAX_RETRIES", max_retries)
        )
        self.validators = validators or []
        self.fail_fast = fail_fast

        # Internal state
        self._retry_count = 0
        self._last_failures: List[Tuple[str, str]] = []
        self._original_prompt: Optional[str] = None

        logger.info(
            f"[ResultValidationHook] Initialized: enabled={self.enabled}, "
            f"max_retries={self.max_retries}, validators={len(self.validators)}, "
            f"fail_fast={self.fail_fast}"
        )

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register callbacks for result validation."""
        registry.add_callback(AfterInvocationEvent, self._validate_result)

    async def _validate_result(self, event: AfterInvocationEvent) -> None:
        """
        Validate agent output and trigger self-correction if needed.

        This is the main entry point called after each agent invocation.
        It runs all validators against the structured_output and handles
        failures by triggering self-correction loops.

        Args:
            event: AfterInvocationEvent containing the agent result.

        Raises:
            ValidationError: If validation fails after max_retries.
        """
        # Skip if disabled
        if not self.enabled:
            logger.debug("[ResultValidationHook] Disabled, skipping validation")
            return

        # Get structured output
        result = getattr(event, "result", None)
        if not result or not hasattr(result, "structured_output"):
            logger.debug("[ResultValidationHook] No result object, skipping")
            return

        structured = result.structured_output
        if not structured:
            logger.debug("[ResultValidationHook] No structured_output, skipping")
            return

        # Run all validators
        failures = self._run_validators(structured)

        if failures:
            # Store failures for debugging
            self._last_failures = failures
            failure_details = "; ".join(f"{name}: {msg}" for name, msg in failures)

            logger.warning(
                f"[ResultValidationHook] Validation failed: {failure_details}"
            )

            # Emit failure metric
            await self._emit_validation_metric(success=False, failures=failures)

            # Trigger self-correction if retries available
            if self.max_retries > 0:
                # NOTE: Self-correction via agent re-invocation is NOT supported
                # in Strands SDK. AfterInvocationEvent callbacks run while the
                # agent lock is held, causing ConcurrencyException.
                # Ref: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/
                logger.warning(
                    f"[ResultValidationHook] Validation failed. Skipping "
                    f"self-correction to avoid ConcurrencyException "
                    f"(Strands SDK Limitation). Failures: {failure_details}"
                )
                # Do NOT call _trigger_self_correction() - it causes ConcurrencyException
            else:
                # Max retries exhausted
                logger.error(
                    f"[ResultValidationHook] Max retries ({self.max_retries}) "
                    f"exhausted. Validation failed: {failure_details}"
                )
                raise ValidationError(
                    f"Agent failed validation after {self.max_retries} retries: "
                    f"{failure_details}",
                    failures=failures,
                )
        else:
            # Validation passed
            logger.info("[ResultValidationHook] Validation passed")

            # Reset retry count on success
            self._retry_count = 0
            self._last_failures = []

            # Emit success metric
            await self._emit_validation_metric(success=True, failures=[])

    def _run_validators(
        self, structured: BaseModel
    ) -> List[Tuple[str, str]]:
        """
        Run all validators against the structured output.

        Args:
            structured: The Pydantic model to validate.

        Returns:
            List of (validator_name, error_message) tuples for failures.
        """
        failures = []

        for validator in self.validators:
            try:
                passed, message = validator(structured)
                if not passed:
                    failures.append((validator.__name__, message))
                    if self.fail_fast:
                        # Stop on first failure in fail_fast mode
                        logger.debug(
                            f"[ResultValidationHook] Fail-fast: stopping at "
                            f"{validator.__name__}"
                        )
                        break
            except Exception as e:
                # Validator crashed - treat as failure
                failures.append((validator.__name__, f"Validator crashed: {str(e)}"))
                logger.exception(
                    f"[ResultValidationHook] Validator {validator.__name__} "
                    f"raised exception: {e}"
                )
                if self.fail_fast:
                    break

        return failures

    async def _trigger_self_correction(
        self,
        event: AfterInvocationEvent,
        failures: List[Tuple[str, str]],
    ) -> None:
        """
        Re-invoke agent with validation feedback for self-correction.

        Pattern: "Ralph Wiggum Loop" - Use failures as data for next iteration.
        This method handles the full retry loop, validating each new result
        until it passes or max_retries is exhausted.

        Args:
            event: The original AfterInvocationEvent.
            failures: List of validation failures to include in feedback.

        Raises:
            ValidationError: If validation fails after max_retries.
        """
        agent = event.agent
        if not agent:
            logger.warning(
                "[ResultValidationHook] No agent reference, cannot self-correct"
            )
            return

        current_failures = failures
        attempts_made = 0

        # Self-correction loop - make exactly max_retries attempts
        while attempts_made < self.max_retries:
            attempts_made += 1
            self._retry_count = attempts_made

            # Build correction prompt with failure details
            correction_prompt = self._build_correction_prompt(current_failures)

            logger.debug(
                f"[ResultValidationHook] Re-invoking agent with correction prompt "
                f"(attempt {attempts_made}/{self.max_retries})"
            )

            # Emit self-correction metric
            await self._emit_self_correction_metric(
                attempt=attempts_made,
                failures=current_failures,
            )

            # Re-invoke agent
            new_result = await agent(correction_prompt)

            # Validate the new result
            new_structured = getattr(new_result, "structured_output", None)
            if not new_structured:
                logger.warning(
                    "[ResultValidationHook] No structured_output in correction result"
                )
                # Treat as failure
                current_failures = [("self_correction", "No structured_output returned")]
            else:
                current_failures = self._run_validators(new_structured)

            if not current_failures:
                # Validation passed!
                logger.info(
                    f"[ResultValidationHook] Self-correction successful on "
                    f"attempt {attempts_made}"
                )
                self._retry_count = 0
                self._last_failures = []
                await self._emit_validation_metric(success=True, failures=[])
                return

            # Validation still failing
            self._last_failures = current_failures
            failure_details = "; ".join(
                f"{name}: {msg}" for name, msg in current_failures
            )
            logger.warning(
                f"[ResultValidationHook] Self-correction attempt {attempts_made} "
                f"still failing: {failure_details}"
            )

        # Max retries exhausted
        failure_details = "; ".join(
            f"{name}: {msg}" for name, msg in current_failures
        )
        logger.error(
            f"[ResultValidationHook] Max retries ({self.max_retries}) exhausted "
            f"during self-correction. Validation failed: {failure_details}"
        )
        raise ValidationError(
            f"Agent failed validation after {self.max_retries} retries: "
            f"{failure_details}",
            failures=current_failures,
        )

    def _build_correction_prompt(
        self, failures: List[Tuple[str, str]]
    ) -> str:
        """
        Build a correction prompt that includes validation failure details.

        Args:
            failures: List of (validator_name, error_message) tuples.

        Returns:
            Formatted correction prompt string.
        """
        failure_list = "\n".join(
            f"  - {name}: {message}" for name, message in failures
        )

        return f"""VALIDATION FAILED - Self-correction required (Attempt {self._retry_count}/{self.max_retries})

Your previous response failed the following validation checks:
{failure_list}

Please regenerate your response addressing these specific issues.
Focus on fixing the validation errors while maintaining the overall structure.
"""

    async def _emit_validation_metric(
        self,
        success: bool,
        failures: List[Tuple[str, str]],
    ) -> None:
        """
        Emit CloudWatch metric for validation result.

        Args:
            success: Whether validation passed.
            failures: List of failures (empty if success).
        """
        # Metric emission is best-effort
        try:
            # Import metrics client lazily to avoid circular imports
            from shared.hooks.metrics_hook import emit_metric

            await emit_metric(
                metric_name="ValidationAttemptCount",
                value=1,
                unit="Count",
                dimensions={
                    "success": str(success).lower(),
                    "failure_count": str(len(failures)),
                },
            )
        except Exception as e:
            logger.debug(f"[ResultValidationHook] Metric emission failed: {e}")

    async def _emit_self_correction_metric(
        self,
        attempt: int,
        failures: List[Tuple[str, str]],
    ) -> None:
        """
        Emit CloudWatch metric for self-correction attempt.

        Args:
            attempt: Current retry attempt number.
            failures: Validation failures that triggered correction.
        """
        try:
            from shared.hooks.metrics_hook import emit_metric

            await emit_metric(
                metric_name="SelfCorrectionCount",
                value=1,
                unit="Count",
                dimensions={
                    "attempt": str(attempt),
                    "failure_count": str(len(failures)),
                },
            )
        except Exception as e:
            logger.debug(f"[ResultValidationHook] Metric emission failed: {e}")

    # =========================================================================
    # State Management Methods
    # =========================================================================

    def get_last_failures(self) -> List[Tuple[str, str]]:
        """
        Get the last validation failures.

        Returns:
            List of (validator_name, error_message) tuples.
        """
        return self._last_failures

    def disable(self) -> None:
        """
        Temporarily disable the hook.

        Note: Disabling validation may impact agent output quality.
        """
        self.enabled = False
        logger.warning("[ResultValidationHook] DISABLED - validation bypassed")

    def enable(self) -> None:
        """Re-enable the hook."""
        self.enabled = True
        logger.info("[ResultValidationHook] Enabled")

    def reset(self) -> None:
        """
        Reset internal state.

        Clears retry count and failure history.
        """
        self._retry_count = 0
        self._last_failures = []
        logger.debug("[ResultValidationHook] State reset")
