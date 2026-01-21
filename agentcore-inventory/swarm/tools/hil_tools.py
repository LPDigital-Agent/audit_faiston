# =============================================================================
# HIL Tools - Human-in-the-Loop for Inventory Swarm
# =============================================================================
# Tools for generating questions and processing user responses.
#
# Used by: hil_agent
# =============================================================================

import logging
from typing import Dict, List, Any, Optional

from strands import tool

logger = logging.getLogger(__name__)


@tool
def generate_questions(
    validation_issues: List[Dict[str, Any]],
    unmapped_columns: List[str],
    low_confidence_mappings: Optional[List[Dict[str, Any]]] = None,
    sample_data: Optional[Dict[str, List[Any]]] = None,
) -> Dict[str, Any]:
    """
    Generate clarification questions based on validation issues.

    Args:
        validation_issues: Issues from schema validation
        unmapped_columns: Columns without target mapping
        low_confidence_mappings: Mappings with confidence < threshold
        sample_data: Sample values for context

    Returns:
        dict with:
        - questions: List of HIL questions
        - stop_action: True (signals Swarm to pause)
        - awaiting_response: True
    """
    logger.info(
        "[generate_questions] Issues: %d, Unmapped: %d, Low confidence: %d",
        len(validation_issues),
        len(unmapped_columns),
        len(low_confidence_mappings or []),
    )

    questions = []

    # Generate questions for unmapped columns
    for col_name in unmapped_columns:
        samples = (sample_data or {}).get(col_name, [])[:3]
        questions.append({
            "id": f"q_unmapped_{len(questions)}",
            "type": "unmapped_column",
            "question": f"Column '{col_name}' has no matching target. How should we handle it?",
            "column_name": col_name,
            "sample_values": samples,
            "options": [
                {
                    "value": "ignore",
                    "label": "Ignore (data will NOT be imported)",
                    "warning": True,
                    "description": "Data in this column will be lost",
                },
                {
                    "value": "metadata",
                    "label": "Store in metadata JSON field (recommended)",
                    "recommended": True,
                    "description": "Preserves data for future reference",
                },
                {
                    "value": "schema_update",
                    "label": "Request database schema update",
                    "description": "Contact Faiston IT to add this field to the database",
                },
            ],
        })

    # Generate questions for low confidence mappings
    for mapping in low_confidence_mappings or []:
        source = mapping.get("source_column", "")
        target = mapping.get("target_column", "")
        confidence = mapping.get("confidence", 0.0)

        questions.append({
            "id": f"q_mapping_{len(questions)}",
            "type": "column_mapping",
            "question": f"Mapping '{source}' → '{target}' has {confidence:.0%} confidence. Is this correct?",
            "source_column": source,
            "proposed_target": target,
            "confidence": confidence,
            "options": [
                {
                    "value": "confirm",
                    "label": f"Yes, map to '{target}'",
                },
                {
                    "value": "change",
                    "label": "No, choose different target",
                    "requires_input": True,
                },
                {
                    "value": "ignore",
                    "label": "Ignore this column",
                    "warning": True,
                },
            ],
        })

    # Generate questions for validation issues
    for issue in validation_issues:
        if issue.get("severity") == "warning":
            questions.append({
                "id": f"q_issue_{len(questions)}",
                "type": "validation_issue",
                "question": f"Issue detected: {issue.get('issue', 'Unknown issue')}. How should we proceed?",
                "column": issue.get("column"),
                "issue": issue.get("issue"),
                "options": [
                    {
                        "value": "proceed",
                        "label": "Proceed anyway",
                        "description": "Import with current settings",
                    },
                    {
                        "value": "fix",
                        "label": "Apply suggested fix",
                        "description": issue.get("suggestion", "Apply automatic fix"),
                    },
                    {
                        "value": "abort",
                        "label": "Cancel import",
                        "warning": True,
                    },
                ],
            })

    return {
        "questions": questions,
        "question_count": len(questions),
        "stop_action": True,  # CRITICAL: Pause Swarm for user input
        "awaiting_response": True,
    }


