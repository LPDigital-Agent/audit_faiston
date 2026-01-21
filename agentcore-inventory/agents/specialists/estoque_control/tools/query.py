# =============================================================================
# Query Tools
# =============================================================================
# Balance and asset location queries.
# =============================================================================

import logging
from typing import Dict, Any, Optional


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "estoque_control"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_query_balance")
async def query_balance_tool(
    part_number: str,
    location_id: Optional[str] = None,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query stock balance for a part number.

    Args:
        part_number: Part number to query
        location_id: Optional location filter
        project_id: Optional project filter
        session_id: Optional session ID for audit

    Returns:
        Balance information
    """
    audit.working(
        message=f"Consultando saldo: {part_number}",
        session_id=session_id,
    )

    try:
        balance = await _get_balance(
            part_number=part_number,
            location_id=location_id,
            project_id=project_id,
        )

        audit.completed(
            message=f"Saldo consultado: {balance.get('available', 0)} disponível",
            session_id=session_id,
        )

        return {
            "success": True,
            "balance": balance,
        }

    except Exception as e:
        logger.error(f"[query_balance] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao consultar saldo",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }


@trace_tool_call("sga_query_asset_location")
async def query_asset_location_tool(
    serial_number: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Find where a specific serial number is located.

    Args:
        serial_number: Serial number to find
        session_id: Optional session ID for audit

    Returns:
        Asset location and status
    """
    audit.working(
        message=f"Localizando ativo: {serial_number}",
        session_id=session_id,
    )

    try:
        asset = await _get_asset_by_serial(serial_number)

        if not asset:
            return {
                "success": False,
                "message": f"Ativo com serial {serial_number} não encontrado",
            }

        audit.completed(
            message=f"Ativo localizado: {asset.get('location_id', 'N/A')}",
            session_id=session_id,
        )

        return {
            "success": True,
            "serial_number": serial_number,
            "location_id": asset.get("location_id"),
            "status": asset.get("status"),
            "part_number": asset.get("part_number"),
            "project_id": asset.get("project_id"),
            "last_movement_id": asset.get("last_movement_id"),
            "last_updated": asset.get("updated_at"),
        }

    except Exception as e:
        logger.error(f"[query_asset_location] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao localizar ativo",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_balance(
    part_number: str,
    location_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get balance for a part number with optional filters.

    Returns calculated balance from projection.
    """
    try:
        from tools.db_client import DBClient
        db = DBClient()

        balance_item = await db.get_balance(
            part_number=part_number,
            location_id=location_id or "ALL",
            project_id=project_id or "ALL",
        )

        if balance_item:
            return {
                "total": balance_item.get("quantity_total", 0),
                "reserved": balance_item.get("quantity_reserved", 0),
                "available": balance_item.get("quantity_available", 0),
                "part_number": part_number,
                "location_id": location_id,
                "project_id": project_id,
                "owner_project_id": balance_item.get("owner_project_id"),
                "last_updated": balance_item.get("updated_at"),
            }

        # Return zero balance if not found
        return {
            "total": 0,
            "reserved": 0,
            "available": 0,
            "part_number": part_number,
            "location_id": location_id,
            "project_id": project_id,
        }

    except ImportError:
        logger.warning("[query] DBClient not available")
        return {
            "total": 0,
            "reserved": 0,
            "available": 0,
            "part_number": part_number,
            "location_id": location_id,
            "project_id": project_id,
        }


async def _get_asset_by_serial(serial_number: str) -> Optional[Dict[str, Any]]:
    """Get asset by serial number."""
    try:
        from tools.db_client import DBClient
        db = DBClient()
        return await db.get_asset_by_serial(serial_number)
    except ImportError:
        logger.warning("[query] DBClient not available")
        return None
