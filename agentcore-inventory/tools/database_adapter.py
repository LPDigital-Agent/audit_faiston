"""
Database Adapter Interface for SGA Inventory.

Abstract interface defining database operations for inventory management.
This adapter pattern allows switching between DynamoDB and PostgreSQL
without changing agent code.

Architecture:
    Agent → DatabaseAdapter (interface) → GatewayPostgresAdapter or DynamoDBAdapter

Author: Faiston NEXO Team
Date: January 2026
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class MovementType(str, Enum):
    """Inventory movement types."""
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    TRANSFERENCIA = "TRANSFERENCIA"
    RESERVA = "RESERVA"
    LIBERACAO = "LIBERACAO"
    AJUSTE_POSITIVO = "AJUSTE_POSITIVO"
    AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO"
    EXPEDICAO = "EXPEDICAO"
    REVERSA = "REVERSA"


class AssetStatus(str, Enum):
    """Asset status values."""
    IN_STOCK = "IN_STOCK"
    IN_TRANSIT = "IN_TRANSIT"
    RESERVED = "RESERVED"
    INSTALLED = "INSTALLED"
    MAINTENANCE = "MAINTENANCE"
    DISPOSED = "DISPOSED"


@dataclass
class InventoryFilters:
    """Filters for inventory queries."""
    location_id: Optional[str] = None
    project_id: Optional[str] = None
    part_number: Optional[str] = None
    status: Optional[AssetStatus] = None
    limit: int = 100
    offset: int = 0


@dataclass
class MovementFilters:
    """Filters for movement queries."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    movement_type: Optional[MovementType] = None
    project_id: Optional[str] = None
    location_id: Optional[str] = None
    limit: int = 100


@dataclass
class MovementData:
    """Data for creating a movement."""
    movement_type: MovementType
    part_number: str
    quantity: int
    source_location_id: Optional[str] = None
    destination_location_id: Optional[str] = None
    project_id: Optional[str] = None
    serial_numbers: Optional[List[str]] = None
    nf_number: Optional[str] = None
    nf_date: Optional[str] = None
    reason: Optional[str] = None


class DatabaseAdapter(ABC):
    """
    Abstract interface for inventory database operations.

    This interface is implemented by:
    - GatewayPostgresAdapter: Uses MCP client to call PostgreSQL tools via Gateway
    - DynamoDBAdapter: Direct boto3 calls to DynamoDB (legacy)

    All agents should depend on this interface, not concrete implementations.
    This enables the adapter pattern for database migration.
    """

    @abstractmethod
    async def list_inventory(
        self,
        filters: Optional[InventoryFilters] = None
    ) -> Dict[str, Any]:
        """
        List assets and balances with optional filters.

        Args:
            filters: Optional filters for location, project, part number, status

        Returns:
            Dict with 'items' list and 'total_count'
        """
        pass

    @abstractmethod
    async def get_balance(
        self,
        part_number: str,
        location_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get stock balance for a part number.

        Args:
            part_number: Part number to query (required)
            location_id: Optional location filter
            project_id: Optional project filter

        Returns:
            Dict with balance information
        """
        pass

    @abstractmethod
    async def search_assets(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search assets by serial number, part number, or description.

        Args:
            query: Search term
            search_type: Type of search (serial, part_number, description, all)
            limit: Maximum results to return

        Returns:
            List of matching assets
        """
        pass

    @abstractmethod
    async def get_asset_timeline(
        self,
        identifier: str,
        identifier_type: str = "serial_number",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get complete history of an asset (event sourcing).

        Args:
            identifier: Asset ID or serial number
            identifier_type: Type of identifier (asset_id, serial_number)
            limit: Maximum events to return

        Returns:
            List of movement events for the asset
        """
        pass

    @abstractmethod
    async def get_movements(
        self,
        filters: Optional[MovementFilters] = None
    ) -> List[Dict[str, Any]]:
        """
        List movements with filters.

        Args:
            filters: Optional filters for date range, type, project, location

        Returns:
            List of movements
        """
        pass

    @abstractmethod
    async def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List pending approval tasks (Human-in-the-Loop).

        Args:
            task_type: Filter by task type
            priority: Filter by priority
            assignee_id: Filter by assignee
            limit: Maximum results

        Returns:
            List of pending tasks
        """
        pass

    @abstractmethod
    async def create_movement(
        self,
        movement_data: MovementData
    ) -> Dict[str, Any]:
        """
        Create a new inventory movement.

        Args:
            movement_data: Movement details including type, part number, quantity

        Returns:
            Dict with created movement ID and status
        """
        pass

    @abstractmethod
    async def reconcile_with_sap(
        self,
        sap_data: List[Dict[str, Any]],
        include_serials: bool = False
    ) -> Dict[str, Any]:
        """
        Compare SGA inventory with SAP export data.

        Args:
            sap_data: List of SAP items to compare
            include_serials: Whether to include serial number comparison

        Returns:
            Dict with comparison results and divergences
        """
        pass
