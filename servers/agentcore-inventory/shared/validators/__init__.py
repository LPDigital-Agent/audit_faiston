# =============================================================================
# Validator Registry for Self-Validating Agents
# =============================================================================
# Central registry of validators for each agent type. Validators are deterministic
# Python functions that check agent outputs for correctness.
#
# Pattern from: "Claude Code Senior Engineers" video
# Concept: "LLM = Brain / Python = Hands" - LLM generates, Python validates
#
# Validator Signature:
#     def validator(output: BaseModel) -> Tuple[bool, str]:
#         # Return (True, "OK") if valid
#         # Return (False, "Error message describing the issue") if invalid
#
# Usage:
#     from shared.validators import AGENT_VALIDATORS
#
#     validators = AGENT_VALIDATORS.get("schema_mapper", [])
#     hook = ResultValidationHook(validators=validators)
#
# Reference: docs/plans/FEAT-self-validating-agents.md
# =============================================================================

from typing import Dict, List, Callable, Tuple
from pydantic import BaseModel


# =============================================================================
# Schema Mapper Validators
# =============================================================================

def validate_mapping_completeness(response: BaseModel) -> Tuple[bool, str]:
    """
    Deterministic check: Required target fields must be mapped.

    Checks that critical fields (part_number, quantity) have mappings.
    """
    # Get mappings from response
    mappings = getattr(response, "mappings", [])
    if not mappings:
        return False, "No mappings provided"

    # Extract target columns from mappings
    mapped_targets = set()
    for mapping in mappings:
        if hasattr(mapping, "target_column"):
            mapped_targets.add(mapping.target_column)
        elif isinstance(mapping, dict):
            mapped_targets.add(mapping.get("target_column", ""))

    # Check for required fields
    required_fields = {"part_number", "quantity"}
    missing = required_fields - mapped_targets

    if missing:
        return False, f"Missing required mappings: {missing}"

    return True, "OK"


def validate_confidence_threshold(response: BaseModel) -> Tuple[bool, str]:
    """
    Deterministic check: Overall confidence must meet minimum threshold.

    Ensures mapping confidence is at least 0.7 (70%).
    """
    confidence = getattr(response, "overall_confidence", None)
    if confidence is None:
        confidence = getattr(response, "confidence", None)

    if confidence is not None and confidence < 0.7:
        return False, f"Confidence too low: {confidence:.2f} < 0.70"

    return True, "OK"


def validate_no_duplicate_targets(response: BaseModel) -> Tuple[bool, str]:
    """
    Deterministic check: No two source columns map to same target.

    Prevents data loss from column collisions.
    """
    mappings = getattr(response, "mappings", [])

    targets = []
    for mapping in mappings:
        if hasattr(mapping, "target_column"):
            targets.append(mapping.target_column)
        elif isinstance(mapping, dict):
            targets.append(mapping.get("target_column", ""))

    # Find duplicates
    seen = set()
    duplicates = []
    for t in targets:
        if t and t in seen:
            duplicates.append(t)
        seen.add(t)

    if duplicates:
        return False, f"Duplicate target mappings: {set(duplicates)}"

    return True, "OK"


# =============================================================================
# Data Transformer Validators
# =============================================================================

def validate_transformation_rules(response: BaseModel) -> Tuple[bool, str]:
    """
    Deterministic check: Transformation rules are valid.

    Ensures that transformation rules have required fields.
    """
    rules = getattr(response, "transformation_rules", [])
    if not rules:
        # No rules is acceptable - may not need transformations
        return True, "OK"

    for i, rule in enumerate(rules):
        if hasattr(rule, "rule_type"):
            rule_type = rule.rule_type
        elif isinstance(rule, dict):
            rule_type = rule.get("rule_type")
        else:
            return False, f"Rule {i} has invalid structure"

        if not rule_type:
            return False, f"Rule {i} missing rule_type"

    return True, "OK"


def validate_type_conversions(response: BaseModel) -> Tuple[bool, str]:
    """
    Deterministic check: Type conversions are valid.

    Ensures numeric columns are converted to appropriate types.
    """
    conversions = getattr(response, "type_conversions", [])

    valid_types = {"string", "integer", "float", "boolean", "date", "datetime"}

    for conv in conversions:
        if hasattr(conv, "target_type"):
            target_type = conv.target_type
        elif isinstance(conv, dict):
            target_type = conv.get("target_type", "")
        else:
            continue

        if target_type and target_type.lower() not in valid_types:
            return False, f"Invalid type conversion: {target_type}"

    return True, "OK"


# =============================================================================
# Observation Agent Validators
# =============================================================================

def validate_observation_structure(response: BaseModel) -> Tuple[bool, str]:
    """
    Deterministic check: Observation has required fields.
    """
    # Check for summary
    summary = getattr(response, "summary", None)
    if not summary:
        return False, "Observation missing summary"

    # Check for confidence
    confidence = getattr(response, "confidence", None)
    if confidence is None:
        return False, "Observation missing confidence score"

    return True, "OK"


# =============================================================================
# Agent → Validators Registry
# =============================================================================

AGENT_VALIDATORS: Dict[str, List[Callable[[BaseModel], Tuple[bool, str]]]] = {
    "schema_mapper": [
        validate_mapping_completeness,
        validate_confidence_threshold,
        validate_no_duplicate_targets,
    ],
    "data_transformer": [
        validate_transformation_rules,
        validate_type_conversions,
    ],
    "observation": [
        validate_observation_structure,
    ],
    # Add more agents as needed
}


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AGENT_VALIDATORS",
    # Schema Mapper
    "validate_mapping_completeness",
    "validate_confidence_threshold",
    "validate_no_duplicate_targets",
    # Data Transformer
    "validate_transformation_rules",
    "validate_type_conversions",
    # Observation
    "validate_observation_structure",
]
