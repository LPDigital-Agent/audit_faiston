# =============================================================================
# AgentCore Identity Utilities
# =============================================================================
# Centralized identity extraction for AgentCore agents.
# Follows AWS Bedrock AgentCore Identity best practices.
#
# Reference:
# - docs/AgentCore/Identity_Implementation_guide.md
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html
#
# CRITICAL: User identity MUST be extracted from context.identity (JWT validated
# by AgentCore) NOT from the A2A payload. The payload extraction is a fallback
# for backward compatibility only and emits deprecation warnings.
#
# Compliance: AgentCore Identity v1.0
# =============================================================================

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass

# AUDIT-003: Global error capture for Debug Agent enrichment
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


@dataclass
class UserIdentity:
    """
    Represents authenticated user identity from AgentCore context.

    Attributes:
        user_id: Unique user identifier (Cognito 'sub' claim or fallback)
        email: User email (from JWT claims, may be None)
        name: User display name (from JWT claims, may be None)
        source: Where identity was extracted from ('jwt_context' or 'payload_fallback')
        raw_claims: Full JWT claims dict (if available)
    """

    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    source: str = "unknown"
    raw_claims: Optional[Dict[str, Any]] = None

    def is_secure(self) -> bool:
        """Returns True if identity came from validated JWT context."""
        return self.source == "jwt_context"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "source": self.source,
        }


def extract_user_identity(context: Any, payload: Dict[str, Any]) -> UserIdentity:
    """
    Extract user identity from AgentCore context or payload (fallback).

    This function implements the AgentCore Identity best practice:
    1. PREFER context.identity (JWT validated by AgentCore Gateway)
    2. FALLBACK to payload.user_id (for backward compatibility only)

    The fallback emits a deprecation warning and should be removed once
    all callers are migrated to pass identity via JWT.

    Args:
        context: AgentCore runtime context object
        payload: A2A message payload dict

    Returns:
        UserIdentity object with extracted identity information

    Example:
        ```python
        @app.entrypoint
        def agent_invocation(payload: Dict[str, Any], context) -> Dict[str, Any]:
            user = extract_user_identity(context, payload)

            if not user.is_secure():
                logger.warning("Using fallback identity - enable JWT authorizer")

            # Use user.user_id for audit trails
            audit.started(message=f"Action by {user.user_id}", ...)
        ```

    Security Note:
        - 'jwt_context' source means identity was validated by AgentCore Gateway
        - 'payload_fallback' means identity came from untrusted A2A payload
        - Production systems should ONLY accept 'jwt_context' source
    """
    # Attempt 1: Extract from context.identity (preferred - JWT validated)
    identity = _extract_from_context(context)
    if identity:
        logger.debug(
            f"Identity extracted from JWT context: user_id={identity.user_id}"
        )
        return identity

    # Attempt 2: Fallback to payload (backward compatibility)
    identity = _extract_from_payload(payload)
    if identity:
        # Emit deprecation warning for non-system users
        if identity.user_id != "system":
            logger.warning(
                f"DEPRECATION: user_id '{identity.user_id}' extracted from payload. "
                "Migrate to context.identity extraction by enabling JWT authorizer on Gateway. "
                "See: docs/AgentCore/Identity_Implementation_guide.md"
            )
        return identity

    # Fallback: system user
    logger.debug("No identity found, using 'system' default")
    return UserIdentity(
        user_id="system",
        source="default",
    )


def _extract_from_context(context: Any) -> Optional[UserIdentity]:
    """
    Extract identity from AgentCore context.identity.

    The context.identity contains JWT claims validated by AgentCore Gateway.
    Standard claims include:
    - sub: Subject (unique user ID from IdP)
    - email: User email
    - name: User display name
    - cognito:username: Cognito username (if using Cognito)

    Args:
        context: AgentCore runtime context

    Returns:
        UserIdentity if identity found in context, None otherwise
    """
    if context is None:
        return None

    # Try different ways to access identity from context
    identity = None

    # Method 1: context.identity (standard AgentCore pattern)
    if hasattr(context, "identity"):
        identity = context.identity

    # Method 2: context.get("identity") (dict-like context)
    elif hasattr(context, "get"):
        identity = context.get("identity")

    # Method 3: context["identity"] (direct dict access)
    elif isinstance(context, dict):
        identity = context.get("identity")

    if not identity:
        return None

    # Extract claims from identity
    if isinstance(identity, dict):
        user_id = identity.get("sub") or identity.get("user_id")
        if user_id:
            return UserIdentity(
                user_id=str(user_id),
                email=identity.get("email"),
                name=identity.get("name") or identity.get("cognito:username"),
                source="jwt_context",
                raw_claims=identity,
            )

    return None


def _extract_from_payload(payload: Dict[str, Any]) -> Optional[UserIdentity]:
    """
    Extract identity from A2A payload (fallback only).

    WARNING: This is NOT secure! The payload can be crafted by any caller.
    Use only for backward compatibility during migration.

    Args:
        payload: A2A message payload dict

    Returns:
        UserIdentity if user_id found in payload, None otherwise
    """
    if not isinstance(payload, dict):
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    return UserIdentity(
        user_id=str(user_id),
        email=payload.get("user_email"),
        name=payload.get("user_name"),
        source="payload_fallback",
    )


def validate_identity_source(
    identity: UserIdentity,
    require_secure: bool = False,
    agent_name: str = "unknown",
) -> bool:
    """
    Validate that identity came from a secure source.

    Use this in production to enforce JWT-based authentication.

    Args:
        identity: UserIdentity object to validate
        require_secure: If True, raises ValueError for non-secure sources
        agent_name: Agent name for logging

    Returns:
        True if identity is secure (from JWT context)

    Raises:
        ValueError: If require_secure=True and source is not 'jwt_context'
    """
    if identity.is_secure():
        return True

    message = (
        f"[{agent_name}] Identity source '{identity.source}' is not secure. "
        f"User: {identity.user_id}. "
        "Enable JWT authorizer on Gateway for production."
    )

    if require_secure:
        # AUDIT-003: Use debug_error for enriched error analysis
        security_error = ValueError(message)
        debug_error(security_error, "identity_security_validation", {
            "identity_source": identity.source,
            "user_id": identity.user_id,
            "agent_name": agent_name,
        })
        raise security_error

    logger.warning(message)
    return False


# =============================================================================
# Audit Trail Helpers
# =============================================================================


def get_audit_user_id(identity: UserIdentity) -> str:
    """
    Get user ID formatted for audit trails.

    Format: "{source}:{user_id}" to clearly indicate identity source.

    Args:
        identity: UserIdentity object

    Returns:
        Formatted user ID string for audit logs
    """
    if identity.source == "jwt_context":
        return identity.user_id
    else:
        # Prefix with source for non-JWT identities to flag in audit logs
        return f"[{identity.source}]:{identity.user_id}"


def log_identity_context(
    identity: UserIdentity,
    agent_name: str,
    action: str,
    session_id: str,
) -> None:
    """
    Log identity context for security monitoring.

    Args:
        identity: UserIdentity object
        agent_name: Name of the agent
        action: Action being performed
        session_id: Session ID
    """
    logger.info(
        f"[{agent_name}] Identity context | "
        f"action={action} | "
        f"user_id={identity.user_id} | "
        f"source={identity.source} | "
        f"secure={identity.is_secure()} | "
        f"session_id={session_id}"
    )
