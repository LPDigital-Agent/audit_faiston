# =============================================================================
# EstoqueControlAgent - Strands A2AServer Entry Point (SPECIALIST)
# =============================================================================
# Core inventory control specialist agent.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
#
# Architecture:
# - This is a SPECIALIST agent for inventory movements
# - Receives requests from ORCHESTRATOR or other specialists via A2A
# - Handles reservations, expeditions, transfers, returns
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# =============================================================================

import os
import sys
import logging
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill
from fastapi import FastAPI
import uvicorn

# Centralized model configuration (MANDATORY - Gemini 3.0 Flash for speed)
from agents.utils import get_model, AGENT_VERSION, create_gemini_model

# A2A client for inter-agent communication
from shared.a2a_client import A2AClient

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import EstoqueControlResponse
from shared.debug_utils import debug_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "estoque_control"
AGENT_NAME = "EstoqueControlAgent"
AGENT_DESCRIPTION = """SPECIALIST Agent for Inventory Control Operations.

This agent manages all inventory movements:
1. RESERVATIONS: Create/cancel asset reservations for projects
2. EXPEDITIONS: Process material exits to customers/technicians
3. TRANSFERS: Move assets between storage locations
4. RETURNS: Process material returns (reverse logistics)
5. QUERIES: Answer about balances and asset locations

Features:
- Event-sourced balance calculation
- HIL routing for high-risk operations
- Cross-project validation
- Serial number tracking
"""

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-3.0-flash (fast, operational)

# Agent Skills (for A2A Agent Card discovery)
AGENT_SKILLS = [
    AgentSkill(
        id="create_reservation",
        name="Create Asset Reservation",
        description="Create asset reservation for a project/call. Blocks inventory balance for specific items. Supports TTL-based auto-expiry and cross-project validation with HIL routing.",
        input_schema={
            "type": "object",
            "properties": {
                "part_number_id": {"type": "string", "description": "Part number to reserve"},
                "quantity": {"type": "integer", "description": "Quantity to reserve"},
                "project_id": {"type": "string", "description": "Project/client to reserve for"},
                "call_id": {"type": "string", "description": "Optional call/ticket ID"},
                "serial_numbers": {"type": "array", "items": {"type": "string"}, "description": "Optional specific serials to reserve"},
                "ttl_hours": {"type": "integer", "description": "Reservation expiry time (default 72h)"},
                "session_id": {"type": "string", "description": "Session ID for context"},
                "user_id": {"type": "string", "description": "User ID for audit"},
            },
            "required": ["part_number_id", "quantity", "project_id"],
        },
    ),
    AgentSkill(
        id="cancel_reservation",
        name="Cancel Reservation",
        description="Cancel an existing reservation and release blocked inventory balance.",
        input_schema={
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string", "description": "Reservation to cancel"},
                "reason": {"type": "string", "description": "Optional cancellation reason"},
                "session_id": {"type": "string", "description": "Session ID for context"},
                "user_id": {"type": "string", "description": "User ID for audit"},
            },
            "required": ["reservation_id"],
        },
    ),
    AgentSkill(
        id="process_expedition",
        name="Process Material Expedition",
        description="Process material expedition (exit). Creates exit movement for items being sent to customer/technician. Can consume existing reservations.",
        input_schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "serial_numbers": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "description": "List of items to expedite",
                },
                "destination": {"type": "string", "description": "Destination address/location"},
                "project_id": {"type": "string", "description": "Project/client for expedition"},
                "recipient_name": {"type": "string", "description": "Optional recipient name"},
                "reservation_id": {"type": "string", "description": "Optional reservation to consume"},
                "session_id": {"type": "string", "description": "Session ID for context"},
                "user_id": {"type": "string", "description": "User ID for audit"},
            },
            "required": ["items", "destination", "project_id"],
        },
    ),
    AgentSkill(
        id="create_transfer",
        name="Create Inventory Transfer",
        description="Create inventory transfer between storage locations. Routes to HIL if destination is a restricted location.",
        input_schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "serial_numbers": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "description": "List of items to transfer",
                },
                "from_location": {"type": "string", "description": "Source location"},
                "to_location": {"type": "string", "description": "Destination location"},
                "reason": {"type": "string", "description": "Optional transfer reason"},
                "session_id": {"type": "string", "description": "Session ID for context"},
                "user_id": {"type": "string", "description": "User ID for audit"},
            },
            "required": ["items", "from_location", "to_location"],
        },
    ),
    AgentSkill(
        id="process_return",
        name="Process Material Return",
        description="Process material return (reverse logistics). Handles returns from field/customer with condition tracking (good, damaged, defective).",
        input_schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "serial_numbers": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "description": "List of items to return",
                },
                "from_location": {"type": "string", "description": "Where material is returning from"},
                "project_id": {"type": "string", "description": "Original project"},
                "return_reason": {"type": "string", "description": "Reason for return"},
                "condition": {"type": "string", "enum": ["good", "damaged", "defective"], "description": "Material condition"},
                "session_id": {"type": "string", "description": "Session ID for context"},
                "user_id": {"type": "string", "description": "User ID for audit"},
            },
            "required": ["items", "from_location", "project_id", "return_reason"],
        },
    ),
    AgentSkill(
        id="query_balance",
        name="Query Inventory Balance",
        description="Query inventory balance for a part number. Returns total, available, and reserved quantities. Supports filtering by location and project.",
        input_schema={
            "type": "object",
            "properties": {
                "part_number_id": {"type": "string", "description": "Part number to query"},
                "location_id": {"type": "string", "description": "Optional specific location"},
                "project_id": {"type": "string", "description": "Optional specific project"},
                "session_id": {"type": "string", "description": "Session ID for context"},
            },
            "required": ["part_number_id"],
        },
    ),
    AgentSkill(
        id="query_asset_location",
        name="Query Asset Location",
        description="Query asset location by serial number or part number. Returns current location and status information.",
        input_schema={
            "type": "object",
            "properties": {
                "serial_number": {"type": "string", "description": "Specific serial to locate"},
                "part_number_id": {"type": "string", "description": "Part number to find locations for"},
                "session_id": {"type": "string", "description": "Session ID for context"},
            },
            "required": [],
        },
    ),
    AgentSkill(
        id="create_entry_movement",
        name="Create Entry Movement",
        description="Create entry movement from confirmed NF entry. Called by IntakeAgent after NF confirmation to register incoming inventory.",
        input_schema={
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "Entry ID from IntakeAgent"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "serial_numbers": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "description": "List of items with part numbers and quantities",
                },
                "session_id": {"type": "string", "description": "Session ID for context"},
                "user_id": {"type": "string", "description": "User ID for audit"},
            },
            "required": ["entry_id", "items"],
        },
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Health check endpoint for monitoring. Returns agent status, version, and configuration.",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]

