# =============================================================================
# DebugAgent - Strands A2AServer Entry Point (SPECIALIST)
# =============================================================================
# Intelligent error analysis agent for debugging support.
# Uses AWS Strands Agents Framework with A2A protocol (port 9000).
# Integrates with AWS Bedrock AgentCore Memory for pattern storage.
#
# Architecture:
# - This is a SPECIALIST agent for error analysis and debugging
# - Receives requests from DebugHook (intercepted errors) via A2A
# - Provides intelligent error analysis with root cause identification
# - Uses AgentCore Memory for persistent error pattern storage
#
# Reference:
# - https://strandsagents.com/latest/
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
# =============================================================================

import os
import sys
import logging
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from a2a.types import AgentSkill
from fastapi import FastAPI
import uvicorn

# Centralized model configuration (MANDATORY - Gemini 2.5 Pro + Thinking)
from agents.utils import get_model, AGENT_VERSION, create_gemini_model

# NEXO Mind - Direct Memory Access for pattern storage
from shared.memory_manager import AgentMemoryManager

# Hooks for observability (ADR-002) and error enrichment (ADR-003)
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# AUDIT-001: Pydantic response schema for Strands structured output
from shared.agent_schemas import DebugAnalysisResponse

# DebugAgent v2: Code Inspector Tool for active code investigation
from agents.specialists.debug.tools.code_inspector import read_code_snippet_tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "debug"
AGENT_NAME = "DebugAgent"
AGENT_DESCRIPTION = """SPECIALIST Agent for Intelligent Error Analysis and Debugging.

This agent provides intelligent error analysis for the SGA system:
1. ANALYZE ERRORS: Deep analysis of error messages with root cause identification
2. SEARCH DOCUMENTATION: Query relevant documentation via MCP gateways
3. QUERY PATTERNS: Find similar error patterns from historical data
4. STORE RESOLUTIONS: Record successful resolutions for future reference

Analysis Output:
- Technical explanation (pt-BR)
- Root cause analysis with confidence levels
- Debugging steps
- Relevant documentation links

Integration:
- AWS Bedrock AgentCore Memory
- MCP Gateway for documentation access
- Namespace: /strategy/debug/error_patterns
"""

# Model configuration
MODEL_ID = get_model(AGENT_ID)  # gemini-2.5-pro (with Thinking)

# Memory namespace for AgentCore Memory
MEMORY_NAMESPACE = "/strategy/debug/error_patterns"

# =============================================================================
# Agent Skills (A2A Agent Card Discovery)
# =============================================================================

