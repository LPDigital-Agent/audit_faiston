# =============================================================================
# DebugAgent Tool: analyze_error - AI-Powered Error Analysis
# =============================================================================
# Deep error analysis with Gemini 2.5 Pro reasoning.
#
# ARCHITECTURE (CLAUDE.md Compliance):
# - "LLM = Brain / Python = Hands" principle
# - "Sandwich Pattern": CODE → LLM → CODE
#
# Analysis Strategy:
# 1. CODE: Generate error signature for pattern matching
# 2. CODE: Query AgentCore Memory for similar patterns
# 3. CODE: Search documentation via MCP gateways
# 4. LLM: Deep reasoning with Gemini 2.5 Pro + Thinking
# 5. CODE: Parse and validate LLM response
#
# Output:
# - Technical explanation (pt-BR)
# - Root causes with confidence levels (LLM-powered)
# - Debugging steps (LLM-powered)
# - Documentation links
# - Similar patterns
# =============================================================================

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from strands import Agent

from agents.utils import create_gemini_model

logger = logging.getLogger(__name__)

# =============================================================================
# Error Categories (Python = Hands - Deterministic Classification)
# =============================================================================

ERROR_CATEGORIES = {
    "ValidationError": {"recoverable": False, "category": "validation"},
    "KeyError": {"recoverable": False, "category": "validation"},
    "ValueError": {"recoverable": False, "category": "validation"},
    "TypeError": {"recoverable": False, "category": "validation"},
    "TimeoutError": {"recoverable": True, "category": "network"},
    "ConnectionError": {"recoverable": True, "category": "network"},
    "OSError": {"recoverable": True, "category": "system"},
    "PermissionError": {"recoverable": False, "category": "permission"},
    "FileNotFoundError": {"recoverable": False, "category": "resource"},
    "ResourceExhausted": {"recoverable": True, "category": "resource"},
    "RateLimitError": {"recoverable": True, "category": "rate_limit"},
}


# =============================================================================
# Python Utility Functions (Python = Hands)
# =============================================================================


def generate_error_signature(
    error_type: str,
    message: str,
    operation: str,
) -> str:
    """
    Generate unique signature for error pattern matching.

    Signature is based on:
    - Error type (class name)
    - Normalized message (stripped of variable content)
    - Operation name

    Args:
        error_type: Exception class name
        message: Error message
        operation: Operation that failed

    Returns:
        Hash-based error signature
    """
    # Normalize message by removing variable content
    # Defensive coding - handle non-string messages
    normalized_msg = str(message).lower() if message else ""
    # Remove UUIDs
    normalized_msg = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<UUID>",
        normalized_msg,
    )
    # Remove timestamps
    normalized_msg = re.sub(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
        "<TIMESTAMP>",
        normalized_msg,
    )
    # Remove numbers
    normalized_msg = re.sub(r"\d+", "<NUM>", normalized_msg)

    # Create signature
    content = f"{error_type}:{operation}:{normalized_msg}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def classify_error(error_type: str) -> Dict[str, Any]:
    """
    Classify error by type.

    Args:
        error_type: Exception class name

    Returns:
        Classification dict with recoverable status and category
    """
    # Direct match
    if error_type in ERROR_CATEGORIES:
        return ERROR_CATEGORIES[error_type]

    # Pattern matching for common suffixes
    if error_type.endswith("Error"):
        base = error_type[:-5]
        for known_type, info in ERROR_CATEGORIES.items():
            if base in known_type:
                return info

    # Default: non-recoverable, unknown category
    return {"recoverable": False, "category": "unknown"}


# =============================================================================
# Main Tool Function - AI-Powered Error Analysis
# =============================================================================


