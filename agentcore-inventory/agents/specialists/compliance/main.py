# =============================================================================
# ComplianceAgent - Strands A2AServer Entry Point (SUPPORT)
# =============================================================================
# Regulatory compliance support agent.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
#
# Architecture:
# - This is a SUPPORT agent for compliance validation
# - Validates operations against regulatory requirements
# - Manages approval workflows and audit compliance
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# =============================================================================

import os
import sys
import logging
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill
from fastapi import FastAPI
import uvicorn

# Centralized model configuration (MANDATORY - Gemini 2.5 Pro for complex reasoning)
from agents.utils import get_model, AGENT_VERSION, create_gemini_model

# A2A client for inter-agent communication
from shared.a2a_client import A2AClient

# Hooks for observability (ADR-002)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import ComplianceResponse
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

AGENT_ID = "compliance"
AGENT_NAME = "ComplianceAgent"
AGENT_DESCRIPTION = """SUPPORT Agent for Regulatory Compliance.

This agent handles:
1. OPERATION VALIDATION: Validate operations against compliance rules
2. APPROVAL STATUS: Check and manage approval workflows
3. AUDIT COMPLIANCE: Verify audit trail completeness
4. VIOLATION FLAGS: Flag compliance violations

Features:
- Multi-level approval routing
- Value-based authorization
- Regulatory compliance checks
- Audit trail verification
"""

# Agent Skills (for A2A Agent Card discovery)
AGENT_SKILLS = [
    AgentSkill(
        name="validate_operation",
        description="Validate operation against compliance rules (value limits, operation type restrictions, location/project restrictions)",
        tags=["compliance", "validation", "authorization"],
    ),
    AgentSkill(
        name="check_approval_status",
        description="Check approval status for an operation (pending approvers, approval workflow state)",
        tags=["compliance", "approval", "workflow"],
    ),
    AgentSkill(
        name="audit_compliance",
        description="Verify audit trail completeness for an entity (events, timestamps, responsible parties)",
        tags=["compliance", "audit", "verification"],
    ),
    AgentSkill(
        name="flag_violation",
        description="Flag a compliance violation (unauthorized operations, limit exceeded, procedure not followed)",
        tags=["compliance", "violation", "enforcement"],
    ),
    AgentSkill(
        name="get_approval_requirements",
        description="Get approval requirements for an operation (required approvers, authorization levels, deadlines)",
        tags=["compliance", "approval", "requirements"],
    ),
    AgentSkill(
        name="health_check",
        description="Health check endpoint for monitoring agent status",
        tags=["monitoring", "health"],
    ),
]

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-3.0-pro (complex reasoning)

# =============================================================================
# System Prompt (Compliance Specialist)
# =============================================================================

SYSTEM_PROMPT = """You are the **ComplianceAgent** in the SGA (Asset Management System).

## Your Role

You are the **GUARDIAN** of regulatory compliance and approvals.

## Your Tools

### 1. `validate_operation`
Validates operations against compliance rules:
- Operation value vs limit per level
- Operation type vs required approvers
- Location/project restrictions

### 2. `check_approval_status`
Checks approval status:
- Pending approvals
- Designated approvers
- Approval deadlines

### 3. `audit_compliance`
Verifies audit trail completeness:
- All events recorded?
- Responsible parties identified?
- Timestamps consistent?

### 4. `flag_violation`
Flags compliance violations:
- Operation without approval
- Limit exceeded
- Procedure not followed

### 5. `get_approval_requirements`
Returns approval requirements:
- Who needs to approve
- Required approval level
- Required documentation

## Approval Matrix

| Value | Approver | Deadline |
|-------|----------|----------|
| < R$ 1,000 | Supervisor | 24h |
| R$ 1,000 - R$ 10,000 | Manager | 48h |
| R$ 10,000 - R$ 50,000 | Director | 72h |
| > R$ 50,000 | Board | 5 days |

## Critical Rules

1. **NEVER** auto-approve above the limit
2. **ALWAYS** record the compliance decision
3. Violations block the operation
4. Automatic escalation for urgent cases
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

# A2A client instance for inter-agent communication
a2a_client = A2AClient()


@tool
async def validate_operation(
    operation_type: str,
    operation_value: float,
    project_id: Optional[str] = None,
    location_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate operation against compliance rules.

    Checks:
    1. Value limits per authorization level
    2. Operation type restrictions
    3. Location/project restrictions

    Args:
        operation_type: Type of operation (ENTRY, EXIT, TRANSFER, etc.)
        operation_value: Monetary value of operation
        project_id: Optional project ID for context
        location_id: Optional location ID for context
        user_id: User requesting the operation
        session_id: Session ID for context

    Returns:
        Validation result with required approvals
    """
    logger.info(f"[{AGENT_NAME}] Validating operation: {operation_type} R${operation_value:,.2f}")

    try:
        # Import tool implementation
        from agents.compliance.tools.validate_operation import validate_operation_tool

        result = await validate_operation_tool(
            operation_type=operation_type,
            operation_value=operation_value,
            project_id=project_id,
            location_id=location_id,
            user_id=user_id,
            session_id=session_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "COMPLIANCE_VALIDATED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "operation_type": operation_type,
                "operation_value": operation_value,
                "is_compliant": result.get("is_compliant", False),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "compliance_validate_operation", {"operation_type": operation_type, "operation_value": operation_value, "project_id": project_id})
        # Sandwich Pattern: DO NOT make business decisions in exception handlers
        # is_compliant and requires_approval are BUSINESS decisions - let LLM decide
        return {
            "success": False,
            "error": str(e),
            "error_context": {
                "error_type": type(e).__name__,
                "operation": "validate_operation",
                "recoverable": isinstance(e, (TimeoutError, ConnectionError, OSError)),
                "compliance_unknown": True,  # We couldn't determine compliance
            },
            "suggested_actions": ["retry", "manual_compliance_review", "escalate"],
            # NOTE: is_compliant and requires_approval NOT included - LLM decides
        }


