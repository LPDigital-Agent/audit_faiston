# =============================================================================
# RepairAgent - The Software Surgeon Specialist
# =============================================================================
# Automated code repair specialist triggered by DebugAgent when
# suggested_action == "repair" in DebugAnalysisResponse.
#
# ARCHITECTURE PRINCIPLES (per CLAUDE.md):
# 1. AI-FIRST / AGENTIC - Full Strands Agent with extended thinking
# 2. OBSERVE → THINK → LEARN → ACT loop (Surgical precision)
# 3. TOOL-FIRST - Git operations, AST validation, test execution
# 4. HUMAN-IN-THE-LOOP - ALL repairs create DRAFT PRs for review
# 5. FAIL-CLOSED - SecurityAuditHook ensures complete audit trail
# 6. COGNITIVE MIDDLEWARE - ALL errors enriched by DebugAgent
#
# CAPABILITIES:
# 1. Create safe Git branches (fix/BUG-XXX-description pattern)
# 2. Commit fixes with MANDATORY syntax validation
# 3. Create DRAFT PRs with security audit labels
# 4. Validate Python syntax via AST parsing
# 5. Run targeted tests for verification
#
# SAFETY RULES (IMMUTABLE):
# 1. NEVER commit to protected branches (main, master, prod, production)
# 2. ALWAYS validate syntax before committing
# 3. ALWAYS create DRAFT PRs (never auto-merge)
# 4. Maximum 3 repair attempts per error_signature
# 5. 5-minute cooldown between attempts
#
# TRIGGER MODE:
# - Event: DebugAgent returns suggested_action="repair" → Cognitive middleware invokes RepairAgent
#
# RESPONSE LANGUAGE:
# - System prompt: English (as per CLAUDE.md)
# - User responses: Brazilian Portuguese (pt-BR)
#
# MODEL:
# - Gemini 2.5 Pro + Thinking (critical agent per CLAUDE.md)
#
# VERSION: 2026-01-22T00:00:00Z (Initial implementation)
# =============================================================================

import json
import logging
import os
import sys
from typing import Any, Dict, List

# Add parent directory to path for imports (required by AgentCore runtime)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill

# Agent utilities
from agents.utils import create_gemini_model, AGENT_VERSION

# Hooks (per ADR-002)
from shared.hooks.logging_hook import LoggingHook
from shared.hooks.metrics_hook import MetricsHook
from shared.hooks.debug_hook import DebugHook
from shared.hooks.security_audit_hook import SecurityAuditHook

# Cognitive error handler (Nexo Immune System)
from shared.cognitive_error_handler import cognitive_error_handler

# Structured output schemas
from shared.agent_schemas import RepairResponse

