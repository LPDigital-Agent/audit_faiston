# =============================================================================
# Agent Event Humanizer - Faiston SGA Agent Room
# =============================================================================
# Transforms technical agent events into humanized Portuguese messages.
# Used by the Agent Room "Sala de Transparencia" to show user-friendly
# explanations of what AI agents are doing behind the scenes.
#
# Design Philosophy:
# - First-person perspective ("Estou analisando...", "Encontrei...")
# - Simple, non-technical language
# - Positive and helpful tone
# - Connect users emotionally with the AI
# =============================================================================

from datetime import datetime
from typing import Optional


# =============================================================================
# Agent Name Mapping (Technical -> Friendly)
# =============================================================================

AGENT_FRIENDLY_NAMES = {
    # Core Import Agents
    "NexoImportAgent": "NEXO",
    "nexo_import": "NEXO",
    "nexo_import_agent": "NEXO",
    "IntakeAgent": "Leitor de Notas",
    "intake": "Leitor de Notas",
    "intake_agent": "Leitor de Notas",
    "ImportAgent": "Importador",
    "data_import": "Importador",  # Renamed from "import" (Python reserved word)
    "import_agent": "Importador",

    # Validation & Compliance
    "ComplianceAgent": "Validador",
    "compliance": "Validador",
    "compliance_agent": "Validador",
    "SchemaEvolutionAgent": "Arquiteto",
    "schema_evolution": "Arquiteto",
    "sea": "Arquiteto",

    # Learning & Memory
    "LearningAgent": "Memoria",
    "learning": "Memoria",
    "learning_agent": "Memoria",

    # Inventory Operations
    "EstoqueControlAgent": "Controlador",
    "estoque_control": "Controlador",
    "estoque": "Controlador",

    # Communication
    "ComunicacaoAgent": "Comunicador",
    "comunicacao": "Comunicador",

    # Observation & Research
    "ObservationAgent": "Observador",
    "observation": "Observador",
    "observation_agent": "Observador",
    # AUDIT-004/2: equipment_research removed - dead code replaced by enrichment agent
    # BUG-025: Strands structured output agents
    "FileAnalyzer": "Analisador",
    "file_analyzer": "Analisador",
    "VisionAnalyzer": "Visão",
    "vision_analyzer": "Visão",

    # NEXO Chat
    "NexoEstoqueAgent": "NEXO Estoque",
    "nexo_estoque": "NEXO Estoque",

    # Default
    "system": "Sistema",
    "unknown": "Assistente",
}

AGENT_DESCRIPTIONS = {
    "NEXO": "Seu assistente principal de importacao",
    "Leitor de Notas": "Le e entende notas fiscais",
    "Importador": "Traz seus dados para o sistema",
    "Validador": "Verifica se tudo esta correto",
    "Arquiteto": "Adapta o sistema aos seus dados",
    "Memoria": "Aprende com cada interacao",
    "Controlador": "Cuida do estoque",
    "Comunicador": "Envia notificacoes",
    "NEXO Estoque": "Responde suas perguntas sobre estoque",
    "Observador": "Monitora mudancas no estoque",
    "Pesquisador": "Busca informacoes de equipamentos",
    "Sistema": "Operacoes automaticas",
    "Assistente": "Ajuda geral",
}


# =============================================================================
# Status Mapping (Technical -> Friendly)
# =============================================================================

STATUS_FRIENDLY = {
    "idle": "disponivel",
    "processing": "trabalhando",
    "pending_hil": "esperando_voce",
    "error": "problema",
    "inactive": "descansando",
    "waiting": "esperando_voce",
    "running": "trabalhando",
    "completed": "disponivel",
    "failed": "problema",
}

STATUS_LABELS = {
    "disponivel": "Disponivel",
    "trabalhando": "Trabalhando...",
    "esperando_voce": "Esperando voce",
    "problema": "Encontrou um problema",
    "descansando": "Descansando",
}


# =============================================================================
# Event Message Templates (Portuguese, First Person)
# =============================================================================