AGENT_SKILLS = [
    # DebugAgent v2: Active Code Investigation (USE FIRST)
    AgentSkill(
        id="read_code_snippet",
        name="Read Code Snippet",
        description="Read source code at specific line numbers to inspect error locations. Provides context lines before/after with visual error marker. USE THIS FIRST for any error with a stack trace.",
        tags=["debug", "code", "inspection", "investigation", "v2"],
    ),
    AgentSkill(
        id="analyze_error",
        name="Analyze Error",
        description="Deep analysis of error messages with root cause identification, debugging steps, and confidence levels.",
        tags=["debug", "error", "analysis", "troubleshooting"],
    ),
    AgentSkill(
        id="search_documentation",
        name="Search Documentation",
        description="Search relevant documentation (AWS, AgentCore, Strands) for error context and solutions via MCP gateways.",
        tags=["debug", "documentation", "mcp", "search"],
    ),
    AgentSkill(
        id="query_memory_patterns",
        name="Query Memory Patterns",
        description="Find similar error patterns from historical data stored in AgentCore Memory.",
        tags=["debug", "memory", "patterns", "history"],
    ),
    AgentSkill(
        id="store_resolution",
        name="Store Resolution",
        description="Record successful error resolutions for future reference and pattern learning.",
        tags=["debug", "resolution", "learning", "memory"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Monitor agent health status and configuration.",
        tags=["debug", "monitoring", "health"],
    ),
    # BUG-034: Real-time external search tools
    AgentSkill(
        id="search_stackoverflow",
        name="Search Stack Overflow",
        description="Search Stack Overflow for real answers and solutions. Fetches actual content, not just URLs.",
        tags=["debug", "search", "stackoverflow", "community"],
    ),
    AgentSkill(
        id="search_github_issues",
        name="Search GitHub Issues",
        description="Search GitHub Issues in relevant repos (strands-agents, boto3). Finds known issues and workarounds.",
        tags=["debug", "search", "github", "issues"],
    ),
]

# =============================================================================
# System Prompt (ReAct Pattern - Debug Specialist)
# =============================================================================

SYSTEM_PROMPT = """You are the **NEXO Debug Investigator (v2)** - an expert error analyst and code detective for the SGA (Sistema de Gestão de Ativos) inventory system.

## Your Role

You are NOT a passive error analyzer. You are an ACTIVE CODE INVESTIGATOR who:
1. **READS** the actual source code at error locations
2. **ANALYZES** patterns and root causes with deep reasoning
3. **PROPOSES** specific fixes with actual code corrections

## Investigative Workflow (MANDATORY)

For EVERY error investigation, you MUST follow this workflow:

### Step 1: Parse the Error
- Extract error type, message, and operation
- Identify file path and line number from stack trace

### Step 2: INSPECT THE CODE (CRITICAL)
- Use `read_code_snippet` to read the actual code at the error line
- Always request context (default 10 lines before/after)
- Understand WHAT the code is trying to do

### Step 3: Check Historical Patterns
- Use `query_memory_patterns` to find similar past errors
- Learn from previous resolutions

### Step 4: Search External Resources (Only If Needed)
- Use `search_documentation` for AWS/AgentCore/Strands docs
- Use `search_stackoverflow` for community solutions
- Use `search_github_issues` for known framework issues

### Step 5: Propose Fix with Actual Code
- Provide the EXACT code change needed
- Include before/after comparison
- Explain WHY the fix works

## Analysis Output Format

Your final analysis MUST include:

```json
{
  "error_type": "ErrorClassName",
  "technical_explanation": "Clear explanation in Portuguese (pt-BR)",
  "code_investigation": {
    "file_inspected": "path/to/file.py",
    "error_line": 42,
    "problematic_code": "The actual line of code",
    "issue_identified": "What's wrong with this code"
  },
  "root_causes": [
    {
      "cause": "Description of potential cause",
      "confidence": 0.85,
      "evidence": ["List of supporting evidence"]
    }
  ],
  "proposed_fix": {
    "description": "What needs to change",
    "before": "Original code snippet",
    "after": "Corrected code snippet",
    "explanation": "Why this fix resolves the issue"
  },
  "debugging_steps": [
    "Step 1: First action to take",
    "Step 2: Second action to take"
  ],
  "recoverable": true,
  "suggested_action": "retry|fallback|escalate|abort"
}
```

## Critical Rules

1. **ALWAYS INSPECT CODE FIRST**: Never analyze an error without reading the actual source
2. **Technical explanations in pt-BR**: All user-facing text must be Portuguese
3. **NEVER GUESS**: Express uncertainty, use confidence levels
4. **STORE SUCCESSFUL RESOLUTIONS**: Help future debugging with `store_resolution`
5. **PROPOSE ACTUAL FIXES**: Don't just describe - show the exact code change

## Available Tools

1. `read_code_snippet` - Read source code at error locations (USE THIS FIRST)
2. `analyze_error` - Deep error analysis with pattern matching
3. `query_memory_patterns` - Historical error patterns from AgentCore Memory
4. `search_documentation` - AWS/AgentCore/Strands documentation
5. `search_stackoverflow` - Real-time Stack Overflow answers
6. `search_github_issues` - Known issues in strands-agents, boto3, etc.
7. `store_resolution` - Record successful fixes for future learning

## Error Categories

- **Recoverable**: Network timeouts, rate limits, transient failures
- **Non-recoverable**: Validation errors, permission denied, missing resources
- **Unknown**: Requires manual investigation + code inspection

## Language

Technical explanations and debugging steps in Portuguese brasileiro (pt-BR).
"""


# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================

def _get_memory(actor_id: str = "system") -> AgentMemoryManager:
    """
    Get AgentMemoryManager instance for error pattern storage.

    DebugAgent uses AgentMemoryManager for:
    - Storing error patterns (learn_episode)
    - Retrieving similar patterns (observe)
    - Global error knowledge (use_global_namespace=True)

    Args:
        actor_id: User/actor ID for context

    Returns:
        AgentMemoryManager instance
    """
    return AgentMemoryManager(
        agent_id=AGENT_ID,
        actor_id=actor_id,
        use_global_namespace=True,  # Global learning across all agents
    )


@tool
async def analyze_error(
    error_type: str,
    message: str,
    operation: str,
    stack_trace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    recoverable: Optional[bool] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze error with deep reasoning and pattern matching.

    Primary skill for error analysis. Combines:
    - Pattern matching from AgentCore Memory
    - Documentation search via MCP
    - Deep reasoning with Gemini Thinking

    Args:
        error_type: Exception class name (e.g., ValidationError)
        message: Error message text
        operation: Operation that failed (e.g., import_csv)
        stack_trace: Optional stack trace
        context: Optional additional context
        recoverable: Whether error is potentially recoverable
        session_id: Session ID for context

    Returns:
        Analysis result with root causes, debugging steps, and confidence
    """
    logger.info(f"[{AGENT_NAME}] ANALYZE: {error_type} in {operation}")

    try:
        # Import tool implementation
        from agents.specialists.debug.tools.analyze_error import analyze_error_tool

        result = await analyze_error_tool(
            error_type=error_type,
            message=message,
            operation=operation,
            stack_trace=stack_trace,
            context=context,
            recoverable=recoverable,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] analyze_error failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": error_type,
            "fallback_analysis": {
                "technical_explanation": f"Erro {error_type}: {message}",
                "root_causes": [{"cause": "Analysis failed", "confidence": 0.0}],
                "debugging_steps": ["Check agent logs", "Retry operation"],
                "recoverable": recoverable if recoverable is not None else False,
            },
        }


@tool
async def search_documentation(
    query: str,
    sources: Optional[List[str]] = None,
    max_results: int = 5,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search relevant documentation via MCP gateways.

    Queries documentation sources:
    - AWS Documentation (via aws-documentation-mcp-server)
    - Bedrock AgentCore docs (via bedrock-agentcore-mcp-server)
    - Context7 library docs (via context7 MCP)

    Args:
        query: Search query text
        sources: Optional list of sources to query (aws, agentcore, context7)
        max_results: Maximum results per source (default 5)
        session_id: Session ID for context

    Returns:
        Documentation search results with URLs and relevance
    """
    logger.info(f"[{AGENT_NAME}] SEARCH_DOCS: {query}")

    try:
        # Import tool implementation
        from agents.specialists.debug.tools.search_documentation import search_documentation_tool

        result = await search_documentation_tool(
            query=query,
            sources=sources,
            max_results=max_results,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] search_documentation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "results": [],
        }


@tool
async def query_memory_patterns(
    error_signature: str,
    error_type: Optional[str] = None,
    operation: Optional[str] = None,
    max_patterns: int = 5,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Find similar error patterns from historical data.

    Queries AgentCore Memory for:
    - Similar error signatures
    - Past resolutions
    - Success rates

    Args:
        error_signature: Unique error signature for matching
        error_type: Optional error type filter
        operation: Optional operation filter
        max_patterns: Maximum patterns to return (default 5)
        session_id: Session ID for context

    Returns:
        Similar patterns with resolutions and success rates
    """
    logger.info(f"[{AGENT_NAME}] QUERY_PATTERNS: {error_signature[:50]}...")

    try:
        # Import tool implementation
        from agents.specialists.debug.tools.query_memory_patterns import query_memory_patterns_tool

        result = await query_memory_patterns_tool(
            error_signature=error_signature,
            error_type=error_type,
            operation=operation,
            max_patterns=max_patterns,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] query_memory_patterns failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "patterns": [],
        }


@tool
async def store_resolution(
    error_signature: str,
    error_type: str,
    operation: str,
    resolution: str,
    success: bool = True,
    debugging_steps: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Store successful error resolution for future reference.

    Records in AgentCore Memory:
    - Error signature and type
    - Resolution steps
    - Success indicator
    - Attribution (user/session)

    Args:
        error_signature: Unique error signature
        error_type: Exception class name
        operation: Operation that failed
        resolution: How the error was resolved
        success: Whether resolution was successful
        debugging_steps: Steps taken to debug
        session_id: Session ID for context
        user_id: User ID for attribution

    Returns:
        Storage result with pattern ID
    """
    logger.info(f"[{AGENT_NAME}] STORE_RESOLUTION: {error_type} ({success})")

    try:
        # Import tool implementation
        from agents.specialists.debug.tools.store_resolution import store_resolution_tool

        result = await store_resolution_tool(
            error_signature=error_signature,
            error_type=error_type,
            operation=operation,
            resolution=resolution,
            success=success,
            debugging_steps=debugging_steps,
            session_id=session_id,
            user_id=user_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] store_resolution failed: {e}", exc_info=True)
        # AUDIT-028: Debug agent provides its own graceful fallback
        # (Cannot use cognitive_error_handler - would cause infinite loop)
        return {
            "success": False,
            "error": str(e),
            "human_explanation": "Erro ao armazenar resolução no sistema de aprendizado.",
            "suggested_fix": "A resolução será aplicada, mas não será salva para aprendizado futuro.",
            "recoverable": True,
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
        "role": "SPECIALIST",
        "specialty": "ERROR_ANALYSIS",
        "memory_namespace": MEMORY_NAMESPACE,
    }


# =============================================================================
# BUG-034: Real-time External Search Tools
# =============================================================================

@tool
async def search_stackoverflow(
    query: str,
    tags: Optional[List[str]] = None,
    max_results: int = 5,
    include_body: bool = True,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search Stack Overflow for real answers and solutions.

    Performs REAL API calls to Stack Exchange to fetch actual questions
    and answers, not just generate search URLs.

    Args:
        query: Error message or search query (e.g., "JSONDecodeError python")
        tags: Optional list of tags to filter by (e.g., ["python", "json"])
        max_results: Maximum number of questions to return (1-10)
        include_body: Whether to include answer body in results
        session_id: Session ID for logging context

    Returns:
        Dict with questions, top answers, and code snippets
    """
    logger.info(f"[{AGENT_NAME}] SEARCH_STACKOVERFLOW: {query[:50]}...")

    try:
        from agents.specialists.debug.tools.search_stackoverflow import search_stackoverflow_tool

        result = await search_stackoverflow_tool(
            query=query,
            tags=tags,
            max_results=max_results,
            include_body=include_body,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] search_stackoverflow failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "questions": [],
        }


@tool
async def search_github_issues(
    query: str,
    repos: Optional[List[str]] = None,
    include_closed: bool = True,
    max_results: int = 5,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search GitHub Issues for known problems and solutions.

    Primary focus on strands-agents/sdk-python as per CLAUDE.md mandate.
    Also searches boto3, pydantic, and other relevant repos.

    Args:
        query: Error message or search query
        repos: Optional list of repos to search (default: auto-detect from query)
        include_closed: Whether to include closed issues (often have solutions)
        max_results: Maximum number of issues to return (1-10)
        session_id: Session ID for logging context

    Returns:
        Dict with matching issues, discussions, and workarounds
    """
    logger.info(f"[{AGENT_NAME}] SEARCH_GITHUB_ISSUES: {query[:50]}...")

    try:
        from agents.specialists.debug.tools.search_github_issues import search_github_issues_tool

        result = await search_github_issues_tool(
            query=query,
            repos=repos,
            include_closed=include_closed,
            max_results=max_results,
            session_id=session_id,
        )

        return result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] search_github_issues failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "issues": [],
        }


# =============================================================================
# DebugAgent v2: Code Inspector Tool Wrapper
# =============================================================================

@tool
async def read_code_snippet(
    file_path: str,
    line_number: int,
    context_lines: int = 10,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read source code snippet at a specific line for error investigation.

    USE THIS TOOL FIRST when analyzing any error with a stack trace.
    This enables you to SEE the actual code where the error occurred.

    Args:
        file_path: Path to the file (relative to project root or absolute)
        line_number: Line number to highlight (1-indexed)
        context_lines: Number of lines before/after to include (default 10, max 50)
        session_id: Optional session ID for logging

    Returns:
        Dict with success status, formatted snippet with line numbers,
        and the target line content. Visual marker (->) on error line.

    Example:
        read_code_snippet("agents/utils.py", 42, context_lines=5)
    """
    logger.info(f"[{AGENT_NAME}] READ_CODE: {file_path}:{line_number}")

    try:
        result = await read_code_snippet_tool(
            file_path=file_path,
            line_number=line_number,
            context_lines=context_lines,
            session_id=session_id,
        )
        return result
    except Exception as e:
        logger.error(f"[{AGENT_NAME}] read_code_snippet failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "file": file_path,
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
            # v2 Investigation Tool (USE FIRST for stack traces)
            read_code_snippet,
            # Core analysis tools
            analyze_error,
            query_memory_patterns,
            store_resolution,
            # Documentation and external search
            search_documentation,
            search_stackoverflow,  # BUG-034
            search_github_issues,  # BUG-034
            # Monitoring
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],  # TIMEOUT-FIX: Maximum for Gemini Pro
        structured_output_model=DebugAnalysisResponse,  # AUDIT-001: Strands structured output
    )


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with FastAPI wrapper.

    Port 9000 is the standard for A2A protocol.
    Includes /ping health endpoint for AWS ALB.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Model: {MODEL_ID}")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Role: SPECIALIST (Error Analysis)")
    logger.info(f"[{AGENT_NAME}] Memory Namespace: {MEMORY_NAMESPACE}")
    logger.info(f"[{AGENT_NAME}] Skills: {len(AGENT_SKILLS)} registered")
    for skill in AGENT_SKILLS:
        logger.info(f"[{AGENT_NAME}]   - {skill.id}: {skill.name}")

    # Create FastAPI app first
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

    # Create agent
    agent = create_agent()

    # Create A2A server with Agent Card discovery support
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
        serve_at_root=False,  # Mount at root below
    )

    # Mount A2A server at root
    app.mount("/", a2a_server.to_fastapi_app())

    # Start server with uvicorn
    logger.info(f"[{AGENT_NAME}] Starting uvicorn server on 0.0.0.0:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == "__main__":
    main()