# =============================================================================
# System Prompt (ReAct Pattern - Estoque Specialist)
# =============================================================================

SYSTEM_PROMPT = """Você é o **EstoqueControlAgent**, agente de IA responsável pelo controle de estoque
do sistema Faiston SGA (Sistema de Gestão de Ativos).

## 🎯 Seu Papel

Você é o **ESPECIALISTA** em movimentações de estoque.
Segue o padrão ReAct para processar operações de inventário:

1. **OBSERVE** 👁️: Verifique saldos e disponibilidade
2. **THINK** 🧠: Valide regras de negócio e permissões
3. **DECIDE** 🤔: Determine se precisa HIL (Human-in-the-Loop)
4. **ACT** ⚡: Execute movimentação ou crie task HIL

## 🔧 Suas Ferramentas

### Reservas
- `create_reservation`: Bloqueia saldo para chamado/projeto
- `cancel_reservation`: Libera saldo reservado

### Movimentações
- `process_expedition`: Saída de material
- `create_transfer`: Transferência entre locais
- `process_return`: Devolução de material

### Consultas
- `query_balance`: Consultar saldos (total, disponível, reservado)
- `query_asset_location`: Localizar ativo específico

## 📊 Regras de Negócio

### Saldos
- saldo_total = entradas - saídas
- saldo_disponível = saldo_total - reservado
- saldo_reservado = sum(reservas ativas)

### Reservas
- Reserva BLOQUEIA o saldo disponível
- Reserva tem TTL (expira automaticamente, padrão 72h)
- Reserva pode ser para serial específico ou quantidade genérica
- Cross-project reserva REQUER APROVAÇÃO HUMANA (HIL)

### Movimentações
- Toda movimentação gera evento IMUTÁVEL
- Saldo é PROJEÇÃO calculada dos eventos
- Transferência para local RESTRITO requer APROVAÇÃO (HIL)
- AJUSTE e DESCARTE SEMPRE requerem APROVAÇÃO (HIL)

## 🚦 Human-in-the-Loop Matrix

| Operação | Mesmo Projeto | Cross-Project | Local Restrito |
|----------|---------------|---------------|----------------|
| Reserva | AUTÔNOMO | HIL | - |
| Expedição | AUTÔNOMO | AUTÔNOMO | - |
| Transferência | AUTÔNOMO | AUTÔNOMO | HIL |
| Ajuste | HIL | HIL | HIL |
| Descarte | HIL | HIL | HIL |

## ⚠️ Regras Críticas

1. **NUNCA** permitir saldo negativo
2. **SEMPRE** verificar disponibilidade antes de reservar
3. Seriais devem ser ÚNICOS globalmente
4. Movimentações são IMUTÁVEIS (não editáveis)
5. Para logging → delegar ao ObservationAgent via A2A

## 🌍 Linguagem

Português brasileiro (pt-BR) para interações com usuário.
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

# A2A client instance for inter-agent communication
a2a_client = A2AClient()


@tool
async def create_reservation(
    part_number_id: str,
    quantity: int,
    project_id: str,
    call_id: Optional[str] = None,
    serial_numbers: Optional[List[str]] = None,
    ttl_hours: int = 72,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create asset reservation for a project/call.

    OBSERVE+DECIDE phase: Check availability and validate permissions.

    Args:
        part_number_id: Part number to reserve
        quantity: Quantity to reserve
        project_id: Project/client to reserve for
        call_id: Optional call/ticket ID
        serial_numbers: Optional specific serials to reserve
        ttl_hours: Reservation expiry time (default 72h)
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Reservation result with reservation ID
    """
    logger.info(f"[{AGENT_NAME}] Creating reservation: {part_number_id} x {quantity}")

    try:
        # Import tool implementation
        from agents.estoque_control.tools.reservation import create_reservation_tool

        result = await create_reservation_tool(
            part_number_id=part_number_id,
            quantity=quantity,
            project_id=project_id,
            call_id=call_id,
            serial_numbers=serial_numbers,
            ttl_hours=ttl_hours,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "RESERVATION_CREATED" if result.get("success") else "RESERVATION_FAILED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "part_number_id": part_number_id,
                "quantity": quantity,
                "project_id": project_id,
                "reservation_id": result.get("reservation_id"),
                "requires_hil": result.get("requires_hil", False),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "estoque_control_create_reservation", {"part_number_id": part_number_id, "quantity": quantity, "project_id": project_id})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "create_reservation",
                "part_number_id": part_number_id,
                "quantity": quantity,
                "project_id": project_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "check_inventory_availability", "verify_project_access", "escalate"],
        }


