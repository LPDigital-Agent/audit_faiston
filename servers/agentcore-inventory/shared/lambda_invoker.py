# =============================================================================
# Lambda Invoker - Direct Lambda Invocation with OTEL Tracing
# =============================================================================
# Provides synchronous Lambda invocation for deterministic operations
# that have been extracted from agents (BRAIN/HANDS pattern).
#
# Architecture:
#   Orchestrator → LambdaInvoker → Lambda (intake-tools, file-analyzer)
#                      ↓
#   Creates X-Ray child span for distributed tracing
#   Emits audit events for observability
#   Raises CognitiveError for DebugAgent enrichment
#
# Usage:
#   from shared.lambda_invoker import LambdaInvoker
#
#   invoker = LambdaInvoker()
#   result = invoker.invoke_intake(
#       action="get_nf_upload_url",
#       payload={"filename": "inventory.xlsx"},
#       user_id="user-123",
#       session_id="session-456",
#   )
#
# Related:
#   - ADR-010: Lambda Migration for Deterministic Operations
#   - server/lambdas/intake-tools/ - Intake operations Lambda
#   - server/lambdas/file-analyzer/ - File analysis Lambda
#
# Author: Faiston NEXO Team
# Date: January 2026
# =============================================================================

import json
import logging
import os
from typing import Any

from shared.cognitive_error_handler import CognitiveError
from shared.audit_emitter import AgentAuditEmitter, AgentStatus
from shared.xray_tracer import trace_subsegment, add_trace_annotation

logger = logging.getLogger(__name__)

# Environment configuration
INTAKE_TOOLS_FUNCTION = os.environ.get(
    "INTAKE_TOOLS_LAMBDA",
    "faiston-one-prod-sga-intake-tools",
)
FILE_ANALYZER_FUNCTION = os.environ.get(
    "FILE_ANALYZER_LAMBDA",
    "faiston-one-prod-sga-file-analyzer",
)
AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-2")

# Lazy imports for cold start optimization
_lambda_client = None


def _get_lambda_client():
    """Get Lambda client with lazy initialization."""
    global _lambda_client
    if _lambda_client is None:
        import boto3
        _lambda_client = boto3.client("lambda", region_name=AWS_REGION)
        logger.info("[LambdaInvoker] Client created: region=%s", AWS_REGION)
    return _lambda_client


