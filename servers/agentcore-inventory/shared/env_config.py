# =============================================================================
# Environment Configuration with FAIL-CLOSED Behavior
# =============================================================================
# Centralized environment variable access with explicit fail-fast semantics.
# All required environment variables must be explicitly set - production
# fallbacks are FORBIDDEN to prevent accidental production data access.
#
# Security Principle: FAIL-CLOSED
# - If configuration is missing, fail immediately with clear error
# - Never silently use production resources from local development
# - Follows OWASP/AWS security best practices
#
# Usage:
#     from shared.env_config import get_required_env, get_optional_env
#
#     # Required - fails if not set
#     INVENTORY_TABLE = get_required_env("INVENTORY_TABLE", "inventory access")
#
#     # Optional - uses safe default
#     LOG_LEVEL = get_optional_env("LOG_LEVEL", "INFO")
# =============================================================================

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class EnvironmentConfigError(Exception):
    """
    Raised when a required environment variable is missing.

    This exception indicates a configuration error that must be fixed
    before the application can run. In deployed environments, all
    required variables are set by Terraform. For local development,
    developers must explicitly set environment variables.
    """
    pass


def get_required_env(name: str, context: str = "") -> str:
    """
    Get a required environment variable or raise with helpful error.

    This function implements FAIL-CLOSED behavior: if the variable is not
    set, the application fails immediately with a clear error message
    rather than silently using a production fallback.

    Args:
        name: Environment variable name (e.g., "INVENTORY_TABLE")
        context: Optional context for error message describing the use case
                (e.g., "inventory data access", "S3 document storage")

    Returns:
        The environment variable value (guaranteed non-empty)

    Raises:
        EnvironmentConfigError: If variable is not set or is empty string

    Example:
        >>> INVENTORY_TABLE = get_required_env("INVENTORY_TABLE", "DynamoDB access")
        >>> # If INVENTORY_TABLE is not set:
        >>> # EnvironmentConfigError: Missing required environment variable: INVENTORY_TABLE (DynamoDB access)
    """
    value = os.environ.get(name)

    if not value:
        ctx = f" ({context})" if context else ""
        error_msg = (
            f"Missing required environment variable: {name}{ctx}\n\n"
            f"For deployed environments → Variable is set via Terraform\n"
            f"For local development → export {name}=<your-dev-value>\n\n"
            f"IMPORTANT: NEVER use production resource names for local development!"
        )
        logger.error(f"Environment configuration error: {error_msg}")
        raise EnvironmentConfigError(error_msg)

    return value


def get_optional_env(name: str, default: str) -> str:
    """
    Get an optional environment variable with a safe default.

    Use this ONLY for non-resource configuration such as:
    - Log levels (LOG_LEVEL)
    - Timeouts and thresholds
    - Feature flags
    - Formatting options

    NEVER use this for:
    - Table names (use get_required_env)
    - Bucket names (use get_required_env)
    - Account IDs (use get_required_env)
    - Any resource identifier

    Args:
        name: Environment variable name
        default: Safe default value to use if variable is not set

    Returns:
        The environment variable value or the default

    Example:
        >>> LOG_LEVEL = get_optional_env("LOG_LEVEL", "INFO")
        >>> TIMEOUT_SECONDS = get_optional_env("TIMEOUT_SECONDS", "30")
    """
    return os.environ.get(name, default)


def get_required_env_int(name: str, context: str = "") -> int:
    """
    Get a required environment variable as an integer.

    Args:
        name: Environment variable name
        context: Optional context for error message

    Returns:
        The environment variable value as an integer

    Raises:
        EnvironmentConfigError: If variable is not set or not a valid integer
    """
    value = get_required_env(name, context)
    try:
        return int(value)
    except ValueError:
        error_msg = f"Environment variable {name} must be an integer, got: {value}"
        logger.error(error_msg)
        raise EnvironmentConfigError(error_msg)


def get_optional_env_int(name: str, default: int) -> int:
    """
    Get an optional environment variable as an integer with a safe default.

    Args:
        name: Environment variable name
        default: Safe default integer value

    Returns:
        The environment variable value as an integer, or the default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer for {name}: {value}, using default: {default}")
        return default
