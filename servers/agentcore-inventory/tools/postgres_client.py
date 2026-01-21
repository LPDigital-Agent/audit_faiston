"""
PostgreSQL Client for SGA Inventory.

This client connects to Aurora PostgreSQL via RDS Proxy.
Supports two authentication modes:
1. Password auth via Secrets Manager (default, most reliable)
2. IAM auth (optional, set USE_IAM_AUTH=true)

Architecture:
    Lambda -> RDS Proxy -> Aurora PostgreSQL Serverless v2

Security:
    - Credentials from Secrets Manager (encrypted)
    - TLS encryption required
    - Connection pooling via RDS Proxy

Author: Faiston NEXO Team
Date: January 2026
"""

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
import boto3

from shared.debug_utils import debug_error

# Configure logging
logger = logging.getLogger(__name__)


class SGAPostgresClient:
    """
    PostgreSQL client for SGA inventory operations.

    Connects via RDS Proxy with credentials from Secrets Manager.
    Optionally supports IAM auth when USE_IAM_AUTH=true.
    """

    def __init__(self):
        """Initialize the PostgreSQL client."""
        self._connection = None

        # CRITICAL: Get region FIRST before creating boto3 clients
        # AgentCore runtime may not set AWS_REGION consistently during cold starts
        # Must explicitly pass region_name to all boto3.client() calls
        self._region = os.environ.get(
            "AWS_REGION",
            os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
        )

        # Create boto3 clients WITH explicit region (fixes "You must specify a region" error)
        self._secrets_client = boto3.client("secretsmanager", region_name=self._region)
        self._rds_client = boto3.client("rds", region_name=self._region)

        # Configuration from environment
        self._proxy_endpoint = os.environ.get("RDS_PROXY_ENDPOINT")
        # BUG-022 v9 FIX (HIGH-T2): Remove hardcoded ARN - security vulnerability!
        # Hardcoded secrets in source code can be leaked via version control.
        # The ARN MUST come from environment variable (set by Terraform/Lambda config).
        self._secret_arn = os.environ.get("RDS_SECRET_ARN")
        if not self._secret_arn:
            config_error = ValueError(
                "RDS_SECRET_ARN environment variable is required. "
                "Hardcoded ARNs are not allowed for security reasons."
            )
            debug_error(config_error, "postgres_client_init", {"missing_env": "RDS_SECRET_ARN"})
            raise ValueError(
                "RDS_SECRET_ARN environment variable is required. "
                "Hardcoded ARNs are not allowed for security reasons."
            )
        self._database = os.environ.get("RDS_DATABASE_NAME", "sga_inventory")
        self._port = int(os.environ.get("RDS_PORT", "5432"))
        # DIRECT_CONNECT=true bypasses RDS Proxy and connects directly to Aurora with password
        # Use for bootstrap operations or when Proxy requires IAM auth not yet configured
        self._direct_connect = os.environ.get("DIRECT_CONNECT", "false").lower() == "true"
        # USE_IAM_AUTH=true uses IAM authentication (requires rds_iam role in PostgreSQL)
        self._use_iam_auth = os.environ.get("USE_IAM_AUTH", "false").lower() == "true"

        # Cache for credentials
        self._credentials = None

    def _get_credentials(self) -> Dict[str, str]:
        """
        Get database credentials from Secrets Manager.

        Returns:
            Dictionary with host, username, password, dbname, port
        """
        if self._credentials:
            return self._credentials

        try:
            response = self._secrets_client.get_secret_value(SecretId=self._secret_arn)
            self._credentials = json.loads(response["SecretString"])
            logger.info("Retrieved credentials from Secrets Manager")
            return self._credentials
        except Exception as e:
            debug_error(e, "postgres_get_credentials", {"secret_arn": self._secret_arn})
            raise

    def _get_connection(self):
        """
        Get or create a database connection.

        Connection modes:
        1. DIRECT_CONNECT=true: Connect directly to Aurora with password (bootstrap)
        2. USE_IAM_AUTH=true: Connect to RDS Proxy with IAM auth (production)
        3. Default: Connect to RDS Proxy with password (requires Proxy password auth)

        Returns:
            psycopg connection object
        """
        if self._connection is not None and not self._connection.closed:
            return self._connection

        try:
            import psycopg
            from psycopg.rows import dict_row

            creds = self._get_credentials()

            if self._direct_connect:
                # Direct connection to Aurora (bypasses Proxy)
                # Use for bootstrap when Proxy IAM auth not configured
                host = creds.get("host")  # Use Aurora cluster endpoint
                logger.info(f"Connecting directly to Aurora at {host}")

                self._connection = psycopg.connect(
                    host=host,
                    port=creds.get("port", self._port),
                    user=creds.get("username"),
                    password=creds.get("password"),
                    dbname=creds.get("dbname", self._database),
                    sslmode="require",
                    row_factory=dict_row
                )
                logger.info("Connected to PostgreSQL directly (bypass Proxy)")

            elif self._use_iam_auth:
                # IAM authentication via RDS Proxy
                user = creds.get("username", "sgaadmin")
                host = self._proxy_endpoint or creds.get("host")

                # Generate IAM auth token
                token = self._rds_client.generate_db_auth_token(
                    DBHostname=host,
                    Port=self._port,
                    DBUsername=user,
                    Region=self._region
                )

                self._connection = psycopg.connect(
                    host=host,
                    port=self._port,
                    user=user,
                    password=token,
                    dbname=self._database,
                    sslmode="require",
                    row_factory=dict_row
                )
                logger.info("Connected to PostgreSQL via IAM auth")

            else:
                # Password authentication via RDS Proxy
                # Note: RDS Proxy must be configured to accept password auth
                host = self._proxy_endpoint or creds.get("host")

                self._connection = psycopg.connect(
                    host=host,
                    port=creds.get("port", self._port),
                    user=creds.get("username"),
                    password=creds.get("password"),
                    dbname=creds.get("dbname", self._database),
                    sslmode="require",
                    row_factory=dict_row
                )
                logger.info("Connected to PostgreSQL via password auth")

            return self._connection

        except Exception as e:
            debug_error(e, "postgres_connect", {"proxy_endpoint": self._proxy_endpoint, "direct_connect": self._direct_connect})
            raise

    def _execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch_all: bool = True
    ) -> List[Dict]:
        """
        Execute a SQL query and return results.

        Args:
            query: SQL query string
            params: Query parameters (optional)
            fetch_all: If True, fetch all results; if False, return cursor

        Returns:
            List of dictionaries representing rows
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch_all:
                    return cur.fetchall()
                return []
        except Exception as e:
            conn.rollback()
            debug_error(e, "postgres_execute_query", {"query_preview": query[:200] if query else None})
            raise

    def _execute_write(self, query: str, params: Optional[tuple] = None) -> int:
        """
        Execute a write query (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Number of affected rows
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
                return cur.rowcount
        except Exception as e:
            conn.rollback()
            debug_error(e, "postgres_execute_write", {"query_preview": query[:200] if query else None})
            raise

    # =========================================================================
    # Query Methods
    # =========================================================================

    def list_inventory(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List inventory with optional filters.

        Args:
            filters: Dictionary of filter conditions
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Dictionary with items and pagination info
        """
        filters = filters or {}

        # Build query using materialized view for performance
        query = """
            SELECT *
            FROM sga.mv_inventory_summary
            WHERE 1=1
        """
        params = []

        if "location_id" in filters:
            query += " AND location_code = %s"
            params.append(filters["location_id"])

        if "part_number" in filters:
            query += " AND part_number = %s"
            params.append(filters["part_number"])

        if "status" in filters:
            query += " AND stock_status = %s"
            params.append(filters["status"])

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM ({query}) AS subq"
        count_result = self._execute_query(count_query, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        # Add pagination
        query += " ORDER BY part_number, location_code LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        items = self._execute_query(query, tuple(params))

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total
        }

    def get_balance(
        self,
        part_number: str,
        location_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get stock balance for a part number.

        Args:
            part_number: Part number to query
            location_id: Optional location filter
            project_id: Optional project filter

        Returns:
            Balance information
        """
        query = """
            SELECT
                b.balance_id,
                pn.part_number,
                pn.description,
                l.location_code,
                l.location_name,
                p.project_code,
                p.project_name,
                b.quantity_total,
                b.quantity_reserved,
                b.quantity_available,
                b.last_movement_at,
                b.last_count_at
            FROM sga.balances b
            JOIN sga.part_numbers pn ON b.part_number_id = pn.part_number_id
            JOIN sga.locations l ON b.location_id = l.location_id
            LEFT JOIN sga.projects p ON b.project_id = p.project_id
            WHERE pn.part_number = %s
        """
        params = [part_number]

        if location_id:
            query += " AND l.location_code = %s"
            params.append(location_id)

        if project_id:
            query += " AND p.project_code = %s"
            params.append(project_id)

        results = self._execute_query(query, tuple(params))

        if not results:
            return {
                "found": False,
                "part_number": part_number,
                "message": "No balance found for this part number"
            }

        # Aggregate if multiple locations
        total_quantity = sum(r["quantity_total"] for r in results)
        total_reserved = sum(r["quantity_reserved"] for r in results)
        total_available = sum(r["quantity_available"] for r in results)

        return {
            "found": True,
            "part_number": part_number,
            "description": results[0]["description"],
            "summary": {
                "total_quantity": total_quantity,
                "total_reserved": total_reserved,
                "total_available": total_available
            },
            "by_location": results
        }

    def search_assets(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search assets by serial, part number, or description.

        Args:
            query: Search term
            search_type: Type of search (serial, part_number, description, all)
            limit: Maximum results

        Returns:
            Search results
        """
        base_query = """
            SELECT
                a.asset_id,
                a.serial_number,
                pn.part_number,
                pn.description,
                l.location_code,
                l.location_name,
                p.project_code,
                a.status,
                a.condition,
                a.last_movement_at
            FROM sga.assets a
            JOIN sga.part_numbers pn ON a.part_number_id = pn.part_number_id
            LEFT JOIN sga.locations l ON a.location_id = l.location_id
            LEFT JOIN sga.projects p ON a.project_id = p.project_id
            WHERE a.is_active = TRUE
        """

        if search_type == "serial":
            base_query += " AND a.serial_number ILIKE %s"
            params = [f"%{query}%"]
        elif search_type == "part_number":
            base_query += " AND pn.part_number ILIKE %s"
            params = [f"%{query}%"]
        elif search_type == "description":
            base_query += " AND pn.search_vector @@ plainto_tsquery('portuguese', %s)"
            params = [query]
        else:  # all
            base_query += """
                AND (
                    a.serial_number ILIKE %s
                    OR pn.part_number ILIKE %s
                    OR pn.search_vector @@ plainto_tsquery('portuguese', %s)
                )
            """
            params = [f"%{query}%", f"%{query}%", query]

        base_query += " ORDER BY a.serial_number LIMIT %s"
        params.append(limit)

        results = self._execute_query(base_query, tuple(params))

        return {
            "query": query,
            "search_type": search_type,
            "count": len(results),
            "items": results
        }

    def get_asset_timeline(
        self,
        identifier: str,
        identifier_type: str = "serial_number",
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get complete movement history of an asset.

        Args:
            identifier: Asset ID or serial number
            identifier_type: Type of identifier
            limit: Maximum events to return

        Returns:
            Asset info and timeline events
        """
        # First, get asset info
        if identifier_type == "asset_id":
            asset_query = """
                SELECT
                    a.asset_id,
                    a.serial_number,
                    pn.part_number,
                    pn.description,
                    l.location_code,
                    l.location_name,
                    p.project_code,
                    a.status,
                    a.condition,
                    a.purchase_date,
                    a.nf_number,
                    a.nf_date,
                    a.created_at
                FROM sga.assets a
                JOIN sga.part_numbers pn ON a.part_number_id = pn.part_number_id
                LEFT JOIN sga.locations l ON a.location_id = l.location_id
                LEFT JOIN sga.projects p ON a.project_id = p.project_id
                WHERE a.asset_id = %s::uuid
            """
        else:
            asset_query = """
                SELECT
                    a.asset_id,
                    a.serial_number,
                    pn.part_number,
                    pn.description,
                    l.location_code,
                    l.location_name,
                    p.project_code,
                    a.status,
                    a.condition,
                    a.purchase_date,
                    a.nf_number,
                    a.nf_date,
                    a.created_at
                FROM sga.assets a
                JOIN sga.part_numbers pn ON a.part_number_id = pn.part_number_id
                LEFT JOIN sga.locations l ON a.location_id = l.location_id
                LEFT JOIN sga.projects p ON a.project_id = p.project_id
                WHERE a.serial_number = %s
            """

        asset_result = self._execute_query(asset_query, (identifier,))

        if not asset_result:
            return {
                "found": False,
                "identifier": identifier,
                "message": "Asset not found"
            }

        asset = asset_result[0]

        # Get movement timeline
        timeline_query = """
            SELECT
                m.movement_id,
                m.movement_type,
                m.movement_date,
                m.quantity,
                sl.location_code as source_location,
                dl.location_code as destination_location,
                p.project_code,
                m.nf_number,
                m.reason,
                m.created_by
            FROM sga.movement_items mi
            JOIN sga.movements m ON mi.movement_id = m.movement_id
            LEFT JOIN sga.locations sl ON m.source_location_id = sl.location_id
            LEFT JOIN sga.locations dl ON m.destination_location_id = dl.location_id
            LEFT JOIN sga.projects p ON m.project_id = p.project_id
            WHERE mi.asset_id = %s::uuid
            ORDER BY m.movement_date DESC
            LIMIT %s
        """

        timeline = self._execute_query(
            timeline_query,
            (str(asset["asset_id"]), limit)
        )

        return {
            "found": True,
            "asset": asset,
            "timeline": timeline,
            "timeline_count": len(timeline)
        }

    def get_movements(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List movements with filters.

        Args:
            filters: Filter conditions
            limit: Maximum results

        Returns:
            List of movements
        """
        filters = filters or {}

        query = """
            SELECT
                m.movement_id,
                m.movement_type,
                m.movement_date,
                pn.part_number,
                pn.description,
                m.quantity,
                sl.location_code as source_location,
                dl.location_code as destination_location,
                p.project_code,
                m.nf_number,
                m.nf_date,
                m.reason,
                m.created_by,
                m.created_at
            FROM sga.movements m
            JOIN sga.part_numbers pn ON m.part_number_id = pn.part_number_id
            LEFT JOIN sga.locations sl ON m.source_location_id = sl.location_id
            LEFT JOIN sga.locations dl ON m.destination_location_id = dl.location_id
            LEFT JOIN sga.projects p ON m.project_id = p.project_id
            WHERE 1=1
        """
        params = []

        if "start_date" in filters:
            query += " AND m.movement_date >= %s"
            params.append(filters["start_date"])

        if "end_date" in filters:
            query += " AND m.movement_date <= %s"
            params.append(filters["end_date"])

        if "movement_type" in filters:
            query += " AND m.movement_type = %s"
            params.append(filters["movement_type"])

        if "project_id" in filters:
            query += " AND p.project_code = %s"
            params.append(filters["project_id"])

        if "location_id" in filters:
            query += " AND (sl.location_code = %s OR dl.location_code = %s)"
            params.extend([filters["location_id"], filters["location_id"]])

        query += " ORDER BY m.movement_date DESC LIMIT %s"
        params.append(limit)

        results = self._execute_query(query, tuple(params))

        return {
            "count": len(results),
            "items": results
        }

    def get_pending_tasks(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        List pending approval tasks (from pending_entries table).

        Args:
            filters: Filter conditions
            limit: Maximum results

        Returns:
            List of pending tasks
        """
        filters = filters or {}

        query = """
            SELECT
                entry_id,
                source_type,
                nf_number,
                nf_date,
                supplier_name,
                total_value,
                total_items,
                status,
                ocr_confidence,
                created_at,
                created_by
            FROM sga.pending_entries
            WHERE status IN ('PENDING', 'PROCESSING')
        """
        params = []

        if "task_type" in filters:
            # Map task_type to source_type
            task_mapping = {
                "APPROVAL_ENTRY": ["NF_XML", "NF_PDF", "NF_IMAGE", "MANUAL"],
                "DOCUMENT_REVIEW": ["SAP_IMPORT", "BULK_IMPORT"],
            }
            source_types = task_mapping.get(filters["task_type"], [])
            if source_types:
                placeholders = ",".join(["%s"] * len(source_types))
                query += f" AND source_type IN ({placeholders})"
                params.extend(source_types)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        results = self._execute_query(query, tuple(params))

        return {
            "count": len(results),
            "items": results
        }

    def create_movement(
        self,
        movement_type: str,
        part_number: str,
        quantity: int,
        source_location_id: Optional[str] = None,
        destination_location_id: Optional[str] = None,
        project_id: Optional[str] = None,
        serial_numbers: Optional[List[str]] = None,
        nf_number: Optional[str] = None,
        nf_date: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new inventory movement.

        Args:
            movement_type: Type of movement
            part_number: Part number
            quantity: Quantity
            source_location_id: Source location code
            destination_location_id: Destination location code
            project_id: Project code
            serial_numbers: List of serial numbers
            nf_number: NF number
            nf_date: NF date
            reason: Reason for movement

        Returns:
            Created movement info
        """
        # Look up IDs from codes
        pn_query = "SELECT part_number_id FROM sga.part_numbers WHERE part_number = %s"
        pn_result = self._execute_query(pn_query, (part_number,))
        if not pn_result:
            return {"error": f"Part number not found: {part_number}"}
        part_number_id = pn_result[0]["part_number_id"]

        source_id = None
        if source_location_id:
            loc_query = "SELECT location_id FROM sga.locations WHERE location_code = %s"
            loc_result = self._execute_query(loc_query, (source_location_id,))
            if loc_result:
                source_id = loc_result[0]["location_id"]

        dest_id = None
        if destination_location_id:
            loc_query = "SELECT location_id FROM sga.locations WHERE location_code = %s"
            loc_result = self._execute_query(loc_query, (destination_location_id,))
            if loc_result:
                dest_id = loc_result[0]["location_id"]

        proj_id = None
        if project_id:
            proj_query = "SELECT project_id FROM sga.projects WHERE project_code = %s"
            proj_result = self._execute_query(proj_query, (project_id,))
            if proj_result:
                proj_id = proj_result[0]["project_id"]

        # Insert movement
        insert_query = """
            INSERT INTO sga.movements (
                movement_type,
                part_number_id,
                quantity,
                source_location_id,
                destination_location_id,
                project_id,
                nf_number,
                nf_date,
                reason,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING movement_id, movement_date
        """

        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(insert_query, (
                movement_type,
                str(part_number_id),
                quantity,
                str(source_id) if source_id else None,
                str(dest_id) if dest_id else None,
                str(proj_id) if proj_id else None,
                nf_number,
                nf_date,
                reason,
                "mcp_lambda"  # Created by MCP tool
            ))
            result = cur.fetchone()
            conn.commit()

        return {
            "success": True,
            "movement_id": str(result["movement_id"]),
            "movement_date": result["movement_date"].isoformat(),
            "message": f"Movement created: {movement_type} - {quantity} x {part_number}"
        }

    def reconcile_with_sap(
        self,
        sap_data: List[Dict[str, Any]],
        include_serials: bool = False
    ) -> Dict[str, Any]:
        """
        Compare SGA inventory with SAP export data.

        Args:
            sap_data: List of SAP items with part_number, quantity, location_code
            include_serials: Whether to include serial number comparison

        Returns:
            Reconciliation results with matches and discrepancies
        """
        results = {
            "total_sap_items": len(sap_data),
            "matches": [],
            "discrepancies": [],
            "sap_only": [],
            "sga_only": []
        }

        # Get all SGA balances
        sga_query = """
            SELECT
                pn.part_number,
                l.location_code,
                p.project_code,
                SUM(b.quantity_total) as sga_quantity
            FROM sga.balances b
            JOIN sga.part_numbers pn ON b.part_number_id = pn.part_number_id
            JOIN sga.locations l ON b.location_id = l.location_id
            LEFT JOIN sga.projects p ON b.project_id = p.project_id
            GROUP BY pn.part_number, l.location_code, p.project_code
        """
        sga_balances = self._execute_query(sga_query)

        # Create lookup for SGA data
        sga_lookup = {}
        for row in sga_balances:
            key = (row["part_number"], row.get("location_code"))
            sga_lookup[key] = row["sga_quantity"]

        # Compare each SAP item
        sap_keys_found = set()
        for sap_item in sap_data:
            key = (sap_item["part_number"], sap_item.get("location_code"))
            sap_keys_found.add(key)

            sap_qty = sap_item["quantity"]
            sga_qty = sga_lookup.get(key, 0)

            item_result = {
                "part_number": sap_item["part_number"],
                "location_code": sap_item.get("location_code"),
                "sap_quantity": sap_qty,
                "sga_quantity": sga_qty,
                "variance": sga_qty - sap_qty
            }

            if sap_qty == sga_qty:
                results["matches"].append(item_result)
            elif key not in sga_lookup:
                results["sap_only"].append(item_result)
            else:
                results["discrepancies"].append(item_result)

        # Find items in SGA but not in SAP
        for key, sga_qty in sga_lookup.items():
            if key not in sap_keys_found:
                results["sga_only"].append({
                    "part_number": key[0],
                    "location_code": key[1],
                    "sap_quantity": 0,
                    "sga_quantity": sga_qty,
                    "variance": sga_qty
                })

        results["summary"] = {
            "matches_count": len(results["matches"]),
            "discrepancies_count": len(results["discrepancies"]),
            "sap_only_count": len(results["sap_only"]),
            "sga_only_count": len(results["sga_only"]),
            "accuracy_percentage": round(
                len(results["matches"]) / len(sap_data) * 100, 2
            ) if sap_data else 100
        }

        return results

    # =========================================================================
    # Schema Introspection Methods (for Schema-Aware NEXO Import)
    # =========================================================================

    def get_table_columns(self, table_name: str, schema_name: str = "sga") -> List[Dict]:
        """
        Get column metadata for a table from information_schema.

        Used by NEXO agents to understand target table structure
        before analyzing import files.

        Args:
            table_name: Name of the table (e.g., "pending_entry_items")
            schema_name: Schema name (default: "sga")

        Returns:
            List of column metadata dictionaries with:
            - name: Column name
            - data_type: PostgreSQL data type
            - character_maximum_length: Max length for VARCHAR
            - is_nullable: YES/NO
            - column_default: Default value
            - udt_name: User-defined type name (for ENUMs)
            - is_primary_key: Boolean
            - ordinal_position: Column order
        """
        query = """
            SELECT
                c.column_name as name,
                c.data_type,
                c.character_maximum_length,
                c.is_nullable,
                c.column_default,
                c.udt_name,
                c.ordinal_position,
                CASE
                    WHEN pk.column_name IS NOT NULL THEN TRUE
                    ELSE FALSE
                END as is_primary_key
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        """
        try:
            results = self._execute_query(
                query,
                (schema_name, table_name, schema_name, table_name)
            )
            logger.info(f"Retrieved {len(results)} columns for {schema_name}.{table_name}")
            return results
        except Exception as e:
            debug_error(e, "postgres_get_table_columns", {"table_name": table_name, "schema_name": schema_name})
            return []

    def get_enum_values(self, enum_name: str) -> List[str]:
        """
        Get valid values for a PostgreSQL ENUM type.

        Used by NEXO agents to validate movement_type, asset_status, etc.

        Args:
            enum_name: Name of the ENUM type (e.g., "movement_type")

        Returns:
            List of valid enum values in sort order
        """
        query = """
            SELECT enumlabel as value
            FROM pg_catalog.pg_enum e
            JOIN pg_catalog.pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = %s
            ORDER BY e.enumsortorder
        """
        try:
            results = self._execute_query(query, (enum_name,))
            values = [r["value"] for r in results]
            logger.info(f"Retrieved {len(values)} values for ENUM {enum_name}")
            return values
        except Exception as e:
            debug_error(e, "postgres_get_enum_values", {"enum_name": enum_name})
            return []

    def get_foreign_keys(self, table_name: str, schema_name: str = "sga") -> List[Dict]:
        """
        Get foreign key constraints for a table.

        Used by NEXO agents to understand FK relationships
        and validate references during import.

        Args:
            table_name: Name of the table
            schema_name: Schema name (default: "sga")

        Returns:
            List of FK constraint dictionaries with:
            - constraint_name: Name of the constraint
            - column_name: Column in this table
            - foreign_table_schema: Schema of referenced table
            - foreign_table_name: Referenced table name
            - foreign_column_name: Referenced column name
        """
        query = """
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_schema as foreign_table_schema,
                ccu.table_name as foreign_table_name,
                ccu.column_name as foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
        """
        try:
            results = self._execute_query(query, (schema_name, table_name))
            logger.info(f"Retrieved {len(results)} FK constraints for {schema_name}.{table_name}")
            return results
        except Exception as e:
            debug_error(e, "postgres_get_foreign_keys", {"table_name": table_name, "schema_name": schema_name})
            return []

    def get_schema_metadata(self) -> Dict[str, Any]:
        """
        Get complete schema metadata for all SGA import-related tables.

        This method is optimized to retrieve all necessary schema info
        in a single call, minimizing database round trips.

        Used by SchemaProvider for caching schema knowledge.

        Returns:
            Dictionary with:
            - tables: Dict[table_name, List[column_info]]
            - enums: Dict[enum_name, List[values]]
            - foreign_keys: Dict[table_name, List[fk_info]]
            - timestamp: ISO timestamp of retrieval
        """
        # Import target tables (relevant for NEXO import)
        import_tables = [
            "part_numbers",
            "locations",
            "projects",
            "assets",
            "movements",
            "movement_items",
            "pending_entries",
            "pending_entry_items",
            "balances",
            "reservations",
        ]

        # Known ENUMs in schema
        enum_types = [
            "movement_type",
            "asset_status",
            "entry_source",
            "task_status",
            "priority",
        ]

        tables = {}
        foreign_keys = {}
        enums = {}

        # Get all table columns
        for table in import_tables:
            columns = self.get_table_columns(table)
            if columns:
                tables[table] = columns

            fks = self.get_foreign_keys(table)
            if fks:
                foreign_keys[table] = fks

        # Get all enum values
        for enum_name in enum_types:
            values = self.get_enum_values(enum_name)
            if values:
                enums[enum_name] = values

        # Get required columns (NOT NULL without default)
        required_columns = {}
        for table_name, columns in tables.items():
            required = [
                col["name"]
                for col in columns
                if col["is_nullable"] == "NO"
                and col["column_default"] is None
                and not col["is_primary_key"]  # PKs are auto-generated
            ]
            if required:
                required_columns[table_name] = required

        return {
            "tables": tables,
            "enums": enums,
            "foreign_keys": foreign_keys,
            "required_columns": required_columns,
            "table_list": list(tables.keys()),
            "timestamp": datetime.now().isoformat(),
        }

    def list_tables(self, schema_name: str = "sga") -> List[str]:
        """
        List all tables in a schema.

        Args:
            schema_name: Schema name (default: "sga")

        Returns:
            List of table names
        """
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
                AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        try:
            results = self._execute_query(query, (schema_name,))
            return [r["table_name"] for r in results]
        except Exception as e:
            debug_error(e, "postgres_list_tables", {"schema_name": schema_name})
            return []

    def validate_column_exists(
        self,
        table_name: str,
        column_name: str,
        schema_name: str = "sga"
    ) -> bool:
        """
        Check if a column exists in a table.

        Used by SchemaValidator to verify column mappings.

        Args:
            table_name: Table name
            column_name: Column name to check
            schema_name: Schema name (default: "sga")

        Returns:
            True if column exists, False otherwise
        """
        query = """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s
                AND table_name = %s
                AND column_name = %s
        """
        try:
            results = self._execute_query(query, (schema_name, table_name, column_name))
            return len(results) > 0
        except Exception as e:
            debug_error(e, "postgres_validate_column_exists", {"table_name": table_name, "column_name": column_name})
            return False

    # =========================================================================
    # Schema Evolution Methods (Dynamic Column Creation)
    # =========================================================================

    # Whitelist of tables that allow dynamic column creation
    ALLOWED_TABLES = frozenset({"pending_entry_items", "pending_entries"})

    # Whitelist of allowed PostgreSQL types for dynamic columns
    ALLOWED_TYPES = frozenset({
        "TEXT", "VARCHAR(100)", "VARCHAR(255)", "VARCHAR(500)",
        "INTEGER", "BIGINT", "NUMERIC(12,2)", "BOOLEAN",
        "TIMESTAMPTZ", "DATE", "JSONB", "TEXT[]"
    })

    def _sanitize_identifier(self, name: str) -> str:
        """
        Sanitize a SQL identifier (table/column name) for safety.

        - Lowercase
        - Replace non-alphanumeric chars with underscore
        - Remove consecutive underscores
        - Ensure doesn't start with number
        - Limit to 63 chars (PostgreSQL limit)
        """
        if not name:
            return "unknown"

        sanitized = name.lower().strip()
        sanitized = re.sub(r'[^a-z0-9_]', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_')

        # Ensure doesn't start with number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"col_{sanitized}"

        return sanitized[:63] if sanitized else "unknown"

    def _validate_column_type(self, column_type: str) -> str:
        """
        Validate and return a safe column type.

        Returns TEXT if type not in whitelist.
        """
        if column_type in self.ALLOWED_TYPES:
            return column_type
        logger.warning(f"Column type '{column_type}' not in whitelist, using TEXT")
        return "TEXT"

    def create_column_safe(
        self,
        table_name: str,
        column_name: str,
        column_type: str,
        requested_by: str,
        original_csv_column: Optional[str] = None,
        sample_values: Optional[List[str]] = None,
        lock_timeout_ms: int = 5000,
    ) -> Dict[str, Any]:
        """
        Create a new column with advisory locking for concurrency safety.

        Uses pg_advisory_xact_lock() for transaction-scoped locking.
        If lock cannot be acquired within timeout, returns fallback signal.

        This method is called by the Schema Evolution Agent (SEA) via MCP.

        Concurrency handling:
        1. Acquire advisory lock based on table.column hash
        2. Double-check column doesn't exist (race condition protection)
        3. Execute DDL if column doesn't exist
        4. Log to schema_evolution_log for audit
        5. Release lock (automatic on transaction end)

        Args:
            table_name: Target table (must be in ALLOWED_TABLES)
            column_name: Column name (will be sanitized)
            column_type: PostgreSQL type (must be in ALLOWED_TYPES)
            requested_by: User ID for audit trail
            original_csv_column: Original column name from CSV
            sample_values: Sample values (first 5, for debugging)
            lock_timeout_ms: Lock acquisition timeout (default 5000ms)

        Returns:
            Dictionary with:
            - success: bool
            - created: bool (True if new column, False if already existed)
            - column_name: sanitized column name
            - column_type: validated column type
            - reason: explanation string
            - use_metadata_fallback: bool (True if should use JSONB)
            - error: error type string (if failed)
            - message: error message (if failed)
        """
        # Sanitize inputs
        safe_table = self._sanitize_identifier(table_name)
        safe_column = self._sanitize_identifier(column_name)
        safe_type = self._validate_column_type(column_type)

        # Validate table is in whitelist
        if safe_table not in self.ALLOWED_TABLES:
            logger.warning(f"Table '{safe_table}' not allowed for dynamic columns")
            return {
                "success": False,
                "error": "table_not_allowed",
                "message": f"Table '{safe_table}' not in allowed tables: {self.ALLOWED_TABLES}",
                "use_metadata_fallback": True,
            }

        # Generate deterministic lock ID from table.column
        lock_key = f"sga.{safe_table}.{safe_column}"
        lock_id = int(hashlib.md5(lock_key.encode()).hexdigest()[:8], 16)

        logger.info(
            f"[SEA] Creating column '{safe_column}' ({safe_type}) in {safe_table} "
            f"[lock_id={lock_id}, requested_by={requested_by}]"
        )

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Set lock timeout
                cur.execute(f"SET LOCAL lock_timeout = '{lock_timeout_ms}ms'")

                # Acquire transaction-scoped advisory lock
                # This will wait up to lock_timeout_ms for the lock
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))

                # Double-check column doesn't exist (race condition protection)
                cur.execute("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'sga'
                      AND table_name = %s
                      AND column_name = %s
                """, (safe_table, safe_column))

                if cur.fetchone():
                    # Column already exists (likely created by another user)
                    logger.info(f"[SEA] Column '{safe_column}' already exists (race condition handled)")

                    # Log as ALREADY_EXISTS
                    cur.execute("""
                        INSERT INTO sga.schema_evolution_log
                        (table_name, column_name, column_type, requested_by, status,
                         original_csv_column, completed_at)
                        VALUES (%s, %s, %s, %s, 'ALREADY_EXISTS', %s, NOW())
                    """, (safe_table, safe_column, safe_type, requested_by, original_csv_column))

                    conn.commit()

                    return {
                        "success": True,
                        "created": False,
                        "reason": "already_exists",
                        "column_name": safe_column,
                        "column_type": safe_type,
                        "use_metadata_fallback": False,
                    }

                # Execute DDL - Use double quotes for column name to preserve case
                ddl = f'ALTER TABLE sga.{safe_table} ADD COLUMN "{safe_column}" {safe_type}'
                cur.execute(ddl)

                logger.info(f"[SEA] Column '{safe_column}' created successfully")

                # Audit log - mark as CREATED
                cur.execute("""
                    INSERT INTO sga.schema_evolution_log
                    (table_name, column_name, column_type, requested_by, status,
                     original_csv_column, sample_values, completed_at)
                    VALUES (%s, %s, %s, %s, 'CREATED', %s, %s, NOW())
                """, (
                    safe_table, safe_column, safe_type, requested_by,
                    original_csv_column, sample_values
                ))

                # Also track in dynamic_columns table
                cur.execute("""
                    INSERT INTO sga.dynamic_columns
                    (table_name, column_name, column_type, inferred_from, sample_values, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (table_name, column_name) DO UPDATE
                    SET usage_count = sga.dynamic_columns.usage_count + 1,
                        last_used_at = NOW()
                """, (
                    safe_table, safe_column, safe_type,
                    original_csv_column, sample_values, requested_by
                ))

                conn.commit()

                return {
                    "success": True,
                    "created": True,
                    "column_name": safe_column,
                    "column_type": safe_type,
                    "reason": "created",
                    "use_metadata_fallback": False,
                }

        except Exception as e:
            conn.rollback()
            error_msg = str(e)
            debug_error(e, "postgres_create_column_safe", {"table_name": safe_table, "column_name": safe_column, "column_type": safe_type})

            # Log failure
            try:
                with conn.cursor() as cur2:
                    cur2.execute("""
                        INSERT INTO sga.schema_evolution_log
                        (table_name, column_name, column_type, requested_by, status,
                         original_csv_column, error_message, completed_at)
                        VALUES (%s, %s, %s, %s, 'FAILED', %s, %s, NOW())
                    """, (
                        safe_table, safe_column, safe_type, requested_by,
                        original_csv_column, error_msg
                    ))
                    conn.commit()
            except Exception as log_err:
                debug_error(log_err, "postgres_sea_log_failure", {"table_name": safe_table, "column_name": safe_column})

            # Check if it's a lock timeout (recommend metadata fallback)
            if "lock timeout" in error_msg.lower() or "canceling statement" in error_msg.lower():
                return {
                    "success": False,
                    "error": "lock_timeout",
                    "message": "Another user is creating the same column. Use metadata fallback.",
                    "use_metadata_fallback": True,
                    "column_name": safe_column,
                    "column_type": safe_type,
                }

            return {
                "success": False,
                "error": "ddl_failed",
                "message": error_msg,
                "use_metadata_fallback": True,
                "column_name": safe_column,
                "column_type": safe_type,
            }