async def analyze_error_tool(
    error_type: str,
    message: str,
    operation: str,
    stack_trace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    recoverable: Optional[bool] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze error with Gemini 2.5 Pro reasoning.

    AI-powered error analysis implementing CLAUDE.md "Sandwich Pattern"
    (CODE → LLM → CODE). Uses LLM for deep reasoning while Python handles
    deterministic tasks like signature generation and memory queries.

    Architecture:
    - CODE (Python = Hands): Signature generation, memory query, doc search
    - LLM (Gemini = Brain): Deep reasoning, root cause analysis, recommendations
    - CODE (Python = Hands): Response validation and formatting

    Args:
        error_type: Exception class name
        message: Error message text
        operation: Operation that failed
        stack_trace: Optional stack trace
        context: Optional additional context
        recoverable: Whether error is potentially recoverable
        session_id: Session ID for context

    Returns:
        Comprehensive analysis result with LLM-powered insights

    Raises:
        MemoryError: If AgentCore Memory query fails (caught internally).
        Exception: If Gemini API call fails (caught internally, returns fallback analysis).
    """
    logger.info(f"[analyze_error] AI-Powered analysis: {error_type} in {operation}")

    # =========================================================================
    # STEP 1: CODE (Python = Hands) - Prepare inputs
    # =========================================================================

    # Generate error signature for pattern matching
    signature = generate_error_signature(error_type, message, operation)
    logger.debug(f"[analyze_error] Generated signature: {signature}")

    # Basic classification (heuristic)
    classification = classify_error(error_type)
    is_recoverable = recoverable if recoverable is not None else classification["recoverable"]

    # Query memory for similar patterns
    similar_patterns = []
    try:
        from agents.specialists.debug.tools.query_memory_patterns import query_memory_patterns_tool

        memory_result = await query_memory_patterns_tool(
            error_signature=signature,
            error_type=error_type,
            operation=operation,
            max_patterns=3,
            session_id=session_id,
        )
        if memory_result.get("success"):
            similar_patterns = memory_result.get("patterns", [])
            logger.info(f"[analyze_error] Found {len(similar_patterns)} similar patterns")
    except Exception as e:
        logger.warning(f"[analyze_error] Memory query failed: {e}")

    # Search documentation if no patterns found
    documentation_links = []
    if not similar_patterns:
        try:
            from agents.specialists.debug.tools.search_documentation import search_documentation_tool

            doc_result = await search_documentation_tool(
                query=f"{error_type} {operation} {message[:50]}",
                sources=["aws", "agentcore"],
                max_results=3,
                session_id=session_id,
            )
            if doc_result.get("success"):
                documentation_links = doc_result.get("results", [])
                logger.info(f"[analyze_error] Found {len(documentation_links)} doc links")
        except Exception as e:
            logger.warning(f"[analyze_error] Documentation search failed: {e}")

    # =========================================================================
    # STEP 2: LLM (Gemini = Brain) - Deep reasoning with Thinking
    # =========================================================================

    analysis_prompt = f"""You are an expert error analyst for the SGA (Sistema de Gestão de Ativos) inventory system built on AWS Bedrock AgentCore with Strands Agents framework.

Analyze this error with deep reasoning and provide actionable insights.

## ERROR DETAILS

- **Type:** {error_type}
- **Message:** {message}
- **Operation:** {operation}
- **Stack Trace:** {stack_trace or 'Not provided'}
- **Context:** {json.dumps(context or {}, indent=2, default=str)}
- **Initial Classification:** {classification.get("category", "unknown")} (recoverable: {is_recoverable})

## HISTORICAL PATTERNS FROM AGENTCORE MEMORY

{json.dumps(similar_patterns, indent=2, default=str) if similar_patterns else 'No similar patterns found in AgentCore Memory.'}

## RELEVANT DOCUMENTATION

{json.dumps(documentation_links, indent=2, default=str) if documentation_links else 'No documentation found.'}

## SYSTEM CONTEXT

This error occurred in the Faiston SGA inventory system:
- 100% Agentic Architecture (AWS Bedrock AgentCore)
- Strands Agents Framework with A2A Protocol
- Gemini 2.5 Pro LLM
- Aurora PostgreSQL database
- S3 for file storage
- Human-in-the-Loop (HIL) for critical decisions

## YOUR TASK

Analyze this error using deep reasoning. Consider:
1. What could cause this specific error type in an agentic system?
2. Is this a transient issue (retry-able) or a permanent problem?
3. What should the user/developer do to resolve it?
4. Are there patterns from similar errors that suggest a root cause?

Provide your analysis in JSON format with these exact keys:

```json
{{
  "technical_explanation": "Clear explanation in Portuguese (pt-BR) of what happened and why",
  "root_causes": [
    {{
      "cause": "Description of potential cause",
      "confidence": 0.85,
      "evidence": ["Supporting evidence 1", "Supporting evidence 2"]
    }}
  ],
  "debugging_steps": [
    "Step 1: First action to take",
    "Step 2: Second action to take"
  ],
  "recoverable": true,
  "suggested_action": "retry|fallback|escalate|abort"
}}
```

IMPORTANT RULES:
- technical_explanation MUST be in Portuguese (pt-BR)
- Rank root_causes by confidence (0.0 to 1.0), highest first
- Provide 3-5 debugging_steps, ordered by effectiveness
- suggested_action must be exactly one of: retry, fallback, escalate, abort
- Be specific to this error and system context, not generic advice
"""

    try:
        # Create Strands Agent with Gemini 2.5 Pro + Thinking
        # Uses centralized model configuration from agents/utils.py
        analysis_agent = Agent(
            name="error_analysis_reasoning",
            model=create_gemini_model("debug"),  # Gemini 2.5 Pro with Thinking
            system_prompt=(
                "You are an expert error analyst for agentic systems. "
                "Always respond with valid JSON matching the requested schema. "
                "Focus on actionable insights specific to the error context."
            ),
        )

        logger.info("[analyze_error] Invoking Gemini 2.5 Pro for deep reasoning...")

        # Invoke agent for deep reasoning
        # Use synchronous call since Strands Agent handles async internally
        result = analysis_agent(analysis_prompt)

        # Extract response text from Strands result
        response_text = ""
        if hasattr(result, "message") and result.message:
            # Strands returns Message with content parts
            if hasattr(result.message, "content"):
                for part in result.message.content:
                    if hasattr(part, "text"):
                        response_text += part.text
        elif hasattr(result, "text"):
            response_text = result.text
        else:
            response_text = str(result)

        logger.debug(f"[analyze_error] Gemini response length: {len(response_text)}")

    except Exception as e:
        logger.error(f"[analyze_error] Gemini reasoning failed: {e}", exc_info=True)
        # Fallback to basic analysis (still better than nothing)
        return _build_fallback_response(
            error_type=error_type,
            message=message,
            operation=operation,
            signature=signature,
            classification=classification,
            is_recoverable=is_recoverable,
        )

    # =========================================================================
    # STEP 3: CODE (Python = Hands) - Parse and validate response
    # =========================================================================

    try:
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
            else:
                json_str = response_text

        analysis = json.loads(json_str)
        logger.info("[analyze_error] Successfully parsed Gemini JSON response")

    except json.JSONDecodeError as e:
        logger.warning(f"[analyze_error] JSON parse failed: {e}, using fallback")
        return _build_fallback_response(
            error_type=error_type,
            message=message,
            operation=operation,
            signature=signature,
            classification=classification,
            is_recoverable=is_recoverable,
        )

    # Validate and format response
    return {
        "success": True,
        "error_signature": signature,
        "error_type": error_type,
        "technical_explanation": analysis.get(
            "technical_explanation",
            f"Erro {error_type}: {message}"
        ),
        "root_causes": analysis.get("root_causes", []),
        "debugging_steps": analysis.get("debugging_steps", []),
        "documentation_links": documentation_links,
        "similar_patterns": similar_patterns,
        "recoverable": analysis.get("recoverable", is_recoverable),
        "suggested_action": analysis.get("suggested_action", "escalate"),
        "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
        "classification": classification,
        "llm_powered": True,  # Flag to indicate AI analysis was used
    }


def _build_fallback_response(
    error_type: str,
    message: str,
    operation: str,
    signature: str,
    classification: Dict[str, Any],
    is_recoverable: bool,
) -> Dict[str, Any]:
    """
    Build fallback response when LLM analysis fails.

    This ensures the tool always returns a valid response structure
    even if Gemini is unavailable.

    Args:
        error_type: Exception class name
        message: Error message
        operation: Operation that failed
        signature: Error signature
        classification: Error classification
        is_recoverable: Whether error is recoverable

    Returns:
        Fallback analysis response
    """
    category = classification.get("category", "unknown")
    category_pt = {
        "validation": "validação de dados",
        "network": "comunicação de rede",
        "permission": "permissões de acesso",
        "resource": "recurso não encontrado",
        "rate_limit": "limite de requisições",
        "system": "sistema operacional",
        "unknown": "erro desconhecido",
    }.get(category, "erro")

    return {
        "success": True,
        "error_signature": signature,
        "error_type": error_type,
        "technical_explanation": (
            f"Erro de {category_pt} durante a operação '{operation}': {message[:200]}"
        ),
        "root_causes": [
            {
                "cause": f"Erro durante operação {operation}",
                "confidence": 0.5,
                "evidence": [f"Tipo: {error_type}"],
            }
        ],
        "debugging_steps": [
            "1. Verifique os logs do agente no CloudWatch",
            "2. Confirme os dados de entrada da requisição",
            "3. Consulte a documentação da operação",
        ],
        "documentation_links": [],
        "similar_patterns": [],
        "recoverable": is_recoverable,
        "suggested_action": "retry" if is_recoverable else "escalate",
        "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
        "classification": classification,
        "llm_powered": False,  # Flag indicates fallback was used
    }