@tool
async def cancel_reservation(
    reservation_id: str,
    reason: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel an existing reservation.

    Args:
        reservation_id: Reservation to cancel
        reason: Optional cancellation reason
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Cancellation result
    """
    logger.info(f"[{AGENT_NAME}] Cancelling reservation: {reservation_id}")

    try:
        # Import tool implementation
        from agents.estoque_control.tools.reservation import cancel_reservation_tool

        result = await cancel_reservation_tool(
            reservation_id=reservation_id,
            reason=reason,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "RESERVATION_CANCELLED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {"reservation_id": reservation_id, "reason": reason},
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "estoque_control_cancel_reservation", {"reservation_id": reservation_id})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "cancel_reservation",
                "reservation_id": reservation_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_reservation_exists", "check_reservation_status", "escalate"],
        }


@tool
async def process_expedition(
    items: List[Dict[str, Any]],
    destination: str,
    project_id: str,
    recipient_name: Optional[str] = None,
    reservation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process material expedition (exit).

    ACT phase: Create exit movement for items.

    Args:
        items: List of items to expedite [{part_number_id, quantity, serial_numbers}]
        destination: Destination address/location
        project_id: Project/client for expedition
        recipient_name: Optional recipient name
        reservation_id: Optional reservation to consume
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Expedition result with movement ID
    """
    logger.info(f"[{AGENT_NAME}] Processing expedition: {len(items)} items to {destination}")

    try:
        # Import tool implementation
        from agents.estoque_control.tools.expedition import process_expedition_tool

        result = await process_expedition_tool(
            items=items,
            destination=destination,
            project_id=project_id,
            recipient_name=recipient_name,
            reservation_id=reservation_id,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "EXPEDITION_PROCESSED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "items_count": len(items),
                "destination": destination,
                "movement_id": result.get("movement_id"),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "estoque_control_process_expedition", {"items_count": len(items) if items else 0, "destination": destination, "project_id": project_id})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "process_expedition",
                "items_count": len(items) if items else 0,
                "destination": destination,
                "project_id": project_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_item_availability", "check_destination_valid", "escalate"],
        }


