# =============================================================================
# Process Entry Tool
# =============================================================================
# Creates pending entry record with confidence scoring and HIL routing.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "intake"
audit = AgentAuditEmitter(agent_id=AGENT_ID)

# Constants
HIGH_VALUE_THRESHOLD = 5000.0  # R$
MIN_CONFIDENCE_AUTONOMOUS = 0.80


@trace_tool_call("sga_process_entry")
async def process_entry_tool(
    extraction: Dict[str, Any],
    matched_items: List[Dict[str, Any]],
    unmatched_items: List[Dict[str, Any]],
    project_id: str = "",
    destination_location_id: str = "ESTOQUE_CENTRAL",
    uploaded_by: str = "system",
    s3_key: str = "",
    file_type: str = "xml",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create pending entry record from NF extraction.

    Calculates confidence score and routes to HIL if needed.

    Args:
        extraction: NF extraction data
        matched_items: Items with matched part numbers
        unmatched_items: Items without matches
        project_id: Optional project ID
        destination_location_id: Destination location
        uploaded_by: User who uploaded
        s3_key: S3 key of original file
        file_type: File type (xml, pdf, image)
        session_id: Optional session ID for audit

    Returns:
        Entry creation result
    """
    audit.working(
        message="Criando entrada...",
        session_id=session_id,
    )

    try:
        # Generate IDs
        entry_id = _generate_id("ENT")
        nf_id = extraction.get("chave_acesso") or _generate_id("NF")
        now = _now_iso()

        # Calculate confidence score
        confidence = _calculate_confidence(
            extraction=extraction,
            matched_count=len(matched_items),
            total_count=len(matched_items) + len(unmatched_items),
        )

        # Determine status based on requirements
        requires_project = not project_id or project_id.strip() == ""
        requires_hil = _check_requires_hil(
            confidence=confidence,
            extraction=extraction,
            unmatched_items=unmatched_items,
        )

        if requires_project:
            status = "PENDING_PROJECT"
        elif requires_hil:
            status = "PENDING_APPROVAL"
        else:
            status = "PENDING_CONFIRMATION"

        # Create entry record
        entry_data = {
            "entry_id": entry_id,
            "nf_id": nf_id,
            "nf_numero": extraction.get("numero"),
            "nf_serie": extraction.get("serie"),
            "nf_chave": extraction.get("chave_acesso"),
            "emitente_cnpj": extraction.get("emitente", {}).get("cnpj"),
            "emitente_nome": extraction.get("emitente", {}).get("nome"),
            "destinatario_cnpj": extraction.get("destinatario", {}).get("cnpj"),
            "data_emissao": extraction.get("data_emissao"),
            "valor_total": extraction.get("valor_total", 0),
            "project_id": project_id if project_id else None,
            "destination_location_id": destination_location_id,
            "status": status,
            "matched_items": matched_items,
            "unmatched_items": unmatched_items,
            "confidence_score": confidence["overall"],
            "confidence_factors": confidence["factors"],
            "s3_key": s3_key,
            "file_type": file_type,
            "uploaded_by": uploaded_by,
            "created_at": now,
            "requires_project": requires_project,
        }

        # Store entry in database
        await _store_entry(entry_data)

        # Create HIL tasks if needed
        hil_task_id = None
        project_task_id = None

        if requires_project:
            project_task_id = await _create_project_request_task(
                entry_data=entry_data,
                extraction=extraction,
                uploaded_by=uploaded_by,
                session_id=session_id,
            )

        if requires_hil and not requires_project:
            hil_task_id = await _create_review_task(
                entry_data=entry_data,
                extraction=extraction,
                confidence=confidence,
                matched_items=matched_items,
                unmatched_items=unmatched_items,
                uploaded_by=uploaded_by,
                session_id=session_id,
            )

        # Determine message
        if requires_project:
            message = "NF processada, aguardando atribuição de projeto"
        elif requires_hil:
            message = "NF processada, aguardando revisão"
        else:
            message = "NF processada, pronta para confirmação"

        audit.completed(
            message=message,
            session_id=session_id,
            details={
                "entry_id": entry_id,
                "status": status,
                "confidence": confidence["overall"],
            },
        )

        return {
            "success": True,
            "entry_id": entry_id,
            "nf_id": nf_id,
            "status": status,
            "message": message,
            "confidence": confidence,
            "requires_hil": requires_hil or requires_project,
            "hil_task_id": hil_task_id or project_task_id,
            "items_processed": len(matched_items),
            "items_pending": len(unmatched_items),
        }

    except Exception as e:
        logger.error(f"[process_entry] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao criar entrada",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }


def _calculate_confidence(
    extraction: Dict[str, Any],
    matched_count: int,
    total_count: int,
) -> Dict[str, Any]:
    """
    Calculate confidence score for the entry.
    """
    factors = []

    # Extraction quality
    extraction_quality = extraction.get("confidence", 0.5)
    if extraction_quality < 0.8:
        factors.append("low_extraction_quality")

    # Match ratio
    match_ratio = matched_count / total_count if total_count > 0 else 0
    if match_ratio < 0.5:
        factors.append("many_unmatched_items")

    # High value
    valor_total = extraction.get("valor_total", 0)
    if valor_total > HIGH_VALUE_THRESHOLD:
        factors.append("high_value_entry")

    # Missing access key
    if not extraction.get("chave_acesso"):
        factors.append("missing_access_key")

    # Calculate overall score
    # Base = extraction quality * 0.4 + match ratio * 0.4 + 0.2 (base)
    overall = (extraction_quality * 0.4) + (match_ratio * 0.4) + 0.2

    # Penalty for risk factors
    penalty = len(factors) * 0.05
    overall = max(0.3, overall - penalty)

    # Determine risk level
    if overall >= 0.9:
        risk_level = "LOW"
    elif overall >= 0.8:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    return {
        "overall": round(overall, 2),
        "factors": factors,
        "risk_level": risk_level,
        "extraction_quality": extraction_quality,
        "match_ratio": match_ratio,
    }


def _check_requires_hil(
    confidence: Dict[str, Any],
    extraction: Dict[str, Any],
    unmatched_items: List[Dict[str, Any]],
) -> bool:
    """
    Check if HIL is required for this entry.
    """
    # Always HIL for unmatched items
    if unmatched_items:
        return True

    # HIL if low confidence
    if confidence["overall"] < MIN_CONFIDENCE_AUTONOMOUS:
        return True

    # HIL for high value
    if extraction.get("valor_total", 0) > HIGH_VALUE_THRESHOLD:
        return True

    return False


async def _store_entry(entry_data: Dict[str, Any]) -> None:
    """
    Store entry in database.

    BUG-022 v9 FIX (CRITICAL-A2): This function MUST raise on failure.
    Silent failures cause NF entries to be lost without user awareness.
    """
    try:
        from tools.db_client import DBClient

        db = DBClient()
        await db.put_entry(entry_data)

    except ImportError:
        # BUG-022 v9 FIX: NEVER swallow ImportError - this causes silent data loss!
        logger.error(
            "[process_entry] CRITICAL: DBClient not available - entry NOT persisted! "
            "entry_id=%s",
            entry_data.get("entry_id", "unknown"),
        )
        raise RuntimeError(
            "Database client not available - entry cannot be stored. "
            "This is a critical infrastructure error."
        )

    except Exception as e:
        logger.error(f"[process_entry] Failed to store entry: {e}")
        raise


async def _create_project_request_task(
    entry_data: Dict[str, Any],
    extraction: Dict[str, Any],
    uploaded_by: str,
    session_id: Optional[str],
) -> Optional[str]:
    """Create HIL task for project assignment."""
    try:
        from tools.hil_workflow import HILWorkflowManager
        hil = HILWorkflowManager()

        task = await hil.create_task(
            task_type="NEW_PROJECT_REQUEST",
            title=f"Atribuir projeto para NF: {extraction.get('numero', 'N/A')}",
            description=_format_project_request_message(entry_data, extraction),
            entity_type="NF_ENTRY",
            entity_id=entry_data["entry_id"],
            requested_by=uploaded_by,
            priority="HIGH",
            assigned_role="FINANCE_OPERATOR",
        )

        return task.get("task_id")

    except Exception as e:
        logger.warning(f"[process_entry] Failed to create project task: {e}")
        return None


async def _create_review_task(
    entry_data: Dict[str, Any],
    extraction: Dict[str, Any],
    confidence: Dict[str, Any],
    matched_items: List[Dict[str, Any]],
    unmatched_items: List[Dict[str, Any]],
    uploaded_by: str,
    session_id: Optional[str],
) -> Optional[str]:
    """Create HIL task for entry review."""
    try:
        from tools.hil_workflow import HILWorkflowManager
        hil = HILWorkflowManager()

        task_type = "APPROVAL_ENTRY" if unmatched_items else "REVIEW_ENTRY"

        task = await hil.create_task(
            task_type=task_type,
            title=f"Revisar entrada NF: {extraction.get('numero', 'N/A')}",
            description=_format_review_message(
                extraction, confidence, matched_items, unmatched_items
            ),
            entity_type="NF_ENTRY",
            entity_id=entry_data["entry_id"],
            requested_by=uploaded_by,
            priority="HIGH" if unmatched_items else "MEDIUM",
        )

        return task.get("task_id")

    except Exception as e:
        logger.warning(f"[process_entry] Failed to create review task: {e}")
        return None


def _format_project_request_message(
    entry_data: Dict[str, Any],
    extraction: Dict[str, Any],
) -> str:
    """Format project request HIL message."""
    items = extraction.get("items", [])
    items_summary = "\n".join([
        f"- {item.get('descricao', 'N/A')[:60]}"
        for item in items[:5]
    ])
    if len(items) > 5:
        items_summary += f"\n- ... e mais {len(items) - 5} itens"

    return f"""## Solicitação de Atribuição de Projeto

### Contexto
NF recebida **SEM projeto atribuído**.

### Dados da NF
- **Entry ID**: `{entry_data['entry_id']}`
- **Número**: {extraction.get('numero', 'N/A')} / Série: {extraction.get('serie', 'N/A')}
- **Chave**: {extraction.get('chave_acesso', 'N/A')}

### Fornecedor
- **Nome**: {extraction.get('emitente', {}).get('nome', 'N/A')}
- **CNPJ**: {extraction.get('emitente', {}).get('cnpj', 'N/A')}

### Valor e Itens
- **Valor Total**: R$ {extraction.get('valor_total', 0):,.2f}
- **Quantidade**: {len(items)} itens

### Itens
{items_summary}

### Ações
1. Identificar projeto no SAP
2. Criar projeto se necessário
3. Atribuir a esta entrada
"""


def _format_review_message(
    extraction: Dict[str, Any],
    confidence: Dict[str, Any],
    matched_items: List[Dict[str, Any]],
    unmatched_items: List[Dict[str, Any]],
) -> str:
    """Format entry review HIL message."""
    matched_summary = "\n".join([
        f"- {item.get('descricao', 'N/A')[:40]} -> **{item.get('matched_pn')}** ({item.get('match_confidence', 0):.0%})"
        for item in matched_items[:5]
    ])

    unmatched_summary = ""
    if unmatched_items:
        unmatched_summary = "\n".join([
            f"- {item.get('descricao', 'N/A')[:40]} (Sugestão: **{item.get('suggested_pn')}**)"
            for item in unmatched_items[:5]
        ])

    return f"""## Revisão de Entrada NF

### Dados da NF
- **Número**: {extraction.get('numero', 'N/A')} / Série: {extraction.get('serie', 'N/A')}
- **Emitente**: {extraction.get('emitente', {}).get('nome', 'N/A')}
- **Valor Total**: R$ {extraction.get('valor_total', 0):,.2f}

### Confiança
- **Score**: {confidence['overall']:.0%}
- **Risco**: {confidence['risk_level']}
- **Fatores**: {', '.join(confidence['factors']) or 'Nenhum'}

### Itens Identificados ({len(matched_items)})
{matched_summary}
{f'... e mais {len(matched_items) - 5}' if len(matched_items) > 5 else ''}

### Itens NÃO Identificados ({len(unmatched_items)}) {'- REQUER AÇÃO' if unmatched_items else ''}
{unmatched_summary or 'Todos identificados.'}

### Ações
- **Aprovar**: Confirmar entrada
- **Rejeitar**: Cancelar
- **Modificar**: Ajustar mapeamentos
"""


def _generate_id(prefix: str) -> str:
    """Generate unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
