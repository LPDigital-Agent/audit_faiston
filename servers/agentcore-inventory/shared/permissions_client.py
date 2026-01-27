"""
DynamoDB Permissions Client for Faiston NEXO.

Provides access to modules, functionalities, profiles, and user permissions
stored in DynamoDB following the single-table design pattern.

Reference: docs/permissions/PRD-permissions-system.md
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Environment variable for table name
USERS_TABLE_NAME = os.environ.get("USERS_TABLE_NAME", "faiston-one-sga-sessions-prod")


@dataclass
class Module:
    """Represents a system module."""
    code: str
    name: str
    full_name: str | None = None
    description: str | None = None
    icon: str | None = None
    order: int = 0
    is_active: bool = True


@dataclass
class Functionality:
    """Represents a system functionality (permission)."""
    code: str
    name: str
    module: str
    description: str | None = None
    submodule: str | None = None
    operation: str = "READ"  # READ | CREATE | UPDATE | DELETE | EXECUTE
    route: str | None = None
    is_active: bool = True


@dataclass
class Profile:
    """Represents a permission profile."""
    id: str
    name: str
    description: str | None = None
    profile_type: str = "BASE"  # BASE | CUSTOM
    base_profile: str | None = None
    cognito_group: str | None = None
    permissions: list[str] | None = None
    denied_permissions: list[str] | None = None
    version: int = 1
    is_active: bool = True


@dataclass
class UserPermissions:
    """Represents resolved user permissions."""
    user_id: str
    profile_id: str
    profile_name: str
    base_profile: str
    permissions: set[str]
    version: int


class PermissionsClient:
    """
    Client for accessing permission data from DynamoDB.

    Uses single-table design with the following entity patterns:
    - MODULE#{code} / MODULE#{code}: Module definition
    - MODULE#{module} / FUNC#{code}: Functionality (nested in module)
    - PROFILE#{id} / PROFILE#{id}: Profile definition
    - USER#{id} / USER#{id}: User with profileId attribute
    """

    def __init__(self, table_name: str | None = None):
        """
        Initialize the permissions client.

        Args:
            table_name: DynamoDB table name (defaults to USERS_TABLE_NAME env var)
        """
        self.table_name = table_name or USERS_TABLE_NAME
        self._dynamodb = None
        self._table = None

    @property
    def dynamodb(self):
        """Lazy initialization of DynamoDB resource."""
        if self._dynamodb is None:
            self._dynamodb = boto3.resource("dynamodb")
        return self._dynamodb

    @property
    def table(self):
        """Lazy initialization of DynamoDB table."""
        if self._table is None:
            self._table = self.dynamodb.Table(self.table_name)
        return self._table

    # =========================================================================
    # Module Operations
    # =========================================================================

    def get_module(self, code: str) -> Module | None:
        """
        Get a module by code.

        Args:
            code: Module code (e.g., "EST", "EXP")

        Returns:
            Module or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    "PK": f"MODULE#{code}",
                    "SK": f"MODULE#{code}"
                }
            )
            item = response.get("Item")
            if item:
                return Module(
                    code=item.get("code", code),
                    name=item.get("name", ""),
                    full_name=item.get("fullName"),
                    description=item.get("description"),
                    icon=item.get("icon"),
                    order=item.get("order", 0),
                    is_active=item.get("isActive", True)
                )
            return None
        except ClientError as e:
            logger.error(f"Error getting module {code}: {e}")
            return None

    def list_modules(self) -> list[Module]:
        """
        List all active modules.

        Returns:
            List of modules sorted by order
        """
        try:
            response = self.table.query(
                IndexName="GSI1",
                KeyConditionExpression=Key("GSI1PK").eq("MODULES")
            )
            modules = []
            for item in response.get("Items", []):
                modules.append(Module(
                    code=item.get("code", ""),
                    name=item.get("name", ""),
                    full_name=item.get("fullName"),
                    description=item.get("description"),
                    icon=item.get("icon"),
                    order=item.get("order", 0),
                    is_active=item.get("isActive", True)
                ))
            return sorted(modules, key=lambda m: m.order)
        except ClientError as e:
            logger.error(f"Error listing modules: {e}")
            return []

    # =========================================================================
    # Functionality Operations
    # =========================================================================

    def get_functionality(self, code: str) -> Functionality | None:
        """
        Get a functionality by code.

        Args:
            code: Functionality code (e.g., "EST_R01")

        Returns:
            Functionality or None if not found
        """
        try:
            # Use GSI2 for direct lookup by code
            response = self.table.query(
                IndexName="GSI2",
                KeyConditionExpression=Key("GSI2PK").eq(f"FUNC#{code}")
            )
            items = response.get("Items", [])
            if items:
                item = items[0]
                return Functionality(
                    code=item.get("code", code),
                    name=item.get("name", ""),
                    module=item.get("module", ""),
                    description=item.get("description"),
                    submodule=item.get("submodule"),
                    operation=item.get("operation", "READ"),
                    route=item.get("route"),
                    is_active=item.get("isActive", True)
                )
            return None
        except ClientError as e:
            logger.error(f"Error getting functionality {code}: {e}")
            return None

    def list_functionalities(self, module_code: str | None = None) -> list[Functionality]:
        """
        List functionalities, optionally filtered by module.

        Args:
            module_code: Optional module code to filter by

        Returns:
            List of functionalities
        """
        try:
            if module_code:
                # Query by module
                response = self.table.query(
                    KeyConditionExpression=Key("PK").eq(f"MODULE#{module_code}") & Key("SK").begins_with("FUNC#")
                )
            else:
                # Query all functionalities
                response = self.table.query(
                    IndexName="GSI1",
                    KeyConditionExpression=Key("GSI1PK").eq("FUNCS")
                )

            functionalities = []
            for item in response.get("Items", []):
                functionalities.append(Functionality(
                    code=item.get("code", ""),
                    name=item.get("name", ""),
                    module=item.get("module", ""),
                    description=item.get("description"),
                    submodule=item.get("submodule"),
                    operation=item.get("operation", "READ"),
                    route=item.get("route"),
                    is_active=item.get("isActive", True)
                ))
            return functionalities
        except ClientError as e:
            logger.error(f"Error listing functionalities: {e}")
            return []

    # =========================================================================
    # Profile Operations
    # =========================================================================

    def get_profile(self, profile_id: str) -> Profile | None:
        """
        Get a profile by ID.

        Args:
            profile_id: Profile ID

        Returns:
            Profile or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    "PK": f"PROFILE#{profile_id}",
                    "SK": f"PROFILE#{profile_id}"
                }
            )
            item = response.get("Item")
            if item:
                return Profile(
                    id=item.get("id", profile_id),
                    name=item.get("name", ""),
                    description=item.get("description"),
                    profile_type=item.get("type", "BASE"),
                    base_profile=item.get("baseProfile"),
                    cognito_group=item.get("cognitoGroup"),
                    permissions=item.get("permissions", []),
                    denied_permissions=item.get("deniedPermissions", []),
                    version=item.get("version", 1),
                    is_active=item.get("isActive", True)
                )
            return None
        except ClientError as e:
            logger.error(f"Error getting profile {profile_id}: {e}")
            return None

    def list_profiles(self, base_profile: str | None = None) -> list[Profile]:
        """
        List profiles, optionally filtered by base profile.

        Args:
            base_profile: Optional base profile code to filter by

        Returns:
            List of profiles
        """
        try:
            if base_profile:
                # Query by base profile
                response = self.table.query(
                    IndexName="GSI2",
                    KeyConditionExpression=Key("GSI2PK").eq(f"BASE#{base_profile}")
                )
            else:
                # Query all profiles
                response = self.table.query(
                    IndexName="GSI1",
                    KeyConditionExpression=Key("GSI1PK").eq("PROFILES")
                )

            profiles = []
            for item in response.get("Items", []):
                profiles.append(Profile(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    description=item.get("description"),
                    profile_type=item.get("type", "BASE"),
                    base_profile=item.get("baseProfile"),
                    cognito_group=item.get("cognitoGroup"),
                    permissions=item.get("permissions", []),
                    denied_permissions=item.get("deniedPermissions", []),
                    version=item.get("version", 1),
                    is_active=item.get("isActive", True)
                ))
            return profiles
        except ClientError as e:
            logger.error(f"Error listing profiles: {e}")
            return []

    # =========================================================================
    # User Permission Operations
    # =========================================================================

    def get_user_profile_id(self, user_id: str) -> str | None:
        """
        Get the profile ID assigned to a user.

        Args:
            user_id: User ID (Cognito sub)

        Returns:
            Profile ID or None if not assigned
        """
        try:
            response = self.table.get_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"USER#{user_id}"
                },
                ProjectionExpression="profileId"
            )
            item = response.get("Item")
            return item.get("profileId") if item else None
        except ClientError as e:
            logger.error(f"Error getting user profile ID: {e}")
            return None

    def get_user_permissions(self, user_id: str, groups: list[str] | None = None) -> UserPermissions | None:
        """
        Get resolved permissions for a user.

        This method:
        1. Looks up the user's assigned profile
        2. Falls back to base profile from Cognito groups
        3. Resolves profile inheritance for custom profiles
        4. Returns the final set of permissions

        Args:
            user_id: User ID (Cognito sub)
            groups: Optional Cognito groups (for fallback)

        Returns:
            UserPermissions or None if unable to resolve
        """
        # Get user's assigned profile
        profile_id = self.get_user_profile_id(user_id)

        # Fallback to base profile from groups
        if not profile_id and groups:
            profile_id = self._get_base_profile_from_groups(groups)

        if not profile_id:
            logger.warning(f"No profile found for user {user_id}")
            return None

        # Get the profile
        profile = self.get_profile(profile_id)
        if not profile:
            logger.warning(f"Profile {profile_id} not found")
            return None

        # Resolve permissions
        permissions = set(profile.permissions or [])
        base_profile = profile_id

        # Handle custom profile inheritance
        if profile.profile_type == "CUSTOM" and profile.base_profile:
            base_profile = profile.base_profile
            base = self.get_profile(profile.base_profile)
            if base:
                # Start with base permissions
                permissions = set(base.permissions or [])
                # Remove denied permissions
                denied = set(profile.denied_permissions or [])
                permissions = permissions - denied

        return UserPermissions(
            user_id=user_id,
            profile_id=profile.id,
            profile_name=profile.name,
            base_profile=base_profile,
            permissions=permissions,
            version=profile.version
        )

    def _get_base_profile_from_groups(self, groups: list[str]) -> str | None:
        """
        Determine base profile from Cognito groups.

        Args:
            groups: List of Cognito group names

        Returns:
            Base profile ID or None
        """
        group_to_profile = {
            "Admins": "admin",
            "Logistica": "logistica",
            "Tecnicos": "tecnico",
            "Financeiro": "financeiro"
        }

        for group_name in ["Admins", "Logistica", "Tecnicos", "Financeiro"]:
            if group_name in groups:
                return group_to_profile[group_name]

        return None

    # =========================================================================
    # Permission Validation
    # =========================================================================

    def has_permission(self, user_permissions: UserPermissions, code: str) -> bool:
        """
        Check if user has a specific permission.

        Args:
            user_permissions: Resolved user permissions
            code: Permission code to check

        Returns:
            True if user has the permission
        """
        # Admin has all permissions
        if user_permissions.base_profile == "admin":
            return True

        return code in user_permissions.permissions

    def has_any_permission(self, user_permissions: UserPermissions, codes: list[str]) -> bool:
        """
        Check if user has any of the specified permissions.

        Args:
            user_permissions: Resolved user permissions
            codes: List of permission codes

        Returns:
            True if user has at least one permission
        """
        if user_permissions.base_profile == "admin":
            return True

        return bool(user_permissions.permissions.intersection(set(codes)))

    def has_all_permissions(self, user_permissions: UserPermissions, codes: list[str]) -> bool:
        """
        Check if user has all specified permissions.

        Args:
            user_permissions: Resolved user permissions
            codes: List of permission codes

        Returns:
            True if user has all permissions
        """
        if user_permissions.base_profile == "admin":
            return True

        return set(codes).issubset(user_permissions.permissions)

    def can_access_module(self, user_permissions: UserPermissions, module: str) -> bool:
        """
        Check if user can access a module.

        This is a quick check based on the base profile mapping.

        Args:
            user_permissions: Resolved user permissions
            module: Module code

        Returns:
            True if user can access the module
        """
        if user_permissions.base_profile == "admin":
            return True

        # Module access by base profile
        module_access = {
            "EST": ["admin", "logistica", "tecnico", "financeiro"],
            "MOV": ["admin", "logistica", "tecnico"],
            "EXP": ["admin", "logistica"],
            "REV": ["admin", "logistica"],
            "INV": ["admin", "logistica", "tecnico"],
            "CAD": ["admin", "logistica"],
            "TRANSP": ["admin", "logistica"],
            "DISP": ["admin", "logistica", "tecnico"],
            "ACAD": ["admin", "logistica", "tecnico", "financeiro"],
            "FISC": ["admin", "financeiro"],
            "AUTH": ["admin", "logistica", "tecnico", "financeiro"],
            "INTRA": ["admin", "logistica", "tecnico", "financeiro"],
            "NEXO": ["admin", "logistica", "tecnico", "financeiro"],
        }

        allowed = module_access.get(module, ["admin"])
        return user_permissions.base_profile in allowed


# Singleton instance
_client: PermissionsClient | None = None


def get_permissions_client() -> PermissionsClient:
    """
    Get the singleton permissions client instance.

    Returns:
        PermissionsClient instance
    """
    global _client
    if _client is None:
        _client = PermissionsClient()
    return _client
