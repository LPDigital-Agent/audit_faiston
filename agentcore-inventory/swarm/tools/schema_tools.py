# =============================================================================
# Schema Tools - PostgreSQL Validation for Inventory Swarm
# =============================================================================
# Tools for schema validation and column mapping.
#
# Used by: schema_validator agent
# =============================================================================

import asyncio
import logging
from typing import Dict, List, Any, Optional

from strands import tool

# AUDIT-004/3: Import A2A client for schema_evolution delegation
from shared.a2a_client import A2AClient

logger = logging.getLogger(__name__)


@tool
def get_target_schema(table_name: str) -> Dict[str, Any]:
    """
    Fetch the PostgreSQL schema for a target table.

    Args:
        table_name: Name of the target table (e.g., "inventory_movements")

    Returns:
        dict with:
        - table_name: Target table
        - columns: List of column definitions
        - primary_key: Primary key column(s)
        - constraints: Table constraints
    """
    logger.info("[get_target_schema] Fetching schema for: %s", table_name)

    # In production, this would query PostgreSQL via MCP Gateway
    # For now, return the standard inventory schema
    if table_name == "inventory_movements":
        return {
            "table_name": table_name,
            "columns": [
                {"name": "id", "type": "uuid", "nullable": False, "primary_key": True},
                {"name": "part_number", "type": "varchar(50)", "nullable": False},
                {"name": "serial_number", "type": "varchar(100)", "nullable": True},
                {"name": "quantity", "type": "integer", "nullable": False, "default": 1},
                {"name": "unit_price", "type": "decimal(15,2)", "nullable": True},
                {"name": "movement_type", "type": "varchar(20)", "nullable": False},
                {"name": "location_from", "type": "varchar(50)", "nullable": True},
                {"name": "location_to", "type": "varchar(50)", "nullable": True},
                {"name": "reference_doc", "type": "varchar(100)", "nullable": True},
                {"name": "movement_date", "type": "timestamp", "nullable": False},
                {"name": "description", "type": "text", "nullable": True},
                {"name": "metadata", "type": "jsonb", "nullable": True},
                {"name": "created_at", "type": "timestamp", "nullable": False, "default": "now()"},
                {"name": "created_by", "type": "varchar(100)", "nullable": False},
            ],
            "primary_key": ["id"],
            "constraints": [
                {"type": "check", "name": "quantity_positive", "condition": "quantity > 0"},
                {"type": "check", "name": "valid_movement_type", "condition": "movement_type IN ('IN', 'OUT', 'TRANSFER', 'ADJUSTMENT')"},
            ],
        }

    # Generic fallback
    return {
        "table_name": table_name,
        "columns": [],
        "primary_key": [],
        "constraints": [],
        "error": f"Schema not found for table: {table_name}",
    }


