# =============================================================================
# CodeReviewerAgent - The Code Guardian Specialist
# =============================================================================
# Automated code review specialist triggered after RepairAgent creates DRAFT PR.
# Acts as Red Team adversary to catch issues before human review.
#
# ARCHITECTURE PRINCIPLES (per CLAUDE.md):
# 1. AI-FIRST / AGENTIC - Full Strands Agent with extended thinking
# 2. OBSERVE → THINK → LEARN → ACT loop (Systematic review)
# 3. TOOL-FIRST - AST analysis, security scanning, coverage calculation
# 4. HUMAN-IN-THE-LOOP - ALL reviews posted as COMMENTS (never auto-approve)
# 5. FAIL-CLOSED - Never auto-approve PRs, human final authority
# 6. RED TEAM PATTERN - Act as adversary to find issues proactively
#
# CAPABILITIES:
# 1. AST analysis for complexity and type coverage
# 2. Security vulnerability detection (OWASP Top 10)
# 3. Test coverage analysis for changed lines
# 4. Code quality metrics (cyclomatic complexity, LOC)
# 5. GitHub PR review comment posting
#
# REVIEW RULES (IMMUTABLE):
# 1. NEVER auto-approve PRs (COMMENT or REQUEST_CHANGES only)
# 2. ALWAYS prioritize: Security > Complexity > Coverage > Style
# 3. ALWAYS post findings as GitHub review comments
# 4. CRITICAL findings → REQUEST_CHANGES
# 5. WARNING/INFO findings → COMMENT with suggestions
#
# TRIGGER MODE:
# - Event: RepairAgent creates DRAFT PR → Middleware invokes CodeReviewerAgent
#
# RESPONSE LANGUAGE:
# - System prompt: English (as per CLAUDE.md)
# - User responses: Brazilian Portuguese (pt-BR)
#
# MODEL:
# - Gemini 2.5 Pro + Thinking (critical agent per CLAUDE.md)
#
# VERSION: 2026-01-22T12:00:00Z (Initial implementation)
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

# Structured output schemas
from shared.agent_schemas import CodeReviewResponse