class LambdaInvoker:
    """
    Lambda invoker with OTEL tracing and audit logging.

    Provides synchronous Lambda invocation for operations extracted from
    agents following the BRAIN/HANDS pattern. The Orchestrator (BRAIN)
    coordinates which Lambda (HANDS) to call; the Lambda executes
    deterministic operations.

    Features:
        - X-Ray distributed tracing (child spans)
        - Audit logging for observability
        - Response transformation to Orchestrator envelope
        - CognitiveError for DebugAgent enrichment

    Example:
        invoker = LambdaInvoker()

        # Generate presigned upload URL
        result = invoker.invoke_intake(
            action="get_nf_upload_url",
            payload={"filename": "inventory.xlsx"},
            user_id="user-123",
            session_id="session-456",
        )
        # Returns: {"success": True, "specialist_agent": "intake", "response": {...}}
    """

    def __init__(self, audit_agent_id: str = "inventory_hub"):
        """
        Initialize Lambda invoker.

        Args:
            audit_agent_id: Agent ID for audit logging (default: inventory_hub)
        """
        self.audit = AgentAuditEmitter(agent_id=audit_agent_id)

    def invoke_intake(
        self,
        action: str,
        payload: dict[str, Any],
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Invoke intake-tools Lambda for file upload/verification operations.

        Supported actions:
            - get_nf_upload_url: Generate presigned PUT URL for file upload
            - verify_file: Check if file exists in S3 and get metadata

        Args:
            action: Operation to perform ("get_nf_upload_url" or "verify_file")
            payload: Action-specific parameters
            user_id: User identifier for audit and path namespacing
            session_id: Session identifier for audit and path namespacing

        Returns:
            Orchestrator envelope:
                {
                    "success": True,
                    "specialist_agent": "intake",
                    "response": {...}  # Lambda data
                }

        Raises:
            CognitiveError: On Lambda invocation or response errors
                (routed to DebugAgent via @cognitive_sync_handler)
        """
        # Build Lambda event
        event = {
            "action": action,
            "payload": payload,
            "user_id": user_id,
            "session_id": session_id,
        }

        # Invoke with tracing
        result = self._invoke_lambda(
            function_name=INTAKE_TOOLS_FUNCTION,
            event=event,
            operation_name=f"intake.{action}",
            session_id=session_id,
        )

        # Transform to Orchestrator envelope
        return {
            "success": True,
            "specialist_agent": "intake",
            "response": result["data"],
        }

    def invoke_file_analyzer(
        self,
        action: str,
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Invoke file-analyzer Lambda for file structure analysis.

        Supported actions:
            - analyze_file_structure: Inspect CSV/Excel file structure
            - validate_file_columns: Validate required columns exist

        Args:
            action: Operation to perform
            payload: Action-specific parameters (s3_key, etc.)
            session_id: Optional session identifier for audit

        Returns:
            Orchestrator envelope:
                {
                    "success": True,
                    "specialist_agent": "file_analyzer",
                    "response": {...}  # Lambda data
                }

        Raises:
            CognitiveError: On Lambda invocation or response errors
        """
        # Build Lambda event (MCP Gateway format)
        event = {
            **payload,
        }

        # File analyzer uses context for tool name (MCP pattern)
        # For direct invocation, we pass action in payload
        if action:
            event["action"] = action

        # Invoke with tracing
        result = self._invoke_lambda(
            function_name=FILE_ANALYZER_FUNCTION,
            event=event,
            operation_name=f"file_analyzer.{action}",
            session_id=session_id,
        )

        # File analyzer returns MCP format, extract content
        if "content" in result:
            # MCP format: {"content": [{"type": "text", "text": "..."}], "isError": ...}
            content = result.get("content", [])
            if content and isinstance(content, list):
                text = content[0].get("text", "{}")
                data = json.loads(text) if isinstance(text, str) else text
            else:
                data = result
        else:
            data = result.get("data", result)

        return {
            "success": True,
            "specialist_agent": "file_analyzer",
            "response": data,
        }

    def _invoke_lambda(
        self,
        function_name: str,
        event: dict[str, Any],
        operation_name: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Invoke Lambda function with tracing and audit logging.

        Internal method that handles the actual Lambda invocation
        with X-Ray tracing, audit logging, and error handling.

        Args:
            function_name: Lambda function name or ARN
            event: Event payload to send to Lambda
            operation_name: Operation name for tracing/logging
            session_id: Optional session ID for audit

        Returns:
            Lambda response parsed as dict

        Raises:
            CognitiveError: On any invocation or response error
        """
        # Emit audit event for observability
        self.audit.working(
            f"Executando operacao: {operation_name}",
            session_id=session_id,
            details={"function": function_name, "action": operation_name},
        )

        # Create X-Ray subsegment for distributed tracing
        with trace_subsegment(
            f"Lambda-{operation_name}",
            annotations={
                "lambda_function": function_name,
                "operation": operation_name,
                "session_id": session_id or "unknown",
            },
        ) as subsegment:
            try:
                # Invoke Lambda synchronously
                client = _get_lambda_client()
                response = client.invoke(
                    FunctionName=function_name,
                    InvocationType="RequestResponse",  # Synchronous
                    Payload=json.dumps(event).encode("utf-8"),
                )

                # Check for Lambda execution errors
                if "FunctionError" in response:
                    error_payload = response["Payload"].read().decode("utf-8")
                    logger.error(
                        "[LambdaInvoker] Function error: %s - %s",
                        function_name, error_payload,
                    )
                    subsegment.put_annotation("success", False)
                    raise CognitiveError(
                        technical_message=f"Lambda function error: {error_payload}",
                        human_explanation="Ocorreu um erro ao processar a operacao no servidor.",
                        suggested_fix="Verifique os parametros e tente novamente.",
                        error_type="LAMBDA_FUNCTION_ERROR",
                        recoverable=True,
                        context={
                            "function": function_name,
                            "operation": operation_name,
                            "error_payload": error_payload[:500],
                        },
                    )

                # Parse response
                payload_bytes = response["Payload"].read()
                result = json.loads(payload_bytes.decode("utf-8"))

                logger.debug(
                    "[LambdaInvoker] Response from %s: success=%s",
                    function_name, result.get("success"),
                )

                # Check for application-level errors
                if not result.get("success", True):
                    error = result.get("error", "Unknown error")
                    error_type = result.get("error_type", "LAMBDA_ERROR")

                    logger.warning(
                        "[LambdaInvoker] Application error: %s - %s",
                        error_type, error,
                    )
                    subsegment.put_annotation("success", False)
                    subsegment.put_annotation("error_type", error_type)

                    # For FILE_NOT_FOUND, this is expected behavior, not an error
                    if error_type == "FILE_NOT_FOUND":
                        # Return the result as-is, let caller handle
                        subsegment.put_annotation("success", True)
                        return result

                    raise CognitiveError(
                        technical_message=f"Lambda operation failed: {error}",
                        human_explanation=self._translate_error(error),
                        suggested_fix=self._suggest_fix(error_type),
                        error_type=error_type,
                        recoverable=error_type in ("VALIDATION_ERROR", "FILE_NOT_FOUND"),
                        context={
                            "function": function_name,
                            "operation": operation_name,
                            "original_error": error,
                        },
                    )

                # Success - record in trace
                subsegment.put_annotation("success", True)

                # Emit completion audit event
                self.audit.completed(
                    f"Operacao concluida: {operation_name}",
                    session_id=session_id,
                )

                return result

            except CognitiveError:
                # Re-raise cognitive errors (already formatted)
                raise

            except json.JSONDecodeError as e:
                logger.exception("[LambdaInvoker] Failed to parse response: %s", e)
                subsegment.put_annotation("success", False)
                raise CognitiveError(
                    technical_message=f"Failed to parse Lambda response: {e}",
                    human_explanation="Resposta inesperada do servidor.",
                    suggested_fix="Contate o suporte tecnico.",
                    error_type="PARSE_ERROR",
                    recoverable=False,
                    original_exception=e,
                )

            except Exception as e:
                logger.exception("[LambdaInvoker] Invocation failed: %s", e)
                subsegment.put_annotation("success", False)
                subsegment.add_exception(e)

                # Emit error audit event
                self.audit.error(
                    f"Erro na operacao: {operation_name}",
                    session_id=session_id,
                    error=str(e),
                )

                raise CognitiveError(
                    technical_message=f"Lambda invocation failed: {e}",
                    human_explanation="Nao foi possivel executar a operacao.",
                    suggested_fix="Verifique sua conexao e tente novamente.",
                    error_type="INVOCATION_ERROR",
                    recoverable=True,
                    original_exception=e,
                    context={
                        "function": function_name,
                        "operation": operation_name,
                    },
                )

    def _translate_error(self, error: str) -> str:
        """Translate error message to user-friendly Portuguese."""
        # Map common error patterns to friendly messages
        if "filename" in error.lower() and "obrigat" in error.lower():
            return "O nome do arquivo e obrigatorio para esta operacao."
        if "extensao" in error.lower():
            return "O tipo de arquivo nao e suportado."
        if "s3_key" in error.lower():
            return "A referencia do arquivo e obrigatoria."
        if "user_id" in error.lower():
            return "Identificacao do usuario nao encontrada."
        if "session_id" in error.lower():
            return "Sessao nao identificada."
        if "permission" in error.lower() or "seguranca" in error.lower():
            return "Voce nao tem permissao para esta operacao."
        if "not found" in error.lower() or "nao encontrado" in error.lower():
            return "O arquivo solicitado nao foi encontrado."
        return "Ocorreu um erro ao processar sua solicitacao."

    def _suggest_fix(self, error_type: str) -> str:
        """Get fix suggestion based on error type."""
        suggestions = {
            "VALIDATION_ERROR": "Verifique os dados informados e tente novamente.",
            "FILE_NOT_FOUND": "Certifique-se de que o arquivo foi enviado corretamente.",
            "SECURITY_ERROR": "Verifique suas permissoes de acesso.",
            "S3_ERROR": "Problema de armazenamento. Tente novamente em alguns instantes.",
            "CONFIG_ERROR": "Erro de configuracao do sistema. Contate o suporte.",
            "LAMBDA_FUNCTION_ERROR": "Erro interno. Tente novamente.",
            "PARSE_ERROR": "Resposta inesperada. Contate o suporte.",
            "INVOCATION_ERROR": "Problema de conexao. Tente novamente.",
        }
        return suggestions.get(error_type, "Tente novamente ou contate o suporte.")


# =============================================================================
# Module-level convenience functions
# =============================================================================


def invoke_intake_tools(
    action: str,
    payload: dict[str, Any],
    user_id: str,
    session_id: str,
) -> dict[str, Any]:
    """
    Convenience function to invoke intake-tools Lambda.

    Args:
        action: Operation to perform
        payload: Action-specific parameters
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Orchestrator envelope with response

    Example:
        result = invoke_intake_tools(
            action="get_nf_upload_url",
            payload={"filename": "inventory.xlsx"},
            user_id="user-123",
            session_id="session-456",
        )
    """
    invoker = LambdaInvoker()
    return invoker.invoke_intake(action, payload, user_id, session_id)


def invoke_file_analyzer(
    action: str,
    payload: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Convenience function to invoke file-analyzer Lambda.

    Args:
        action: Operation to perform
        payload: Action-specific parameters
        session_id: Optional session identifier

    Returns:
        Orchestrator envelope with response
    """
    invoker = LambdaInvoker()
    return invoker.invoke_file_analyzer(action, payload, session_id)
