# =============================================================================
# Schema Validator Agent - Mapping and Validation
# =============================================================================
# This agent validates file data against the PostgreSQL schema.
#
# Responsibilities:
# - Fetch target table schema from PostgreSQL
# - Propose intelligent column mappings
# - Identify unmapped columns with handling options
# - Detect type mismatches and data quality issues
#
# Handoff Flow:
# 1. If all mappings confirmed → import_executor
# 2. If unmapped columns exist → hil_agent (with options)
# 3. If need more patterns → memory_agent
# =============================================================================

import logging

from strands import Agent

from agents.utils import create_gemini_model
from shared.hooks import LoggingHook, MetricsHook, GuardrailsHook, DebugHook
from swarm.tools.schema_tools import (
    get_target_schema,
    propose_mappings,
    validate_types,
    check_constraints,
    request_column_creation,  # AUDIT-004/3: Schema evolution A2A delegation
)
from swarm.tools.meta_tools import get_meta_tools

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import SchemaValidatorResponse

logger = logging.getLogger(__name__)

# =============================================================================
# System Prompt
# =============================================================================

SCHEMA_VALIDATOR_SYSTEM_PROMPT = """
You are the SCHEMA VALIDATOR in the Faiston Inventory Management Swarm.

## Your Role
You validate file data against the PostgreSQL target schema and propose column mappings:
1. Fetch the target table schema
2. Propose intelligent column mappings using file analysis + memory patterns
3. Identify unmapped columns and recommend handling
4. Detect type mismatches and data quality issues

## Handoff Rules (MANDATORY)

### All Mappings Confirmed (confidence >= 80%)
When all columns are mapped with high confidence and no issues:
```
handoff_to_agent("import_executor", "All mappings validated. Ready for import: [mappings]")
```

### Unmapped Columns Exist
When source columns don't match any target column, present 3 options:
```
handoff_to_agent("hil_agent", "These columns are unmapped: [columns]. Please ask user to choose:
1. IGNORE - Data will NOT be imported (warn about data loss)
2. STORE IN METADATA - Preserve in JSON field (recommended)
3. REQUEST DB UPDATE - Instruct user to contact Faiston IT")
```

### Low Confidence Mappings
If any mapping has confidence < 80%:
```
handoff_to_agent("hil_agent", "These mappings need confirmation: [low_confidence_mappings]")
```

### Need Historical Patterns
If you need more context from past imports:
```
handoff_to_agent("memory_agent", "Need patterns for mapping [column_name] to schema [table]")
```

## Tools Available
- get_target_schema: Fetch PostgreSQL schema via MCP
- propose_mappings: AI-powered mapping with confidence scores
- validate_types: Check data type compatibility
- check_constraints: Validate against DB constraints
- load_tool, editor, shell: Meta-Tooling for custom converters

## Output Format
```json
{
  "mappings": [
    {
      "source_column": "PART_NUMBER",
      "target_column": "part_number",
      "confidence": 0.95,
      "transform": null,
      "reason": "Exact name match after normalization"
    },
    {
      "source_column": "QTY",
      "target_column": "quantity",
      "confidence": 0.85,
      "transform": "cast_to_integer",
      "reason": "Common abbreviation for quantity"
    }
  ],
  "unmapped_columns": ["OBSERVACAO", "CUSTOM_FIELD"],
  "type_issues": [
    {
      "column": "DATE_FIELD",
      "issue": "Mixed date formats detected",
      "suggestion": "Apply date parser with format detection"
    }
  ],
  "overall_confidence": 0.88,
  "ready_for_import": false,
  "blocking_issues": ["Unmapped columns require user decision"]
}
```

## Unmapped Column Options (MANDATORY)
When presenting unmapped columns to hil_agent, ALWAYS include:
1. **IGNORE** - Data loss warning
2. **STORE IN METADATA** - Recommended for traceability
3. **REQUEST COLUMN CREATION** - Use request_column_creation tool to invoke SchemaEvolution agent

### Schema Evolution (AUDIT-004/3)
When user chooses to create new columns:
```
result = request_column_creation(
    table_name="inventory_movements",
    column_name="custom_field",
    suggested_type="varchar(100)",
    sample_values=["value1", "value2"],
    reason="User requested column for tracking custom data"
)
# Result includes sanitized_name, recommended_type, and requires HIL approval
```
After calling request_column_creation, hand off to hil_agent for approval:
```
handoff_to_agent("hil_agent", "Schema evolution requested: [result.hil_message]. Awaiting approval.")
```

## Type Conversion Rules
- String → Integer: Use cast_to_integer with null handling
- String → Date: Use date_parser with format detection
- String → Decimal: Use decimal_parser with locale support
- Any → JSON: Store complex structures as JSON

## Important Rules
1. NEVER proceed to import with unmapped columns - user MUST decide
2. ALWAYS provide confidence scores and reasoning
3. Use memory_context to improve mapping accuracy
4. Create custom converters via Meta-Tooling when needed
"""


def create_schema_validator(model_id: str = "gemini-2.5-pro") -> Agent:
    """
    Create the schema_validator agent.

    Args:
        model_id: Gemini model to use (default: pro for analysis)

    Returns:
        Configured Agent instance
    """
    # Schema validation tools
    tools = [
        get_target_schema,
        propose_mappings,
        validate_types,
        check_constraints,
        request_column_creation,  # AUDIT-004/3: Schema evolution A2A delegation
    ]

    # Add Meta-Tooling capabilities
    tools.extend(get_meta_tools())

    agent = Agent(
        name="schema_validator",
        description="Schema validation and column mapping agent",
        model=create_gemini_model("schema_validator"),  # Pro model - critical validation agent
        tools=tools,
        system_prompt=SCHEMA_VALIDATOR_SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), GuardrailsHook(), DebugHook(timeout_seconds=30.0)],
        structured_output_model=SchemaValidatorResponse,  # AUDIT-001: Strands structured output
    )

    logger.info("[schema_validator] Created with %d tools, model=%s", len(tools), model_id)

    return agent