@tool
def propose_mappings(
    source_columns: List[Dict[str, Any]],
    target_schema: Dict[str, Any],
    memory_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Propose column mappings from source to target using AI analysis.

    Args:
        source_columns: List of source column info from file analysis
        target_schema: Target schema from get_target_schema
        memory_context: Optional prior patterns from memory_agent

    Returns:
        dict with:
        - mappings: List of proposed mappings with confidence
        - unmapped_source: Source columns without mapping
        - unmapped_target: Required target columns without source
        - overall_confidence: Average mapping confidence
    """
    logger.info(
        "[propose_mappings] Mapping %d source columns to %d target columns",
        len(source_columns),
        len(target_schema.get("columns", [])),
    )

    target_columns = {c["name"]: c for c in target_schema.get("columns", [])}
    mappings = []
    mapped_sources = set()
    mapped_targets = set()

    # Use memory context if available
    prior_mappings = {}
    if memory_context and "patterns" in memory_context:
        for pattern in memory_context.get("patterns", []):
            for m in pattern.get("column_mappings", []):
                prior_mappings[m["source"].lower()] = m["target"]

    # Mapping rules (priority order)
    for source in source_columns:
        source_name = source["name"]
        source_lower = source_name.lower().strip()
        best_match = None
        best_confidence = 0.0
        transform = None
        reason = ""

        # 1. Check prior mappings from memory
        if source_lower in prior_mappings:
            target_name = prior_mappings[source_lower]
            if target_name in target_columns:
                best_match = target_name
                best_confidence = 0.95
                reason = "Learned from prior successful import"

        # 2. Exact name match (case-insensitive)
        if not best_match:
            for target_name in target_columns:
                if source_lower == target_name.lower():
                    best_match = target_name
                    best_confidence = 1.0
                    reason = "Exact name match"
                    break

        # 3. Common name variations
        if not best_match:
            variations = _get_name_variations(source_lower)
            for target_name in target_columns:
                if target_name.lower() in variations:
                    best_match = target_name
                    best_confidence = 0.9
                    reason = f"Name variation match: {source_lower} → {target_name}"
                    break

        # 4. Type-based matching for common fields
        if not best_match:
            match_result = _match_by_type_and_samples(
                source, target_columns, mapped_targets
            )
            if match_result:
                best_match, best_confidence, reason = match_result

        # Add mapping
        if best_match:
            # Determine if transform needed
            source_type = source.get("inferred_type", "string")
            target_type = target_columns[best_match].get("type", "varchar")
            transform = _get_type_transform(source_type, target_type)

            mappings.append({
                "source_column": source_name,
                "target_column": best_match,
                "confidence": best_confidence,
                "transform": transform,
                "reason": reason,
            })
            mapped_sources.add(source_name)
            mapped_targets.add(best_match)

    # Find unmapped columns
    unmapped_source = [
        c["name"] for c in source_columns if c["name"] not in mapped_sources
    ]
    unmapped_target = [
        c["name"]
        for c in target_schema.get("columns", [])
        if c["name"] not in mapped_targets
        and not c.get("default")  # Exclude columns with defaults
        and c.get("nullable", True) is False  # Only required columns
    ]

    # Calculate overall confidence
    confidences = [m["confidence"] for m in mappings]
    overall = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "mappings": mappings,
        "unmapped_source": unmapped_source,
        "unmapped_target": unmapped_target,
        "overall_confidence": round(overall, 2),
        "ready_for_import": len(unmapped_source) == 0 and overall >= 0.8,
    }


@tool
def validate_types(
    mappings: List[Dict[str, Any]],
    sample_data: Dict[str, List[Any]],
) -> Dict[str, Any]:
    """
    Validate data types for proposed mappings against sample data.

    Args:
        mappings: Proposed mappings from propose_mappings
        sample_data: Sample data by column name

    Returns:
        dict with:
        - valid: Boolean indicating all validations passed
        - issues: List of type/format issues
        - suggestions: Recommended transforms
    """
    logger.info("[validate_types] Validating %d mappings", len(mappings))

    issues = []
    suggestions = []

    for mapping in mappings:
        source = mapping["source_column"]
        samples = sample_data.get(source, [])

        if not samples:
            continue

        # Check for mixed types
        types_found = set()
        for value in samples[:20]:
            if value is None:
                continue
            str_val = str(value).strip()
            if _is_integer_str(str_val):
                types_found.add("integer")
            elif _is_decimal_str(str_val):
                types_found.add("decimal")
            elif _is_date_str(str_val):
                types_found.add("date")
            else:
                types_found.add("string")

        if len(types_found) > 1:
            issues.append({
                "column": source,
                "issue": f"Mixed types detected: {types_found}",
                "severity": "warning",
            })
            suggestions.append({
                "column": source,
                "suggestion": "Apply type coercion with error handling",
            })

    return {
        "valid": len([i for i in issues if i["severity"] == "error"]) == 0,
        "issues": issues,
        "suggestions": suggestions,
    }


@tool
def check_constraints(
    mappings: List[Dict[str, Any]],
    sample_data: Dict[str, List[Any]],
    target_schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Check if sample data violates target schema constraints.

    Args:
        mappings: Proposed mappings
        sample_data: Sample data by column name
        target_schema: Target schema with constraints

    Returns:
        dict with:
        - valid: Boolean indicating no constraint violations
        - violations: List of constraint violations found
    """
    logger.info("[check_constraints] Checking constraints")

    violations = []

    for constraint in target_schema.get("constraints", []):
        if constraint["type"] == "check":
            # Check constraints would be validated in database
            # Here we can do basic validation
            pass

    # Check for null values in non-nullable columns
    for mapping in mappings:
        target = mapping["target_column"]
        source = mapping["source_column"]

        # Find target column definition
        target_def = None
        for col in target_schema.get("columns", []):
            if col["name"] == target:
                target_def = col
                break

        if target_def and not target_def.get("nullable", True):
            samples = sample_data.get(source, [])
            null_count = sum(1 for v in samples if v is None or str(v).strip() == "")
            if null_count > 0:
                violations.append({
                    "column": source,
                    "constraint": "NOT NULL",
                    "message": f"Found {null_count} null values in non-nullable column",
                })

    return {
        "valid": len(violations) == 0,
        "violations": violations,
    }


# =============================================================================
# Helper Functions
# =============================================================================


def _get_name_variations(name: str) -> set:
    """Get common name variations for a column name."""
    variations = {name}

    # Common abbreviations
    abbrev_map = {
        "qty": {"quantity", "quant"},
        "pn": {"part_number", "partnumber"},
        "sn": {"serial_number", "serialnumber"},
        "desc": {"description"},
        "dt": {"date"},
        "ref": {"reference", "reference_doc"},
        "loc": {"location"},
        "amt": {"amount"},
        "num": {"number"},
        "observacao": {"description", "notes", "observation"},
        "data": {"date", "movement_date"},
        "valor": {"value", "unit_price", "amount"},
    }

    # Add variations from map
    for abbrev, expansions in abbrev_map.items():
        if abbrev in name:
            variations.update(expansions)
        if name in expansions:
            variations.add(abbrev)

    # Add underscore/no-underscore variations
    variations.add(name.replace("_", ""))
    variations.add(name.replace(" ", "_"))

    return variations


def _match_by_type_and_samples(
    source: Dict[str, Any],
    target_columns: Dict[str, Dict],
    already_mapped: set,
) -> Optional[tuple]:
    """Match column by type and sample values."""
    source_type = source.get("inferred_type", "string")
    samples = source.get("sample_values", [])

    # Serial number detection
    if source_type == "string" and samples:
        if all(len(str(s)) > 5 for s in samples[:5]):
            if "serial_number" in target_columns and "serial_number" not in already_mapped:
                return ("serial_number", 0.75, "Detected as serial number by pattern")

    return None


def _get_type_transform(source_type: str, target_type: str) -> Optional[str]:
    """Determine if type transform is needed."""
    target_type_lower = target_type.lower()

    if source_type == "string" and "int" in target_type_lower:
        return "cast_to_integer"
    if source_type == "string" and ("decimal" in target_type_lower or "numeric" in target_type_lower):
        return "cast_to_decimal"
    if source_type == "string" and ("timestamp" in target_type_lower or "date" in target_type_lower):
        return "parse_date"

    return None


def _is_integer_str(val: str) -> bool:
    """Check if string is integer."""
    try:
        int(val)
        return True
    except ValueError:
        return False


def _is_decimal_str(val: str) -> bool:
    """Check if string is decimal."""
    try:
        float(val.replace(",", "."))
        return "." in val or "," in val
    except ValueError:
        return False


def _is_date_str(val: str) -> bool:
    """Check if string looks like a date."""
    import re

    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
    ]
    return any(re.match(p, val) for p in patterns)