EVENT_TEMPLATES = {
    # File Processing
    "file_received": "Recebi o arquivo {filename}. Vou analisar agora!",
    "file_analyzing": "Estou analisando o arquivo {filename}...",
    "file_analyzed": "Terminei de analisar! Encontrei {count} itens.",
    "file_error": "Ops! Tive um problema ao ler o arquivo: {error}",

    # NF Processing (IntakeAgent)
    "nf_received": "Recebi a nota fiscal. Vou extrair os dados!",
    "nf_extracting": "Estou lendo a nota fiscal {nf_number}...",
    "nf_extracted": "Encontrei {count} itens na nota fiscal {nf_number}.",
    "nf_validation_needed": "Preciso que voce confirme alguns dados da nota {nf_number}.",
    "nf_confirmed": "Perfeito! Nota fiscal {nf_number} confirmada.",

    # Import Processing
    "import_started": "Comecando a importacao de {count} itens...",
    "import_progress": "Ja importei {done} de {total} itens.",
    "import_completed": "Pronto! {count} itens foram importados com sucesso.",
    "import_partial": "Importei {success} itens. {failed} precisam de atencao.",

    # Schema Evolution
    "schema_analyzing": "Estou analisando a estrutura dos seus dados...",
    "schema_column_created": "Criei uma nova coluna '{column}' para seus dados.",
    "schema_adapted": "Adaptei o sistema para receber seus dados.",

    # HIL (Human-in-the-Loop)
    "hil_created": "Preciso da sua ajuda com: {description}",
    "hil_waiting": "Aguardando sua decisao sobre: {description}",
    "hil_approved": "Obrigado! Voce aprovou: {description}",
    "hil_rejected": "Entendido. Voce rejeitou: {description}",

    # Validation
    "validation_started": "Estou validando os dados...",
    "validation_passed": "Tudo certo! Os dados estao corretos.",
    "validation_issues": "Encontrei {count} itens que precisam de atencao.",

    # Movement Operations
    "movement_created": "Registrei a movimentacao: {type} de {quantity} {unit}.",
    "reservation_created": "Criei uma reserva de {quantity} itens.",
    "transfer_completed": "Transferencia de {location_from} para {location_to} concluida.",

    # Search & Query
    "search_started": "Procurando por '{query}'...",
    "search_completed": "Encontrei {count} resultados para '{query}'.",
    "search_no_results": "Nao encontrei resultados para '{query}'.",

    # Learning
    "learning_pattern": "Aprendi que {pattern}.",
    "learning_preference": "Notei que voce prefere {preference}.",
    "learning_format": "Reconheco esse formato de arquivo agora.",

    # General
    "task_started": "Comecando: {task}",
    "task_completed": "Terminei: {task}",
    "task_error": "Encontrei um problema: {error}",
    "heartbeat": "Tudo funcionando normalmente.",
}


# =============================================================================
# Humanization Functions
# =============================================================================

def get_friendly_agent_name(technical_name: str) -> str:
    """
    Convert technical agent name to user-friendly name.

    Args:
        technical_name: Technical agent identifier

    Returns:
        Friendly name in Portuguese
    """
    if not technical_name:
        return "Assistente"

    # Try exact match first
    if technical_name in AGENT_FRIENDLY_NAMES:
        return AGENT_FRIENDLY_NAMES[technical_name]

    # Try lowercase
    lower_name = technical_name.lower()
    if lower_name in AGENT_FRIENDLY_NAMES:
        return AGENT_FRIENDLY_NAMES[lower_name]

    # Try to find partial match
    for key, value in AGENT_FRIENDLY_NAMES.items():
        if key.lower() in lower_name or lower_name in key.lower():
            return value

    return "Assistente"


def get_agent_description(friendly_name: str) -> str:
    """
    Get description for an agent by its friendly name.

    Args:
        friendly_name: Friendly agent name

    Returns:
        Description in Portuguese
    """
    return AGENT_DESCRIPTIONS.get(friendly_name, "Ajuda com tarefas")


def get_friendly_status(technical_status: str) -> str:
    """
    Convert technical status to user-friendly status.

    Args:
        technical_status: Technical status string

    Returns:
        Friendly status key
    """
    if not technical_status:
        return "disponivel"

    lower_status = technical_status.lower()
    return STATUS_FRIENDLY.get(lower_status, "disponivel")


def get_status_label(friendly_status: str) -> str:
    """
    Get display label for a friendly status.

    Args:
        friendly_status: Friendly status key

    Returns:
        Human-readable label in Portuguese
    """
    return STATUS_LABELS.get(friendly_status, "Disponivel")


def humanize_event(
    event_type: str,
    agent_name: Optional[str] = None,
    data: Optional[dict] = None
) -> dict:
    """
    Transform a technical event into a humanized message.

    Args:
        event_type: Type of event (e.g., "file_received", "import_completed")
        agent_name: Technical agent name (optional)
        data: Event data for template substitution

    Returns:
        Humanized event dict with:
        - agent: Friendly agent name
        - message: Humanized message in Portuguese
        - type: Message type (info, success, warning, action_needed)
        - timestamp: ISO timestamp
    """
    data = data or {}

    # Get friendly agent name
    friendly_agent = get_friendly_agent_name(agent_name) if agent_name else "Sistema"

    # Get message template
    template = EVENT_TEMPLATES.get(event_type, "Trabalhando...")

    # Substitute data into template
    try:
        message = template.format(**data)
    except KeyError:
        # If template has missing keys, use template as-is with placeholders
        message = template

    # Determine message type based on event
    message_type = _get_message_type(event_type)

    return {
        "agent": friendly_agent,
        "message": message,
        "type": message_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
    }


