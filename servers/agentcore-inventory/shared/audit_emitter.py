# =============================================================================
# Audit Emitter - Agent Activity Logging
# =============================================================================
# Standardized helper for all agents to emit events to DynamoDB audit log.
# Events are stored for observability and debugging purposes.
#
# Usage:
#   from shared.audit_emitter import AgentAuditEmitter, AgentStatus
#   audit = AgentAuditEmitter(agent_id="learning")
#   audit.started("Iniciando busca por conhecimento prévio...", session_id)
#
# Architecture:
# - Writes to DynamoDB audit table (faiston-one-sga-audit-log-prod)
# - Events available for CloudWatch Insights queries and debugging
# =============================================================================

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import os

from shared.env_config import get_required_env


def _convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert float values to Decimal for DynamoDB compatibility.

    DynamoDB does not support Python float type directly - it requires Decimal.
    This function converts any float values (including nested in dicts/lists)
    to Decimal using string conversion to preserve precision.

    Args:
        obj: Any Python object (dict, list, float, or other)

    Returns:
        Same structure with floats converted to Decimal
    """
    if isinstance(obj, float):
        # Convert via string to preserve precision
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats_to_decimal(i) for i in obj]
    return obj


class AgentStatus(Enum):
    """
    Standardized agent statuses for Agent Room display.

    These statuses are shown in the Live Feed with friendly Portuguese labels.
    """
    STARTING = "iniciando"
    WORKING = "trabalhando"
    WAITING_USER = "esperando_voce"
    DELEGATING = "delegando"
    LEARNING = "aprendendo"
    COMPLETED = "concluido"
    ERROR = "erro"
    IDLE = "disponivel"


@dataclass
class AuditEvent:
    """
    Structured audit event for DynamoDB.

    Attributes:
        agent_id: Technical agent identifier (e.g., "learning", "nexo_import")
        status: Current agent status from AgentStatus enum
        message: Human-readable message in Portuguese
        session_id: Optional session ID for tracking
        details: Optional additional details (dict)
        target_agent: Optional target agent for A2A delegation tracking
    """
    agent_id: str
    status: AgentStatus
    message: str
    session_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    target_agent: Optional[str] = None


class AgentAuditEmitter:
    """
    Audit emitter for Agent Room real-time visibility.

    Every agent MUST use this to emit events to DynamoDB.
    Agent Room frontend polls every 3-5 seconds.

    Example:
        audit = AgentAuditEmitter(agent_id="learning")

        # At start
        audit.started("Iniciando busca por conhecimento prévio...", session_id)

        # During processing
        audit.working("Analisando arquivo CSV...", session_id)

        # When delegating to another agent
        audit.delegating("validation", "Delegando validação de schema...", session_id)

        # On completion
        audit.completed("Encontrei 5 mapeamentos válidos", session_id)

        # On error
        audit.error("Erro ao buscar memória", session_id, error=str(e))
    """

    def __init__(self, agent_id: str):
        """
        Initialize audit emitter for an agent.

        Args:
            agent_id: Technical agent identifier (e.g., "learning", "nexo_import")
        """
        self.agent_id = agent_id
        self._table_name = get_required_env("AUDIT_LOG_TABLE", "audit event emission")
        self._dynamodb = None

    @property
    def dynamodb(self):
        """Lazy-load DynamoDB table resource."""
        if self._dynamodb is None:
            import boto3
            # Explicitly set region to ensure consistency across all environments
            self._dynamodb = boto3.resource("dynamodb", region_name="us-east-2").Table(self._table_name)
        return self._dynamodb

    def emit(self, event: AuditEvent) -> bool:
        """
        Emit audit event to DynamoDB for Agent Room visibility.

        This is SYNCHRONOUS to ensure events are captured before
        any potential failure. Latency is acceptable (<50ms).

        Args:
            event: Structured AuditEvent to emit

        Returns:
            True if event was logged successfully, False otherwise
        """
        try:
            now = datetime.utcnow()
            date_key = now.strftime("%Y-%m-%d")
            timestamp = now.isoformat() + "Z"
            event_id = f"{timestamp}#{self.agent_id}"

            item = {
                # Primary Key (date-partitioned for efficient queries)
                "PK": f"LOG#{date_key}",
                "SK": event_id,

                # GSI Keys for different query patterns
                "GSI1PK": f"ACTOR#AGENT#{self.agent_id}",
                "GSI1SK": event_id,
                "GSI3PK": "TYPE#AGENT_ACTIVITY",
                "GSI3SK": event_id,

                # Event Data
                "event_type": "AGENT_ACTIVITY",
                "actor_type": "AGENT",
                "actor_id": self.agent_id,
                "action": event.status.value,
                "timestamp": timestamp,

                # Event details for debugging/observability
                "details": {
                    "agent_id": self.agent_id,
                    "status": event.status.value,
                    "message": event.message,
                    **(event.details or {})
                }
            }

            # Add session GSI if provided
            if event.session_id:
                item["GSI4PK"] = f"SESSION#{event.session_id}"
                item["GSI4SK"] = event_id
                item["session_id"] = event.session_id

            # Add delegation target if A2A call
            if event.target_agent:
                item["details"]["target_agent"] = event.target_agent

            # Convert floats to Decimal for DynamoDB compatibility
            # DynamoDB rejects Python float type - requires Decimal
            item = _convert_floats_to_decimal(item)

            self.dynamodb.put_item(Item=item)
            return True

        except Exception as e:
            # Log error but don't fail the agent
            print(f"[Audit] Failed to emit event: {e}")
            return False

    # =========================================================================
    # Convenience Methods for Common Patterns
    # =========================================================================

    def started(self, message: str, session_id: Optional[str] = None) -> bool:
        """
        Emit start event.

        Args:
            message: Human-readable message (Portuguese)
            session_id: Optional session ID

        Returns:
            True if emitted successfully
        """
        return self.emit(AuditEvent(
            agent_id=self.agent_id,
            status=AgentStatus.STARTING,
            message=message,
            session_id=session_id,
        ))

    def working(
        self,
        message: str,
        session_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> bool:
        """
        Emit progress event.

        Args:
            message: Human-readable message (Portuguese)
            session_id: Optional session ID
            details: Optional additional details

        Returns:
            True if emitted successfully
        """
        return self.emit(AuditEvent(
            agent_id=self.agent_id,
            status=AgentStatus.WORKING,
            message=message,
            session_id=session_id,
            details=details,
        ))

    def delegating(
        self,
        target_agent: str,
        message: str,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Emit A2A delegation event.

        Args:
            target_agent: ID of the agent being called
            message: Human-readable message (Portuguese)
            session_id: Optional session ID

        Returns:
            True if emitted successfully
        """
        return self.emit(AuditEvent(
            agent_id=self.agent_id,
            status=AgentStatus.DELEGATING,
            message=message,
            session_id=session_id,
            target_agent=target_agent,
        ))

    def learning(
        self,
        message: str,
        session_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> bool:
        """
        Emit learning event (for LearningAgent memory operations).

        Args:
            message: Human-readable message (Portuguese)
            session_id: Optional session ID
            details: Optional additional details

        Returns:
            True if emitted successfully
        """
        return self.emit(AuditEvent(
            agent_id=self.agent_id,
            status=AgentStatus.LEARNING,
            message=message,
            session_id=session_id,
            details=details,
        ))

    def waiting_user(
        self,
        message: str,
        session_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> bool:
        """
        Emit waiting for user event (HIL).

        Args:
            message: Human-readable message (Portuguese)
            session_id: Optional session ID
            details: Optional additional details

        Returns:
            True if emitted successfully
        """
        return self.emit(AuditEvent(
            agent_id=self.agent_id,
            status=AgentStatus.WAITING_USER,
            message=message,
            session_id=session_id,
            details=details,
        ))

    def completed(
        self,
        message: str,
        session_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> bool:
        """
        Emit completion event.

        Args:
            message: Human-readable message (Portuguese)
            session_id: Optional session ID
            details: Optional additional details (e.g., results summary)

        Returns:
            True if emitted successfully
        """
        return self.emit(AuditEvent(
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            message=message,
            session_id=session_id,
            details=details,
        ))

    def error(
        self,
        message: str,
        session_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Emit error event.

        Args:
            message: Human-readable message (Portuguese)
            session_id: Optional session ID
            error: Optional error string for debugging

        Returns:
            True if emitted successfully
        """
        return self.emit(AuditEvent(
            agent_id=self.agent_id,
            status=AgentStatus.ERROR,
            message=message,
            session_id=session_id,
            details={"error": error} if error else None,
        ))


# =============================================================================
# Module-level helper for quick access
# =============================================================================

def emit_agent_event(
    agent_id: str,
    status: str,
    message: str,
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Quick helper to emit an agent event without instantiating a class.

    This is a convenience function for simple use cases.
    For repeated emissions, prefer using AgentAuditEmitter class.

    Args:
        agent_id: Agent identifier (e.g., "nexo_import", "learning")
        status: Status string (e.g., "trabalhando", "concluido")
        message: Human-readable message in Portuguese
        session_id: Optional session ID
        details: Optional additional details

    Returns:
        True if event was logged successfully
    """
    emitter = AgentAuditEmitter(agent_id)
    status_enum = AgentStatus(status) if status in [s.value for s in AgentStatus] else AgentStatus.WORKING
    return emitter.emit(AuditEvent(
        agent_id=agent_id,
        status=status_enum,
        message=message,
        session_id=session_id,
        details=details,
    ))