@tool
def process_answers(
    questions: List[Dict[str, Any]],
    answers: Dict[str, Any],
    current_mappings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Process user answers and update mapping context.

    Args:
        questions: Original questions that were asked
        answers: User's answers keyed by question ID
        current_mappings: Current proposed mappings

    Returns:
        dict with:
        - updated_mappings: Mappings updated with user decisions
        - metadata_columns: Columns to store in metadata
        - ignored_columns: Columns to ignore
        - ready_for_approval: Whether all questions are answered
    """
    logger.info(
        "[process_answers] Processing %d answers for %d questions",
        len(answers),
        len(questions),
    )

    updated_mappings = list(current_mappings)
    metadata_columns = []
    ignored_columns = []
    schema_update_requests = []

    for question in questions:
        q_id = question["id"]
        answer = answers.get(q_id)

        if not answer:
            continue

        q_type = question.get("type")

        if q_type == "unmapped_column":
            col_name = question.get("column_name")
            if answer == "ignore":
                ignored_columns.append(col_name)
            elif answer == "metadata":
                metadata_columns.append(col_name)
            elif answer == "schema_update":
                schema_update_requests.append(col_name)

        elif q_type == "column_mapping":
            source = question.get("source_column")
            if answer == "confirm":
                # Keep the mapping as-is, but increase confidence
                for m in updated_mappings:
                    if m.get("source_column") == source:
                        m["confidence"] = 1.0
                        m["user_confirmed"] = True
            elif answer == "ignore":
                # Remove from mappings, add to ignored
                updated_mappings = [
                    m for m in updated_mappings
                    if m.get("source_column") != source
                ]
                ignored_columns.append(source)
            elif isinstance(answer, dict) and "new_target" in answer:
                # User specified different target
                for m in updated_mappings:
                    if m.get("source_column") == source:
                        m["target_column"] = answer["new_target"]
                        m["confidence"] = 1.0
                        m["user_confirmed"] = True

        elif q_type == "validation_issue":
            # Handle validation issue responses
            pass

    # Check if all questions are answered
    unanswered = [q["id"] for q in questions if q["id"] not in answers]
    ready = len(unanswered) == 0

    return {
        "updated_mappings": updated_mappings,
        "metadata_columns": metadata_columns,
        "ignored_columns": ignored_columns,
        "schema_update_requests": schema_update_requests,
        "ready_for_approval": ready,
        "unanswered_questions": unanswered,
    }


@tool
def request_approval(
    mappings: List[Dict[str, Any]],
    row_count: int,
    target_table: str,
    metadata_columns: Optional[List[str]] = None,
    ignored_columns: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate final approval request for the import.

    Args:
        mappings: Final confirmed mappings
        row_count: Number of rows to import
        target_table: Target database table
        metadata_columns: Columns going to metadata field
        ignored_columns: Columns being ignored
        warnings: Any warnings to show user

    Returns:
        dict with:
        - approval_request: True
        - summary: Import summary for user review
        - stop_action: True (pause for approval)
    """
    logger.info(
        "[request_approval] Requesting approval for %d rows to %s",
        row_count,
        target_table,
    )

    summary = {
        "total_rows": row_count,
        "target_table": target_table,
        "mapped_columns": len(mappings),
        "mappings": [
            {
                "source": m["source_column"],
                "target": m["target_column"],
                "transform": m.get("transform"),
            }
            for m in mappings
        ],
        "metadata_columns": metadata_columns or [],
        "ignored_columns": ignored_columns or [],
        "warnings": warnings or [],
    }

    return {
        "approval_request": True,
        "summary": summary,
        "question": {
            "id": "q_final_approval",
            "type": "final_approval",
            "question": f"Ready to import {row_count} rows to {target_table}. Please review and confirm.",
            "summary": summary,
            "options": [
                {
                    "value": "approve",
                    "label": "Confirmar Importação",
                    "primary": True,
                },
                {
                    "value": "reject",
                    "label": "Cancelar",
                    "warning": True,
                },
            ],
        },
        "stop_action": True,
        "awaiting_approval": True,
    }


@tool
def format_summary(
    mappings: List[Dict[str, Any]],
    row_count: int,
    file_name: str,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Format a human-readable import summary.

    Args:
        mappings: Column mappings
        row_count: Number of rows
        file_name: Source file name
        issues: Any issues or warnings

    Returns:
        dict with formatted summary text and structured data
    """
    logger.info("[format_summary] Formatting summary for %s", file_name)

    # Build text summary
    lines = [
        f"## Import Summary for {file_name}",
        "",
        f"**Total Rows:** {row_count}",
        f"**Mapped Columns:** {len(mappings)}",
        "",
        "### Column Mappings",
    ]

    for m in mappings:
        source = m.get("source_column", "?")
        target = m.get("target_column", "?")
        conf = m.get("confidence", 0.0)
        transform = m.get("transform", "")
        transform_str = f" (transform: {transform})" if transform else ""
        lines.append(f"- {source} → {target} ({conf:.0%}){transform_str}")

    if issues:
        lines.extend(["", "### Issues"])
        for issue in issues:
            lines.append(f"- ⚠️ {issue.get('issue', 'Unknown issue')}")

    return {
        "text": "\n".join(lines),
        "structured": {
            "file_name": file_name,
            "row_count": row_count,
            "mapping_count": len(mappings),
            "issue_count": len(issues or []),
        },
    }