# Tools
from agents.specialists.code_reviewer.tools import (
    ast_analyzer_tool,
    security_scanner_tool,
    coverage_calculator_tool,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "code_reviewer"
AGENT_NAME = "FaistonCodeReviewerAgent"
AGENT_DESCRIPTION = """
The Code Guardian - Automated code review specialist.
Acts as Red Team adversary to catch issues before human review.
Reviews DRAFT PRs created by RepairAgent for security, complexity, and coverage.
"""

# Port for local A2A server (9021, following RepairAgent which uses 9020)
AGENT_PORT = 9021

# Runtime ID for AgentCore deployment (IaC Mandate: from environment)
# Local dev fallback: faiston_code_reviewer-local-dev-only
RUNTIME_ID = os.getenv(
    "CODE_REVIEWER_AGENT_RUNTIME_ID",
    "faiston_code_reviewer-local-dev-only"
)


# =============================================================================
# System Prompt (English per CLAUDE.md)
# =============================================================================

SYSTEM_PROMPT = """You are **The Code Guardian** - CodeReviewerAgent specialist.

## Your Role
Perform automated code review on DRAFT PRs created by RepairAgent.
You are a Red Team adversary whose job is to catch issues BEFORE human review.

## Core Workflow: ANALYZE → DETECT → REPORT → COMMENT

1. **ANALYZE**: Examine PR changes comprehensively
   - Parse Python files with AST analysis
   - Calculate cyclomatic complexity (McCabe)
   - Measure type annotation coverage
   - Count lines of code changed

2. **DETECT**: Find issues proactively
   - **SECURITY** (highest priority): SQL injection, XSS, hardcoded secrets, insecure randomness
   - **COMPLEXITY**: Functions with complexity > 10 (McCabe)
   - **COVERAGE**: Changed lines without test coverage
   - **TYPE_SAFETY**: Missing type annotations on functions/parameters
   - **STYLE**: PEP 8 violations, inconsistent naming
   - **BEST_PRACTICE**: Anti-patterns, code smells

3. **REPORT**: Categorize findings by severity
   - **CRITICAL**: Security vulnerabilities, must fix before merge
   - **WARNING**: High complexity, low coverage, should fix
   - **INFO**: Style issues, suggestions for improvement
   - **PASS**: No issues found

4. **COMMENT**: Post review to GitHub
   - Use `post_pr_review()` tool to add comments
   - Group findings by file and line number
   - Provide actionable recommendations
   - NEVER auto-approve (COMMENT or REQUEST_CHANGES only)

## Review Priority (IMMUTABLE)

Always prioritize in this order:
1. **Security** → Vulnerabilities must be fixed (CRITICAL)
2. **Complexity** → Maintainability issues (WARNING)
3. **Coverage** → Testing gaps (WARNING)
4. **Type Safety** → Type annotations (INFO)
5. **Style** → Code style (INFO)
6. **Best Practice** → Improvements (INFO)

## Detection Rules

### Security (CRITICAL)
- SQL queries with string concatenation (SQL injection risk)
- User input in eval(), exec(), __import__() (code injection)
- Hardcoded passwords, API keys, tokens
- Use of random.random() instead of secrets module
- Unsafe deserialization (pickle, yaml.load)
- Shell command injection (subprocess with shell=True)

### Complexity (WARNING)
- Cyclomatic complexity > 10 (refactor recommended)
- Function length > 50 lines
- Nested loops > 3 levels deep
- Too many parameters (> 5)

### Coverage (WARNING)
- Changed lines with < 80% test coverage
- New functions without any tests
- Critical code paths untested

### Type Safety (INFO)
- Functions without return type annotations
- Parameters without type hints
- Use of `Any` type (too permissive)

### Style (INFO)
- PEP 8 violations (line length, naming)
- Inconsistent formatting
- Missing docstrings on public functions

### Best Practice (INFO)
- Mutable default arguments
- Bare except clauses
- Global variables in modules
- TODO/FIXME comments without tracking

## Response Format

Return CodeReviewResponse with:
- pr_number: PR number being reviewed
- pr_url: Full GitHub PR URL
- review_posted: Whether review was posted to GitHub
- severity: Overall severity (PASS, INFO, WARNING, CRITICAL)
- recommendation: "approve", "request_changes", or "comment"
- findings: List of ReviewFinding objects
- metrics: CodeMetrics object with quantitative metrics
- files_reviewed: List of files analyzed
- human_message: Summary in pt-BR

## Example Workflow

Input (after RepairAgent creates PR):
{
  "action": "review_pr",
  "pr_number": 123,
  "pr_url": "https://github.com/org/repo/pull/123",
  "changed_files": [
    "agents/specialists/intake/main.py",
    "tests/unit/test_intake.py"
  ]
}

Output:
{
  "success": true,
  "pr_number": 123,
  "pr_url": "https://github.com/org/repo/pull/123",
  "review_posted": true,
  "severity": "warning",
  "recommendation": "comment",
  "findings": [
    {
      "file_path": "agents/specialists/intake/main.py",
      "line_number": 142,
      "finding_type": "complexity",
      "severity": "warning",
      "title": "Alta complexidade ciclomática",
      "description": "Função process_inventory_import() tem complexidade 15 (limite: 10)",
      "recommendation": "Refatorar em funções menores para melhorar manutenibilidade",
      "code_snippet": "def process_inventory_import(data):\\n    ..."
    }
  ],
  "critical_count": 0,
  "warning_count": 1,
  "info_count": 3,
  "metrics": {
    "cyclomatic_complexity": 15,
    "lines_of_code": 85,
    "test_coverage": 75.0,
    "type_coverage": 90.0,
    "functions_analyzed": 3,
    "security_issues": 0
  },
  "files_reviewed": ["agents/specialists/intake/main.py", "tests/unit/test_intake.py"],
  "files_skipped": [],
  "human_message": "Revisão completa. 1 aviso encontrado (complexidade alta). Sem issues críticos."
}

## Safety Rules (IMMUTABLE)

1. **Never Auto-Approve**: ONLY use "request_changes" or "comment" review status
2. **Human Final Authority**: Human must always approve PRs, you are advisory only
3. **False Positive Awareness**: Mark findings with confidence level, allow human override
4. **Fail-Closed**: If unable to analyze → "comment" with explanation, don't approve
5. **Audit Trail**: All reviews logged via SecurityAuditHook

## Response Language
Always respond to users in Brazilian Portuguese (pt-BR).
"""


# =============================================================================
# Health Check Tool
# =============================================================================


@tool
def health_check() -> str:
    """
    Check the health status of the CodeReviewerAgent.

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
        "architecture": "red-team-reviewer",
        "capabilities": [
            "ast_analysis",
            "security_scanning",
            "coverage_calculation",
            "complexity_metrics",
            "github_pr_review",
        ],
        "model": "gemini-2.5-pro",
        "thinking_enabled": True,  # Critical agent
        "features": [
            "security-vulnerability-detection",
            "cyclomatic-complexity-analysis",
            "test-coverage-validation",
            "type-annotation-checking",
            "github-integration",
            "red-team-pattern",
            "fail-closed-safety",
            "cognitive-middleware",
        ],
    })


# =============================================================================
# Agent Skills (A2A Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="review_pr",
        name="Review Pull Request",
        description="Perform automated code review on DRAFT PR",
        tags=["code-review", "security", "quality"],
    ),
    AgentSkill(
        id="analyze_security",
        name="Analyze Security",
        description="Detect security vulnerabilities in code changes",
        tags=["security", "owasp", "vulnerabilities"],
    ),
    AgentSkill(
        id="check_complexity",
        name="Check Complexity",
        description="Calculate cyclomatic complexity and detect high complexity",
        tags=["complexity", "maintainability", "metrics"],
    ),
    AgentSkill(
        id="verify_coverage",
        name="Verify Coverage",
        description="Validate test coverage for changed lines",
        tags=["testing", "coverage", "quality"],
    ),
    AgentSkill(
        id="check_types",
        name="Check Type Annotations",
        description="Verify type annotation coverage",
        tags=["types", "type-safety", "python"],
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
    Create the CodeReviewerAgent as a full Strands Agent.

    This agent handles automated code review with:
    - AST analysis for complexity and type coverage
    - Security vulnerability detection (OWASP Top 10)
    - Test coverage validation for changed lines
    - GitHub PR review comment posting
    - SecurityAuditHook for forensic audit trail
    - Gemini 2.5 Pro + Thinking (per CLAUDE.md for critical agents)

    Returns:
        Strands Agent configured for automated code review.
    """
    hooks = [
        LoggingHook(log_level=logging.INFO),
        MetricsHook(namespace="FaistonSGA", emit_to_cloudwatch=True),
        DebugHook(timeout_seconds=30.0),
        SecurityAuditHook(enabled=True),  # FAIL-CLOSED audit trail
    ]

    # Code Review Tools
    tools = [
        # Analysis Tools
        ast_analyzer_tool,
        security_scanner_tool,
        coverage_calculator_tool,
        # System Tools
        health_check,
    ]

    agent = Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # Gemini 2.5 Pro + Thinking
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        hooks=hooks,
        # Structured output for type safety (ADR-005)
        structured_output_model=CodeReviewResponse,
    )

    logger.info(f"[CodeReviewerAgent] Created {AGENT_NAME} with {len(hooks)} hooks")
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
        f"[CodeReviewerAgent] Created A2A server on port {AGENT_PORT} "
        f"with {len(AGENT_SKILLS)} skills"
    )
    return server


# =============================================================================
# Main Entrypoint
# =============================================================================


def main() -> None:
    """
    Start the CodeReviewerAgent A2A server.

    For local development:
        cd server/agentcore-inventory
        python -m agents.specialists.code_reviewer.main

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

    logger.info(f"[CodeReviewerAgent] Starting A2A server on port {AGENT_PORT}...")

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
                "ast-analysis",
                "security-scanning",
                "coverage-calculation",
                "complexity-metrics",
                "github-pr-review",
                "red-team-pattern",
                "fail-closed-safety",
                "cognitive-middleware",
            ],
        }

    # Create agent and A2A server
    agent = create_agent()
    a2a_server = create_a2a_server(agent)

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[CodeReviewerAgent] Starting uvicorn server on 0.0.0.0:{AGENT_PORT}")
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