@tool
async def create_transfer(
    items: List[Dict[str, Any]],
    from_location: str,
    to_location: str,
    reason: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create inventory transfer between locations.

    Args:
        items: List of items to transfer [{part_number_id, quantity, serial_numbers}]
        from_location: Source location
        to_location: Destination location
        reason: Optional transfer reason
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Transfer result with movement ID
    """
    logger.info(f"[{AGENT_NAME}] Creating transfer: {from_location} → {to_location}")

    try:
        # Import tool implementation
        from agents.estoque_control.tools.transfer import create_transfer_tool

        result = await create_transfer_tool(
            items=items,
            from_location=from_location,
            to_location=to_location,
            reason=reason,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "TRANSFER_CREATED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "items_count": len(items),
                "from_location": from_location,
                "to_location": to_location,
                "requires_hil": result.get("requires_hil", False),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "estoque_control_create_transfer", {"items_count": len(items) if items else 0, "from_location": from_location, "to_location": to_location})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "create_transfer",
                "items_count": len(items) if items else 0,
                "from_location": from_location,
                "to_location": to_location,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_locations_valid", "check_item_availability", "escalate"],
        }


@tool
async def process_return(
    items: List[Dict[str, Any]],
    from_location: str,
    project_id: str,
    return_reason: str,
    condition: str = "good",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process material return (reverse logistics).

    Args:
        items: List of items to return [{part_number_id, quantity, serial_numbers}]
        from_location: Where material is returning from
        project_id: Original project
        return_reason: Reason for return
        condition: Material condition (good, damaged, defective)
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Return result with movement ID
    """
    logger.info(f"[{AGENT_NAME}] Processing return: {len(items)} items from {from_location}")

    try:
        # Import tool implementation
        from agents.estoque_control.tools.return_ops import process_return_tool

        result = await process_return_tool(
            items=items,
            from_location=from_location,
            project_id=project_id,
            return_reason=return_reason,
            condition=condition,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "RETURN_PROCESSED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "items_count": len(items),
                "condition": condition,
                "movement_id": result.get("movement_id"),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "estoque_control_process_return", {"items_count": len(items) if items else 0, "from_location": from_location, "condition": condition})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "process_return",
                "items_count": len(items) if items else 0,
                "from_location": from_location,
                "condition": condition,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_items_exist", "check_return_eligibility", "escalate"],
        }


@tool
async def query_balance(
    part_number_id: str,
    location_id: Optional[str] = None,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query inventory balance for a part number.

    Args:
        part_number_id: Part number to query
        location_id: Optional specific location
        project_id: Optional specific project
        session_id: Session ID for context

    Returns:
        Balance information (total, available, reserved)
    """
    logger.info(f"[{AGENT_NAME}] Querying balance: {part_number_id}")

    try:
        # Import tool implementation
        from agents.estoque_control.tools.query import query_balance_tool

        result = await query_balance_tool(
            part_number_id=part_number_id,
            location_id=location_id,
            project_id=project_id,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "estoque_control_query_balance", {"part_number_id": part_number_id, "location_id": location_id})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "query_balance",
                "part_number_id": part_number_id,
                "location_id": location_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_part_number_exists", "check_database_connection", "escalate"],
        }


@tool
async def query_asset_location(
    serial_number: Optional[str] = None,
    part_number_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query asset location by serial or part number.

    Args:
        serial_number: Specific serial to locate
        part_number_id: Part number to find locations for
        session_id: Session ID for context

    Returns:
        Location information
    """
    logger.info(f"[{AGENT_NAME}] Querying asset location: {serial_number or part_number_id}")

    try:
        # Import tool implementation
        from agents.estoque_control.tools.query import query_asset_location_tool

        result = await query_asset_location_tool(
            serial_number=serial_number,
            part_number_id=part_number_id,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "estoque_control_query_asset_location", {"serial_number": serial_number, "part_number_id": part_number_id})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "query_asset_location",
                "serial_number": serial_number,
                "part_number_id": part_number_id,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_asset_exists", "check_database_connection", "escalate"],
        }