# Tools (absolute imports for AgentCore runtime compatibility)
from agents.specialists.repair.tools import (
    create_fix_branch_tool,
    commit_fix_tool,
    create_pr_tool,
    validate_python_ast_tool,
    run_targeted_tests_tool,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "repair"
AGENT_NAME = "FaistonRepairAgent"
AGENT_DESCRIPTION = """
The Software Surgeon - Automated code repair specialist.
Applies fixes when DebugAgent identifies repairable errors.
Creates DRAFT PRs for human review with complete audit trail.
"""

# Port for local A2A server (see LOCAL_AGENTS in a2a_client.py:1465)
AGENT_PORT = 9020

# Runtime ID for AgentCore deployment (IaC Mandate: from environment)
# Local dev fallback: faiston_repair-local-dev-only
RUNTIME_ID = os.getenv(
    "REPAIR_AGENT_RUNTIME_ID",
    "faiston_repair-local-dev-only"
)


# =============================================================================
# System Prompt (English per CLAUDE.md)
# =============================================================================

SYSTEM_PROMPT = """You are **The Software Surgeon** - RepairAgent specialist.

## Your Role
Apply automated code fixes when DebugAgent identifies repairable errors.
You are triggered when `suggested_action == "repair"` in DebugAnalysisResponse.

## Core Workflow: DIAGNOSE → FIX → VALIDATE → PR

1. **DIAGNOSE**: Receive error context from DebugAgent
   - error_signature: Unique error identifier
   - root_causes: List of potential root causes with confidence
   - suggested_fix: Human-readable fix suggestion
   - file_context: Source file and line number

2. **FIX**: Generate code fix
   - Use `create_fix_branch_tool()` to create safe branch (fix/BUG-XXX-description)
   - Apply minimal, targeted fix to address root cause
   - NEVER modify unrelated code (surgical precision)

3. **VALIDATE**: Ensure fix quality
   - Use `validate_python_ast_tool()` to check syntax (MANDATORY)
   - Use `run_targeted_tests_tool()` to run relevant tests
   - If validation fails → ABORT and return error

4. **PR**: Submit for human review
   - Use `commit_fix_tool()` to commit changes
   - Use `create_pr_tool()` to create DRAFT PR with labels
   - PR title: "fix(BUG-XXX): [Brief description]"
   - PR body: Includes error details, fix explanation, test results

## Safety Rules (IMMUTABLE)

1. **Branch Protection**: NEVER commit to main/master/prod branches
   - ONLY commit to branches with prefix: fix/, feature/, hotfix/
   - Validation enforced by validate_branch_safety() in tools

2. **Syntax Validation**: ALWAYS validate before commit
   - Call validate_python_ast_tool() on new code
   - If AST parsing fails → ABORT repair

3. **Loop Prevention**: Maximum 3 repair attempts per error_signature
   - Use error_signature for deduplication
   - 5-minute cooldown between attempts
   - If 3 attempts fail → ESCALATE to human

4. **Minimal Changes**: Surgical precision only
   - Change ONLY the lines directly related to the error
   - NO refactoring, NO style changes, NO "improvements"
   - Preserve existing code style and formatting

5. **Human-in-the-Loop**: ALL repairs require review
   - ALWAYS create DRAFT PRs (never auto-merge)
   - Include test results in PR body
   - Add labels: automated-fix, needs-review, security-audit

## Response Format

Return RepairResponse with:
- fix_applied: Whether fix was successful
- branch_name: Git branch with fix
- pr_url: Draft PR URL for review
- syntax_valid: AST validation result
- tests_passed: Test execution result
- human_message: Summary in pt-BR

## Example Workflow

Input from DebugAgent:
{
  "error_signature": "ValidationError:missing_part_number:L142",
  "error_type": "ValidationError",
  "root_causes": [
    {"cause": "Missing required field validation", "confidence": 0.95}
  ],
  "suggested_action": "repair",
  "file_context": {
    "file": "agents/specialists/intake/main.py",
    "line": 142,
    "function": "process_inventory_import"
  }
}

Output:
{
  "success": true,
  "fix_applied": true,
  "branch_name": "fix/BUG-044-missing-part-number-validation",
  "commit_sha": "a1b2c3d",
  "pr_url": "https://github.com/org/repo/pull/123",
  "syntax_valid": true,
  "tests_passed": true,
  "files_modified": ["agents/specialists/intake/main.py"],
  "human_message": "Correção aplicada com sucesso! PR #123 criado para revisão."
}

## Response Language
Always respond to users in Brazilian Portuguese (pt-BR).
"""


# =============================================================================
# Health Check Tool
# =============================================================================


@tool
def health_check() -> str:
    """
    Check the health status of the RepairAgent.

    Returns system information useful for debugging and monitoring.

    Returns:
        JSON string with health status, version, and capabilities.
    """
    return json.dumps({
        "success": True,
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "runtime_id": RUNTIME_ID,
        "architecture": "software-surgeon",
        "capabilities": [
            "create_fix_branch",
            "commit_fix",
            "create_pr",
            "validate_python_ast",
            "run_targeted_tests",
        ],
        "model": "gemini-2.5-pro",
        "thinking_enabled": True,  # Critical agent
        "features": [
            "git-operations",
            "syntax-validation",
            "test-execution",
            "branch-protection",
            "draft-prs",
            "security-audit",
            "cognitive-middleware",
        ],
    })


# =============================================================================
# Agent Skills (A2A Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="create_fix_branch",
        name="Create Fix Branch",
        description="Create safe Git branch for automated fix",
        tags=["git", "branch", "safety"],
    ),
    AgentSkill(
        id="commit_fix",
        name="Commit Fix",
        description="Commit fix with mandatory syntax validation",
        tags=["git", "commit", "validation"],
    ),
    AgentSkill(
        id="create_pr",
        name="Create PR",
        description="Create DRAFT pull request for human review",
        tags=["git", "pr", "review"],
    ),
    AgentSkill(
        id="validate_syntax",
        name="Validate Syntax",
        description="Validate Python syntax via AST parsing",
        tags=["validation", "ast", "syntax"],
    ),
    AgentSkill(
        id="run_tests",
        name="Run Tests",
        description="Execute targeted tests for verification",
        tags=["testing", "verification", "pytest"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Check agent health status and capabilities",
        tags=["health", "monitoring"],
    ),
]


