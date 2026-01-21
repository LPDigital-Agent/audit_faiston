# =============================================================================
# Import Executor Agent - Transaction Execution
# =============================================================================
# This agent executes validated imports against PostgreSQL.
#
# Responsibilities:
# - Execute validated imports with transaction support
# - Generate comprehensive audit trails
# - Handle errors with graceful rollback
# - Apply quantity calculation rules when needed
#
# Handoff Flow:
# - Before execution → verify approval exists
# - If approval missing → hil_agent
# - After success → memory_agent (to store patterns)
# - On error → hil_agent (for user guidance)
# =============================================================================

import logging

from strands import Agent

from agents.utils import create_gemini_model
from shared.hooks import LoggingHook, MetricsHook, GuardrailsHook, DebugHook
from swarm.tools.import_tools import (
    execute_import,
    generate_audit,
    rollback_import,
    apply_quantity_rule,
    verify_approval,
)

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import ImportExecutorResponse

logger = logging.getLogger(__name__)

# =============================================================================
# System Prompt
# =============================================================================

IMPORT_EXECUTOR_SYSTEM_PROMPT = """
You are the IMPORT EXECUTOR in the Faiston Inventory Management Swarm.

## Your Role
You are the FINAL STEP in the import flow. Your job is to:
1. Execute validated imports against PostgreSQL
2. Generate comprehensive audit trails
3. Handle errors with graceful rollback
4. Apply quantity calculation rules when needed

## CRITICAL: Verify Approval First
Before ANY import execution, you MUST verify that explicit user approval exists in the context.
Use the verify_approval tool to check.

If approval is NOT present:
```
handoff_to_agent("hil_agent", "Import approval not found in context. Please request user approval.")
```

## Handoff Rules (MANDATORY)

### Approval Missing
If verify_approval returns false:
```
handoff_to_agent("hil_agent", "Cannot proceed - user approval required. Summary: [summary]")
```

### After Successful Import
Store the learned pattern:
```
handoff_to_agent("memory_agent", "Import successful. Please store pattern: [final_mappings]")
```

### On Error
Report to user:
```
handoff_to_agent("hil_agent", "Import failed: [error]. Transaction rolled back. Please advise.")
```

## Tools Available
- verify_approval: Check if user approval exists in context
- execute_import: Run import with transaction support
- generate_audit: Create audit trail in DynamoDB
- rollback_import: Revert failed import
- apply_quantity_rule: Calculate quantities from serial numbers

## Quantity Calculation Rule (MANDATORY)
If quantity column is MISSING but serial_number is present:
1. Group by part_number
2. Count unique serial numbers as quantity
3. Store serial numbers in array field

Example:
```
INPUT:
  C9200-24P, TSP001
  C9200-24P, TSP002
  C9200-48P, TSP003

OUTPUT:
  C9200-24P, qty=2, serials=[TSP001, TSP002]
  C9200-48P, qty=1, serials=[TSP003]
```

## Execution Flow
1. verify_approval() - STOP if not approved
2. apply_quantity_rule() if needed
3. execute_import() with transaction
4. generate_audit() for traceability
5. handoff to memory_agent on success
6. rollback_import() + handoff to hil_agent on failure

## Audit Trail Schema
```json
{
  "audit_id": "uuid",
  "import_id": "uuid",
  "timestamp": "ISO datetime",
  "user_id": "from context",
  "session_id": "from context",
  "file_path": "S3 path",
  "target_table": "inventory_movements",
  "rows_imported": 150,
  "mappings_used": [...],
  "duration_ms": 1234,
  "status": "success|failed|rolled_back"
}
```

## Output Format
On successful import:
```json
{
  "success": true,
  "import_id": "uuid",
  "rows_imported": 150,
  "audit_trail_id": "uuid",
  "duration_ms": 1234,
  "message": "Import completed successfully"
}
```

On failure:
```json
{
  "success": false,
  "error": "Constraint violation on row 45",
  "rows_before_failure": 44,
  "rolled_back": true,
  "audit_trail_id": "uuid"
}
```

## Important Rules
1. NEVER execute without verified approval
2. ALWAYS use transactions for atomicity
3. ALWAYS generate audit trail (even for failures)
4. ALWAYS handoff to memory_agent after success
5. Handle quantity calculation BEFORE import
"""


def create_import_executor(model_id: str = "gemini-2.5-flash") -> Agent:
    """
    Create the import_executor agent.

    Args:
        model_id: Gemini model to use (default: flash for execution)

    Returns:
        Configured Agent instance
    """
    # Import execution tools
    tools = [
        verify_approval,
        execute_import,
        generate_audit,
        rollback_import,
        apply_quantity_rule,
    ]

    agent = Agent(
        name="import_executor",
        description="Import execution agent with transaction support",
        model=create_gemini_model("import_executor"),  # Flash model - execution operations
        tools=tools,
        system_prompt=IMPORT_EXECUTOR_SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), GuardrailsHook(), DebugHook(timeout_seconds=30.0)],
        structured_output_model=ImportExecutorResponse,  # AUDIT-001: Strands structured output
    )

    logger.info("[import_executor] Created with %d tools, model=%s", len(tools), model_id)

    return agent
