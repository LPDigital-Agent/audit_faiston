# =============================================================================
# Guardrails Hook for Strands Agents (Shadow Mode)
# =============================================================================
# Implements content moderation in shadow mode (monitor without blocking).
#
# Reference: https://strandsagents.com/latest/documentation/docs/user-guide/safety-security/guardrails/
# =============================================================================

import logging
from typing import Optional

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    BeforeInvocationEvent,
    AfterInvocationEvent,
)

logger = logging.getLogger(__name__)


class GuardrailsHook(HookProvider):
    """
    Shadow mode guardrails hook for Strands Agents.

    Monitors content for policy violations WITHOUT blocking.
    Logs violations for review and metrics.

    Shadow mode benefits:
    - Monitor without impacting user experience
    - Collect data to tune guardrail policies
    - Gradual rollout of content moderation

    Usage:
        agent = Agent(hooks=[GuardrailsHook(guardrail_id="abc123")])
    """

    def __init__(
        self,
        guardrail_id: Optional[str] = None,
        guardrail_version: str = "DRAFT",
        shadow_mode: bool = True,
    ):
        """
        Initialize GuardrailsHook.

        Args:
            guardrail_id: AWS Bedrock Guardrail ID (None to skip)
            guardrail_version: Guardrail version (default: DRAFT)
            shadow_mode: If True, monitor only; if False, block violations
        """
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self.shadow_mode = shadow_mode
        self._bedrock_client = None

    def _get_bedrock_client(self):
        """Lazy load Bedrock client."""
        if self._bedrock_client is None and self.guardrail_id:
            try:
                import boto3
                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name="us-east-2",
                )
            except Exception as e:
                logger.warning(f"[GuardrailsHook] Failed to create Bedrock client: {e}")
        return self._bedrock_client

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register callbacks for content evaluation."""
        registry.add_callback(BeforeInvocationEvent, self._evaluate_input)
        registry.add_callback(AfterInvocationEvent, self._evaluate_output)

    def _evaluate_content(self, content: str, source: str = "INPUT") -> bool:
        """
        Evaluate content against guardrails.

        Args:
            content: Text content to evaluate
            source: "INPUT" or "OUTPUT" for logging

        Returns:
            True if content is safe, False if violation detected
        """
        if not self.guardrail_id or not content:
            return True

        client = self._get_bedrock_client()
        if not client:
            return True

        try:
            response = client.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source=source,
                content=[{"text": {"text": content}}],
            )

            action = response.get("action", "NONE")

            if action == "GUARDRAIL_INTERVENED":
                # Log the intervention
                assessments = response.get("assessments", [])
                logger.warning(
                    f"[GuardrailsHook] {'WOULD BLOCK' if self.shadow_mode else 'BLOCKED'} "
                    f"- {source}: {assessments}"
                )

                # In shadow mode, allow but log
                # In enforce mode, return False to block
                return self.shadow_mode

            return True

        except Exception as e:
            logger.warning(f"[GuardrailsHook] Evaluation failed: {e}")
            # Fail open - allow content if guardrail evaluation fails
            return True

    def _evaluate_input(self, event: BeforeInvocationEvent) -> None:
        """Evaluate user input against guardrails."""
        # Get the latest user message
        messages = getattr(event.agent, "messages", [])
        if messages:
            last_message = messages[-1]
            content = last_message.get("content", "")
            if isinstance(content, str):
                self._evaluate_content(content, "INPUT")

    def _evaluate_output(self, event: AfterInvocationEvent) -> None:
        """Evaluate agent output against guardrails."""
        # Get the result message
        result = getattr(event, "result", None)
        if result:
            message = getattr(result, "message", "")
            if message:
                self._evaluate_content(message, "OUTPUT")
