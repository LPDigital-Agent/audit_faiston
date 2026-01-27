"""
Permission Utilities for Faiston NEXO.

Provides utility functions for permission validation, hash calculation,
and permission-related operations.

Reference: docs/permissions/PRD-permissions-system.md
"""

import hashlib
import json
import logging
from typing import Any

from shared.identity_utils import UserIdentity
from shared.permissions_client import (
    PermissionsClient,
    UserPermissions,
    get_permissions_client,
)

logger = logging.getLogger(__name__)


def calculate_permissions_hash(permissions: list[str] | set[str]) -> str:
    """
    Calculate SHA-256 hash of permissions for integrity validation.

    This hash is included in the JWT token and can be used by the frontend
    to validate that permissions haven't been tampered with.

    Args:
        permissions: List or set of permission codes

    Returns:
        Truncated (16 char) SHA-256 hash
    """
    if not permissions:
        return ""

    # Convert to sorted list for consistent hashing
    sorted_permissions = sorted(list(permissions))
    permissions_json = json.dumps(sorted_permissions, sort_keys=True)

    # Calculate SHA-256 and truncate
    hash_full = hashlib.sha256(permissions_json.encode()).hexdigest()
    return hash_full[:16]


def validate_permissions_hash(
    permissions: list[str] | set[str],
    expected_hash: str
) -> bool:
    """
    Validate permissions against expected hash.

    Args:
        permissions: List of permission codes
        expected_hash: Expected hash from JWT token

    Returns:
        True if hash matches
    """
    if not expected_hash:
        return True  # No hash to validate

    calculated = calculate_permissions_hash(permissions)
    return calculated == expected_hash


def get_permissions_response(
    identity: UserIdentity,
    groups: list[str] | None = None
) -> dict[str, Any]:
    """
    Get permissions response for API endpoint.

    This function returns the data needed by the frontend to
    initialize the permissions context.

    Args:
        identity: User identity from context
        groups: Optional Cognito groups

    Returns:
        Dict with profile and permissions data
    """
    client = get_permissions_client()
    user_permissions = client.get_user_permissions(identity.user_id, groups)

    if user_permissions is None:
        return {
            "profileId": None,
            "profileName": None,
            "baseProfile": None,
            "permissions": [],
            "version": 0,
            "hash": ""
        }

    permissions_list = sorted(list(user_permissions.permissions))
    permissions_hash = calculate_permissions_hash(permissions_list)

    return {
        "profileId": user_permissions.profile_id,
        "profileName": user_permissions.profile_name,
        "baseProfile": user_permissions.base_profile,
        "permissions": permissions_list,
        "version": user_permissions.version,
        "hash": permissions_hash
    }


def get_modules_with_access(
    user_permissions: UserPermissions | None
) -> list[dict[str, Any]]:
    """
    Get list of modules the user can access.

    Args:
        user_permissions: Resolved user permissions

    Returns:
        List of module dicts with code, name, and access status
    """
    client = get_permissions_client()
    modules = client.list_modules()

    result = []
    for module in modules:
        has_access = (
            user_permissions is not None
            and client.can_access_module(user_permissions, module.code)
        )
        result.append({
            "code": module.code,
            "name": module.name,
            "fullName": module.full_name,
            "icon": module.icon,
            "order": module.order,
            "hasAccess": has_access
        })

    return result


def get_functionalities_for_user(
    user_permissions: UserPermissions | None,
    module_code: str | None = None
) -> list[dict[str, Any]]:
    """
    Get functionalities available to the user.

    Args:
        user_permissions: Resolved user permissions
        module_code: Optional module filter

    Returns:
        List of functionality dicts with permission status
    """
    client = get_permissions_client()
    functionalities = client.list_functionalities(module_code)

    result = []
    for func in functionalities:
        has_permission = (
            user_permissions is not None
            and client.has_permission(user_permissions, func.code)
        )
        result.append({
            "code": func.code,
            "name": func.name,
            "module": func.module,
            "submodule": func.submodule,
            "operation": func.operation,
            "route": func.route,
            "hasPermission": has_permission
        })

    return result


def check_route_permission(
    user_permissions: UserPermissions | None,
    route: str
) -> bool:
    """
    Check if user can access a specific route.

    Args:
        user_permissions: Resolved user permissions
        route: Route path to check

    Returns:
        True if user can access the route
    """
    if user_permissions is None:
        return False

    # Admin has access to all routes
    if user_permissions.base_profile == "admin":
        return True

    # Route to permission mapping
    # This should be kept in sync with frontend ROUTE_PERMISSIONS
    route_permissions = {
        "/ferramentas/ativos/dashboard": "EST_R01",
        "/ferramentas/ativos/estoque": "EST_R02",
        "/ferramentas/ativos/estoque/entrada": "EST_R02",
        "/ferramentas/ativos/estoque/saida": "EST_R02",
        "/ferramentas/ativos/movimentacoes": "MOV_R01",
        "/estoque/movimentacoes/entrada": "MOV_C01",
        "/estoque/movimentacoes/saida": "MOV_C02",
        "/estoque/movimentacoes/transferencia": "MOV_C03",
        "/expedicao": "EXP_R01",
        "/expedicao/nova": "EXP_C01",
        "/reversa": "REV_R01",
        "/reversa/nova": "REV_C01",
        "/inventario": "INV_R01",
        "/inventario/novo": "INV_C01",
        "/cadastros": "CAD_R01",
        "/transportadoras": "TRANSP_R01",
        "/fiscal": "FISC_R01",
        "/academy": "ACAD_R01",
        "/admin/usuarios": "ADMIN_U01",
        "/admin/perfis": "ADMIN_P01",
    }

    # Check exact match first
    required_code = route_permissions.get(route)
    if required_code:
        return required_code in user_permissions.permissions

    # Check prefix matches for dynamic routes
    for route_pattern, code in route_permissions.items():
        if route.startswith(route_pattern):
            return code in user_permissions.permissions

    # Default: allow if no specific permission required
    return True


def enrich_identity_with_permissions(
    identity: UserIdentity,
    groups: list[str] | None = None
) -> dict[str, Any]:
    """
    Enrich user identity with permission information.

    Useful for logging and audit purposes.

    Args:
        identity: User identity
        groups: Optional Cognito groups

    Returns:
        Dict with identity and permission summary
    """
    client = get_permissions_client()
    user_permissions = client.get_user_permissions(identity.user_id, groups)

    return {
        "userId": identity.user_id,
        "email": identity.email,
        "name": identity.name,
        "source": identity.source,
        "isSecure": identity.is_secure(),
        "profile": {
            "id": user_permissions.profile_id if user_permissions else None,
            "name": user_permissions.profile_name if user_permissions else None,
            "base": user_permissions.base_profile if user_permissions else None,
            "version": user_permissions.version if user_permissions else 0,
            "permissionCount": len(user_permissions.permissions) if user_permissions else 0
        } if user_permissions else None
    }