# =============================================================================
# AUDIT-004/3: Schema Evolution A2A Delegation Tool
# =============================================================================
# This tool enables the schema_validator to invoke the schema_evolution agent
# via A2A protocol when new columns need to be created dynamically.
# =============================================================================


@tool
def request_column_creation(
    table_name: str,
    column_name: str,
    suggested_type: str,
    sample_values: Optional[List[str]] = None,
    reason: str = "Unmapped column requires dynamic creation",
) -> Dict[str, Any]:
    """
    Request the creation of a new database column via the SchemaEvolution agent.

    This tool delegates to the schema_evolution A2A agent which handles:
    - Column name sanitization (snake_case, reserved words)
    - Type inference from sample data
    - Advisory locking for concurrent access
    - JSONB fallback if creation fails

    IMPORTANT: This requires Human-in-the-Loop (HIL) approval in production.

    Args:
        table_name: Target table (e.g., "inventory_movements")
        column_name: Proposed column name
        suggested_type: Suggested PostgreSQL type (e.g., "varchar(100)", "integer")
        sample_values: Sample values for type inference (optional)
        reason: Why this column needs to be created

    Returns:
        dict with:
        - success: Boolean indicating request was submitted
        - validation: Pre-validation result from schema_evolution
        - requires_approval: Always True (HIL required for schema changes)
        - sanitized_name: Sanitized column name
        - recommended_type: Recommended type based on analysis
    """
    logger.info(
        "[request_column_creation] Requesting column '%s' on table '%s'",
        column_name, table_name
    )

    # Run async A2A call in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _invoke_schema_evolution():
        client = A2AClient()
        return await client.invoke_agent("schema_evolution", {
            "action": "validate_column_request",
            "table_name": table_name,
            "column_name": column_name,
            "suggested_type": suggested_type,
            "sample_values": sample_values or [],
            "reason": reason,
        })

    try:
        result = loop.run_until_complete(_invoke_schema_evolution())

        if result.success:
            import json
            try:
                response_data = json.loads(result.response)
            except json.JSONDecodeError:
                response_data = {"raw_response": result.response}

            logger.info(
                "[request_column_creation] Schema evolution validated: %s",
                response_data.get("sanitized_name", column_name)
            )

            return {
                "success": True,
                "validation": response_data,
                "requires_approval": True,  # HIL always required for schema changes
                "sanitized_name": response_data.get("sanitized_name", column_name),
                "recommended_type": response_data.get("recommended_type", suggested_type),
                "hil_message": (
                    f"A criação da coluna '{column_name}' requer aprovação. "
                    f"Nome sugerido: {response_data.get('sanitized_name', column_name)}, "
                    f"Tipo: {response_data.get('recommended_type', suggested_type)}"
                ),
            }
        else:
            logger.warning(
                "[request_column_creation] Schema evolution validation failed: %s",
                result.error
            )
            return {
                "success": False,
                "error": result.error or "Schema evolution validation failed",
                "requires_approval": True,
                "hil_message": (
                    f"Falha ao validar criação da coluna '{column_name}'. "
                    f"Erro: {result.error}. Entre em contato com o suporte Faiston."
                ),
            }

    except Exception as e:
        logger.error(
            "[request_column_creation] A2A call to schema_evolution failed: %s", e
        )
        return {
            "success": False,
            "error": str(e),
            "requires_approval": True,
            "hil_message": (
                f"Erro ao comunicar com o agente de evolução de schema. "
                f"Coluna '{column_name}' não pode ser criada automaticamente. "
                f"Entre em contato com o suporte Faiston."
            ),
        }
