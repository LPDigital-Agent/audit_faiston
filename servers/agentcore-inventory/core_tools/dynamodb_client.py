# =============================================================================
# DynamoDB Client for SGA Inventory
# =============================================================================
# Client for all DynamoDB operations in the inventory management module.
#
# Features:
# - Single-table design with PK/SK pattern
# - GSI queries for common access patterns
# - Atomic balance updates
# - Batch operations for efficiency
# - Audit trail integration
#
# CRITICAL: Lazy imports for cold start optimization (<30s limit)
# =============================================================================

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import os

from shared.debug_utils import debug_error
from shared.env_config import get_required_env

logger = logging.getLogger(__name__)

# Lazy imports - boto3 imported only when needed
_dynamodb_resource = None
_dynamodb_client = None


def _get_dynamodb_resource():
    """
    Get DynamoDB resource with lazy initialization.

    Returns:
        boto3 DynamoDB resource
    """
    global _dynamodb_resource
    if _dynamodb_resource is None:
        import boto3
        # Explicitly set region to ensure consistency across all environments
        _dynamodb_resource = boto3.resource("dynamodb", region_name="us-east-2")
    return _dynamodb_resource


def _get_dynamodb_client():
    """
    Get DynamoDB client with lazy initialization.

    Returns:
        boto3 DynamoDB client
    """
    global _dynamodb_client
    if _dynamodb_client is None:
        import boto3
        # Explicitly set region to ensure consistency across all environments
        _dynamodb_client = boto3.client("dynamodb", region_name="us-east-2")
    return _dynamodb_client


# =============================================================================
# Table Names from Environment
# =============================================================================

def _get_inventory_table() -> str:
    """Get inventory table name from environment (FAIL-CLOSED)."""
    return get_required_env("INVENTORY_TABLE", "DynamoDB inventory access")


def _get_hil_table() -> str:
    """Get HIL tasks table name from environment (FAIL-CLOSED)."""
    return get_required_env("HIL_TASKS_TABLE", "DynamoDB HIL tasks")


def _get_audit_table() -> str:
    """Get audit log table name from environment (FAIL-CLOSED)."""
    return get_required_env("AUDIT_LOG_TABLE", "DynamoDB audit log")


def _get_sessions_table() -> str:
    """Get sessions table name from environment (FAIL-CLOSED)."""
    return get_required_env("SESSIONS_TABLE", "DynamoDB sessions")


# =============================================================================
# Decimal Conversion for JSON Serialization (LOW-001 FIX)
# =============================================================================

def _convert_decimals_to_numbers(obj: Any) -> Any:
    """
    Recursively convert Decimal values to int/float for JSON serialization.

    DynamoDB returns numeric values as Python Decimal objects, which are NOT
    JSON-serializable by default. This function converts:
    - Decimal with no fractional part → int (e.g., Decimal('5') → 5)
    - Decimal with fractional part → float (e.g., Decimal('5.5') → 5.5)

    Args:
        obj: Any Python object (dict, list, Decimal, or other)

    Returns:
        Same structure with Decimals converted to int/float
    """
    # Lazy import to avoid import at module load time
    from decimal import Decimal

    if isinstance(obj, Decimal):
        # Convert to int if no fractional part, else float
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimals_to_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals_to_numbers(i) for i in obj]
    return obj


# =============================================================================
# DynamoDB Client Class
# =============================================================================