def humanize_audit_entry(audit_entry: dict) -> dict:
    """
    Convert a DynamoDB audit log entry into a humanized Agent Room message.

    Args:
        audit_entry: Raw audit log entry from DynamoDB

    Returns:
        Humanized message dict for Agent Room
    """
    event_type_raw = audit_entry.get("event_type", "")
    action = audit_entry.get("action", "unknown")
    entity_type = audit_entry.get("entity_type", "")
    details = audit_entry.get("details", {})
    actor_id = audit_entry.get("actor_id", "system")
    timestamp = audit_entry.get("timestamp", datetime.utcnow().isoformat())

    # Special handling for AGENT_ACTIVITY events (from emit_agent_event)
    # These already have humanized messages in the details
    if event_type_raw == "AGENT_ACTIVITY":
        agent_id = details.get("agent_id", actor_id)
        friendly_name = get_friendly_agent_name(agent_id)
        status = details.get("status", "trabalhando")
        message = details.get("message", "Trabalhando...")

        # Determine message type from status
        if status in ("esperando_voce", "pending_hil"):
            msg_type = "action_needed"
        elif status in ("disponivel", "completed", "idle"):
            msg_type = "success"
        elif status in ("problema", "error"):
            msg_type = "warning"
        else:
            msg_type = "info"

        return {
            "agent": friendly_name,
            "message": message,
            "type": msg_type,
            "timestamp": timestamp,
            "event_type": "agent_activity",
            "audit_id": audit_entry.get("event_id", ""),
        }

    # Standard humanization for other event types
    # Map audit actions to event types
    event_type = _map_audit_action_to_event(action, entity_type)

    # Extract relevant data for humanization
    data = _extract_humanization_data(action, entity_type, details)

    # Get agent name from actor or details
    agent_name = details.get("agent") or _infer_agent_from_action(action)

    humanized = humanize_event(event_type, agent_name, data)
    humanized["timestamp"] = timestamp
    humanized["audit_id"] = audit_entry.get("id", audit_entry.get("event_id", ""))

    return humanized


def _get_message_type(event_type: str) -> str:
    """Determine message type from event type."""
    if "error" in event_type or "failed" in event_type:
        return "warning"
    if "completed" in event_type or "success" in event_type or "confirmed" in event_type:
        return "success"
    if "hil" in event_type or "waiting" in event_type or "needed" in event_type:
        return "action_needed"
    return "info"


def _map_audit_action_to_event(action: str, entity_type: str) -> str:
    """Map audit action to humanization event type."""
    action_lower = action.lower()

    # Import actions
    if "import" in action_lower:
        if "start" in action_lower:
            return "import_started"
        if "complete" in action_lower:
            return "import_completed"
        return "import_progress"

    # NF actions
    if "nf" in action_lower or entity_type.lower() == "nf":
        if "extract" in action_lower:
            return "nf_extracted"
        if "confirm" in action_lower:
            return "nf_confirmed"
        return "nf_received"

    # HIL actions
    if "hil" in action_lower or "task" in action_lower:
        if "approve" in action_lower:
            return "hil_approved"
        if "reject" in action_lower:
            return "hil_rejected"
        if "create" in action_lower:
            return "hil_created"
        return "hil_waiting"

    # Movement actions
    if "movement" in action_lower or entity_type.lower() == "movement":
        return "movement_created"

    # Schema actions
    if "schema" in action_lower or "column" in action_lower:
        if "create" in action_lower:
            return "schema_column_created"
        return "schema_adapted"

    # Search actions
    if "search" in action_lower:
        return "search_completed"

    # Default
    if "error" in action_lower:
        return "task_error"
    if "complete" in action_lower:
        return "task_completed"
    return "task_started"


def _extract_humanization_data(action: str, entity_type: str, details: dict) -> dict:
    """Extract data for template substitution from audit details."""
    data = {}

    # Count fields
    for key in ["count", "total", "items", "success", "failed", "done"]:
        if key in details:
            data[key] = details[key]

    # Identifiers
    for key in ["filename", "nf_number", "query", "column", "description", "task"]:
        if key in details:
            data[key] = details[key]

    # Movement specific
    if "type" in details:
        data["type"] = details["type"]
    if "quantity" in details:
        data["quantity"] = details["quantity"]
    if "unit" in details:
        data["unit"] = details.get("unit", "unidades")

    # Location
    if "location_from" in details:
        data["location_from"] = details["location_from"]
    if "location_to" in details:
        data["location_to"] = details["location_to"]

    # Error
    if "error" in details:
        data["error"] = details["error"]

    return data


def _infer_agent_from_action(action: str) -> str:
    """Infer agent name from action type."""
    action_lower = action.lower()

    if "nexo" in action_lower:
        return "NexoImportAgent"
    if "intake" in action_lower or "nf" in action_lower:
        return "IntakeAgent"
    if "import" in action_lower:
        return "ImportAgent"
    if "compliance" in action_lower or "validat" in action_lower:
        return "ComplianceAgent"
    if "schema" in action_lower or "column" in action_lower:
        return "SchemaEvolutionAgent"
    if "movement" in action_lower or "estoque" in action_lower:
        return "EstoqueControlAgent"

    return "system"
