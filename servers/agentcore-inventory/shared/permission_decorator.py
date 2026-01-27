"""
Permission Decorator for Faiston NEXO Agents.

Provides decorators for validating user permissions on agent tools and endpoints.
Follows the FAIL-CLOSED security model - access is denied by default.

Reference: docs/permissions/PRD-permissions-system.md
"""

import functools
import logging
from typing import Any, Callable

from shared.identity_utils import UserIdentity, extract_user_identity
from shared.permissions_client import (
    PermissionsClient,
    UserPermissions,
    get_permissions_client,
)

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    """Raised when user lacks required permission."""

    def __init__(self, message: str, code: str | None = None, user_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.user_id = user_id


class ModuleAccessDeniedError(PermissionDeniedError):
    """Raised when user cannot access a module."""

    def __init__(self, module: str, user_id: str | None = None):
        super().__init__(
            f"Acesso negado ao modulo {module}",
            code=module,
            user_id=user_id
        )
        self.module = module


def requires_permission(
    code: str,
    check_module: bool = True,
    fallback_groups: list[str] | None = None
) -> Callable:
    """
    Decorator that validates user has a specific permission.

    This decorator:
    1. Extracts user identity from context
    2. Optionally validates module access (fast path via Cognito groups)
    3. Validates specific permission code
    4. Raises PermissionDeniedError if validation fails

    Args:
        code: Permission code required (e.g., "EST_C01")
        check_module: Whether to check module access first (default True)
        fallback_groups: Optional groups for testing/fallback

    Returns:
        Decorated function

    Example:
        ```python
        @requires_permission("EST_C01")
        async def create_asset(context, data: dict):
            # User has EST_C01 permission
            pass
        ```
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(context, *args, **kwargs) -> Any:
            # Extract identity
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            # Validate permissions
            _validate_permission(
                identity,
                code,
                check_module=check_module,
                fallback_groups=fallback_groups
            )

            return await func(context, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(context, *args, **kwargs) -> Any:
            # Extract identity
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            # Validate permissions
            _validate_permission(
                identity,
                code,
                check_module=check_module,
                fallback_groups=fallback_groups
            )

            return func(context, *args, **kwargs)

        # Return appropriate wrapper based on function type
        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def requires_any_permission(*codes: str, check_module: bool = True) -> Callable:
    """
    Decorator that validates user has at least one of the specified permissions.

    Args:
        *codes: Permission codes (at least one required)
        check_module: Whether to check module access first

    Returns:
        Decorated function

    Example:
        ```python
        @requires_any_permission("EST_R01", "EST_R02", "EST_R03")
        async def view_inventory(context):
            # User has at least one read permission
            pass
        ```
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(context, *args, **kwargs) -> Any:
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            _validate_any_permission(identity, list(codes), check_module=check_module)

            return await func(context, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(context, *args, **kwargs) -> Any:
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            _validate_any_permission(identity, list(codes), check_module=check_module)

            return func(context, *args, **kwargs)

        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def requires_all_permissions(*codes: str, check_module: bool = True) -> Callable:
    """
    Decorator that validates user has all specified permissions.

    Args:
        *codes: Permission codes (all required)
        check_module: Whether to check module access first

    Returns:
        Decorated function

    Example:
        ```python
        @requires_all_permissions("EST_C01", "EST_U01")
        async def bulk_update_assets(context, data: list):
            # User has both create and update permissions
            pass
        ```
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(context, *args, **kwargs) -> Any:
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            _validate_all_permissions(identity, list(codes), check_module=check_module)

            return await func(context, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(context, *args, **kwargs) -> Any:
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            _validate_all_permissions(identity, list(codes), check_module=check_module)

            return func(context, *args, **kwargs)

        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def requires_module_access(module: str) -> Callable:
    """
    Decorator that validates user can access a specific module.

    This is a fast-path check using Cognito groups, without
    looking up specific permissions.

    Args:
        module: Module code (e.g., "EST", "EXP")

    Returns:
        Decorated function

    Example:
        ```python
        @requires_module_access("EST")
        async def list_inventory(context):
            # User can access inventory module
            pass
        ```
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(context, *args, **kwargs) -> Any:
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            _validate_module_access(identity, module)

            return await func(context, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(context, *args, **kwargs) -> Any:
            payload = kwargs.get("payload", {})
            identity = extract_user_identity(context, payload)

            _validate_module_access(identity, module)

            return func(context, *args, **kwargs)

        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Internal Validation Functions
# =============================================================================

def _validate_permission(
    identity: UserIdentity,
    code: str,
    check_module: bool = True,
    fallback_groups: list[str] | None = None
) -> None:
    """
    Validate user has specific permission.

    Args:
        identity: User identity from context
        code: Permission code
        check_module: Whether to check module first
        fallback_groups: Optional groups for fallback

    Raises:
        ModuleAccessDeniedError: If module access denied
        PermissionDeniedError: If permission denied
    """
    client = get_permissions_client()

    # Extract module from code (e.g., "EST_R01" -> "EST")
    module = code.split("_")[0] if "_" in code else code

    # Get user's groups from identity
    groups = _get_groups_from_identity(identity, fallback_groups)

    # Step 1: Module access check (fast path)
    if check_module:
        user_permissions = client.get_user_permissions(identity.user_id, groups)
        if user_permissions and not client.can_access_module(user_permissions, module):
            logger.warning(
                f"Module access denied | user={identity.user_id} | module={module}"
            )
            raise ModuleAccessDeniedError(module, identity.user_id)

    # Step 2: Specific permission check
    if user_permissions is None:
        user_permissions = client.get_user_permissions(identity.user_id, groups)

    if user_permissions is None:
        logger.warning(f"No permissions found for user {identity.user_id}")
        raise PermissionDeniedError(
            f"Sem permissao para {code}",
            code=code,
            user_id=identity.user_id
        )

    if not client.has_permission(user_permissions, code):
        logger.warning(
            f"Permission denied | user={identity.user_id} | code={code}"
        )
        raise PermissionDeniedError(
            f"Sem permissao para {code}",
            code=code,
            user_id=identity.user_id
        )

    logger.debug(f"Permission granted | user={identity.user_id} | code={code}")


def _validate_any_permission(
    identity: UserIdentity,
    codes: list[str],
    check_module: bool = True
) -> None:
    """Validate user has at least one of the permissions."""
    client = get_permissions_client()
    groups = _get_groups_from_identity(identity)
    user_permissions = client.get_user_permissions(identity.user_id, groups)

    if user_permissions is None:
        raise PermissionDeniedError(
            f"Sem permissao para nenhum dos codigos: {codes}",
            user_id=identity.user_id
        )

    # Module check (check first module in the list)
    if check_module and codes:
        module = codes[0].split("_")[0]
        if not client.can_access_module(user_permissions, module):
            raise ModuleAccessDeniedError(module, identity.user_id)

    if not client.has_any_permission(user_permissions, codes):
        raise PermissionDeniedError(
            f"Sem permissao para nenhum dos codigos: {codes}",
            user_id=identity.user_id
        )


def _validate_all_permissions(
    identity: UserIdentity,
    codes: list[str],
    check_module: bool = True
) -> None:
    """Validate user has all permissions."""
    client = get_permissions_client()
    groups = _get_groups_from_identity(identity)
    user_permissions = client.get_user_permissions(identity.user_id, groups)

    if user_permissions is None:
        raise PermissionDeniedError(
            f"Sem permissao para os codigos: {codes}",
            user_id=identity.user_id
        )

    # Module checks
    if check_module:
        modules = set(c.split("_")[0] for c in codes if "_" in c)
        for module in modules:
            if not client.can_access_module(user_permissions, module):
                raise ModuleAccessDeniedError(module, identity.user_id)

    if not client.has_all_permissions(user_permissions, codes):
        missing = set(codes) - user_permissions.permissions
        raise PermissionDeniedError(
            f"Faltam permissoes: {list(missing)}",
            user_id=identity.user_id
        )


def _validate_module_access(identity: UserIdentity, module: str) -> None:
    """Validate user can access module."""
    client = get_permissions_client()
    groups = _get_groups_from_identity(identity)
    user_permissions = client.get_user_permissions(identity.user_id, groups)

    if user_permissions is None or not client.can_access_module(user_permissions, module):
        raise ModuleAccessDeniedError(module, identity.user_id)


def _get_groups_from_identity(
    identity: UserIdentity,
    fallback: list[str] | None = None
) -> list[str]:
    """
    Extract Cognito groups from user identity.

    Args:
        identity: User identity
        fallback: Optional fallback groups

    Returns:
        List of group names
    """
    if identity.raw_claims:
        # Groups come from cognito:groups claim
        groups = identity.raw_claims.get("cognito:groups", [])
        if groups:
            return groups if isinstance(groups, list) else [groups]

    return fallback or []