class SGADynamoDBClient:
    """
    DynamoDB client for SGA Inventory operations.

    Implements single-table design with GSI queries for:
    - Asset management (CRUD)
    - Movement tracking (event sourcing)
    - Balance calculations (projections)
    - HIL task management
    - Audit logging

    Example:
        client = SGADynamoDBClient()
        asset = client.get_asset_by_serial("SN123456")
    """

    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize the DynamoDB client.

        Args:
            table_name: Override table name (for testing)
        """
        self._table_name = table_name or _get_inventory_table()
        self._table = None

    @property
    def table(self):
        """Lazy-load DynamoDB table resource."""
        if self._table is None:
            self._table = _get_dynamodb_resource().Table(self._table_name)
        return self._table

    # =========================================================================
    # Basic CRUD Operations
    # =========================================================================

    def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """
        Get a single item by primary key.

        Args:
            pk: Partition key value
            sk: Sort key value

        Returns:
            Item dict if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={"PK": pk, "SK": sk}
            )
            item = response.get("Item")
            # LOW-001 FIX: Convert Decimal to int/float for JSON serialization
            return _convert_decimals_to_numbers(item) if item else None
        except Exception as e:
            debug_error(e, "dynamodb_get_item", {"pk": pk, "sk": sk})
            return None

    def put_item(self, item: Dict[str, Any]) -> bool:
        """
        Create or update an item.

        Args:
            item: Item dict with PK and SK

        Returns:
            True if successful
        """
        try:
            # Add timestamps
            now = datetime.utcnow().isoformat() + "Z"
            if "created_at" not in item:
                item["created_at"] = now
            item["updated_at"] = now

            self.table.put_item(Item=item)
            return True
        except Exception as e:
            debug_error(e, "dynamodb_put_item", {"item_pk": item.get("PK")})
            return False

    def delete_item(self, pk: str, sk: str) -> bool:
        """
        Delete an item by primary key.

        Args:
            pk: Partition key value
            sk: Sort key value

        Returns:
            True if successful
        """
        try:
            self.table.delete_item(
                Key={"PK": pk, "SK": sk}
            )
            return True
        except Exception as e:
            debug_error(e, "dynamodb_delete_item", {"pk": pk, "sk": sk})
            return False

    def update_item(
        self,
        pk: str,
        sk: str,
        updates: Dict[str, Any],
        conditions: Optional[str] = None,
    ) -> bool:
        """
        Update specific attributes of an item.

        Args:
            pk: Partition key value
            sk: Sort key value
            updates: Dict of attribute_name -> new_value
            conditions: Optional condition expression

        Returns:
            True if successful
        """
        try:
            # Build update expression
            update_parts = []
            expr_names = {}
            expr_values = {}

            for i, (key, value) in enumerate(updates.items()):
                attr_name = f"#attr{i}"
                attr_value = f":val{i}"
                update_parts.append(f"{attr_name} = {attr_value}")
                expr_names[attr_name] = key
                expr_values[attr_value] = value

            # Add updated_at
            update_parts.append("#updated = :updated")
            expr_names["#updated"] = "updated_at"
            expr_values[":updated"] = datetime.utcnow().isoformat() + "Z"

            update_expr = "SET " + ", ".join(update_parts)

            params = {
                "Key": {"PK": pk, "SK": sk},
                "UpdateExpression": update_expr,
                "ExpressionAttributeNames": expr_names,
                "ExpressionAttributeValues": expr_values,
            }

            if conditions:
                params["ConditionExpression"] = conditions

            self.table.update_item(**params)
            return True
        except Exception as e:
            debug_error(e, "dynamodb_update_item", {"pk": pk, "sk": sk, "updates": list(updates.keys())})
            return False

    # =========================================================================
    # Query Operations
    # =========================================================================

    def query_pk(
        self,
        pk: str,
        sk_prefix: Optional[str] = None,
        limit: int = 100,
        scan_forward: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Query items by partition key with optional SK prefix.

        Args:
            pk: Partition key value
            sk_prefix: Optional sort key prefix filter
            limit: Maximum items to return
            scan_forward: True for ascending, False for descending

        Returns:
            List of items
        """
        try:
            params = {
                "KeyConditionExpression": "PK = :pk",
                "ExpressionAttributeValues": {":pk": pk},
                "Limit": limit,
                "ScanIndexForward": scan_forward,
            }

            if sk_prefix:
                params["KeyConditionExpression"] += " AND begins_with(SK, :sk)"
                params["ExpressionAttributeValues"][":sk"] = sk_prefix

            response = self.table.query(**params)
            items = response.get("Items", [])
            # LOW-001 FIX: Convert Decimal to int/float for JSON serialization
            return [_convert_decimals_to_numbers(item) for item in items]
        except Exception as e:
            debug_error(e, "dynamodb_query_pk", {"pk": pk, "sk_prefix": sk_prefix})
            return []

    def query_gsi(
        self,
        gsi_name: str,
        pk_value: str,
        sk_prefix: Optional[str] = None,
        limit: int = 100,
        scan_forward: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Query items using a Global Secondary Index.

        Args:
            gsi_name: Name of the GSI (e.g., "GSI1-SerialLookup")
            pk_value: GSI partition key value
            sk_prefix: Optional GSI sort key prefix
            limit: Maximum items to return
            scan_forward: True for ascending, False for descending

        Returns:
            List of items
        """
        try:
            # Determine GSI key names based on index name
            gsi_num = gsi_name.split("-")[0].replace("GSI", "")
            pk_name = f"GSI{gsi_num}PK"
            sk_name = f"GSI{gsi_num}SK"

            params = {
                "IndexName": gsi_name,
                "KeyConditionExpression": f"{pk_name} = :pk",
                "ExpressionAttributeValues": {":pk": pk_value},
                "Limit": limit,
                "ScanIndexForward": scan_forward,
            }

            if sk_prefix:
                params["KeyConditionExpression"] += f" AND begins_with({sk_name}, :sk)"
                params["ExpressionAttributeValues"][":sk"] = sk_prefix

            response = self.table.query(**params)
            items = response.get("Items", [])
            # LOW-001 FIX: Convert Decimal to int/float for JSON serialization
            return [_convert_decimals_to_numbers(item) for item in items]
        except Exception as e:
            debug_error(e, "dynamodb_query_gsi", {"gsi_name": gsi_name, "pk_value": pk_value})
            return []

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def batch_get(self, keys: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Batch get multiple items.

        Args:
            keys: List of {"PK": pk, "SK": sk} dicts

        Returns:
            List of found items
        """
        if not keys:
            return []

        try:
            # DynamoDB limit: 100 items per batch
            all_items = []
            for i in range(0, len(keys), 100):
                batch = keys[i:i+100]
                response = _get_dynamodb_resource().batch_get_item(
                    RequestItems={
                        self._table_name: {
                            "Keys": batch
                        }
                    }
                )
                items = response.get("Responses", {}).get(self._table_name, [])
                all_items.extend(items)

            return all_items
        except Exception as e:
            debug_error(e, "dynamodb_batch_get", {"key_count": len(keys)})
            return []

    def batch_write(self, items: List[Dict[str, Any]]) -> bool:
        """
        Batch write multiple items.

        Args:
            items: List of items to write (each must have PK and SK)

        Returns:
            True if all successful
        """
        if not items:
            return True

        try:
            now = datetime.utcnow().isoformat() + "Z"

            # DynamoDB limit: 25 items per batch
            for i in range(0, len(items), 25):
                batch = items[i:i+25]
                request_items = []

                for item in batch:
                    if "created_at" not in item:
                        item["created_at"] = now
                    item["updated_at"] = now
                    request_items.append({"PutRequest": {"Item": item}})

                _get_dynamodb_resource().batch_write_item(
                    RequestItems={self._table_name: request_items}
                )

            return True
        except Exception as e:
            debug_error(e, "dynamodb_batch_write", {"item_count": len(items)})
            return False

    # =========================================================================
    # Asset Operations
    # =========================================================================

    def get_asset_by_serial(self, serial: str) -> Optional[Dict[str, Any]]:
        """
        Find asset by serial number using GSI1.

        Args:
            serial: Serial number to search

        Returns:
            Asset item if found
        """
        items = self.query_gsi(
            gsi_name="GSI1-SerialLookup",
            pk_value=f"SERIAL#{serial}",
            limit=1
        )
        return items[0] if items else None

    def get_assets_by_location(
        self,
        location_id: str,
        entity_type: str = "ASSET",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get assets or balances at a location using GSI2.

        Args:
            location_id: Location identifier
            entity_type: Filter by entity type (ASSET, BALANCE)
            limit: Maximum items

        Returns:
            List of items
        """
        return self.query_gsi(
            gsi_name="GSI2-LocationQuery",
            pk_value=f"LOC#{location_id}",
            sk_prefix=f"{entity_type}#" if entity_type else None,
            limit=limit
        )

    def get_assets_by_project(
        self,
        project_id: str,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get assets or movements for a project using GSI3.

        Args:
            project_id: Project identifier
            entity_type: Optional filter (ASSET, MOVE)
            limit: Maximum items

        Returns:
            List of items
        """
        return self.query_gsi(
            gsi_name="GSI3-ProjectQuery",
            pk_value=f"PROJ#{project_id}",
            sk_prefix=f"{entity_type}#" if entity_type else None,
            limit=limit
        )

    def get_asset_timeline(
        self,
        asset_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get complete timeline of an asset using GSI6.

        Args:
            asset_id: Asset identifier
            limit: Maximum events

        Returns:
            List of timeline events (newest first)
        """
        return self.query_gsi(
            gsi_name="GSI6-AssetTimeline",
            pk_value=f"TIMELINE#{asset_id}",
            limit=limit,
            scan_forward=False  # Newest first
        )

    # =========================================================================
    # Balance Operations
    # =========================================================================

    def get_balance(
        self,
        location_id: str,
        pn_id: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get balance for a part number at a location.

        Args:
            location_id: Location identifier
            pn_id: Part number identifier
            project_id: Optional project filter

        Returns:
            Balance dict with total, available, reserved.
            CRITICAL: Return found: False for missing items - returns `found: False`
            when item doesn't exist instead of zeros. This allows callers to
            distinguish between "no data" and "zero quantity" - preventing silent data loss.
        """
        pk = f"BALANCE#{location_id}#{pn_id}"
        sk = f"PROJ#{project_id}" if project_id else "METADATA"

        item = self.get_item(pk, sk)

        if item:
            return {
                "found": True,
                "total": item.get("total", 0),
                "available": item.get("available", 0),
                "reserved": item.get("reserved", 0),
                "location_id": location_id,
                "pn_id": pn_id,
                "project_id": project_id,
            }

        # Return found: False for missing items - return found=False instead of zeros!
        # Returning zeros on "not found" is DANGEROUS - it's indistinguishable
        # from "item exists with zero stock", causing silent data corruption.
        logger.debug(
            "[get_balance] Item not found: location=%s, pn=%s, project=%s",
            location_id, pn_id, project_id
        )
        return {
            "found": False,
            "total": None,
            "available": None,
            "reserved": None,
            "location_id": location_id,
            "pn_id": pn_id,
            "project_id": project_id,
            "message": "Balance record not found",
        }

    def update_balance(
        self,
        location_id: str,
        pn_id: str,
        delta: int,
        project_id: Optional[str] = None,
        is_reservation: bool = False,
    ) -> bool:
        """
        Atomically update balance for a part number.

        Args:
            location_id: Location identifier
            pn_id: Part number identifier
            delta: Change in quantity (positive or negative)
            project_id: Optional project
            is_reservation: If True, updates reserved instead of total

        Returns:
            True if successful
        """
        pk = f"BALANCE#{location_id}#{pn_id}"
        sk = f"PROJ#{project_id}" if project_id else "METADATA"

        try:
            if is_reservation:
                # Update reserved quantity
                self.table.update_item(
                    Key={"PK": pk, "SK": sk},
                    UpdateExpression="""
                        SET reserved = if_not_exists(reserved, :zero) + :delta,
                            available = if_not_exists(available, :zero) - :delta,
                            updated_at = :now
                    """,
                    ExpressionAttributeValues={
                        ":delta": delta,
                        ":zero": 0,
                        ":now": datetime.utcnow().isoformat() + "Z",
                    },
                )
            else:
                # Update total and available
                self.table.update_item(
                    Key={"PK": pk, "SK": sk},
                    UpdateExpression="""
                        SET total = if_not_exists(total, :zero) + :delta,
                            available = if_not_exists(available, :zero) + :delta,
                            updated_at = :now
                    """,
                    ExpressionAttributeValues={
                        ":delta": delta,
                        ":zero": 0,
                        ":now": datetime.utcnow().isoformat() + "Z",
                    },
                )
            return True
        except Exception as e:
            debug_error(e, "dynamodb_update_balance", {"location_id": location_id, "pn_id": pn_id, "delta": delta})
            return False

    # =========================================================================
    # Movement Operations
    # =========================================================================

    def create_movement(
        self,
        movement_id: str,
        movement_type: str,
        location_id: str,
        pn_id: str,
        quantity: int,
        project_id: Optional[str] = None,
        asset_ids: Optional[List[str]] = None,
        reference_id: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: str = "system",
    ) -> bool:
        """
        Create an inventory movement record.

        Movements are IMMUTABLE (event sourcing pattern).

        Args:
            movement_id: Unique movement identifier
            movement_type: Type (ENTRY, EXIT, TRANSFER, etc.)
            location_id: Source or destination location
            pn_id: Part number
            quantity: Quantity moved
            project_id: Related project
            asset_ids: List of serialized asset IDs
            reference_id: Reference (NF number, ticket ID)
            notes: Additional notes
            user_id: User who created the movement

        Returns:
            True if successful
        """
        now = datetime.utcnow()
        iso_now = now.isoformat() + "Z"
        month = now.strftime("%Y-%m")

        item = {
            "PK": f"MOVE#{movement_id}",
            "SK": "METADATA",
            "movement_id": movement_id,
            "movement_type": movement_type,
            "location_id": location_id,
            "pn_id": pn_id,
            "quantity": quantity,
            "created_at": iso_now,
            "created_by": user_id,
            # GSI keys
            "GSI3PK": f"PROJ#{project_id}" if project_id else "PROJ#_NONE",
            "GSI3SK": f"MOVE#{iso_now}#{movement_id}",
            "GSI5PK": f"DATE#{month}",
            "GSI5SK": f"{iso_now}#{movement_id}",
        }

        if project_id:
            item["project_id"] = project_id
        if asset_ids:
            item["asset_ids"] = asset_ids
        if reference_id:
            item["reference_id"] = reference_id
        if notes:
            item["notes"] = notes

        return self.put_item(item)

    def get_movements_by_date(
        self,
        year_month: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get movements for a specific month using GSI5.

        Args:
            year_month: Month in YYYY-MM format
            limit: Maximum items

        Returns:
            List of movements
        """
        return self.query_gsi(
            gsi_name="GSI5-DateQuery",
            pk_value=f"DATE#{year_month}",
            limit=limit,
            scan_forward=False  # Newest first
        )

    # =========================================================================
    # HIL Task Operations
    # =========================================================================

    def get_pending_tasks(
        self,
        assignee_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get pending HIL tasks using GSI4 or GSI1.

        Args:
            assignee_id: Optional filter by assignee
            limit: Maximum tasks

        Returns:
            List of pending tasks
        """
        hil_client = SGADynamoDBClient(table_name=_get_hil_table())

        if assignee_id:
            return hil_client.query_gsi(
                gsi_name="GSI1-AssigneeQuery",
                pk_value=f"ASSIGNEE#{assignee_id}",
                sk_prefix="PENDING#",
                limit=limit
            )
        else:
            return hil_client.query_gsi(
                gsi_name="GSI2",
                pk_value="STATUS#PENDING",
                limit=limit,
                scan_forward=False  # Most recent first
            )

    def create_hil_task(
        self,
        task_id: str,
        task_type: str,
        title: str,
        description: str,
        reference_entity: str,
        reference_id: str,
        priority: str = "normal",
        assignee_id: Optional[str] = None,
        created_by: str = "system",
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a new HIL task in the HIL table.

        Args:
            task_id: Unique task identifier
            task_type: Type of approval needed
            title: Task title
            description: Detailed description
            reference_entity: Entity type (ASSET, MOVEMENT, etc.)
            reference_id: ID of referenced entity
            priority: Task priority (low, normal, high, urgent)
            assignee_id: Optional assignee user ID
            created_by: User/agent who created the task
            payload: Additional data for the task

        Returns:
            True if successful
        """
        hil_client = SGADynamoDBClient(table_name=_get_hil_table())

        now = datetime.utcnow()
        iso_now = now.isoformat() + "Z"

        item = {
            "PK": f"TASK#{task_id}",
            "SK": "METADATA",
            "task_id": task_id,
            "task_type": task_type,
            "title": title,
            "description": description,
            "status": "PENDING",
            "priority": priority,
            "reference_entity": reference_entity,
            "reference_id": reference_id,
            "created_at": iso_now,
            "created_by": created_by,
            # GSI keys
            "GSI2PK": "STATUS#PENDING",
            "GSI2SK": f"{priority}#{iso_now}#{task_id}",
            "GSI3PK": f"TYPE#{task_type}",
            "GSI3SK": f"PENDING#{iso_now}#{task_id}",
            "GSI4PK": f"REF#{reference_entity}#{reference_id}",
            "GSI4SK": f"{iso_now}#{task_id}",
        }

        if assignee_id:
            item["assignee_id"] = assignee_id
            item["GSI1PK"] = f"ASSIGNEE#{assignee_id}"
            item["GSI1SK"] = f"PENDING#{iso_now}#{task_id}"

        if payload:
            item["payload"] = payload

        return hil_client.put_item(item)

    # =========================================================================
    # Part Number Lookup Operations (PN Matching)
    # =========================================================================

    def query_pn_by_supplier_code(
        self,
        supplier_code: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find part number by supplier code.

        Uses table Scan with filter on supplier_code attribute.
        For production scale, consider adding a dedicated GSI.

        Args:
            supplier_code: Supplier's internal part code

        Returns:
            Part number item if found, None otherwise
        """
        try:
            # Scan with filter for supplier_code attribute
            # Part numbers have PK starting with "PN#"
            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND supplier_code = :code",
                ExpressionAttributeValues={
                    ":pk_prefix": "PN#",
                    ":code": supplier_code,
                },
                Limit=1,
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except Exception as e:
            debug_error(e, "dynamodb_query_pn_by_supplier_code", {"supplier_code": supplier_code})
            return None

    def search_pn_by_keywords(
        self,
        keywords: List[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search part numbers by description keywords.

        Returns candidate PNs whose description contains any of the keywords.
        Results are then ranked by an AI model for best match.

        Args:
            keywords: List of keywords to search for
            limit: Maximum candidates to return

        Returns:
            List of candidate part numbers
        """
        if not keywords:
            return []

        try:
            # Build filter expression for keyword matching
            # Using CONTAINS for each keyword with OR logic
            filter_parts = []
            expr_names = {"#desc": "description"}
            expr_values = {":pk_prefix": "PN#"}

            for i, keyword in enumerate(keywords[:5]):  # Limit to 5 keywords
                kw = keyword.upper().strip()
                if len(kw) >= 3:  # Only use meaningful keywords
                    filter_parts.append(f"contains(#desc, :kw{i})")
                    expr_values[f":kw{i}"] = kw

            if not filter_parts:
                return []

            # Scan for part numbers matching any keyword
            filter_expr = (
                "begins_with(PK, :pk_prefix) AND (" +
                " OR ".join(filter_parts) + ")"
            )

            response = self.table.scan(
                FilterExpression=filter_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                Limit=limit,
            )

            items = response.get("Items", [])
            # LOW-001 FIX: Convert Decimal to int/float for JSON serialization
            return [_convert_decimals_to_numbers(item) for item in items]
        except Exception as e:
            debug_error(e, "dynamodb_search_pn_by_keywords", {"keywords": keywords})
            return []

    def query_pn_by_ncm(
        self,
        ncm_code: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find part numbers by NCM (Nomenclatura Comum do Mercosul) code.

        NCM is an 8-digit fiscal classification code. We match by prefix
        to find items in the same category:
        - 4 digits: Same chapter/heading
        - 6 digits: Same subheading
        - 8 digits: Exact match

        Args:
            ncm_code: NCM code (4-8 digits)
            limit: Maximum items to return

        Returns:
            List of matching part numbers
        """
        if not ncm_code or len(ncm_code) < 4:
            return []

        try:
            # Use first 4-6 digits for category matching
            ncm_prefix = ncm_code[:6].replace(".", "")

            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND begins_with(ncm, :ncm_prefix)",
                ExpressionAttributeValues={
                    ":pk_prefix": "PN#",
                    ":ncm_prefix": ncm_prefix,
                },
                Limit=limit,
            )

            items = response.get("Items", [])
            # LOW-001 FIX: Convert Decimal to int/float for JSON serialization
            return [_convert_decimals_to_numbers(item) for item in items]
        except Exception as e:
            debug_error(e, "dynamodb_query_pn_by_ncm", {"ncm_code": ncm_code})
            return []

    def get_all_part_numbers(
        self,
        limit: int = 100,
        last_key: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Get all part numbers with pagination.

        Useful for building search indexes or bulk operations.

        Args:
            limit: Maximum items per page
            last_key: Last evaluated key for pagination

        Returns:
            Tuple of (items, next_last_key)
        """
        try:
            params = {
                "FilterExpression": "begins_with(PK, :pk_prefix)",
                "ExpressionAttributeValues": {":pk_prefix": "PN#"},
                "Limit": limit,
            }

            if last_key:
                params["ExclusiveStartKey"] = last_key

            response = self.table.scan(**params)

            items = response.get("Items", [])
            next_key = response.get("LastEvaluatedKey")

            return items, next_key
        except Exception as e:
            debug_error(e, "dynamodb_get_all_part_numbers", {"limit": limit})
            return [], None


# =============================================================================
# Audit Logger
# =============================================================================


class SGAAuditLogger:
    """
    Audit logger for SGA Inventory operations.

    All entries are APPEND-ONLY (immutable).
    """

    def __init__(self):
        """Initialize the audit logger."""
        self._client = SGADynamoDBClient(table_name=_get_audit_table())

    def log_event(
        self,
        event_type: str,
        actor_type: str,
        actor_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Log an audit event.

        Args:
            event_type: Type of event (MOVEMENT_CREATE, ASSET_UPDATE, etc.)
            actor_type: Actor type (USER, AGENT, SYSTEM)
            actor_id: Actor identifier
            entity_type: Entity type affected
            entity_id: Entity identifier
            action: Action performed
            details: Additional safe-to-log details
            session_id: Optional session identifier

        Returns:
            True if successful
        """
        now = datetime.utcnow()
        iso_now = now.isoformat() + "Z"
        date_key = now.strftime("%Y-%m-%d")

        import uuid
        event_id = str(uuid.uuid4())[:12]

        item = {
            "PK": f"LOG#{date_key}",
            "SK": f"{iso_now}#{event_id}",
            "event_id": event_id,
            "event_type": event_type,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "timestamp": iso_now,
            # GSI keys
            "GSI1PK": f"ACTOR#{actor_type}#{actor_id}",
            "GSI1SK": f"{iso_now}#{event_id}",
            "GSI2PK": f"ENTITY#{entity_type}#{entity_id}",
            "GSI2SK": f"{iso_now}#{event_id}",
            "GSI3PK": f"TYPE#{event_type}",
            "GSI3SK": f"{iso_now}#{event_id}",
        }

        if details:
            # Filter sensitive data
            safe_details = {k: v for k, v in details.items()
                          if not any(s in k.lower() for s in ["password", "secret", "token", "key"])}
            if safe_details:
                item["details"] = safe_details

        if session_id:
            item["session_id"] = session_id
            item["GSI4PK"] = f"SESSION#{session_id}"
            item["GSI4SK"] = f"{iso_now}#{event_id}"

        return self._client.put_item(item)

    def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: str,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Convenience wrapper for log_event.
        Maps simplified parameters to full log_event signature.

        Args:
            action: Action performed (e.g., NF_ENTRY_CONFIRMED, VIOLATION_FLAGGED)
            entity_type: Entity type affected (e.g., NF_ENTRY, CAMPAIGN)
            entity_id: Entity identifier
            actor: Actor identifier (user who performed the action)
            details: Additional safe-to-log details
            session_id: Optional session identifier

        Returns:
            True if successful
        """
        # Infer event_type from action (e.g., NF_ENTRY_CONFIRMED -> INVENTORY_NF_ENTRY_CONFIRMED)
        event_type = f"INVENTORY_{action}"

        return self.log_event(
            event_type=event_type,
            actor_type="USER",  # Default to USER, can be overridden
            actor_id=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details=details,
            session_id=session_id,
        )


# =============================================================================
# Session Manager
# =============================================================================


class SGASessionManager:
    """
    Session manager for SGA Inventory agent sessions.

    Manages session persistence in DynamoDB with:
    - Session creation and updates
    - Turn counting
    - TTL-based expiration (30 days)
    - GSI queries for agent type and status filtering

    Example:
        manager = SGASessionManager()
        manager.ensure_session_exists("user123", "session456", "query_inventory")
        session = manager.get_session("user123", "session456")
    """

    def __init__(self):
        """Initialize the session manager."""
        self._table_name = _get_sessions_table()
        self._table = None

    @property
    def table(self):
        """Lazy-load DynamoDB table resource."""
        if self._table is None:
            self._table = _get_dynamodb_resource().Table(self._table_name)
        return self._table

    def ensure_session_exists(
        self,
        user_id: str,
        session_id: str,
        action: str,
        agent_type: str = "inventory",
    ) -> bool:
        """
        Create or update session record in DynamoDB.

        If session exists, updates lastActiveAt, lastAction, and increments turnCount.
        If session does not exist, creates a new session record.

        Args:
            user_id: User identifier
            session_id: Session identifier
            action: Current action being performed
            agent_type: Type of agent (default: "inventory")

        Returns:
            True if successful, False otherwise
        """
        from botocore.exceptions import ClientError

        now = datetime.utcnow().isoformat() + "Z"
        expires_at = int((datetime.utcnow() + timedelta(days=30)).timestamp())

        try:
            # Try to update existing session
            self.table.update_item(
                Key={"PK": f"USER#{user_id}", "SK": f"SESSION#{session_id}"},
                UpdateExpression="SET lastActiveAt = :now, lastAction = :action, turnCount = turnCount + :inc, expiresAt = :exp",
                ExpressionAttributeValues={
                    ":now": now,
                    ":action": action,
                    ":inc": 1,
                    ":exp": expires_at
                },
                ConditionExpression="attribute_exists(PK)"
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Create new session
                try:
                    self.table.put_item(Item={
                        "PK": f"USER#{user_id}",
                        "SK": f"SESSION#{session_id}",
                        "session_id": session_id,
                        "user_id": user_id,
                        "agent_type": agent_type,
                        "createdAt": now,
                        "lastActiveAt": now,
                        "lastAction": action,
                        "turnCount": 1,
                        "status": "ACTIVE",
                        "expiresAt": expires_at,
                        # GSI keys
                        "GSI1PK": f"AGENT#{agent_type}",
                        "GSI1SK": now,
                        "GSI2PK": "STATUS#ACTIVE",
                        "GSI2SK": now
                    })
                    return True
                except Exception as put_error:
                    debug_error(put_error, "session_manager_put_item", {"user_id": user_id, "session_id": session_id})
                    return False
            else:
                debug_error(e, "session_manager_update_item", {"user_id": user_id, "session_id": session_id})
                return False
        except Exception as e:
            debug_error(e, "session_manager_ensure_session_exists", {"user_id": user_id, "session_id": session_id})
            return False

    def get_session(
        self,
        user_id: str,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a session by user ID and session ID.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            Session dict if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"SESSION#{session_id}"
                }
            )
            return response.get("Item")
        except Exception as e:
            debug_error(e, "session_manager_get_session", {"user_id": user_id, "session_id": session_id})
            return None

    def list_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List sessions for a user, sorted by most recent first.

        Args:
            user_id: User identifier
            limit: Maximum sessions to return (default: 50)

        Returns:
            List of session dicts
        """
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"USER#{user_id}",
                    ":sk_prefix": "SESSION#"
                },
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            items = response.get("Items", [])
            # LOW-001 FIX: Convert Decimal to int/float for JSON serialization
            return [_convert_decimals_to_numbers(item) for item in items]
        except Exception as e:
            debug_error(e, "session_manager_list_user_sessions", {"user_id": user_id})
            return []