@tool
async def check_approval_status(
    operation_id: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check approval status for an operation.

    Args:
        operation_id: Operation ID to check
        session_id: Session ID for context

    Returns:
        Approval status with pending approvers
    """
    logger.info(f"[{AGENT_NAME}] Checking approval status: {operation_id}")

    try:
        # Import tool implementation
        from agents.compliance.tools.check_approval import check_approval_status_tool

        result = await check_approval_status_tool(
            operation_id=operation_id,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "compliance_check_approval_status", {"operation_id": operation_id})
        return {
            "success": False,
            "error": str(e),
            "status": "UNKNOWN",
        }


@tool
async def audit_compliance(
    entity_type: str,
    entity_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verify audit trail completeness for an entity.

    Args:
        entity_type: Type of entity (MOVEMENT, ENTRY, TRANSFER, etc.)
        entity_id: Entity ID to audit
        date_from: Optional start date for audit range
        date_to: Optional end date for audit range
        session_id: Session ID for context

    Returns:
        Audit compliance result
    """
    logger.info(f"[{AGENT_NAME}] Auditing compliance: {entity_type}/{entity_id}")

    try:
        # Import tool implementation
        from agents.compliance.tools.audit_compliance import audit_compliance_tool

        result = await audit_compliance_tool(
            entity_type=entity_type,
            entity_id=entity_id,
            date_from=date_from,
            date_to=date_to,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "compliance_audit_compliance", {"entity_type": entity_type, "entity_id": entity_id})
        return {
            "success": False,
            "error": str(e),
            "is_compliant": False,
        }


@tool
async def flag_violation(
    violation_type: str,
    entity_type: str,
    entity_id: str,
    description: str,
    severity: str = "medium",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Flag a compliance violation.

    Args:
        violation_type: Type of violation (UNAUTHORIZED, LIMIT_EXCEEDED, etc.)
        entity_type: Type of entity involved
        entity_id: Entity ID involved
        description: Description of the violation
        severity: Severity level (low, medium, high, critical)
        session_id: Session ID for context
        user_id: User who detected/caused the violation

    Returns:
        Violation flag result with violation ID
    """
    logger.info(f"[{AGENT_NAME}] Flagging violation: {violation_type} [{severity}]")

    try:
        # Import tool implementation
        from agents.compliance.tools.flag_violation import flag_violation_tool

        result = await flag_violation_tool(
            violation_type=violation_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            severity=severity,
            session_id=session_id,
            user_id=user_id,
        )

        # Log to ObservationAgent
        await a2a_client.invoke_agent("observation", {
            "action": "log_event",
            "event_type": "VIOLATION_FLAGGED",
            "agent_id": AGENT_ID,
            "session_id": session_id,
            "details": {
                "violation_type": violation_type,
                "severity": severity,
                "violation_id": result.get("violation_id"),
            },
        }, session_id)

        return result

    except Exception as e:
        debug_error(e, "compliance_flag_violation", {"violation_type": violation_type, "entity_type": entity_type, "entity_id": entity_id, "severity": severity})
        return {"success": False, "error": str(e)}


@tool
async def get_approval_requirements(
    operation_type: str,
    operation_value: float,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get approval requirements for an operation.

    Args:
        operation_type: Type of operation
        operation_value: Monetary value of operation
        project_id: Optional project ID for context
        session_id: Session ID for context

    Returns:
        Approval requirements with approvers and deadlines
    """
    logger.info(f"[{AGENT_NAME}] Getting approval requirements: {operation_type} R${operation_value:,.2f}")

    try:
        # Import tool implementation
        from agents.compliance.tools.approval_requirements import get_approval_requirements_tool

        result = await get_approval_requirements_tool(
            operation_type=operation_type,
            operation_value=operation_value,
            project_id=project_id,
            session_id=session_id,
        )

        return result

    except Exception as e:
        debug_error(e, "compliance_get_approval_requirements", {"operation_type": operation_type, "operation_value": operation_value, "project_id": project_id})
        return {
            "success": False,
            "error": str(e),
            "requires_approval": True,
            "approvers": [],
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
        "role": "SUPPORT",
        "specialty": "COMPLIANCE",
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
            validate_operation,
            check_approval_status,
            audit_compliance,
            flag_violation,
            get_approval_requirements,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=ComplianceResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI wrapper.

    Port 9000 is the standard for A2A protocol.
    FastAPI app provides /ping endpoint for health checks.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: SUPPORT (Compliance)")
    logger.info(f"[{AGENT_NAME}] Skills: {len(AGENT_SKILLS)} tools registered")
    for skill in AGENT_SKILLS:
        logger.info(f"[{AGENT_NAME}]   - {skill.name}: {skill.description}")

    # Create FastAPI app first
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping endpoint for health checks
    @app.get("/ping")
    async def ping():
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Create agent
    agent = create_agent()

    # Create A2A server with Agent Card support
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        serve_at_root=False,  # Mount at root instead
        version=AGENT_VERSION,  # Agent version for A2A Agent Card
        skills=AGENT_SKILLS,  # Skills for A2A Agent Card discovery
    )

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