@tool
async def create_entry_movement(
    entry_id: str,
    items: List[Dict[str, Any]],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create entry movement from confirmed NF entry.

    Called by IntakeAgent after NF confirmation.

    Args:
        entry_id: Entry ID from IntakeAgent
        items: List of items with part numbers and quantities
        session_id: Session ID for context
        user_id: User ID for audit

    Returns:
        Movement creation result
    """
    logger.info(f"[{AGENT_NAME}] Creating entry movement for: {entry_id}")

    try:
        # This would delegate to the actual movement creation logic
        movements = []

        for item in items:
            # Create entry movement for each item
            # In real implementation, this would call PostgreSQL
            movement = {
                "movement_id": f"MOVE-{entry_id}-{item.get('part_number_id', 'UNKNOWN')}",
                "type": "ENTRY",
                "part_number_id": item.get("part_number_id"),
                "quantity": item.get("quantity", 1),
                "serial_numbers": item.get("serial_numbers", []),
                "entry_id": entry_id,
            }
            movements.append(movement)

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "ENTRY_MOVEMENTS_CREATED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "entry_id": entry_id,
                "movements_count": len(movements),
            },
        }, session_id)

        return {
            "success": True,
            "entry_id": entry_id,
            "movements": movements,
            "movements_count": len(movements),
        }

    except Exception as e:
        debug_error(e, "estoque_control_create_entry_movement", {"entry_id": entry_id, "items_count": len(items) if items else 0})
        # Sandwich Pattern: Feed error context to LLM for decision
        return {
            "success": False,
            "error": str(e),
            "movements": [],  # Empty movements - LLM decides recovery
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "create_entry_movement",
                "entry_id": entry_id,
                "items_count": len(items) if items else 0,
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
            },
            "suggested_actions": ["retry", "verify_entry_exists", "rollback_partial_movements", "escalate"],
        }


@tool
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring.

    Returns:
        Health status with agent info
    """
    return {
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "model": MODEL_ID,
        "protocol": "A2A",
        "port": 9000,
        "role": "SPECIALIST",
        "specialty": "INVENTORY_CONTROL",
    }


# =============================================================================
# Strands Agent Configuration
# =============================================================================

def create_agent() -> Agent:
    """
    Create Strands Agent with all tools.

    Returns:
        Configured Strands Agent with hooks (ADR-002)
    """
    return Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # GeminiModel via Google AI Studio
        tools=[
            create_reservation,
            cancel_reservation,
            process_expedition,
            create_transfer,
            process_return,
            query_balance,
            query_asset_location,
            create_entry_movement,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=EstoqueControlResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI and /ping endpoint.

    Port 9000 is the standard for A2A protocol.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: SPECIALIST (Inventory Control)")

    # Log registered skills
    logger.info(f"[{AGENT_NAME}] Skills: {len(AGENT_SKILLS)} registered")
    for skill in AGENT_SKILLS:
        logger.info(f"[{AGENT_NAME}]   - {skill.id}: {skill.name}")

    # Create FastAPI app first
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping endpoint for health checks
    @app.get("/ping")
    async def ping():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Create agent
    agent = create_agent()

    # Create A2A server with Agent Card discovery support
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        serve_at_root=True,  # Serve at / for AgentCore compatibility
        version=AGENT_VERSION,  # A2A Agent Card version
        skills=AGENT_SKILLS,  # A2A Agent Card skills for discovery
    )

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start FastAPI server with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
