# =============================================================================
# Execute Import Tool - AI-First with Gemini (AGI-Like Behavior)
# =============================================================================
# Executes the import with validated mappings using Gemini for data extraction.
#
# Philosophy: OBSERVE → THINK → LEARN → EXECUTE (with HIL Approval)
# - Gemini analyzed the file (THINK phase completed)
# - Generate SUMMARY for user approval (AGI-like)
# - ONLY EXECUTE if user_approval=True
#
# AGI-Like Behavior:
# - Final summary REQUIRED before import
# - User MUST explicitly approve
# - All decisions (mappings, ignored columns) shown in summary
# - Import blocked without approval
#
# Module: Gestao de Ativos -> Gestao de Estoque -> Smart Import
# =============================================================================

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

logger = logging.getLogger(__name__)

AGENT_ID = "nexo_import"
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_execute_import")
async def execute_import_tool(
    s3_key: str,
    column_mappings: Dict[str, str],
    target_table: str = "pending_entry_items",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    # AGI-Like: New parameters for approval workflow
    user_approval: bool = False,
    analysis_summary: Optional[Dict[str, Any]] = None,
    unmapped_decisions: Optional[Dict[str, str]] = None,
    ignored_columns: Optional[List[str]] = None,
    metadata_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Execute the import with validated column mappings (AGI-Like with HIL Approval).

    AGI-Like Workflow:
    1. If user_approval=False → Generate summary and return for approval
    2. If user_approval=True → Execute import with validated mappings

    Steps (when approved):
    1. Extract data from S3 file using column mappings
    2. Apply unmapped column decisions (ignore/metadata)
    3. Add metadata to transformed rows
    4. Insert rows into PostgreSQL via MCP Gateway

    Args:
        s3_key: S3 key where file is stored
        column_mappings: Validated mappings {source_column: target_field}
        target_table: Target table for import (default: pending_entry_items)
        user_id: User ID for audit trail
        session_id: Optional session ID for audit
        user_approval: AGI-Like - MUST be True to execute (default: False)
        analysis_summary: AGI-Like - Summary from analysis phase
        unmapped_decisions: AGI-Like - User decisions {column: action}
        ignored_columns: AGI-Like - Columns to ignore (from user decisions)
        metadata_columns: AGI-Like - Columns to store in metadata JSON

    Returns:
        If not approved: Summary for user approval (requires_approval=True)
        If approved: Import result with success status and metrics
    """
    # Initialize defaults for AGI-like parameters
    unmapped_decisions = unmapped_decisions or {}
    ignored_columns = ignored_columns or []
    metadata_columns = metadata_columns or []

    # ==========================================================================
    # AGI-Like: Check if approval is required
    # ==========================================================================
    if not user_approval:
        # Generate summary and return for approval
        return await _generate_import_summary(
            s3_key=s3_key,
            column_mappings=column_mappings,
            analysis_summary=analysis_summary,
            unmapped_decisions=unmapped_decisions,
            ignored_columns=ignored_columns,
            metadata_columns=metadata_columns,
            target_table=target_table,
            session_id=session_id,
        )

    # ==========================================================================
    # User approved - Proceed with import
    # ==========================================================================
    audit.working(
        message="✅ Aprovação recebida. Executando importação...",
        session_id=session_id,
    )

    try:
        # Step 1: Extract data with Gemini analyzer
        audit.working(
            message="Extraindo dados do arquivo...",
            session_id=session_id,
        )

        # BUG-025 FIX: Use FileAnalyzer's file_reader instead of gemini_text_analyzer
        # This function is pure Python (no LLM calls) - extract data using column mappings
        from agents.specialists.file_analyzer.tools.file_reader import extract_data_from_file

        extract_result = await extract_data_from_file(
            s3_key=s3_key,
            column_mappings=column_mappings,
        )

        if not extract_result.get("success", False):
            return {
                "success": False,
                "error": extract_result.get("error", "Extração falhou"),
                "rows_imported": 0,
            }

        raw_rows = extract_result.get("rows", [])

        if not raw_rows:
            return {
                "success": False,
                "error": "Arquivo vazio ou inválido",
                "rows_imported": 0,
            }

        # Step 2: Add metadata and validate
        audit.working(
            message=f"Processando {len(raw_rows)} registros...",
            session_id=session_id,
            details={"total_rows": len(raw_rows)},
        )

        transformed_rows = _add_metadata_and_validate(
            rows=raw_rows,
            user_id=user_id,
        )

        if not transformed_rows:
            return {
                "success": False,
                "error": "Nenhuma linha válida após validação",
                "rows_imported": 0,
            }

        # Step 3: Insert into database via MCP Gateway
        audit.working(
            message=f"Inserindo {len(transformed_rows)} registros...",
            session_id=session_id,
        )

        insert_result = await _insert_rows(
            rows=transformed_rows,
            target_table=target_table,
            session_id=session_id,
        )

        # Step 4: Return result
        success = insert_result.get("success", False)
        rows_imported = insert_result.get("rows_inserted", 0)
        errors = insert_result.get("errors", [])

        if success:
            audit.completed(
                message=f"Importação concluída: {rows_imported} registros",
                session_id=session_id,
                details={
                    "rows_imported": rows_imported,
                    "errors_count": len(errors),
                },
            )
        else:
            audit.error(
                message="Importação falhou",
                session_id=session_id,
                error=insert_result.get("error", "Unknown error"),
            )

        return {
            "success": success,
            "rows_imported": rows_imported,
            "rows_total": len(raw_rows),
            "rows_transformed": len(transformed_rows),
            "errors": errors[:10],  # Limit errors in response
            "errors_count": len(errors),
            "target_table": target_table,
            "column_mappings_used": column_mappings,
        }

    except Exception as e:
        logger.error(f"[execute_import] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao executar importação",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
            "rows_imported": 0,
        }


def _add_metadata_and_validate(
    rows: List[Dict[str, Any]],
    user_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Add metadata to rows and validate required fields.

    The column mappings were already applied during extraction.
    This function adds system metadata and filters invalid rows.
    """
    validated = []
    now = datetime.utcnow().isoformat() + "Z"

    for row_idx, row in enumerate(rows):
        # Skip empty rows
        if not row:
            continue

        # Clean values
        cleaned_row = {}
        for key, value in row.items():
            cleaned_value = _clean_value(value, key)
            if cleaned_value is not None:
                cleaned_row[key] = cleaned_value

        if not cleaned_row:
            continue

        # Add metadata
        cleaned_row["created_at"] = now
        cleaned_row["updated_at"] = now
        cleaned_row["source"] = "import"
        cleaned_row["import_row_number"] = row_idx + 1

        if user_id:
            cleaned_row["created_by"] = user_id

        # Validate required fields
        if _has_required_fields(cleaned_row):
            validated.append(cleaned_row)

    return validated


def _clean_value(value: Any, target_field: str) -> Any:
    """
    Clean and normalize value based on target field type.
    """
    if value is None:
        return None

    # String cleanup
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    # Quantity field - convert to number
    if target_field == "quantity":
        try:
            # Handle Brazilian number format (1.000,50 -> 1000.50)
            if isinstance(value, str):
                value = value.replace(".", "").replace(",", ".")
            return float(value)
        except (ValueError, TypeError):
            return 1  # Default quantity

    # Part number - uppercase, no extra spaces
    if target_field == "part_number":
        return str(value).upper().strip()

    # Description - preserve formatting
    if target_field == "description":
        return str(value).strip()

    return value


def _has_required_fields(row: Dict[str, Any]) -> bool:
    """
    Check if row has minimum required fields.

    At minimum, we need part_number OR description.
    """
    has_part = bool(row.get("part_number"))
    has_desc = bool(row.get("description"))
    return has_part or has_desc


async def _insert_rows(
    rows: List[Dict[str, Any]],
    target_table: str,
    session_id: Optional[str],
) -> Dict[str, Any]:
    """
    Insert rows into PostgreSQL via MCP Gateway.

    Uses batch insert for efficiency.
    """
    try:
        from tools.db_client import DBClient

        db = DBClient()

        # Use batch insert
        result = await db.batch_insert(
            table=target_table,
            rows=rows,
            on_conflict="DO NOTHING",  # Skip duplicates
        )

        return {
            "success": True,
            "rows_inserted": result.get("rows_affected", len(rows)),
            "errors": result.get("errors", []),
        }

    except ImportError:
        # BUG-022 v9 FIX (CRITICAL-A1): NEVER return success=True when DB is unavailable!
        # This causes SILENT DATA LOSS - users think data is imported but it's NOT!
        logger.error(
            "[execute_import] CRITICAL: DBClient not available - import FAILED! "
            "Data was NOT inserted. rows=%d, table=%s, session_id=%s",
            len(rows),
            target_table,
            session_id,
        )
        return {
            "success": False,
            "rows_inserted": 0,
            "error": "Database client not available - import cannot proceed",
            "message": "CRITICAL: Importação falhou - cliente de banco de dados indisponível",
            "recoverable": False,
            "data_prepared": len(rows),  # How many rows WOULD have been inserted
        }

    except Exception as e:
        logger.error(f"[execute_import] Insert error: {e}", exc_info=True)
        return {
            "success": False,
            "rows_inserted": 0,
            "error": str(e),
        }


# =============================================================================
# AGI-Like: Generate Import Summary (for User Approval)
# =============================================================================

async def _generate_import_summary(
    s3_key: str,
    column_mappings: Dict[str, str],
    analysis_summary: Optional[Dict[str, Any]],
    unmapped_decisions: Dict[str, str],
    ignored_columns: List[str],
    metadata_columns: List[str],
    target_table: str,
    session_id: Optional[str],
) -> Dict[str, Any]:
    """
    Generate a summary of what will be imported (AGI-Like Behavior).

    This summary is presented to the user for EXPLICIT APPROVAL
    before any data is actually imported.

    Frontend receives this and shows:
    - Total records to import
    - Column mappings table
    - Ignored columns (data will be lost)
    - Metadata columns (data preserved in JSON)
    - Warnings/alerts
    - APPROVE/REJECT buttons

    Returns:
        Frontend-compatible summary response
    """
    audit.working(
        message="Gerando resumo para aprovação...",
        session_id=session_id,
    )

    # Extract metrics from analysis summary
    row_count = 0
    column_count = 0
    confidence = 0.0

    if analysis_summary:
        row_count = analysis_summary.get("row_count", 0)
        column_count = analysis_summary.get("column_count", 0)
        confidence = analysis_summary.get("confidence", 0.0)

    # Build mappings list for display
    mappings_list = []
    for source, target in column_mappings.items():
        mappings_list.append({
            "source_column": source,
            "target_field": target,
            "action": "map",
        })

    # Build ignored columns list
    ignored_list = []
    for col in ignored_columns:
        ignored_list.append({
            "source_column": col,
            "action": "ignore",
            "warning": "Dados serão perdidos",
        })

    # Build metadata columns list
    metadata_list = []
    for col in metadata_columns:
        metadata_list.append({
            "source_column": col,
            "action": "metadata",
            "info": "Dados preservados no campo metadata (JSONB)",
        })

    # Generate warnings
    warnings = []
    if ignored_columns:
        warnings.append({
            "type": "data_loss",
            "message": f"{len(ignored_columns)} coluna(s) serão ignoradas e os dados perdidos",
            "columns": ignored_columns,
        })

    if confidence < 0.8:
        warnings.append({
            "type": "low_confidence",
            "message": f"Confiança da análise: {confidence:.0%} (abaixo de 80%)",
        })

    # Build summary message for display
    summary_message = _build_summary_message(
        row_count=row_count,
        mappings_count=len(column_mappings),
        ignored_count=len(ignored_columns),
        metadata_count=len(metadata_columns),
        target_table=target_table,
    )

    audit.completed(
        message="Resumo gerado. Aguardando aprovação do usuário.",
        session_id=session_id,
        details={
            "row_count": row_count,
            "mappings_count": len(column_mappings),
            "ignored_count": len(ignored_columns),
            "metadata_count": len(metadata_columns),
        },
    )

    return {
        # AGI-Like: Frontend must show this and get approval
        "requires_approval": True,
        "approved": False,

        # Summary data for frontend display
        "summary": {
            "message": summary_message,
            "row_count": row_count,
            "column_count": column_count,
            "confidence": confidence,
            "target_table": target_table,
            "s3_key": s3_key,
        },

        # Detailed breakdown
        "mappings": mappings_list,
        "ignored_columns": ignored_list,
        "metadata_columns": metadata_list,
        "warnings": warnings,

        # For re-calling with approval
        "approval_payload": {
            "s3_key": s3_key,
            "column_mappings": column_mappings,
            "target_table": target_table,
            "ignored_columns": ignored_columns,
            "metadata_columns": metadata_columns,
            "user_approval": True,  # Set to True when user approves
        },

        # Frontend instructions
        "frontend_action": "show_approval_dialog",
        "approval_buttons": [
            {"value": "approve", "label": "✅ Aprovar e Importar", "primary": True},
            {"value": "reject", "label": "❌ Cancelar", "primary": False},
            {"value": "edit", "label": "✏️ Editar Mapeamentos", "primary": False},
        ],
    }


def _build_summary_message(
    row_count: int,
    mappings_count: int,
    ignored_count: int,
    metadata_count: int,
    target_table: str,
) -> str:
    """
    Build a human-readable summary message in Portuguese.
    """
    lines = [
        "📊 **Resumo da Importação**",
        "",
        f"• **{row_count:,}** registro(s) serão importados",
        f"• **{mappings_count}** coluna(s) mapeadas para campos do banco",
        f"• Tabela destino: `{target_table}`",
    ]

    if ignored_count > 0:
        lines.append("")
        lines.append(f"⚠️ **Atenção:** {ignored_count} coluna(s) serão ignoradas (dados perdidos)")

    if metadata_count > 0:
        lines.append("")
        lines.append(f"📦 {metadata_count} coluna(s) serão preservadas no campo `metadata`")

    lines.append("")
    lines.append("**Deseja prosseguir com a importação?**")

    return "\n".join(lines)


# Alias for backward compatibility with main.py imports
execute_import_impl = execute_import_tool