# =============================================================================
# Agent Factory
# =============================================================================


def create_agent() -> Agent:
    """
    Create the RepairAgent as a full Strands Agent.

    This agent handles automated code repairs with:
    - Git operations via GitHub CLI
    - MANDATORY syntax validation before commits
    - DRAFT PRs for human review
    - SecurityAuditHook for forensic audit trail
    - Cognitive Middleware for error enrichment
    - Gemini 2.5 Pro + Thinking (per CLAUDE.md for critical agents)

    Returns:
        Strands Agent configured for automated code repair.
    """
    hooks = [
        LoggingHook(log_level=logging.INFO),
        MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        DebugHook(timeout_seconds=30.0),
        SecurityAuditHook(enabled=True),  # FAIL-CLOSED audit trail
    ]

    agent = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # Gemini 2.5 Pro + Thinking
        tools=[
            # Git operations
            create_fix_branch_tool,
            commit_fix_tool,
            create_pr_tool,
            # Syntax validation
            validate_python_ast_tool,
            run_targeted_tests_tool,
            # System
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
        # Structured output for type safety (AUDIT-001)
        structured_output_model=RepairResponse,
    )

    logger.info(f"[RepairAgent] Created {AGENT_NAME} with {len(hooks)} hooks")
    return agent


def create_a2a_server(agent: Agent) -> A2AServer:
    """
    Create A2A server for agent-to-agent communication.

    The A2AServer wraps the Strands Agent and provides:
    - JSON-RPC 2.0 endpoint at /
    - Agent Card discovery at /.well-known/agent-card.json
    - Health check at /health

    Args:
        agent: The Strands Agent to wrap.

    Returns:
        A2AServer instance ready to mount on FastAPI.
    """
    server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=AGENT_PORT,
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
        serve_at_root=False,  # Mount at root below
    )

    logger.info(
        f"[RepairAgent] Created A2A server on port {AGENT_PORT} "
        f"with {len(AGENT_SKILLS)} skills"
    )
    return server


# =============================================================================
# Main Entrypoint
# =============================================================================


def main() -> None:
    """
    Start the RepairAgent A2A server.

    For local development:
        cd server/agentcore-inventory
        python -m agents.specialists.repair.main

    For AgentCore deployment:
        agentcore deploy --profile faiston-aio
    """
    # Import FastAPI and uvicorn here to avoid circular imports
    from fastapi import FastAPI
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info(f"[RepairAgent] Starting A2A server on port {AGENT_PORT}...")

    # Create FastAPI app
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    # Add /ping health endpoint for AWS ALB
    @app.get("/ping")
    async def ping():
        """Health check endpoint for AWS Application Load Balancer."""
        return {
            "status": "healthy",
            "agent": AGENT_ID,
            "version": AGENT_VERSION,
        }

    # Add /health endpoint
    @app.get("/health")
    async def health():
        """Detailed health check endpoint."""
        return {
            "status": "healthy",
            "agent_id": AGENT_ID,
            "agent_name": AGENT_NAME,
            "version": AGENT_VERSION,
            "port": AGENT_PORT,
            "runtime_id": RUNTIME_ID,
            "features": [
                "git-operations",
                "syntax-validation",
                "test-execution",
                "branch-protection",
                "draft-prs",
                "security-audit",
                "cognitive-middleware",
            ],
        }

    # Create agent and A2A server
    agent = create_agent()
    a2a_server = create_a2a_server(agent)

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[RepairAgent] Starting uvicorn server on 0.0.0.0:{AGENT_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "AGENT_ID",
    "AGENT_NAME",
    "AGENT_PORT",
    "RUNTIME_ID",
    "create_agent",
    "create_a2a_server",
    "main",
]


if __name__ == "__main__":
    main()
